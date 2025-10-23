from typing import Any, cast

from withings2weeks.measure_client import MeasureType, _transform_measure_groups


def test_transform_measure_groups_basic() -> None:
    # Two groups with partial measures
    groups: list[dict[str, Any]] = [
        {
            "grpid": 100,
            "category": 1,
            "date": 1700000000,  # fixed timestamp
            "deviceid": "abc123",
            "measures": [
                {"type": MeasureType.WEIGHT_KG, "value": 80000, "unit": -3},  # 80.0 kg
                {"type": MeasureType.FAT_MASS_WEIGHT_KG, "value": 16000, "unit": -3},  # 16.0 kg
            ],
        },
        {
            "grpid": 101,
            "category": 1,
            "date": 1700000300,
            "deviceid": "abc123",
            "measures": [
                {"type": MeasureType.WEIGHT_KG, "value": 80150, "unit": -3},  # 80.15 kg
                {"type": MeasureType.MUSCLE_MASS_KG, "value": 35000, "unit": -3},  # 35.0 kg
            ],
        },
    ]
    df = _transform_measure_groups(groups)
    assert list(df.columns) == [
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
    assert df.shape[0] == 2
    # First row weight
    assert abs(cast(float, df.loc[0, "weight_kg"]) - 80.0) < 1e-9
    assert abs(cast(float, df.loc[0, "fat_mass_kg"]) - 16.0) < 1e-9
    # fat ratio pct removed from schema; ensure remaining values intact
    # Second row muscle mass
    assert abs(cast(float, df.loc[1, "muscle_mass_kg"]) - 35.0) < 1e-9


def test_transform_measure_groups_empty() -> None:
    df = _transform_measure_groups([])
    assert df.empty
    assert set(df.columns) == {
        "timestamp",
        "group_id",
        "device_id",
        "weight_kg",
        "fat_free_mass_kg",
        "fat_mass_kg",
        "muscle_mass_kg",
        "bone_mass_kg",
        "hydration_kg",
    }
