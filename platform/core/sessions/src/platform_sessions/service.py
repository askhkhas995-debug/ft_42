"""Session lifecycle placeholder service."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SessionService:
    """Create, advance, pause, resume, and complete sessions."""

    def start_session(self, mode: str, pool_id: str | None = None) -> str:
        """Return a new session identifier."""
        raise NotImplementedError("Session start is not implemented yet.")
