"""F6 Scheduled Incremental Convention Discovery — pure validation/scheduling math, no DB.

Covers: per-mode required-field validation (mirrors the `projects` CHECK constraints, defense
in depth at the DTO layer too) and `compute_next_run_at`'s timezone/DST correctness, including
MANUAL_ONLY never getting a next_run_at and a real DST-transition case.
"""

from __future__ import annotations

from datetime import datetime, time

import pytest
from pydantic import ValidationError

from src.dto.request.discovery_schedule_request_dto import DiscoveryScheduleUpdateRequestDTO
from src.infrastructure.scheduling.convention_discovery_scheduler import compute_next_run_at
from src.model.enums import DiscoveryMode
from src.model.project import Project


def _dto(**kwargs):
    return DiscoveryScheduleUpdateRequestDTO(**kwargs)


# ------------------------------------------------------------------ DTO per-mode validation


def test_manual_only_needs_no_other_field():
    dto = _dto(discovery_mode=DiscoveryMode.MANUAL_ONLY)
    assert dto.discovery_mode == DiscoveryMode.MANUAL_ONLY


def test_every_n_hours_requires_interval_hours():
    with pytest.raises(ValidationError):
        _dto(discovery_mode=DiscoveryMode.EVERY_N_HOURS)
    dto = _dto(discovery_mode=DiscoveryMode.EVERY_N_HOURS, discovery_interval_hours=6)
    assert dto.discovery_interval_hours == 6


def test_every_n_hours_interval_must_be_at_least_1():
    with pytest.raises(ValidationError):
        _dto(discovery_mode=DiscoveryMode.EVERY_N_HOURS, discovery_interval_hours=0)


def test_daily_at_requires_time_and_timezone():
    with pytest.raises(ValidationError):
        _dto(discovery_mode=DiscoveryMode.DAILY_AT)
    with pytest.raises(ValidationError):
        _dto(discovery_mode=DiscoveryMode.DAILY_AT, discovery_time_of_day=time(9, 0))
    dto = _dto(
        discovery_mode=DiscoveryMode.DAILY_AT,
        discovery_time_of_day=time(9, 0),
        discovery_timezone="Asia/Ho_Chi_Minh",
    )
    assert dto.discovery_timezone == "Asia/Ho_Chi_Minh"


def test_weekly_at_requires_day_of_week_too():
    with pytest.raises(ValidationError):
        _dto(
            discovery_mode=DiscoveryMode.WEEKLY_AT,
            discovery_time_of_day=time(9, 0),
            discovery_timezone="Asia/Ho_Chi_Minh",
        )
    dto = _dto(
        discovery_mode=DiscoveryMode.WEEKLY_AT,
        discovery_time_of_day=time(9, 0),
        discovery_timezone="Asia/Ho_Chi_Minh",
        discovery_day_of_week=0,
    )
    assert dto.discovery_day_of_week == 0


def test_day_of_week_out_of_range_rejected():
    with pytest.raises(ValidationError):
        _dto(
            discovery_mode=DiscoveryMode.WEEKLY_AT,
            discovery_time_of_day=time(9, 0),
            discovery_timezone="Asia/Ho_Chi_Minh",
            discovery_day_of_week=7,
        )


def test_unknown_timezone_rejected():
    with pytest.raises(ValidationError):
        _dto(
            discovery_mode=DiscoveryMode.DAILY_AT,
            discovery_time_of_day=time(9, 0),
            discovery_timezone="Not/AZone",
        )


def test_dto_has_no_pipeline_internal_fields():
    """PM-facing surface never accepts model/concurrency/embedding-batch/threshold/retry
    fields — the DTO simply has no such attribute."""
    fields = set(DiscoveryScheduleUpdateRequestDTO.model_fields)
    forbidden = {"model", "concurrency", "embedding_batch_size", "cosine_threshold", "retry_policy", "cron"}
    assert fields.isdisjoint(forbidden)


# ------------------------------------------------------------------ compute_next_run_at


def _project(**overrides) -> Project:
    defaults = dict(
        key="K", name="N", created_by_admin_id=1, discovery_mode=DiscoveryMode.MANUAL_ONLY
    )
    defaults.update(overrides)
    return Project(**defaults)


def test_manual_only_never_gets_a_next_run_at():
    project = _project(discovery_mode=DiscoveryMode.MANUAL_ONLY)
    assert compute_next_run_at(project, after=datetime(2026, 1, 1, 0, 0)) is None


def test_every_n_hours_adds_interval_from_after():
    project = _project(discovery_mode=DiscoveryMode.EVERY_N_HOURS, discovery_interval_hours=6)
    next_run = compute_next_run_at(project, after=datetime(2026, 1, 1, 10, 0))
    assert next_run == datetime(2026, 1, 1, 16, 0)


def test_daily_at_next_occurrence_same_day_if_not_yet_passed():
    project = _project(
        discovery_mode=DiscoveryMode.DAILY_AT,
        discovery_time_of_day=time(9, 0),
        discovery_timezone="UTC",
    )
    # 08:00 UTC, before 09:00 -> fires today.
    next_run = compute_next_run_at(project, after=datetime(2026, 1, 1, 8, 0))
    assert next_run == datetime(2026, 1, 1, 9, 0)


def test_daily_at_rolls_to_next_day_if_time_already_passed():
    project = _project(
        discovery_mode=DiscoveryMode.DAILY_AT,
        discovery_time_of_day=time(9, 0),
        discovery_timezone="UTC",
    )
    next_run = compute_next_run_at(project, after=datetime(2026, 1, 1, 10, 0))
    assert next_run == datetime(2026, 1, 2, 9, 0)


def test_weekly_at_finds_next_matching_weekday():
    # 2026-01-01 is a Thursday (weekday()==3). Target Monday (0).
    project = _project(
        discovery_mode=DiscoveryMode.WEEKLY_AT,
        discovery_time_of_day=time(9, 0),
        discovery_timezone="UTC",
        discovery_day_of_week=0,
    )
    next_run = compute_next_run_at(project, after=datetime(2026, 1, 1, 8, 0))
    assert next_run == datetime(2026, 1, 5, 9, 0)  # next Monday
    assert next_run.weekday() == 0


def test_weekly_at_same_weekday_but_time_passed_rolls_a_full_week():
    project = _project(
        discovery_mode=DiscoveryMode.WEEKLY_AT,
        discovery_time_of_day=time(9, 0),
        discovery_timezone="UTC",
        discovery_day_of_week=3,  # Thursday, same as `after`
    )
    next_run = compute_next_run_at(project, after=datetime(2026, 1, 1, 10, 0))
    assert next_run == datetime(2026, 1, 8, 9, 0)


def test_daily_at_handles_dst_transition_in_local_timezone():
    """America/New_York DST spring-forward is 2026-03-08 02:00 -> 03:00 local. A 09:00 local
    DAILY_AT schedule must still land at 09:00 local (not drift by an hour) either side of the
    transition — the whole reason this uses zoneinfo instead of manual UTC-offset math."""
    project = _project(
        discovery_mode=DiscoveryMode.DAILY_AT,
        discovery_time_of_day=time(9, 0),
        discovery_timezone="America/New_York",
    )
    # after = 2026-03-07 08:00 local (EST, UTC-5) = 13:00 UTC, before the DST transition.
    before_dst = datetime(2026, 3, 7, 13, 0)
    next_run = compute_next_run_at(project, after=before_dst)
    # 2026-03-07 09:00 EST == 14:00 UTC.
    assert next_run == datetime(2026, 3, 7, 14, 0)

    # after = 2026-03-09 08:00 local (EDT, UTC-4, after the transition) = 12:00 UTC.
    after_dst = datetime(2026, 3, 9, 12, 0)
    next_run_after = compute_next_run_at(project, after=after_dst)
    # 2026-03-09 09:00 EDT == 13:00 UTC — offset shifted by exactly the DST hour.
    assert next_run_after == datetime(2026, 3, 9, 13, 0)
