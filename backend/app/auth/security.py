import hashlib
import secrets
from typing import Tuple


def generate_salt() -> str:
    """Generate a cryptographic random 16-byte salt in hex format."""
    return secrets.token_hex(16)


def generate_token() -> str:
    """Generate a 32-byte secure random session token."""
    return secrets.token_hex(32)


def hash_password(password: str, salt: str) -> str:
    """Hash password using PBKDF2-HMAC-SHA256 with 100,000 iterations."""
    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        100000
    )
    return key.hex()


def verify_password(password: str, salt: str, expected_hash: str) -> bool:
    """Safely verify password hash using constant-time comparison."""
    computed_hash = hash_password(password, salt)
    return secrets.compare_digest(computed_hash, expected_hash)

