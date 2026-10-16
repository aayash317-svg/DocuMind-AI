import pytest
from backend.app.auth.models import UserSignUp, UserLogin, PasswordReset
from backend.app.auth.service import AuthService
from backend.app.auth.security import hash_password, verify_password, generate_salt


def test_password_hashing():
    salt = generate_salt()
    pwd = "SecretPassword123!"
    h1 = hash_password(pwd, salt)
    assert verify_password(pwd, salt, h1) is True
    assert verify_password("WrongPassword", salt, h1) is False


def test_auth_service_signup_login_reset():
    email = "testuser@documind.ai"
    password = "MySecurePassword123"

    # Signup
    signup_res = AuthService.signup(UserSignUp(email=email, password=password, full_name="Test User"))
    assert signup_res.token is not None
    assert signup_res.user.email == email

    # Verify session lookup
    looked_up_user = AuthService.get_user_by_token(signup_res.token)
    assert looked_up_user is not None
    assert looked_up_user.email == email

    # Login
    login_res = AuthService.login(UserLogin(email=email, password=password))
    assert login_res.token is not None

    # Reset Password
    new_pwd = "UpdatedPassword456"
    AuthService.reset_password(PasswordReset(email=email, new_password=new_pwd))

    # Old password fails
    with pytest.raises(Exception):
        AuthService.login(UserLogin(email=email, password=password))

    # New password succeeds
    login_new = AuthService.login(UserLogin(email=email, password=new_pwd))
    assert login_new.user.email == email

