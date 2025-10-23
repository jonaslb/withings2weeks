from pathlib import Path

from withings2weeks.cli import _read_withings_csv, _daily_averages, _weekly_averages


def test_weekly_aggregation(tmp_path: Path) -> None:
    src = Path(__file__).parent / "sample_weights.csv"
    df = _read_withings_csv(src)
    daily = _daily_averages(df)
    weekly = _weekly_averages(daily)

    # Expect two ISO weeks: 2025W01 (Jan 1-2) and 2025W02 (Jan 8-9)
    weeks = weekly["Week number"].tolist()
    assert weeks == ["2025W01", "2025W02"], weeks

    # Validate an averaged value roughly
    w1 = weekly.loc[weekly["Week number"] == "2025W01", "Weight (kg)"].iloc[0]
    # Day averages: Jan1 avg weight = (80+82)/2=81; Jan2 weight=81 -> week avg=(81+81)/2=81
    assert abs(w1 - 81) < 1e-6

    w2 = weekly.loc[weekly["Week number"] == "2025W02", "Weight (kg)"].iloc[0]
    # Jan8=79, Jan9=78.5 -> avg=78.75
    assert abs(w2 - 78.75) < 1e-6
