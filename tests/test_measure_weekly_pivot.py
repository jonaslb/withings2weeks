from datetime import timedelta, timezone

import pandas as pd
import pytest

from withings2weeks.measure_client import pivot_scale_measurements_weekly
from withings2weeks.weeks import resolve_week_range


def test_pivot_weekly_basic() -> None:
    # Two days in same ISO week
    df = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                [
                    "2025-01-01T08:00:00Z",
                    "2025-01-01T12:00:00Z",
                    "2025-01-02T08:00:00Z",
                ]
            ),
            "weight_kg": [80.0, 82.0, 81.0],
            "muscle_mass_kg": [35.0, 35.5, 35.2],
            "hydration_kg": [45.0, 44.8, 44.9],
            "fat_mass_kg": [16.0, 16.2, 16.1],
            "bone_mass_kg": [3.2, 3.25, 3.22],
        }
    )
    weekly = pivot_scale_measurements_weekly(df)
    assert list(weekly.columns) == [
        "Week number",
        "Weight (kg)",
        "Muscle mass (kg)",
        "Hydration (kg)",
        "Fat mass (kg)",
        "Bone mass (kg)",
    ]
    assert weekly.shape[0] == 1
    coefficient = 2 ** (-1 / 2)
    assert weekly.loc[0, "Week number"] == "2025W01"
    assert weekly.iloc[0, 1:].tolist() == pytest.approx(
        [
            (low + coefficient * high) / (1 + coefficient)
            for low, high in [(80, 81), (35, 35.2), (45, 44.9), (16, 16.1), (3.2, 3.22)]
        ]
    )


def test_pivot_weekly_empty() -> None:
    weekly = pivot_scale_measurements_weekly(pd.DataFrame(columns=["timestamp"]))
    assert weekly.empty
    assert list(weekly.columns) == [
        "Week number",
        "Weight (kg)",
        "Muscle mass (kg)",
        "Hydration (kg)",
        "Fat mass (kg)",
        "Bone mass (kg)",
    ]


def test_weight_halves_every_two_kg_and_resets_each_week() -> None:
    df = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                ["2025-01-06", "2025-01-07", "2025-01-08", "2025-01-13", "2025-01-14"]
            ),
            "weight_kg": [80, 82, 84, 90, 92],
            "muscle_mass_kg": [30, 33, 36, 40, 46],
        }
    )
    weekly = pivot_scale_measurements_weekly(df)
    assert weekly["Weight (kg)"].tolist() == pytest.approx(
        [(80 + 0.5 * 82 + 0.25 * 84) / 1.75, (90 + 0.5 * 92) / 1.5]
    )
    assert weekly["Muscle mass (kg)"].tolist() == pytest.approx(
        [(30 + 0.5 * 33 + 0.25 * 36) / 1.75, 42]
    )
    assert weekly["Bone mass (kg)"].isna().all()


def test_daily_selection_keeps_whole_row_and_breaks_ties_by_time_then_input() -> None:
    df = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                ["2025-01-01 10:00", "2025-01-01 08:00", "2025-01-01 08:00", "2025-01-01 07:00"]
            ),
            "weight_kg": [80, 80, 80, 82],
            "muscle_mass_kg": [31, 35, 36, 30],
            "hydration_kg": [40, None, 41, 39],
        },
        index=[0, 0, 0, 0],
    )
    weekly = pivot_scale_measurements_weekly(df)
    assert weekly.loc[0, "Weight (kg)"] == 80
    assert weekly.loc[0, "Muscle mass (kg)"] == 35
    assert pd.isna(weekly.loc[0, "Hydration (kg)"])


def test_missing_components_renormalize_weights_and_invalid_weights_are_ignored() -> None:
    df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2025-01-06", periods=7),
            "weight_kg": [80, 82, None, float("inf"), -1, 0, -float("inf")],
            "muscle_mass_kg": [None, 36, 100, 100, 100, 100, 100],
            "hydration_kg": [40, float("inf"), 100, 100, 100, 100, 100],
            "bone_mass_kg": [None] * 7,
        }
    )
    weekly = pivot_scale_measurements_weekly(df)
    assert weekly.loc[0, "Weight (kg)"] == pytest.approx((80 + 0.5 * 82) / 1.5)
    assert weekly.loc[0, "Muscle mass (kg)"] == 36
    assert weekly.loc[0, "Hydration (kg)"] == 40
    assert pd.isna(weekly.loc[0, "Bone mass (kg)"])


def test_inferred_range_includes_gaps_and_iso_year_rollover() -> None:
    df = pd.DataFrame(
        {"timestamp": ["2020-12-28", "2021-01-18", "invalid"], "weight_kg": [80, 82, 1]}
    )
    weekly = pivot_scale_measurements_weekly(df)
    assert weekly["Week number"].tolist() == ["2020W53", "2021W01", "2021W02", "2021W03"]
    assert weekly.iloc[1:3, 1:].isna().all().all()


@pytest.mark.parametrize("empty", [True, False])
def test_explicit_range_emits_leading_trailing_and_entirely_empty_weeks(empty: bool) -> None:
    df = pd.DataFrame() if empty else pd.DataFrame({"timestamp": ["2025-01-06"], "weight_kg": [80]})
    weekly = pivot_scale_measurements_weekly(
        df, week_range=resolve_week_range("2025W01", "2025W03")
    )
    assert weekly["Week number"].tolist() == ["2025W01", "2025W02", "2025W03"]
    assert weekly.iloc[[0, 2], 1:].isna().all().all()
    if empty:
        assert weekly.iloc[:, 1:].isna().all().all()
    else:
        assert weekly.loc[1, "Weight (kg)"] == 80


def test_range_filtering_and_daily_grouping_use_same_timezone() -> None:
    df = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                [
                    "2025-01-05 21:59",
                    "2025-01-05 22:00",
                    "2025-01-06 08:00",
                    "2025-01-12 21:59",
                    "2025-01-12 22:00",
                ]
            ),
            "weight_kg": [1, 80, 82, 84, 1],
        }
    )
    weekly = pivot_scale_measurements_weekly(
        df,
        week_range=resolve_week_range("2025W02", "2025W02", tz=timezone(timedelta(hours=2))),
    )
    assert weekly["Week number"].tolist() == ["2025W02"]
    assert weekly.loc[0, "Weight (kg)"] == pytest.approx((80 + 0.25 * 84) / 1.25)


def test_valid_timestamps_without_usable_weights_still_emit_weeks() -> None:
    weekly = pivot_scale_measurements_weekly(
        pd.DataFrame({"timestamp": ["2025-01-01", "2025-01-15"], "weight_kg": [None, 0]})
    )
    assert weekly["Week number"].tolist() == ["2025W01", "2025W02", "2025W03"]
    assert weekly.iloc[:, 1:].isna().all().all()


def test_invalid_timestamps_without_range_return_empty_schema() -> None:
    weekly = pivot_scale_measurements_weekly(
        pd.DataFrame({"timestamp": ["invalid"], "weight_kg": [80]})
    )
    assert weekly.empty
    assert len(weekly.columns) == 6


def test_reversed_range_rejected() -> None:
    with pytest.raises(ValueError, match="end must be after"):
        pivot_scale_measurements_weekly(
            pd.DataFrame(), week_range=resolve_week_range("2025W03", "2025W01")
        )
