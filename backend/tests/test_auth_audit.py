import uuid
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.auth.models import UserSignUp, UserLogin, PasswordReset
from backend.app.auth.service import AuthService
from backend.app.chat.service import ChatHistoryService
from backend.app.db.database import get_db_connection


client = TestClient(app)


def test_protected_endpoints_reject_unauthenticated():
    """Verify that protected endpoints reject requests missing authorization or using invalid tokens."""
    protected_urls = [
        ("GET", "/auth/me"),
        ("GET", "/conversations"),
        ("POST", "/conversations"),
        ("GET", "/conversations/conv_fake123"),
        ("PATCH", "/conversations/conv_fake123"),
        ("DELETE", "/conversations/conv_fake123"),
    ]

    for method, url in protected_urls:
        # Case 1: No Authorization header -> 401
        res = client.request(method, url)
        assert res.status_code == 401, f"{method} {url} without auth expected 401, got {res.status_code}"
        assert "Authentication required" in res.json().get("detail", "")

        # Case 2: Invalid Bearer token -> 401
        res_invalid = client.request(method, url, headers={"Authorization": "Bearer invalid_token_xyz_999"})
        assert res_invalid.status_code == 401, f"{method} {url} with invalid token expected 401, got {res_invalid.status_code}"


def test_auth_full_lifecycle_and_revocation():
    """Verify signup, login, profile retrieval, password reset, and session revocation."""
    email = f"audit_user_{uuid.uuid4().hex[:8]}@documind.ai"
    pwd = "AuditPassword123!"

    # 1. Sign up
    res_signup = client.post("/auth/signup", json={"email": email, "password": pwd, "full_name": "Audit User"})
    assert res_signup.status_code == 200
    token1 = res_signup.json()["token"]
    user1 = res_signup.json()["user"]
    assert user1["email"] == email

    # 2. Get profile with valid token
    res_me = client.get("/auth/me", headers={"Authorization": f"Bearer {token1}"})
    assert res_me.status_code == 200
    assert res_me.json()["id"] == user1["id"]

    # 3. Duplicate signup is rejected
    res_dup = client.post("/auth/signup", json={"email": email, "password": pwd})
    assert res_dup.status_code == 400

    # 4. Login with wrong password is rejected
    res_bad_login = client.post("/auth/login", json={"email": email, "password": "WrongPassword!"})
    assert res_bad_login.status_code == 401

    # 5. Password Reset
    new_pwd = "NewSecurePassword456!"
    res_reset = client.post("/auth/reset-password", json={"email": email, "new_password": new_pwd})
    assert res_reset.status_code == 200

    # 6. Session revocation: Old token1 must now be rejected
    res_revoked = client.get("/auth/me", headers={"Authorization": f"Bearer {token1}"})
    assert res_revoked.status_code == 401

    # 7. Login with new password succeeds and yields new token
    res_new_login = client.post("/auth/login", json={"email": email, "password": new_pwd})
    assert res_new_login.status_code == 200
    token2 = res_new_login.json()["token"]
    assert token2 != token1

    # 8. Profile accessible with token2
    res_me2 = client.get("/auth/me", headers={"Authorization": f"Bearer {token2}"})
    assert res_me2.status_code == 200

    # 9. Logout revokes token2
    res_logout = client.post("/auth/logout", headers={"Authorization": f"Bearer {token2}"})
    assert res_logout.status_code == 200
    res_me3 = client.get("/auth/me", headers={"Authorization": f"Bearer {token2}"})
    assert res_me3.status_code == 401


def test_cross_user_isolation_and_chat_injection_protection():
    """Verify that User B cannot read, rename, delete, or inject messages into User A's conversations."""
    # Create User A
    email_a = f"user_a_{uuid.uuid4().hex[:8]}@documind.ai"
    res_a = client.post("/auth/signup", json={"email": email_a, "password": "PassWordA123!"})
    token_a = res_a.json()["token"]

    # Create User B
    email_b = f"user_b_{uuid.uuid4().hex[:8]}@documind.ai"
    res_b = client.post("/auth/signup", json={"email": email_b, "password": "PassWordB123!"})
    token_b = res_b.json()["token"]

    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # User A creates a conversation
    res_conv_a = client.post("/conversations", json={"title": "User A Private Research"}, headers=headers_a)
    assert res_conv_a.status_code == 200
    conv_a_id = res_conv_a.json()["id"]

    # User B lists conversations -> conv_a must NOT appear
    res_b_list = client.get("/conversations", headers=headers_b)
    assert res_b_list.status_code == 200
    b_conv_ids = [c["id"] for c in res_b_list.json()]
    assert conv_a_id not in b_conv_ids

    # User B attempts to read User A's conversation -> 404
    res_b_get = client.get(f"/conversations/{conv_a_id}", headers=headers_b)
    assert res_b_get.status_code == 404

    # User B attempts to rename User A's conversation -> 404
    res_b_patch = client.patch(f"/conversations/{conv_a_id}", json={"title": "Hacked Title"}, headers=headers_b)
    assert res_b_patch.status_code == 404

    # User B attempts to delete User A's conversation -> 404
    res_b_del = client.delete(f"/conversations/{conv_a_id}", headers=headers_b)
    assert res_b_del.status_code == 404

    # User B attempts to inject a message into User A's conversation via /chat -> 403 Forbidden
    res_b_chat = client.post(
        "/chat",
        json={"question": "Injected malicious question", "conversation_id": conv_a_id},
        headers=headers_b
    )
    assert res_b_chat.status_code == 403
    assert "Access denied" in res_b_chat.json()["detail"]


def test_recent_chats_ordering_reopening_and_cleanup():
    """Verify Recent Chats ordering (active chat moves to top) and message cleanup on deletion."""
    email = f"user_order_{uuid.uuid4().hex[:8]}@documind.ai"
    res_user = client.post("/auth/signup", json={"email": email, "password": "Password123!"})
    token = res_user.json()["token"]
    user_id = res_user.json()["user"]["id"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create two chats
    c1 = client.post("/conversations", json={"title": "Chat 1"}, headers=headers).json()
    c2 = client.post("/conversations", json={"title": "Chat 2"}, headers=headers).json()

    # Chat 2 was created last, so it should be first
    list1 = client.get("/conversations", headers=headers).json()
    assert list1[0]["id"] == c2["id"]

    # 2. Add a message to Chat 1 -> it should jump to the top
    ChatHistoryService.save_message(
        conv_id=c1["id"],
        user_id=user_id,
        sender="user",
        text="New message in Chat 1"
    )

    list2 = client.get("/conversations", headers=headers).json()
    assert list2[0]["id"] == c1["id"]

    # 3. Reopen Chat 1 -> contains the message
    detail = client.get(f"/conversations/{c1['id']}", headers=headers).json()
    assert len(detail["messages"]) == 1
    assert detail["messages"][0]["text"] == "New message in Chat 1"

    # 4. Delete Chat 1 -> both conversation and messages are removed
    res_del = client.delete(f"/conversations/{c1['id']}", headers=headers)
    assert res_del.status_code == 200

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM messages WHERE conversation_id = ?", (c1["id"],))
        remaining_messages = cursor.fetchone()[0]
        assert remaining_messages == 0

