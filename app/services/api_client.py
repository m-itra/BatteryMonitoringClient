from __future__ import annotations

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
            with httpx.Client(base_url=self.base_url, timeout=self.timeout_seconds) as client:
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
        data = self.request("GET", "/health")
        if not isinstance(data, dict):
            raise ApiError("Health check response has an unexpected format.")
        if str(data.get("status") or "").lower() != "healthy":
            raise ApiError("Backend health check did not report healthy status.")
        return data

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
