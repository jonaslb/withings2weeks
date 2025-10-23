"""ISO week parsing and range resolution utilities.

Helpers:
* parse week strings in full form (``YYYYWww``) or short form (``ww`` => current ISO year)
* compute week start (Monday 00:00) and following week start (exclusive end boundary)
* resolve a start/end week range where end boundary is Monday of the week *after* ``end_week``
* derive default end when ``end_week`` omitted: latest fully completed week (previous week),
  making the end boundary Monday 00:00 of the current week.

All datetimes returned are naive (no tz) at 00:00 midnight local time.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, tzinfo
from zoneinfo import ZoneInfo

__all__ = [
    "parse_week_str",
    "week_start",
    "week_following_start",
    "resolve_week_range",
    "WeekRange",
]


@dataclass(frozen=True)
class WeekRange:
    start: datetime  # inclusive Monday 00:00
    end: datetime  # exclusive Monday 00:00 of week after end_week (or current week when implicit)
    start_week_code: str  # YYYYWww
    end_week_code: str  # YYYYWww (the last fully included week)


def parse_week_str(value: str, now: datetime | None = None) -> tuple[int, int]:
    """Parse a week string.

    Accepts:
      - Full form: 'YYYYWww' (e.g. '2025W43')
      - Short form: 'ww' which resolves using the current ISO year.

    Returns (year, week_number).
    Raises ValueError on invalid format or range.
    """
    value = value.strip()
    if not value:
        raise ValueError("Week value is empty")
    if "W" in value:
        # Full form
        try:
            year_part, week_part = value.split("W", 1)
            year = int(year_part)
            week_num = int(week_part)
        except Exception as e:  # noqa: BLE001
            raise ValueError(f"Invalid week format '{value}': {e}") from e
    else:
        # Short form
        if not value.isdigit():
            raise ValueError(f"Invalid short week format '{value}'")
        if now is None:
            now = datetime.now()
        year = now.isocalendar().year
        week_num = int(value)
    if not (1 <= week_num <= 53):  # ISO weeks can go up to 53
        raise ValueError(f"Week number out of range 1..53: {week_num}")
    return year, week_num


def week_start(year: int, week_num: int, tz: str | tzinfo | None = None) -> datetime:
    """Return Monday 00:00 of the given ISO week (naive datetime)."""
    if isinstance(tz, str):
        tz = ZoneInfo(tz)
    return datetime.fromisocalendar(year, week_num, 1).replace(
        hour=0, minute=0, second=0, microsecond=0, tzinfo=tz
    )


def week_following_start(year: int, week_num: int, tz: str | tzinfo | None = None) -> datetime:
    """Return Monday 00:00 of the week following the given ISO week."""
    try:
        # Try normal case: next week in same year
        return week_start(year, week_num + 1, tz=tz)
    except ValueError:
        # Likely week_num was 53 and next week is in next year
        return week_start(year + 1, 1, tz=tz)


def resolve_week_range(
    start_week: str,
    end_week: str | None = None,
    now: datetime | None = None,
    tz: str | tzinfo | None = None,
) -> WeekRange:
    """Resolve a week range into concrete datetime bounds.

    If end_week is omitted, the range ends at Monday of the current week (exclusive) and
    the last fully included week is the previous week.

    Returns WeekRange with inclusive start and exclusive end.
    """
    if now is None:
        now = datetime.now()

    start_year, start_week_num = parse_week_str(start_week, now=now)
    start_dt = week_start(start_year, start_week_num, tz=tz)

    if end_week is not None:
        end_year, end_week_num = parse_week_str(end_week, now=now)
        # end boundary exclusive Monday of week after provided end_week
        end_boundary = week_following_start(end_year, end_week_num, tz=tz)
        end_week_code = f"{end_year}W{str(end_week_num).zfill(2)}"
    else:
        # Compute previous fully completed week relative to now
        current_week_start = week_start(now.isocalendar().year, now.isocalendar().week, tz=tz)
        prev_week_monday = current_week_start - timedelta(days=7)
        prev_iso = prev_week_monday.isocalendar()
        end_boundary = current_week_start  # exclusive end Monday of current week
        end_week_code = f"{prev_iso.year}W{str(prev_iso.week).zfill(2)}"

    start_week_code = f"{start_year}W{str(start_week_num).zfill(2)}"

    return WeekRange(
        start=start_dt,
        end=end_boundary,
        start_week_code=start_week_code,
        end_week_code=end_week_code,
    )
