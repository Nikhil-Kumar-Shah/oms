"""
Security & Cryptographic Foundation
Implements Argon2id password hashing, verification, password policies,
and cryptographically secure session token generation and hashing.
"""

import hashlib
import re
import secrets
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError
from app.core.exceptions import ValidationException
from app.core.logging import get_logger

logger = get_logger(__name__)

# Argon2id password hasher configured per RFC 9106 standards
_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,  # 64 MB
    parallelism=2,
    hash_len=32,
    salt_len=16,
)


def hash_password(password: str) -> str:
    """Hashes a plaintext password using Argon2id."""
    return _hasher.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    """
    Verifies a plaintext password against an Argon2id hash.
    Returns True if valid, False otherwise without raising exceptions.
    """
    try:
        return _hasher.verify(password_hash, plain_password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False
    except Exception as exc:
        logger.error(f"Unexpected error during password verification: {exc}")
        return False


def validate_password_strength(password: str) -> None:
    """
    Enforces the application password policy:
    - Minimum length: 8 characters
    - Maximum length: 128 characters
    - Reject empty/whitespace-only passwords
    """
    if not password or len(password) < 8:
        raise ValidationException("Password must be at least 8 characters long")
    if len(password) > 128:
        raise ValidationException("Password must not exceed 128 characters")
    if password.isspace():
        raise ValidationException("Password cannot consist solely of whitespace")


def generate_session_token() -> str:
    """
    Generates a cryptographically secure 256-bit URL-safe session token.
    """
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    """
    Hashes a session token using SHA-256 for persistent database storage.
    Raw session tokens are never stored in the database.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
