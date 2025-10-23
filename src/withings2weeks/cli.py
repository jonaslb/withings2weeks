from datetime import datetime  # used for current time reference
from pathlib import Path

import pandas as pd
from cyclopts import App

from .measure_client import (
    fetch_scale_measurements_all,
    pivot_scale_measurements_weekly,
)
from .oauth_client import WithingsOAuthClient
from .weeks import resolve_week_range

app = App(help="Convert Withings weights.csv to weekly pivot averages (ODS spreadsheet output).")

EXPECTED_CSV_COLS: tuple[str, ...] = (
    # Canonical internal column naming (lowercase second word where applicable)
    "Date",
    "Weight (kg)",
    "Fat mass (kg)",
    "Muscle mass (kg)",
    "Bone mass (kg)",
    "Hydration (kg)",
)

# Input CSV files produced by Withings export (or user-managed) may contain
# alternative capitalization (e.g. "Fat Mass (kg)" instead of canonical
# "Fat mass (kg)"). Normalize known variants immediately after loading so
# downstream logic works with a consistent schema.
_CSV_HEADER_NORMALIZATION: dict[str, str] = {
    "Fat Mass (kg)": "Fat mass (kg)",
    "Muscle Mass (kg)": "Muscle mass (kg)",
    "Bone Mass (kg)": "Bone mass (kg)",
    # Weight / Hydration are already aligned; included defensively if future variants appear.
    "Weight (Kg)": "Weight (kg)",
    "Hydration (Kg)": "Hydration (kg)",
}


def _read_withings_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    # Strip surrounding whitespace from headers (defensive) then normalize variants.
    cleaned_cols: list[str] = [c.strip() for c in df.columns]
    rename_map: dict[str, str] = {}
    for original in cleaned_cols:
        target = _CSV_HEADER_NORMALIZATION.get(original)
        if target is not None:
            rename_map[original] = target
    if rename_map:
        df = df.rename(columns=rename_map)
    # After normalization, validate required columns.
    missing = [c for c in EXPECTED_CSV_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")
    # Parse date column; ensure fully valid.
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
    columns = [
        "Week number",
        "Weight (kg)",
        "Muscle mass (kg)",
        "Hydration (kg)",
        "Fat mass (kg)",
        "Bone mass (kg)",
    ]
    df = df[columns]
    try:
        with pd.ExcelWriter(out_path, engine="odf") as writer:
            df.to_excel(writer, index=False, sheet_name="Weekly Averages")
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f"Failed to write ODS file '{out_path}': {e}") from e


@app.command(help="Run interactive OAuth2 authorization against Withings and store tokens locally.")
def authorize(scopes: list[str] | None = None) -> None:  # noqa: D401
    """Open browser, capture authorization code via local redirect, exchange for tokens."""
    if scopes is None or not scopes:
        # Minimal useful scopes; adjust as needed.
        scopes = ["user.info", "user.activity", "user.metrics"]
    client = WithingsOAuthClient.from_config()
    tokens = client.authorize_interactive(scopes)
    # Print summary (avoid printing secrets)
    print("Access token (truncated):", tokens.access_token[:12] + "...")
    print("Refresh token stored. User ID:", tokens.userid)


@app.command(
    name="fetch-measures",
    help=(
        "Fetch scale measurements for an ISO week range and write weekly pivot ODS, "
        "OR pivot a local Withings CSV export when --file-source is provided."
    ),
)
def fetch_measures(
    week: str,
    end_week: str | None = None,
    output_path: Path | None = None,
    overwrite: bool = False,
    file_source: Path | None = None,
    stdout: bool = False,
) -> None:  # noqa: D401
    """Fetch scale measurements OR pivot a local Withings CSV export.

    When ``--file-source`` is provided, ``week`` / ``end_week`` are ignored and the
    CSV is pivoted (daily then weekly averages) reusing legacy logic.
    Otherwise, hits the Withings API to fetch raw measurements for the resolved
    ISO week range and pivots those.
    """
    local_tz = datetime.now().astimezone().tzinfo
    week_range = resolve_week_range(week, end_week=end_week, now=datetime.now(), tz=local_tz)
    start_date, end_date = week_range.start, week_range.end

    if file_source is not None:
        csv_df = _read_withings_csv(file_source)
        # Transform CSV into same format as from API.
        raw_df = csv_df.assign(timestamp=csv_df["Date"]).rename(  # copy original datetime
            columns={
                "Weight (kg)": "weight_kg",
                "Fat mass (kg)": "fat_mass_kg",
                "Muscle mass (kg)": "muscle_mass_kg",
                "Bone mass (kg)": "bone_mass_kg",
                "Hydration (kg)": "hydration_kg",
            }
        )[
            [
                "timestamp",
                # Provide composition columns (fat_free_mass_kg may be absent -> NaN later)
                "weight_kg",
                "muscle_mass_kg",
                "hydration_kg",
                "fat_mass_kg",
                "bone_mass_kg",
            ]
        ]
        # Ensure expected columns even if missing (defensive)
        for col in ["weight_kg", "muscle_mass_kg", "hydration_kg", "fat_mass_kg", "bone_mass_kg"]:
            if col not in raw_df.columns:
                raw_df[col] = pd.NA
        # Date filtering (inclusive start, exclusive end boundary)
        raw_df = raw_df[(raw_df["timestamp"] >= start_date) & (raw_df["timestamp"] < end_date)]
        if output_path is None and not stdout:
            output_path = _derive_output_path(file_source)
    else:
        client = WithingsOAuthClient.from_config()
        raw_df = fetch_scale_measurements_all(client, start=start_date, end=end_date)
        # Filter again defensively if API returns out-of-range (shouldn't normally)
        if not raw_df.empty:
            raw_df = raw_df[(raw_df["timestamp"] >= start_date) & (raw_df["timestamp"] < end_date)]
        if output_path is None and not stdout:
            output_path = Path(
                f"withings-measures-{week_range.start_week_code}-{week_range.end_week_code}-pivot.ods"
            )

    weekly_df = pivot_scale_measurements_weekly(raw_df)

    if stdout:
        if output_path is not None:
            raise SystemExit("--stdout cannot be combined with --output-path")
        # TODO: Should we give pandas the terminal width if we can?
        print(weekly_df.to_string(index=False, float_format="%.2f"))
        return

    if output_path is None:
        raise SystemExit("No output path resolved (internal error).")
    if output_path.suffix.lower() != ".ods":
        output_path = output_path.with_suffix(".ods")
    if output_path.exists() and not overwrite:
        raise SystemExit(f"Refusing to overwrite existing file: {output_path} (use --overwrite)")
    _write_ods(weekly_df, output_path)
    print(f"Wrote weekly pivot ODS to {output_path}")


@app.command(name="config-dir", help="Print the path to the configuration directory.")
def config_dir() -> None:  # noqa: D401
    from .config import get_config_dir

    print(get_config_dir())
