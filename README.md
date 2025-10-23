# withings2weeks

CLI tool to pivot either a Withings data export `weights.csv` or API data scale measurements into weekly average metrics, writing them to an OpenDocument Spreadsheet (`.ods`) or to terminal directly.

## Features
* Interactive OAuth2 authorization to obtain Withings API access tokens.
* Aggregates measurements first by date, then by ISO week numbers (e.g. `2025W35`).
    * This reduces skew from doing multiple measurements in a day.
* Writes result to an `.ods` spreadsheet for copy-pasting elsewhere - or to stdout in a neat format.

## Installation
Download the repo, and in the directory run:

```bash
uv tool install .
```

## Usage

Create a file in `~/.config/withings2weeks/app_config.toml` with content:

```toml
[withings.oauth]
client_id = "<my_client_id_from_withings>"
client_secret = "<my_client_secret_from_withings>"
redirect_uri = "http://localhost:1992/callback"
```

Where you obtained the values from your Withings developer page.
Then, run:

```
withings2weeks authorize  # Opens browser window for login
withings2weeks fetch-measures 2024W01 2025W01 --output-path weekly-2024.ods
```

Options:
* `--output-path PATH`  Specific output path (a default can be derived).
* `--stdout`            Disables file output, write to terminal.
* `--overwrite`         Allow overwriting an existing output file.

The output columns will be:
* `Week number`
* `Weight (kg)`
* `Muscle mass (kg)`
* `Hydration (kg)`
* `Fat mass (kg)`
* `Bone mass (kg)`

## Development
Run tests:
```bash
uv run pytest
```

Lint & format:
```bash
uv run ruff check .
uv run ruff format .
```

Type checking:
```bash
uv run mypy
```

Please note the tool requires Python 3.14, but ruff and mypy are not yet updated for 3.14, so some errors may occur.
