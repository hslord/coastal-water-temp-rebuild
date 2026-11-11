"""Recent job (daily): update each station's latest reading, then rebuild the region page.

Reads (never writes) data/means/<region id>.csv. Writes data/recent/<region id>.csv and
site/<region id>.html. A failed fetch keeps the stored reading; the page blanks any reading
older than the recent window in config/settings.toml.
"""
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import requests

from coastal_water_temp import means
from coastal_water_temp.adapters import coops, ndbc
from coastal_water_temp.adapters.errors import BlockedError
from coastal_water_temp.recent_readings import read_recent, write_recent
from coastal_water_temp.regions import load_region
from coastal_water_temp.render import render_page, write_site
from coastal_water_temp.settings import default_path, load_settings


def make_latest(settings):
    """{source name: function(station_id) -> (time, temp_f) or None}"""
    return {
        "ndbc": lambda station: ndbc.latest(station, settings),
        "coops": lambda station: coops.latest(station, settings),
    }


def run(region_path, data_dir="data", site_dir="site", now=None, settings=None, latest=None):
    """Returns a list of warning strings (failed fetches).

    A failed fetch for some stations only adds a warning. If the fetch fails for every station of
    a source, nothing is written and RuntimeError is raised, so the run fails instead of publishing
    a stale page.
    """
    now = now or datetime.now(UTC)
    settings = settings or load_settings(default_path(region_path))
    latest = latest or make_latest(settings)
    region = load_region(region_path, settings)
    recent_path = Path(data_dir) / "recent" / f"{region.id}.csv"
    recent = read_recent(recent_path)
    warnings = []
    blocked = set()
    failed = Counter()
    for s in region.stations:
        if s.source in blocked:
            warnings.append(f"{s.id}: skipped, {s.source} is blocking requests")
            failed[s.source] += 1
            continue
        try:
            got = latest[s.source](s.id)
        except BlockedError as e:
            blocked.add(s.source)
            warnings.append(f"{s.id}: {e}")
            failed[s.source] += 1
            continue
        except (RuntimeError, ValueError, KeyError, requests.RequestException) as e:  # the stored reading stays
            warnings.append(f"{s.id}: {type(e).__name__}: {e}")
            failed[s.source] += 1
            continue
        if got and (s.id not in recent or got[0] > recent[s.id][0]):
            recent[s.id] = got
    total = Counter(s.source for s in region.stations)
    dead = [src for src in total if failed[src] == total[src]]
    if dead:
        raise RuntimeError(f"every {', '.join(dead)} station fetch failed for {region.id}: {warnings[0]}")
    write_recent(recent_path, recent)
    rows = means.read_means(Path(data_dir) / "means" / f"{region.id}.csv")
    end_year = max((r.year for r in rows), default=0)  # the monthly job writes only years up to the common end year
    write_site(site_dir, region, render_page(region, rows, end_year, recent, now, settings), settings)
    return warnings


def main(argv=None):
    """Command line: cwt-recent <region file>."""
    args = sys.argv[1:] if argv is None else argv
    for w in run(args[0]):
        print("warning:", w)


if __name__ == "__main__":
    main()
