"""Field-level encryption for bank details at rest."""

from __future__ import annotations

from cryptography.fernet import Fernet


class FieldCipher:
    """Encrypts and decrypts individual sensitive fields."""

    def __init__(self, key: str) -> None:
        self._fernet = Fernet(key.encode("ascii"))

    def encrypt(self, value: str) -> str:
        """Return the ciphertext for a plaintext value."""
        return self._fernet.encrypt(value.encode("utf-8")).decode("ascii")

    def decrypt(self, token: str) -> str:
        """Return the plaintext for a ciphertext produced by encrypt."""
        return self._fernet.decrypt(token.encode("ascii")).decode("utf-8")
