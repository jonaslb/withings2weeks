# withings2weeks: Your Withings Data Week-by-Week

**Turn your Withings scale measurements into weekly summaries. This CLI tool aggregates your weight, muscle mass, and other metrics into a lower-weight-preferring weekly average for tracking long-term trends.**

`withings2weeks` can fetch data directly from the Withings API or use a local data export. It then pivots the measurements into weekly averages and saves them as an OpenDocument Spreadsheet (`.ods`) or prints them to your terminal.

## Why use `withings2weeks`?

It's about control of data and visualizing it the way you want.
This tool is essentially just an exporter, which simultaneously reduces to weekly averages (as daily or individual measurements are usually not meaningful).
You can then plot and analyze using your tools of preference, whether that's Python, R or Excel.

This should be a superior experience to the limited Withings app and webpage.

## Features

*   **Interactive OAuth2 flow:** Securely authorize with the Withings API.
*   **Weekly Averaging:** Selects each day's lowest-weight measurement, then computes weighted weekly averages that reduce the influence of higher-weight readings.
*   **Complete Week Range:** Includes every requested week, with blank values when there are no usable measurements.
*   **ODS Export:** Saves to an `.ods` file by default (spreadsheet).

## Installation

This tool is built with modern Python packaging and can be installed using e.g. `uv`.

```bash
# Using uv
uv tool install https://github.com/jonaslb/withings2weeks
```

## Usage

1.  **Create a configuration file** at `~/.config/withings2weeks/app_config.toml` with your Withings developer credentials:

    ```toml
    [withings.oauth]
    client_id = "<my_client_id_from_withings>"
    client_secret = "<my_client_secret_from_withings>"
    redirect_uri = "http://localhost:1992/callback"
    ```
    You can get these credentials from the [Withings developer portal](https://developer.withings.com/dashboard/).

2.  **Authorize the application:** This will open a browser window for you to log in and grant access.

    ```bash
    withings2weeks authorize
    ```

3.  **Fetch your measures:** Specify a date range and an output file.

    ```bash
    withings2weeks fetch-measures 2024W01 2025W01 --output-path weekly-2024.ods
    ```

### Command-line options:
*   `--output-path PATH`: Specify an output path for the spreadsheet.
*   `--stdout`: Print the results to the terminal instead of saving to a file.
*   `--overwrite`: Allow overwriting an existing output file.
*   `--file-source PATH`: Use a Withings CSV export instead of the API, filtered to the same requested week range.

### Aggregation Algorithm

1. Select the complete measurement row with the lowest total weight on each calendar day. Ties select the earliest timestamp, then the first input row. Components always come from that same row; they are not minimized independently.
2. Within each ISO week (Monday-Sunday), let `m` be the lowest selected daily weight. Assign each daily row the coefficient `a = 2 ** (-(weight_kg - m) / 2)`. The minimum gets 1; +2 kg gets 0.5; +3 kg gets about 0.354; +4 kg gets 0.25.
3. For each metric, calculate `sum(a * value) / sum(a)`, using only selected rows where that metric is present. All metrics use the same row coefficients, but missing components have their own denominators. A day contributes at most one row, regardless of the number of weigh-ins.
4. Emit every week from the requested start through the inclusive end week. With no end specified, stop at the last completed week. Missing weeks and components are blank in ODS and terminal output; no interpolation or zero-filling is performed.

Rows with invalid timestamps or missing, non-finite, or non-positive total weights cannot contribute. Missing/non-finite components are excluded individually. API timestamps are UTC; timezone-naive CSV timestamps are also interpreted as UTC. For CLI output, timestamps are converted to the machine's current local timezone offset before date/week grouping, matching the range boundaries (this offset does not encode historical daylight-saving changes). Direct aggregation without an explicit range uses UTC and fills gaps between the first and last valid timestamps. Calculations retain full precision; terminal values show two decimals.

The fixed 2 kg half-weight distance is a heuristic for suspected upward scale-placement errors, not a calibrated probability or inverse-variance weight. It also downweights genuine higher-weight days and favors spuriously low readings. Taking more readings can lower a day's selected minimum even without a real change. Weights reset each week, so there is no cross-week smoothing, and a placement offset affecting every reading equally is not corrected. Shared component coefficients do not correct hydration-related body-composition errors.

### Output Columns
The output will contain the following columns with weekly averaged data:
*   `Week number`
*   `Weight (kg)`
*   `Muscle mass (kg)`
*   `Hydration (kg)`
*   `Fat mass (kg)`
*   `Bone mass (kg)`

## Development

This project uses `uv` for dependency management and running tasks.

**Run tests:**
```bash
uv run pytest
```

**Lint & format:**
```bash
uv run ruff check .
uv run ruff format .
```

**Type checking:**
```bash
uv run mypy
```

## Contributing

Contributions are welcome! If you have a feature request, bug report, or want to improve the code, please open an issue or a pull request.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
