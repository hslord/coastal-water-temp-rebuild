# coastal-water-temp-rebuild

A rebuild of the decommissioned NOAA NCEI Coastal Water Temperature Guide.

The project currently covers one region, the Northern Atlantic Coast, with its stations listed in `config/regions/northern-atlantic-coast.toml`. A region is added with one config file in `config/regions/` that names its stations from NDBC or CO-OPS. Each region gets its own page.

**Live page:** link to be added after the first deploy.

## Data Refresh Rules
- A daily GitHub Action refreshes the recent temperature for every station.
- A monthly GitHub Action adds a year to the monthly averages when that year is complete.
- Both Actions rebuild the pages and publish them to GitHub Pages. The data used to build the pages is stored in `data/`.

## Calculation Rules
- **Monthly averages:** each JAN-DEC value is the mean temperature for that station and month across all completed years, weighted by the number of hourly readings. A year is included only when both NDBC and CO-OPS have data for it, so the averages end at the latest year that both sources have. The files in `data/means/` show which years are included.
- **Outlier screening:** a station-month is excluded from the averages if its mean is 15 °F or more from that station's median for that calendar month. Screening applies to stations with at least 8 years of that month and to the monthly averages only. It removes bad sensor readings, mostly from old CO-OPS data. The stored rows in `data/means/` keep all values.
- **Recent temperature:** the latest reading is shown if it is under 48 hours old. Otherwise the cell is blank. Times are shown in the region's local time zone.
- **Start years:** stations began recording in different years, so their averages cover different periods. Compare stations with that in mind. The coverage report below shows each station's first reading.

## Data Sources and Limitations
- Buoy data comes from NOAA's National Data Buoy Center (NDBC). Tide station data comes from NOAA's Center for Operational Oceanographic Products and Services (CO-OPS). Station names are copied from those sources.
- A station with no recent reading remains in the table, with a blank recent temperature and its monthly averages. The page shows which stations have no recent reading. The coverage report below gives each station's last valid reading.
- Early CO-OPS water temperature data contains impossible values that have normal quality flags. The outlier screening above excludes them from the averages.

## Station Coverage Report
[`reports/coverage_table.md`](reports/coverage_table.md) (also available as [CSV](reports/coverage_table.csv)) is a one-time snapshot that has one row per station and shows each station's coverage.
- **Realtime check:** PASS if the station reported a valid reading in the 365 days before the run. FAIL stations show their last valid reading.
- **Coverage %:** valid readings divided by the readings expected in the window. "Hourly" is the CO-OPS hourly value. For NDBC, it is any clock hour with at least one valid reading.
- **Windows:** the run year so far (NDBC: the last 45 days), the full history before that year, and the last 5, 10, 20 and 30 years before it. A last-N-years cell is blank when the station's record starts after the window begins.
- **Limitation:** the percentages count any reported value, including the impossible early CO-OPS readings that the outlier screening excludes from the averages. They measure how often a station reported a value.

The scripts that produced the table are in `reports/scripts/`. They are one-off scripts, separate from the data pipeline.

## Running Locally
```
make install
make test
make lint
PYTHONPATH=src uv run python -m coastal_water_temp.jobs.recent config/regions/northern-atlantic-coast.toml
PYTHONPATH=src uv run python -m coastal_water_temp.jobs.monthly config/regions/northern-atlantic-coast.toml
```
The page is written to `site/`. The first monthly run fetches all history and takes about 20 to 25 minutes. Raw responses are cached in `cache/`, so an interrupted run resumes where it stopped.

## Project Structure
- `config/regions/`: one TOML file per region, with the region `id`, `title` and `timezone`, and its stations (`id`, `source`, `name`).
- `config/settings.toml`: settings shared by every region: the outlier screening thresholds, the recent-reading window, the history start years, and each source's address and request pause.
- `src/coastal_water_temp/adapters/`: one module per data source, each with the same two functions.
- `src/coastal_water_temp/means.py` and `render.py`: monthly-means storage and outlier screening, and the HTML page.
- `src/coastal_water_temp/jobs/`: the daily (`recent`) and monthly jobs.
- `.github/workflows/`: the two scheduled Actions.

To add a region, add one TOML file in `config/regions/`. Each region's page is published as `<region id>.html`.

## Data Credit
Water temperature data comes from NOAA NDBC and NOAA CO-OPS. This project is not affiliated with or endorsed by NOAA.
