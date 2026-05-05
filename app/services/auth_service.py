from __future__ import annotations

from app.models.auth import AuthSession, User
from app.services.api_client import ApiClient, ApiError, AuthenticationRequired
from app.services.log_service import LogService
from app.storage.secure_token_storage import SecureTokenStorage


class AuthService:
    def __init__(
        self,
        api_client: ApiClient,
        token_storage: SecureTokenStorage,
        log_service: LogService,
    ) -> None:
        self.api_client = api_client
        self.token_storage = token_storage
        self.log_service = log_service
        self.current_user: User | None = None
        self.current_token: str | None = None

    def login(self, email: str, password: str) -> AuthSession:
        data = self.api_client.request(
            "POST",
            "/api/auth/login",
            json={"email": email, "password": password},
        )
        session = self._session_from_auth_response(data, fallback_email=email)
        self.log_service.add("info", "auth", "User logged in.", {"email": session.user.email})
        return session

    def register(self, email: str, password: str) -> AuthSession:
        data = self.api_client.request(
            "POST",
            "/api/auth/register",
            json={"email": email, "password": password},
        )
        if isinstance(data, dict) and data.get("access_token"):
            session = self._session_from_auth_response(data, fallback_email=email)
        else:
            session = self.login(email, password)
        self.log_service.add(
            "info",
            "auth",
            "User registered.",
            {"email": session.user.email},
        )
        return session

    def _session_from_auth_response(
        self,
        data: dict[str, object] | list[object],
        *,
        fallback_email: str,
    ) -> AuthSession:
        if not isinstance(data, dict):
            raise ApiError("Auth response has an unexpected format.")

        token = data.get("access_token")
        if not token:
            raise ApiError("Auth response did not include an access token.")

        user_data = data.get("user") or {}
        if not isinstance(user_data, dict):
            user_data = {}
        user = User.from_api(user_data)
        if not user.email:
            user = User(id=user.id, email=fallback_email, name=user.name, raw=user.raw)
        token_type = str(data.get("token_type") or "bearer")

        self.token_storage.save_token(str(token))
        self.current_token = str(token)
        self.current_user = user
        return AuthSession(access_token=str(token), token_type=token_type, user=user)

    def restore_session(self) -> User | None:
        token = self.token_storage.load_token()
        if not token:
            self.current_token = None
            self.current_user = None
            return None

        try:
            data = self.api_client.request("GET", "/api/auth/me", token=token)
        except AuthenticationRequired:
            self.token_storage.clear_token()
            self.current_token = None
            self.current_user = None
            self.log_service.add("warning", "auth", "Stored token was rejected.")
            return None

        if not isinstance(data, dict):
            raise ApiError("Session response has an unexpected format.")

        user_data = data.get("user") if isinstance(data.get("user"), dict) else data
        user = User.from_api(user_data)
        self.current_token = token
        self.current_user = user
        self.log_service.add("info", "auth", "Session restored.", {"email": user.email})
        return user

    def logout(self) -> None:
        token = self.current_token or self.token_storage.load_token()
        if token:
            try:
                self.api_client.request("POST", "/api/auth/logout", token=token)
            except ApiError:
                pass
        self.token_storage.clear_token()
        self.current_token = None
        self.current_user = None
        self.log_service.add("info", "auth", "User logged out.")

    def clear_token(self) -> None:
        self.token_storage.clear_token()
        self.current_token = None
        self.current_user = None
        self.log_service.add("warning", "auth", "Stored token cleared.")
