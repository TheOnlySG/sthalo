"""Pure availability-window computation tests."""

from __future__ import annotations

from datetime import UTC, date, datetime, time

from app.modules.availability.models import AvailabilityRule
from app.modules.availability.service import _free_intervals, _merge, _subtract


def _rule(
    weekday: int,
    start_hour: int,
    end_hour: int,
    *,
    valid_from: date | None = None,
    valid_to: date | None = None,
) -> AvailabilityRule:
    return AvailabilityRule(
        weekday=weekday,
        start_time=time(start_hour),
        end_time=time(end_hour),
        valid_from=valid_from,
        valid_to=valid_to,
    )


def test_multi_day_window_merges_rules_at_midnight() -> None:
    start = datetime(2026, 11, 2, 21, 0, tzinfo=UTC)
    end = datetime(2026, 11, 3, 3, 0, tzinfo=UTC)
    rules = [_rule(1, 22, 0), _rule(2, 0, 2)]

    windows = _free_intervals(
        rules=rules,
        timezone="UTC",
        busy=[],
        start=start,
        end=end,
    )

    assert windows == [
        (datetime(2026, 11, 2, 22, 0, tzinfo=UTC), datetime(2026, 11, 3, 2, 0, tzinfo=UTC))
    ]


def test_block_splits_and_clips_windows() -> None:
    start = datetime(2026, 11, 2, 0, 0, tzinfo=UTC)
    end = datetime(2026, 11, 2, 23, 0, tzinfo=UTC)
    rules = [_rule(1, 9, 18)]

    windows = _free_intervals(
        rules=rules,
        timezone="UTC",
        busy=[
            (datetime(2026, 11, 2, 10, 0, tzinfo=UTC), datetime(2026, 11, 2, 11, 0, tzinfo=UTC)),
            (datetime(2026, 11, 2, 12, 0, tzinfo=UTC), datetime(2026, 11, 2, 12, 15, tzinfo=UTC)),
        ],
        start=start,
        end=end,
    )

    assert windows == [
        (datetime(2026, 11, 2, 9, 0, tzinfo=UTC), datetime(2026, 11, 2, 10, 0, tzinfo=UTC)),
        (datetime(2026, 11, 2, 11, 0, tzinfo=UTC), datetime(2026, 11, 2, 12, 0, tzinfo=UTC)),
        (datetime(2026, 11, 2, 12, 15, tzinfo=UTC), datetime(2026, 11, 2, 18, 0, tzinfo=UTC)),
    ]


def test_validity_dates_limit_rules() -> None:
    rules = [
        _rule(1, 9, 12, valid_from=date(2026, 11, 9)),
        _rule(1, 13, 18, valid_to=date(2026, 11, 2)),
    ]
    start = datetime(2026, 11, 2, 0, 0, tzinfo=UTC)
    end = datetime(2026, 11, 3, 0, 0, tzinfo=UTC)

    windows = _free_intervals(
        rules=rules,
        timezone="UTC",
        busy=[],
        start=start,
        end=end,
    )

    assert windows == [
        (datetime(2026, 11, 2, 13, 0, tzinfo=UTC), datetime(2026, 11, 2, 18, 0, tzinfo=UTC))
    ]


def test_subtract_merges_adjacent_rule_windows() -> None:
    windows = _subtract(
        _merge(
            [
                (
                    datetime(2026, 11, 2, 9, 0, tzinfo=UTC),
                    datetime(2026, 11, 2, 12, 0, tzinfo=UTC),
                ),
                (
                    datetime(2026, 11, 2, 12, 0, tzinfo=UTC),
                    datetime(2026, 11, 2, 18, 0, tzinfo=UTC),
                ),
            ]
        ),
        [(datetime(2026, 11, 2, 13, 0, tzinfo=UTC), datetime(2026, 11, 2, 14, 0, tzinfo=UTC))],
    )

    assert windows == [
        (datetime(2026, 11, 2, 9, 0, tzinfo=UTC), datetime(2026, 11, 2, 13, 0, tzinfo=UTC)),
        (datetime(2026, 11, 2, 14, 0, tzinfo=UTC), datetime(2026, 11, 2, 18, 0, tzinfo=UTC)),
    ]
