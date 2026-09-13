from datetime import UTC
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

import pandas as pd
import pytest

from withings2weeks.cli import fetch_measures
from withings2weeks.weeks import resolve_week_range


def test_csv_to_ods_includes_empty_weeks_and_weighted_values(tmp_path: Path) -> None:
    output = tmp_path / "weekly.ods"
    with patch("withings2weeks.cli.resolve_week_range") as resolve:
        resolve.return_value = resolve_week_range("2024W52", "2025W03", tz=UTC)
        fetch_measures(
            "2024W52",
            "2025W03",
            output_path=output,
            file_source=Path(__file__).parent / "sample_weights.csv",
        )
    weekly = pd.read_excel(output, engine="odf")
    assert weekly["Week number"].tolist() == ["2024W52", "2025W01", "2025W02", "2025W03"]
    assert weekly.iloc[[0, 3], 1:].isna().all().all()
    coefficient = 2 ** (-1 / 2)
    assert weekly.loc[1, "Weight (kg)"] == pytest.approx(
        (80 + coefficient * 81) / (1 + coefficient)
    )
    coefficient = 2 ** (-0.5 / 2)
    assert weekly.loc[2, "Weight (kg)"] == pytest.approx(
        (78.5 + coefficient * 79) / (1 + coefficient)
    )
    with ZipFile(output) as ods:
        content = ods.read("content.xml").decode()
    assert "NaN" not in content
    assert "nan" not in content


def test_empty_api_to_ods_still_contains_all_weeks(tmp_path: Path) -> None:
    output = tmp_path / "empty.ods"
    with (
        patch("withings2weeks.cli.WithingsOAuthClient.from_config"),
        patch("withings2weeks.cli.fetch_scale_measurements_all", return_value=pd.DataFrame()),
    ):
        fetch_measures("2025W01", "2025W03", output_path=output)
    weekly = pd.read_excel(output, engine="odf")
    assert weekly["Week number"].tolist() == ["2025W01", "2025W02", "2025W03"]
    assert weekly.iloc[:, 1:].isna().all().all()


def test_csv_stdout_filters_requested_range(capsys: pytest.CaptureFixture[str]) -> None:
    fetch_measures(
        "2025W02",
        "2025W03",
        stdout=True,
        file_source=Path(__file__).parent / "sample_weights.csv",
    )
    output = capsys.readouterr().out
    assert "2025W01" not in output
    assert "2025W02" in output
    assert "2025W03" in output
    assert "NaN" not in output
