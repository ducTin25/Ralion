from __future__ import annotations

from datetime import time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field, model_validator

from src.model.enums import DiscoveryMode


class DiscoveryScheduleUpdateRequestDTO(BaseModel):
    """No raw cron, no pipeline-internal field (model/concurrency/embedding batch size/cosine
    threshold/retry policy) — the PM-facing surface is exactly these 4 modes and their own
    required fields, matching the CHECK constraints already enforced on `projects` at the DB
    layer (defense in depth, not the sole guard)."""

    discovery_mode: DiscoveryMode
    discovery_interval_hours: int | None = Field(default=None, ge=1)
    discovery_time_of_day: time | None = None
    discovery_day_of_week: int | None = Field(default=None, ge=0, le=6)
    discovery_timezone: str | None = None

    @model_validator(mode="after")
    def _validate_mode_requires_its_own_fields(self) -> DiscoveryScheduleUpdateRequestDTO:
        if self.discovery_mode == DiscoveryMode.EVERY_N_HOURS and self.discovery_interval_hours is None:
            raise ValueError("discovery_interval_hours is required when discovery_mode=EVERY_N_HOURS")
        if self.discovery_mode in (DiscoveryMode.DAILY_AT, DiscoveryMode.WEEKLY_AT):
            if self.discovery_time_of_day is None or self.discovery_timezone is None:
                raise ValueError(
                    "discovery_time_of_day and discovery_timezone are required for DAILY_AT/WEEKLY_AT"
                )
        if self.discovery_mode == DiscoveryMode.WEEKLY_AT and self.discovery_day_of_week is None:
            raise ValueError("discovery_day_of_week is required when discovery_mode=WEEKLY_AT")
        if self.discovery_timezone is not None:
            try:
                ZoneInfo(self.discovery_timezone)
            except ZoneInfoNotFoundError as exc:
                raise ValueError(f"unknown IANA timezone: {self.discovery_timezone}") from exc
        return self
