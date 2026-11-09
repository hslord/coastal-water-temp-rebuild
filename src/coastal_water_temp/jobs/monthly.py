"""Monthly job: extend the monthly means with newly completed years, then rebuild the page.

Rules (docs/decisions.md): completed years only; a year enters the means only when both sources
have data for it (a source "has" a year when one of its stations with a reading in the last 365
days has data for it); only station-years after a station's last stored year are fetched, and a
station with no rows starts at its source's first year. The means CSV is written once, after all
fetching succeeded, so a block leaves the stored means unchanged and a rerun resumes from the cache.
"""
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from coastal_water_temp import means
from coastal_water_temp.adapters import coops, ndbc
from coastal_water_temp.config import load_region
from coastal_water_temp.jobs.recent import read_recent
from coastal_water_temp.render import render_page

# First year to try for a station with no stored rows. NDBC: earliest yearly file seen is 1978
# (docs/data_report.md). CO-OPS: no data before 1995 in the 1990 and 1995 probes, so 1990 is a floor.
FIRST_YEAR = {"ndbc": 1970, "coops": 1990}
ACTIVE_WINDOW = timedelta(days=365)


def make_fetchers(cache_dir):
    return {
        "ndbc": lambda station, year: ndbc.hourly_history(station, year, cache_dir=Path(cache_dir) / "ndbc"),
        "coops": lambda station, year: coops.hourly_history(station, year, cache_dir=Path(cache_dir) / "coops"),
    }


def common_end_year(region, recent, now, fetch):
    """Latest completed year (within 3 years back) that every source in the region has data for."""
    active = {}
    for s in region.stations:
        r = recent.get(s.id)
        if r and now - r[0] <= ACTIVE_WINDOW:
            active.setdefault(s.source, []).append(s.id)
    sources = {s.source for s in region.stations}
    missing = sources - set(active)
    if missing:
        raise RuntimeError(f"no station with a reading in the last 365 days for: {sorted(missing)}; run the recent job first")
    for year in range(now.year - 1, now.year - 4, -1):
        if all(any(fetch[src](st, year) for st in active[src]) for src in sources):
            return year
    raise RuntimeError("no completed year in the last 3 has data for every source")


def run(region_path, data_dir="data", cache_dir="cache", site_dir="site", now=None, fetch=None):
    now = now or datetime.now(UTC)
    fetch = fetch or make_fetchers(cache_dir)
    region = load_region(region_path)
    means_path = Path(data_dir) / "means" / f"{region.id}.csv"
    rows = means.read_means(means_path)
    recent = read_recent(Path(data_dir) / "recent" / f"{region.id}.csv")
    end_year = common_end_year(region, recent, now, fetch)
    new = []
    for s in region.stations:
        last = max((r.year for r in rows if r.station_id == s.id), default=None)
        start = FIRST_YEAR[s.source] if last is None else last + 1
        for year in range(start, end_year + 1):
            new += means.monthly_rows(s.id, fetch[s.source](s.id, year))
    rows = means.merge_duplicates([r for r in rows if r.year <= end_year] + new)
    means.write_means(means_path, rows)
    out = Path(site_dir) / f"{region.id}.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_page(region, rows, end_year, recent, now), encoding="utf-8")
    return end_year, len(new)


if __name__ == "__main__":
    year, n = run(sys.argv[1])
    print(f"means through {year}; {n} new station-month rows")
