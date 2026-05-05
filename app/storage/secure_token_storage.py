from __future__ import annotations

from app.config import APP_NAME


class TokenStorageError(RuntimeError):
    """Raised when secure token storage is unavailable."""


class SecureTokenStorage:
    """Bearer token storage backed by the OS credential store through keyring."""

    def __init__(self, service_name: str = APP_NAME, username: str = "access_token") -> None:
        self.service_name = service_name
        self.username = username

    def save_token(self, token: str) -> None:
        keyring = self._keyring()
        keyring.set_password(self.service_name, self.username, token)

    def load_token(self) -> str | None:
        keyring = self._keyring()
        return keyring.get_password(self.service_name, self.username)

    def clear_token(self) -> None:
        keyring = self._keyring()
        try:
            keyring.delete_password(self.service_name, self.username)
        except Exception:
            return

    @staticmethod
    def _keyring():
        try:
            import keyring
        except ImportError as exc:
            raise TokenStorageError(
                "The keyring package is required for secure token storage."
            ) from exc
        return keyring
