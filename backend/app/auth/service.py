import uuid
from datetime import datetime, timezone
from typing import Optional, Tuple, Dict, Any
from fastapi import HTTPException, status, Header

from backend.app.db.database import get_db_connection
from backend.app.auth.models import UserSignUp, UserLogin, PasswordReset, UserResponse, AuthResponse
from backend.app.auth.security import generate_salt, hash_password, verify_password, generate_token


class AuthService:
    """Manages user registration, authentication, sessions, and password resets."""

    @classmethod
    def signup(cls, data: UserSignUp) -> AuthResponse:
        email = data.email.lower().strip()
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
            if cursor.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="An account with this email already exists."
                )

            user_id = f"usr_{uuid.uuid4().hex[:12]}"
            salt = generate_salt()
            pwd_hash = hash_password(data.password, salt)
            now = datetime.now(timezone.utc).isoformat()

            cursor.execute(
                """
                INSERT INTO users (id, email, password_hash, salt, full_name, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user_id, email, pwd_hash, salt, data.full_name or email.split("@")[0], now)
            )

            token = generate_token()
            cursor.execute(
                "INSERT INTO sessions (token, user_id, created_at) VALUES (?, ?, ?)",
                (token, user_id, now)
            )
            conn.commit()

        user_resp = UserResponse(
            id=user_id,
            email=email,
            full_name=data.full_name or email.split("@")[0],
            created_at=now
        )
        return AuthResponse(token=token, user=user_resp)

    @classmethod
    def login(cls, data: UserLogin) -> AuthResponse:
        email = data.email.lower().strip()
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, email, password_hash, salt, full_name, created_at FROM users WHERE email = ?",
                (email,)
            )
            row = cursor.fetchone()
            if not row or not verify_password(data.password, row["salt"], row["password_hash"]):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid email or password."
                )

            user_id = row["id"]
            now = datetime.now(timezone.utc).isoformat()
            token = generate_token()
            cursor.execute(
                "INSERT INTO sessions (token, user_id, created_at) VALUES (?, ?, ?)",
                (token, user_id, now)
            )
            conn.commit()

        user_resp = UserResponse(
            id=user_id,
            email=row["email"],
            full_name=row["full_name"],
            created_at=row["created_at"]
        )
        return AuthResponse(token=token, user=user_resp)

    @classmethod
    def reset_password(cls, data: PasswordReset) -> Dict[str, str]:
        email = data.email.lower().strip()
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
            row = cursor.fetchone()
            if not row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No account found with this email."
                )

            user_id = row["id"]
            salt = generate_salt()
            new_hash = hash_password(data.new_password, salt)
            cursor.execute(
                "UPDATE users SET password_hash = ?, salt = ? WHERE id = ?",
                (new_hash, salt, user_id)
            )
            # Invalidate previous sessions
            cursor.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
            conn.commit()

        return {"message": "Password has been successfully reset. Please log in with your new password."}

    @classmethod
    def get_user_by_token(cls, token: str) -> Optional[UserResponse]:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT u.id, u.email, u.full_name, u.created_at
                FROM sessions s
                JOIN users u ON s.user_id = u.id
                WHERE s.token = ?
                """,
                (token,)
            )
            row = cursor.fetchone()
            if not row:
                return None

            return UserResponse(
                id=row["id"],
                email=row["email"],
                full_name=row["full_name"],
                created_at=row["created_at"]
            )

    @classmethod
    def logout(cls, token: str) -> None:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM sessions WHERE token = ?", (token,))
            conn.commit()



def get_current_user_optional(authorization: Optional[str] = Header(None)) -> Optional[UserResponse]:
    """Extract user from Authorization Bearer token; returns None if not logged in."""
    if not authorization:
        return None

    parts = authorization.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        token = parts[1]
        return AuthService.get_user_by_token(token)

    return None


def get_current_user_required(authorization: Optional[str] = Header(None)) -> UserResponse:
    """Enforce authenticated user requirement."""
    user = get_current_user_optional(authorization)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please log in or sign up."
        )
    return user

