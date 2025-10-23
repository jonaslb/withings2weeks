from datetime import datetime, timedelta

import pytest

from withings2weeks.weeks import (
    parse_week_str,
    resolve_week_range,
    week_following_start,
    week_start,
)


def test_parse_full_week():
    year, week = parse_week_str("2025W43")
    assert year == 2025 and week == 43


def test_parse_short_week_uses_current_year():
    fake_now = datetime(2025, 10, 26, 12, 0, 0)  # Arbitrary date in 2025 ISO year
    year, week = parse_week_str("05", now=fake_now)
    assert year == fake_now.isocalendar().year and week == 5


def test_week_start_and_following():
    monday = week_start(2025, 43)
    following = week_following_start(2025, 43)
    assert following - monday == timedelta(days=7)
    assert monday.weekday() == 0  # Monday


def test_resolve_week_range_with_end_week():
    rng = resolve_week_range("2025W40", end_week="2025W42", now=datetime(2025, 10, 26))
    assert rng.start_week_code == "2025W40"
    assert rng.end_week_code == "2025W42"
    # End boundary should be Monday of week after end_week (2025W43)
    expected_end = week_start(2025, 43)
    assert rng.end == expected_end


def test_resolve_week_range_without_end_week():
    fake_now = datetime(2025, 10, 26)  # Assume this is within ISO week 43
    current_iso = fake_now.isocalendar()
    current_week_start = week_start(current_iso.year, current_iso.week)
    rng = resolve_week_range("2025W40", end_week=None, now=fake_now)
    # End boundary Monday of current week
    assert rng.end == current_week_start
    # end_week_code should be previous week
    prev_week_monday = current_week_start - timedelta(days=7)
    prev_iso = prev_week_monday.isocalendar()
    assert rng.end_week_code == f"{prev_iso.year}W{str(prev_iso.week).zfill(2)}"


def test_year_boundary_next_week():
    # Use the last week of 2024; following Monday should be +7 days
    rng = resolve_week_range("2024W52", end_week="2024W52", now=datetime(2024, 12, 28))
    assert rng.start_week_code == "2024W52"
    assert rng.end_week_code == "2024W52"
    assert rng.end - rng.start == timedelta(days=7)


def test_invalid_week_format():
    with pytest.raises(ValueError):
        parse_week_str("2025X43")
    with pytest.raises(ValueError):
        parse_week_str("")
    with pytest.raises(ValueError):
        parse_week_str("AB")
    with pytest.raises(ValueError):
        parse_week_str("2025W99")


def test_default_end_week_cross_year_boundary():
    # Now inside first ISO week of 2025 (assumed), previous week belongs to 2024.
    fake_now = datetime(2025, 1, 2)  # Thursday of first ISO week (likely week 1)
    rng = resolve_week_range("2024W52", end_week=None, now=fake_now)
    current_week_start = week_start(fake_now.isocalendar().year, fake_now.isocalendar().week)
    assert rng.end == current_week_start
    prev_week_monday = current_week_start - timedelta(days=7)
    prev_iso = prev_week_monday.isocalendar()
    assert rng.end_week_code == f"{prev_iso.year}W{str(prev_iso.week).zfill(2)}"


def test_week_53_following_start():
    # Year 2020 had week 53
    monday_53 = week_start(2020, 53)
    following = week_following_start(2020, 53)
    # Following should be Monday of week 1 of next ISO year
    assert following.weekday() == 0
    # isocalendar week should be 1
    assert following.isocalendar().week == 1
    # sanity difference
    assert following - monday_53 == timedelta(days=7)
