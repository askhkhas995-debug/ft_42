"""Analytics placeholder service."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class AnalyticsService:
    """Update analytics from attempts, reports, and timeline events."""

    def refresh_user_metrics(self, user_id: str) -> dict:
        """Return placeholder analytics payload."""
        raise NotImplementedError("Analytics refresh is not implemented yet.")
