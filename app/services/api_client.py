from __future__ import annotations

import threading
from typing import Any

from app.services.settings_service import SettingsService

try:
    import httpx
except ImportError:
    httpx = None


class ApiError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class AuthenticationRequired(ApiError):
    pass


class ApiClient:
    def __init__(self, settings: SettingsService, timeout_seconds: float = 10.0) -> None:
        self.settings = settings
        self.timeout_seconds = timeout_seconds
        self._client: Any | None = None
        self._client_base_url: str | None = None
        self._client_lock = threading.RLock()

    @property
    def base_url(self) -> str:
        return self.settings.api_base_url.rstrip("/")

    def request(
        self,
        method: str,
        path: str,
        *,
        token: str | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any] | list[Any]:
        if httpx is None:
            raise ApiError("The httpx package is required for backend requests.")

        headers = {"Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        try:
            with self._client_lock:
                client = self._get_or_create_client()
                response = client.request(method, path, json=json, headers=headers)
        except httpx.HTTPError as exc:
            raise ApiError(str(exc)) from exc

        if response.status_code == 401:
            raise AuthenticationRequired("Authentication is required.", 401)

        if response.status_code >= 400:
            raise ApiError(self._error_message(response), response.status_code)

        if not response.content:
            return {}

        try:
            return response.json()
        except ValueError as exc:
            raise ApiError("Backend returned a non-JSON response.", response.status_code) from exc

    def health_check(self) -> dict[str, Any]:
        try:
            data = self.request("GET", "/health")
            if not isinstance(data, dict):
                raise ApiError("Health check response has an unexpected format.")
            if str(data.get("status") or "").lower() != "healthy":
                raise ApiError("Backend health check did not report healthy status.")
            return data
        except ApiError as exc:
            return self._auth_route_health_check(exc)

    def close(self) -> None:
        with self._client_lock:
            if self._client is not None:
                self._client.close()
                self._client = None
                self._client_base_url = None

    def _get_or_create_client(self):
        current_base_url = self.base_url
        if self._client is None or self._client_base_url != current_base_url:
            if self._client is not None:
                self._client.close()
            self._client = httpx.Client(
                base_url=current_base_url,
                timeout=self.timeout_seconds,
                trust_env=False,
            )
            self._client_base_url = current_base_url
        return self._client

    def _auth_route_health_check(self, original_error: ApiError) -> dict[str, Any]:
        if httpx is None:
            raise original_error

        headers = {"Accept": "application/json"}
        try:
            with self._client_lock:
                client = self._get_or_create_client()
                response = client.get("/api/auth/me", headers=headers)
        except httpx.HTTPError as exc:
            raise ApiError(str(exc)) from exc

        if response.status_code in {401, 403}:
            return {
                "status": "healthy",
                "service": "api",
                "source": "auth_probe",
            }

        if response.status_code >= 500:
            raise ApiError(self._error_message(response), response.status_code)

        raise original_error

    @staticmethod
    def _error_message(response) -> str:
        try:
            data = response.json()
        except ValueError:
            return response.text or f"HTTP {response.status_code}"

        if isinstance(data, dict):
            detail = data.get("detail") or data.get("message") or data.get("error")
            if detail:
                return str(detail)
        return f"HTTP {response.status_code}"
