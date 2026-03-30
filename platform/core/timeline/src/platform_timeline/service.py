"""Timeline placeholder service."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class TimelineService:
    """Append and query timeline events."""

    def append_event(self, event: dict) -> str:
        """Persist a placeholder event."""
        raise NotImplementedError("Timeline persistence is not implemented yet.")
