"""Recent job (daily): update each station's latest reading, then rebuild the region page.

Reads (never writes) data/means/<region id>.csv. Writes data/recent/<region id>.csv and
site/<region id>.html. A failed fetch keeps the stored reading; the page blanks any reading
older than 48 hours.
"""
import csv
import sys
from datetime import UTC, datetime
from pathlib import Path

import requests

from coastal_water_temp import means
from coastal_water_temp.adapters import coops, ndbc
from coastal_water_temp.config import load_region
from coastal_water_temp.render import render_page

ADAPTERS = {"ndbc": ndbc, "coops": coops}
TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def read_recent(path):
    p = Path(path)
    if not p.exists():
        return {}
    with p.open(newline="") as f:
        return {r["station_id"]: (datetime.strptime(r["observation_time_utc"], TIME_FORMAT).replace(tzinfo=UTC), float(r["temp_f"]))
                for r in csv.DictReader(f)}


def write_recent(path, recent):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(("station_id", "observation_time_utc", "temp_f"))
        for s, (t, v) in sorted(recent.items()):
            w.writerow((s, t.strftime(TIME_FORMAT), f"{v:.1f}"))


def run(region_path, data_dir="data", site_dir="site", now=None, adapters=ADAPTERS):
    """Returns a list of warning strings (failed fetches). Never raises for a station fetch failure."""
    now = now or datetime.now(UTC)
    region = load_region(region_path)
    recent_path = Path(data_dir) / "recent" / f"{region.id}.csv"
    recent = read_recent(recent_path)
    warnings = []
    blocked = set()
    for s in region.stations:
        if s.source in blocked:
            warnings.append(f"{s.id}: skipped, {s.source} is blocking requests")
            continue
        try:
            got = adapters[s.source].latest(s.id)
        except coops.BlockedError as e:
            blocked.add(s.source)
            warnings.append(f"{s.id}: {e}")
            continue
        except (RuntimeError, ValueError, KeyError, requests.RequestException) as e:  # the stored reading stays
            warnings.append(f"{s.id}: {type(e).__name__}: {e}")
            continue
        if got and (s.id not in recent or got[0] > recent[s.id][0]):
            recent[s.id] = got
    write_recent(recent_path, recent)
    rows = means.read_means(Path(data_dir) / "means" / f"{region.id}.csv")
    end_year = max((r.year for r in rows), default=0)  # the monthly job writes only years up to the common end year
    out = Path(site_dir) / f"{region.id}.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_page(region, rows, end_year, recent, now), encoding="utf-8")
    return warnings


if __name__ == "__main__":
    for w in run(sys.argv[1]):
        print("warning:", w)
