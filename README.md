# withings2weeks: Your Withings Data Week-by-Week

**Turn your Withings scale measurements into clear, weekly insights. This CLI tool aggregates your weight, muscle mass, and other metrics into a simple weekly average, perfect for tracking long-term trends.**

`withings2weeks` can fetch data directly from the Withings API or use a local data export. It then pivots the measurements into weekly averages and saves them as an OpenDocument Spreadsheet (`.ods`) or prints them to your terminal.

## Why use `withings2weeks`?

It's about control of data and visualizing it the way you want.
This tool is essentially just an exporter, which simultaneously reduces to weekly averages (as daily or individual measurements are usually not meaningful).
You can then plot and analyze using your tools of preference, whether that's Python, R or Excel.

This should be a superior experience to the limited Withings app and webpage.

## Features

*   **Interactive OAuth2 flow:** Securely authorize with the Withings API.
*   **Weekly Averaging:** First averages within each day, then averages over the week.
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
