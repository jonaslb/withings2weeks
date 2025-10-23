from __future__ import annotations

from pathlib import Path

import pandas as pd
from cyclopts import App
from pydantic import BaseModel, field_validator

app = App(help="Convert Withings weights.csv to weekly pivot averages (ODS spreadsheet output).")

REQUIRED_COLS: tuple[str, ...] = (
    "Date",
    "Weight (kg)",
    "Fat mass (kg)",
    "Muscle mass (kg)",
    "Bone mass (kg)",
    "Hydration (kg)",
)


class CliArgs(BaseModel):
    csv_path: Path
    output_path: Path | None = None
    overwrite: bool = False

    @field_validator("csv_path")
    @classmethod
    def _must_exist(cls, v: Path) -> Path:  # noqa: D401
        if not v.exists():
            raise ValueError(f"Input file does not exist: {v}")
        if not v.is_file():
            raise ValueError(f"Input path is not a file: {v}")
        return v


def _read_withings_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")
    # Parse date
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    if df["Date"].isna().any():
        raise ValueError("Some Date values could not be parsed.")
    return df


def _daily_averages(df: pd.DataFrame) -> pd.DataFrame:
    """Group by calendar day (date only) and average numeric columns."""
    return (
        df.assign(Date=df["Date"].dt.date).groupby("Date", as_index=False).mean(numeric_only=True)
    )


def _weekly_averages(daily_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate daily averages into ISO week averages."""
    temp = daily_df.assign(Date=pd.to_datetime(daily_df["Date"]))
    # Use ISO week (ISO year + week). Period frequency (e.g. W-MON) may differ from ISO,
    # so rely on isocalendar for canonical ISO week/year info.
    iso = temp["Date"].dt.isocalendar()
    week_id = iso["year"].astype(str) + "W" + iso["week"].astype(str).str.zfill(2)
    numeric_cols = [c for c in daily_df.columns if c != "Date"]
    return (
        temp.assign(Week=week_id)
        .groupby("Week", as_index=False)[numeric_cols]
        .mean(numeric_only=True)
        .rename(columns={"Week": "Week number"})
    )


def _derive_output_path(input_path: Path) -> Path:
    """Return output path with -pivot.ods suffix next to input file."""
    return input_path.with_suffix("").with_name(f"{input_path.stem}-pivot.ods")


def _write_ods(df: pd.DataFrame, out_path: Path) -> None:
    """Write dataframe to an OpenDocument Spreadsheet (.ods)."""
    try:
        with pd.ExcelWriter(out_path, engine="odf") as writer:
            df.to_excel(writer, index=False, sheet_name="Weekly Averages")
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f"Failed to write ODS file '{out_path}': {e}") from e


@app.default
def main(args: CliArgs) -> None:
    """Entry point for CLI."""
    input_path = args.csv_path
    output_path = (
        args.output_path if args.output_path is not None else _derive_output_path(input_path)
    )
    if output_path.suffix.lower() != ".ods":
        # Enforce .ods for clarity; user can pass a path without extension or wrong extension
        output_path = output_path.with_suffix(".ods")

    if output_path.exists() and not args.overwrite:
        raise SystemExit(f"Refusing to overwrite existing file: {output_path} (use --overwrite)")

    df = _read_withings_csv(input_path)
    daily = _daily_averages(df)
    weekly = _weekly_averages(daily)
    _write_ods(weekly, output_path)
    print(f"Wrote weekly averages to {output_path}")
