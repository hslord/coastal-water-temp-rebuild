"""Monthly job: extend the monthly means with newly completed years, then rebuild the page.

Rules: completed years only; a year enters the means only when both sources
have data for it (a source "has" a year when one of its stations with a recent reading has data
for it; the windows are in config/settings.toml); only station-years after a station's last stored year are fetched, and a
station with no rows starts at its source's first year. The means CSV is written once, after all
fetching succeeded, so a block leaves the stored means unchanged and a rerun resumes from the cache.
"""
import sys
from datetime import UTC, datetime
from pathlib import Path

from coastal_water_temp import means
from coastal_water_temp.adapters import coops, ndbc
from coastal_water_temp.recent_readings import read_recent
from coastal_water_temp.regions import load_region
from coastal_water_temp.render import render_page, write_site
from coastal_water_temp.settings import default_path, load_settings


def make_fetchers(settings, cache_dir):
    return {
        "ndbc": lambda station, year: ndbc.hourly_history(station, year, settings, cache_dir=Path(cache_dir) / "ndbc"),
        "coops": lambda station, year: coops.hourly_history(station, year, settings, cache_dir=Path(cache_dir) / "coops"),
    }


def common_end_year(region, recent, now, fetch, settings, stored_end):
    """Latest completed year that every source in the region has data for, looking only forward.

    The search covers the years after stored_end (the latest year already stored) up to the last
    completed year; with nothing stored it starts at each source's first year in the settings. If
    no year in that range has data for every source, the stored end year stays (an error if
    nothing is stored).
    """
    active = {}
    for s in region.stations:
        r = recent.get(s.id)
        if r and now - r[0] <= settings.active_window:
            active.setdefault(s.source, []).append(s.id)
    sources = {s.source for s in region.stations}
    missing = sources - set(active)
    if missing:
        raise RuntimeError(f"no station with a recent reading for: {sorted(missing)}; run the recent job first")
    last_completed = now.year - 1
    available = {}
    for src in sources:
        start = settings.first_year[src] if stored_end is None else stored_end + 1
        available[src] = {y for y in range(start, last_completed + 1)
                          if any(fetch[src](st, y) for st in active[src])}
    common = set.intersection(*available.values())
    if common:
        return max(common)
    if stored_end is None:
        raise RuntimeError("no completed year has data for every source")
    return stored_end


def run(region_path, data_dir="data", cache_dir="cache", site_dir="site", now=None, settings=None, fetch=None):
    now = now or datetime.now(UTC)
    settings = settings or load_settings(default_path(region_path))
    fetch = fetch or make_fetchers(settings, cache_dir)
    region = load_region(region_path, settings)
    means_path = Path(data_dir) / "means" / f"{region.id}.csv"
    rows = means.read_means(means_path)
    recent = read_recent(Path(data_dir) / "recent" / f"{region.id}.csv")
    stored_end = max((r.year for r in rows), default=None)
    end_year = common_end_year(region, recent, now, fetch, settings, stored_end)
    new = []
    for s in region.stations:
        last = max((r.year for r in rows if r.station_id == s.id), default=None)
        start = settings.first_year[s.source] if last is None else last + 1
        for year in range(start, end_year + 1):
            new += means.monthly_rows(s.id, fetch[s.source](s.id, year))
    rows = means.merge_duplicates([r for r in rows if r.year <= end_year] + new)
    means.write_means(means_path, rows)
    write_site(site_dir, region, render_page(region, rows, end_year, recent, now, settings), settings)
    return end_year, len(new)


def main(argv=None):
    """Command line: cwt-monthly <region file>."""
    args = sys.argv[1:] if argv is None else argv
    year, n = run(args[0])
    print(f"means through {year}; {n} new station-month rows")


if __name__ == "__main__":
    main()
