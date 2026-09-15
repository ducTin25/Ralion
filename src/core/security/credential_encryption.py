"""Symmetric encryption for credentials stored at rest — currently just the per-project GitHub
PAT in `project_github_credentials.token_ciphertext` (see `github_credential_provider`).

Single static key from config, no rotation, no KMS — deliberately MVP-scoped (see CHANGE_LOG.md
for the design discussion this came out of). If a second kind of at-rest credential shows up
later, extend this module instead of writing a second encryption helper — same NFR-14 spirit
CLAUDE.md applies to retrieval/logging."""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from src.config import get_settings


class CredentialDecryptionError(RuntimeError):
    """The stored ciphertext could not be decrypted with the configured key — most likely
    GITHUB_CREDENTIAL_ENCRYPTION_KEY changed since the credential was stored."""


def encrypt_token(plaintext: str) -> bytes:
    return _fernet().encrypt(plaintext.encode("utf-8"))


def decrypt_token(ciphertext: bytes) -> str:
    try:
        return _fernet().decrypt(ciphertext).decode("utf-8")
    except InvalidToken as exc:
        raise CredentialDecryptionError(
            "Không giải mã được GitHub credential đã lưu — kiểm tra "
            "GITHUB_CREDENTIAL_ENCRYPTION_KEY có bị đổi không."
        ) from exc


def _fernet() -> Fernet:
    return Fernet(get_settings().github_credential_encryption_key.encode("utf-8"))
