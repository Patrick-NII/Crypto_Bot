"""Encryption helpers for user exchange credentials."""

from __future__ import annotations

from cryptography.fernet import Fernet

from app.core.config import settings

_fernet = Fernet(settings.CREDENTIAL_ENCRYPTION_KEY.encode("utf-8"))


def encrypt_secret(value: str) -> str:
    """Encrypt a plaintext secret for storage."""
    return _fernet.encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_secret(value: str) -> str:
    """Decrypt a stored secret."""
    return _fernet.decrypt(value.encode("utf-8")).decode("utf-8")


def mask_api_key(value: str) -> str:
    """Return a short masked representation of an API key."""
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}...{value[-4:]}"
