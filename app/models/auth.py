from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class User:
    id: str | None
    email: str
    name: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "User":
        return cls(
            id=str(data.get("id") or data.get("user_id") or "") or None,
            email=str(data.get("email") or ""),
            name=data.get("name") or data.get("full_name"),
            raw=data,
        )

    @property
    def display_name(self) -> str:
        return self.name or self.email or "Authenticated user"


@dataclass(frozen=True)
class AuthSession:
    access_token: str
    token_type: str
    user: User
