import pandas as pd

from withings2weeks.measure_client import pivot_scale_measurements_weekly


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
            "weight_kg": [80.0, 82.0, 81.0],  # daily Jan1 avg=81.0, Jan2=81.0 => week avg 81.0
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
    w = weekly.loc[0, "Weight (kg)"]
    assert abs(w - 81.0) < 1e-9


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
