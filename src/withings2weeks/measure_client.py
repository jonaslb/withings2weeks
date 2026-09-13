"""Withings measure API client utilities.

Focuses on scale (body composition) measurements returned by the `measure` service
(`action=getmeas`). Provides helpers to fetch, paginate, and transform results
into pandas DataFrames and weekly pivots.
"""

import time
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import IntEnum
from typing import Any

import pandas as pd
import requests

from .oauth_client import WithingsOAuthClient
from .weeks import WeekRange

MEASURE_ENDPOINT = "https://wbsapi.withings.net/measure"


class MeasureType(IntEnum):
    WEIGHT_KG = 1
    FAT_FREE_MASS_KG = 5
    FAT_MASS_WEIGHT_KG = 8
    MUSCLE_MASS_KG = 76
    HYDRATION_KG = 77
    BONE_MASS_KG = 88

    @classmethod
    def scale_types(cls) -> list[MeasureType]:
        return [
            cls.WEIGHT_KG,
            cls.FAT_FREE_MASS_KG,
            cls.FAT_MASS_WEIGHT_KG,
            cls.MUSCLE_MASS_KG,
            cls.BONE_MASS_KG,
            cls.HYDRATION_KG,
        ]


@dataclass
class MeasureRecord:
    timestamp: datetime
    group_id: int
    device_id: str | None
    weight_kg: float | None
    fat_free_mass_kg: float | None
    fat_mass_kg: float | None
    muscle_mass_kg: float | None
    bone_mass_kg: float | None
    hydration_kg: float | None


def _normalize_timestamp(ts: int) -> datetime:
    return datetime.fromtimestamp(ts, tz=UTC)


def _decode_measure(value: int, unit: int) -> float:
    # Real value is value * 10^unit
    return value * (10**unit)  # type: ignore[no-any-return]  # mypy pow?


def _transform_measure_groups(groups: Sequence[dict[str, Any]]) -> pd.DataFrame:
    records: list[MeasureRecord] = []
    for grp in groups:
        if grp.get("category") != 1:  # 1 = real measurements
            continue
        measures = grp.get("measures", [])
        values: dict[int, float] = {}
        for m in measures:
            t = m.get("type")
            if t is None:
                continue
            try:
                mt = MeasureType(int(t))
            except ValueError:
                continue  # skip unknown type
            raw_val = _decode_measure(int(m.get("value", 0)), int(m.get("unit", 0)))
            values[int(mt)] = raw_val
        rec = MeasureRecord(
            timestamp=_normalize_timestamp(int(grp.get("date", grp.get("created", time.time())))),
            group_id=int(grp.get("grpid", 0)),
            device_id=str(grp.get("deviceid")) if grp.get("deviceid") is not None else None,
            weight_kg=values.get(MeasureType.WEIGHT_KG),
            fat_free_mass_kg=values.get(MeasureType.FAT_FREE_MASS_KG),
            fat_mass_kg=values.get(MeasureType.FAT_MASS_WEIGHT_KG),
            muscle_mass_kg=values.get(MeasureType.MUSCLE_MASS_KG),
            bone_mass_kg=values.get(MeasureType.BONE_MASS_KG),
            hydration_kg=values.get(MeasureType.HYDRATION_KG),
        )
        records.append(rec)
    if not records:
        # Empty frame schema aligns with MeasureRecord fields (fat_ratio_pct deprecated)
        return pd.DataFrame(
            columns=[
                "timestamp",
                "group_id",
                "device_id",
                "weight_kg",
                "fat_free_mass_kg",
                "fat_mass_kg",
                "muscle_mass_kg",
                "bone_mass_kg",
                "hydration_kg",
            ]
        )
    df = pd.DataFrame([r.__dict__ for r in records])
    return df.sort_values("timestamp").reset_index(drop=True)


def fetch_scale_measurements(
    client: WithingsOAuthClient,
    start: datetime | date,
    end: datetime | date,
    meastypes: Iterable[MeasureType] | None = None,
    offset: int | None = None,
    lastupdate: datetime | None = None,
) -> pd.DataFrame:
    """Fetch scale measurements between start and end (UTC).

    Args:
        client: Authorized WithingsOAuthClient.
        start: Start datetime/date (inclusive).
        end: End datetime/date (inclusive).
        meastypes: Iterable of MeasureType to request. Defaults to all scale types.
        offset: Pagination offset (if continuing a previous call).
        lastupdate: If provided, only return groups modified since this timestamp.

    Returns:
        DataFrame with one row per measure group and columns for composition metrics.
    """
    if isinstance(start, date) and not isinstance(start, datetime):
        start_dt = datetime.combine(start, datetime.min.time())
    else:
        start_dt = start
    if isinstance(end, date) and not isinstance(end, datetime):
        end_dt = datetime.combine(end, datetime.max.time())
    else:
        end_dt = end

    types_list = list(meastypes) if meastypes is not None else MeasureType.scale_types()
    types_param = ",".join(str(int(t)) for t in types_list)

    params: dict[str, Any] = {
        "action": "getmeas",
        "meastypes": types_param,
        "startdate": int(start_dt.timestamp()),
        "enddate": int(end_dt.timestamp()),
    }
    if offset is not None:
        params["offset"] = offset
    if lastupdate is not None:
        params["lastupdate"] = int(lastupdate.timestamp())

    access_token = client.get_valid_access_token()
    headers = {"Authorization": f"Bearer {access_token}"}
    resp = requests.get(MEASURE_ENDPOINT, params=params, headers=headers, timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(f"measure getmeas HTTP {resp.status_code}: {resp.text}")
    data = resp.json()
    if data.get("status") != 0:
        raise RuntimeError(f"measure getmeas failed: {data}")
    body = data.get("body", {})
    groups = body.get("measuregrps", [])
    if not isinstance(groups, list):  # defensive
        raise RuntimeError("Unexpected response structure: measuregrps not a list")
    df = _transform_measure_groups(groups)
    # Add pagination info as attributes
    df.attrs["more"] = body.get("more", 0)
    df.attrs["offset"] = body.get("offset")
    df.attrs["timezone"] = body.get("timezone")
    return df


def fetch_scale_measurements_all(
    client: WithingsOAuthClient,
    start: datetime | date,
    end: datetime | date,
    meastypes: Iterable[MeasureType] | None = None,
    lastupdate: datetime | None = None,
    per_page_delay: float = 0.0,
    max_pages: int | None = None,
) -> pd.DataFrame:
    """Fetch ALL pages of scale measurements between start and end.

    Args:
        client: Authorized OAuth client.
        start/end: Date or datetime range (inclusive).
        meastypes: Iterable of MeasureType codes (defaults to scale types).
        lastupdate: Filter by last update timestamp.
        per_page_delay: Optional sleep between page requests (seconds).
        max_pages: Safety cap (None for unlimited until API 'more'==0).
    Returns:
        DataFrame of all measure groups combined.
    """
    combined_frames: list[pd.DataFrame] = []
    current_offset: int | None = None
    pages = 0
    while True:
        print("Getting page", pages + 1, " at offset", current_offset or 0)
        page_df = fetch_scale_measurements(
            client=client,
            start=start,
            end=end,
            meastypes=meastypes,
            offset=current_offset,
            lastupdate=lastupdate,
        )
        # NOTE: We aggregate transformed DataFrames page by page; raw groups not needed.
        combined_frames.append(page_df)
        more = int(page_df.attrs.get("more", 0))
        print(" More pages:", more)
        next_offset = page_df.attrs.get("offset")
        pages += 1
        if max_pages is not None and pages >= max_pages:
            break
        if more != 1 or next_offset is None:
            break
        current_offset = int(next_offset)
        if per_page_delay > 0:
            time.sleep(per_page_delay)
    if not combined_frames:
        return page_df  # empty
    full = pd.concat(combined_frames, ignore_index=True)
    # De-duplicate by group_id if overlapping pages (defensive)
    if "group_id" in full.columns:
        full = full.sort_values("timestamp").drop_duplicates("group_id", keep="last")
    full.attrs["more"] = 0
    full.attrs["offset"] = None
    return full.reset_index(drop=True)


__all__ = [
    "MeasureType",
    "fetch_scale_measurements",
    "fetch_scale_measurements_all",
]


def pivot_scale_measurements_weekly(
    df: pd.DataFrame, *, week_range: WeekRange | None = None
) -> pd.DataFrame:
    """Select each day's lightest measurement, then weight daily rows within weeks.

    A daily row's weight is 2 ** (-(weight_kg - weekly_minimum) / 2): each
    additional 2 kg halves its influence on every component. Ties within a day
    select the earliest timestamp (then input order). Rows without a finite,
    positive total weight cannot be selected. Missing components are excluded
    independently from their weighted denominators, never filled from other rows.

    Emit every ISO week in week_range, filtering to its [start, end) boundaries;
    otherwise emit all weeks between the first and last valid timestamps.
    Empty weeks/components are NaN, exported as blank spreadsheet cells.
    Naive input timestamps are treated as UTC. Calendar days use the range's
    timezone, or UTC if no aware range is supplied.
    """
    value_cols = {
        "weight_kg": "Weight (kg)",
        "muscle_mass_kg": "Muscle mass (kg)",
        "hydration_kg": "Hydration (kg)",
        "fat_mass_kg": "Fat mass (kg)",
        "bone_mass_kg": "Bone mass (kg)",
    }
    df = df.reindex(columns=["timestamp", *value_cols]).copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
    df = df.dropna(subset=["timestamp"])
    if week_range is not None:
        tz = week_range.start.tzinfo or UTC
        start = pd.Timestamp(week_range.start)
        end = pd.Timestamp(week_range.end)
        if start.tzinfo is None:
            start = start.tz_localize(tz)
        if end.tzinfo is None:
            end = end.tz_localize(tz)
        if end <= start:
            raise ValueError("Week range end must be after its start")
        df["timestamp"] = df["timestamp"].dt.tz_convert(tz)
        df = df[(df["timestamp"] >= start) & (df["timestamp"] < end)]
        mondays = pd.date_range(start, end, freq="W-MON", inclusive="left")
    elif not df.empty:
        start = df["timestamp"].min().normalize()
        start -= pd.Timedelta(days=start.dayofweek)
        mondays = pd.date_range(start, df["timestamp"].max(), freq="W-MON")
    else:
        return pd.DataFrame(columns=["Week number", *value_cols.values()])
    weeks = pd.Index(mondays.strftime("%GW%V"), name="Week number")

    df[list(value_cols)] = (
        df[list(value_cols)]
        .apply(pd.to_numeric, errors="coerce")
        .replace([float("inf"), -float("inf")], float("nan"))
    )
    df = df[df["weight_kg"].notna() & (df["weight_kg"] > 0)]
    daily = (
        df.assign(date=df["timestamp"].dt.date)
        .sort_values("timestamp", kind="stable")
        .sort_values("weight_kg", kind="stable")
        .drop_duplicates("date", keep="first")
    )
    week_ids = daily["timestamp"].dt.strftime("%GW%V").rename("Week number")
    minimum = daily.groupby(week_ids)["weight_kg"].transform("min")
    weights = 2.0 ** (-(daily["weight_kg"] - minimum) / 2.0)
    values = daily[list(value_cols)]
    numerator = values.mul(weights, axis=0).groupby(week_ids).sum(min_count=1)
    denominator = values.notna().mul(weights, axis=0).groupby(week_ids).sum()
    weekly = numerator / denominator.replace(0, float("nan"))
    return weekly.reindex(weeks).rename(columns=value_cols).reset_index()


__all__.append("pivot_scale_measurements_weekly")
