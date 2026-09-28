"""
Unit tests for services/crypto.py — BYOK symmetric encryption and fail-closed security.
"""

import os
import pytest
from cryptography.fernet import Fernet, InvalidToken

from services.crypto import encrypt_key, decrypt_key, _get_master_key


def test_encrypt_and_decrypt_roundtrip():
    """Verify that encrypting and decrypting restores the original plaintext."""
    plaintext = "test-sample-secret-api-key-12345"
    encrypted = encrypt_key(plaintext)
    assert encrypted != plaintext
    assert isinstance(encrypted, str)

    decrypted = decrypt_key(encrypted)
    assert decrypted == plaintext


def test_encryption_produces_unique_ciphertexts():
    """Fernet includes timestamps and initialization vectors so identical plaintexts encrypt differently."""
    plaintext = "my-secret-key"
    c1 = encrypt_key(plaintext)
    c2 = encrypt_key(plaintext)
    assert c1 != c2
    assert decrypt_key(c1) == plaintext
    assert decrypt_key(c2) == plaintext


def test_decrypt_corrupted_ciphertext_raises_invalid_token():
    """Tampering with a ciphertext must raise InvalidToken."""
    plaintext = "super-secret"
    encrypted = encrypt_key(plaintext)
    corrupted = encrypted[:-4] + "AAAA"
    with pytest.raises(InvalidToken):
        decrypt_key(corrupted)


def test_missing_encryption_key_raises_runtime_error(monkeypatch):
    """If TELEX_ENCRYPTION_KEY is unset, fail closed with a RuntimeError."""
    monkeypatch.delenv("TELEX_ENCRYPTION_KEY", raising=False)
    monkeypatch.delenv("TELEX_TEST_MODE", raising=False)
    from config import settings

    monkeypatch.setattr(settings, "telex_encryption_key", "")
    with pytest.raises(RuntimeError) as exc:
        _get_master_key()
    assert "Startup blocked" in str(exc.value)


def test_test_mode_without_key_raises_informative_error(monkeypatch):
    """In test mode, missing key explains how to configure conftest.py."""
    monkeypatch.delenv("TELEX_ENCRYPTION_KEY", raising=False)
    monkeypatch.setenv("TELEX_TEST_MODE", "1")
    from config import settings

    monkeypatch.setattr(settings, "telex_encryption_key", "")
    with pytest.raises(RuntimeError) as exc:
        _get_master_key()
    assert "must be set in test mode" in str(exc.value)


def test_invalid_key_format_raises_runtime_error(monkeypatch):
    """Providing a non-Fernet string raises RuntimeError."""
    monkeypatch.setenv("TELEX_ENCRYPTION_KEY", "not-a-valid-base64-key")
    with pytest.raises(RuntimeError) as exc:
        _get_master_key()
    assert "is not a valid Fernet key" in str(exc.value)


def test_encrypt_empty_key_raises_value_error():
    """Attempting to encrypt an empty or whitespace-only key raises ValueError."""
    with pytest.raises(ValueError, match="Cannot encrypt an empty key"):
        encrypt_key("")
    with pytest.raises(ValueError, match="Cannot encrypt an empty key"):
        encrypt_key("   ")


def test_decrypt_empty_ciphertext_raises_value_error():
    """Attempting to decrypt an empty or whitespace-only ciphertext raises ValueError."""
    with pytest.raises(ValueError, match="Cannot decrypt an empty ciphertext"):
        decrypt_key("")
    with pytest.raises(ValueError, match="Cannot decrypt an empty ciphertext"):
        decrypt_key("   ")


def test_get_master_key_from_settings_fallback(monkeypatch):
    """When TELEX_ENCRYPTION_KEY is unset in env, fallback to settings.telex_encryption_key."""
    key = Fernet.generate_key().decode()
    monkeypatch.delenv("TELEX_ENCRYPTION_KEY", raising=False)

    from config import settings

    monkeypatch.setattr(settings, "telex_encryption_key", key)
    master = _get_master_key()
    assert master == key.encode()


def test_decrypt_error_logs_without_leaking_ciphertext(caplog):
    """When InvalidToken occurs, error log warns without echoing the ciphertext."""
    sensitive_token = "gAAAAABfakeCiphertextContainingSecretData999"
    with pytest.raises(InvalidToken):
        decrypt_key(sensitive_token)

    assert "InvalidToken — key may have rotated or ciphertext is corrupt" in caplog.text
    assert sensitive_token not in caplog.text
