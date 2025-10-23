# withings-export-2-pivot

CLI tool to transform a Withings `weights.csv` export into weekly average metrics and write them to an OpenDocument Spreadsheet (`.ods`).

## Features
* Validates expected columns.
* Computes per-day averages first (so multiple same-day measurements don't overweight a week).
* Aggregates into ISO week numbers (e.g. `2025W35`).
* Writes result to an `.ods` spreadsheet: `<input-stem>-pivot.ods`.

## Installation
```bash
uv tool install .
```

## Usage
```bash
withings2weeks /path/to/weights.csv

# Specify a custom output file (will force .ods suffix if missing)
withings2weeks /path/to/weights.csv --output-path /tmp/weekly.ods
```

Options:
* `--output-path PATH`  Custom output file (default: `<input-stem>-pivot.ods`).
* `--overwrite`         Allow overwriting an existing output file.

## Input expectations
CSV must include at least the following columns (exact names):

* `Date` (parsable as datetime)
* `Weight (kg)`
* `Fat mass (kg)`
* `Muscle mass (kg)`
* `Bone mass (kg)`
* `Hydration (kg)`

Additional numeric columns will also be averaged; non-numeric columns besides `Date` are dropped in aggregation.

## Output
An `.ods` file named `<input-stem>-pivot.ods` containing columns:

* `Week number` (ISO year + `W` + two-digit ISO week, e.g. `2025W03`)
* Averaged metric columns (same names as input)

## Aggregation steps
1. Parse and validate required columns.
2. Convert `Date` to date-only, group by date, compute numeric means (daily averages).
3. Compute ISO week for each daily row, group again, compute weekly means.

## Development
Run tests:
```bash
uv run pytest -q
```

Lint & format:
```bash
uv run ruff check .
uv run ruff format .
```

Type checking:
```bash
uv run mypy src
```

Build distribution:
```bash
uv build
```

## License
MIT (add text as needed)
