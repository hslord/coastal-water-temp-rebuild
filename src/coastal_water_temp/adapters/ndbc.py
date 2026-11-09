"""NDBC adapter: realtime file for `latest`, yearly stdmet files for `hourly_history`.

Formats verified in docs/data_report.md and against tests/fixtures. Not verified: yearly files
before 2000 (2-digit years, possibly no minute column). Those raise instead of guessing.
"""
import gzip
from collections import defaultdict
from datetime import UTC, datetime

import requests

BASE = "https://www.ndbc.noaa.gov"
HEADERS = {"User-Agent": "coastal-water-temp-rebuild"}


def _get(url):
    return requests.get(url, headers=HEADERS, timeout=60)


def c_to_f(c):
    return c * 9 / 5 + 32


def parse(text):
    """Yield (utc_datetime, wtmp_celsius) for rows with a valid WTMP. Columns are found by header name."""
    lines = text.splitlines()
    cols = lines[0].lstrip("#").split()
    for need in ("YY", "MM", "DD", "hh", "mm", "WTMP"):
        if need not in cols:
            raise ValueError(f"unsupported NDBC format: no {need} column in {cols}")
    i = {name: cols.index(name) for name in ("YY", "MM", "DD", "hh", "mm", "WTMP")}
    for ln in lines[2:]:
        f = ln.split()
        if not f or f[i["WTMP"]] in ("MM", "999.0"):
            continue
        year = int(f[i["YY"]])
        if year < 1000:
            raise ValueError(f"unsupported NDBC year format: {f[i['YY']]!r}")
        t = datetime(year, int(f[i["MM"]]), int(f[i["DD"]]), int(f[i["hh"]]), int(f[i["mm"]]), tzinfo=UTC)
        yield t, float(f[i["WTMP"]])


def latest(station_id, get=_get):
    """(observation_time_utc, temp_f) of the newest valid reading, or None if there is none.

    No realtime file (HTTP 404, as for 44005 and 44018) means no reading. Other failures raise.
    """
    r = get(f"{BASE}/data/realtime2/{station_id}.txt")
    if r.status_code == 404:
        return None
    if r.status_code != 200:
        raise RuntimeError(f"NDBC realtime {station_id}: HTTP {r.status_code}")
    rows = list(parse(r.text))
    if not rows:
        return None
    t, c = max(rows)
    return t, c_to_f(c)


def hourly_history(station_id, year, get=_get):
    """[(utc_hour, temp_f)] for the year. A clock hour counts if it has at least one valid
    reading; its value is the mean of the valid readings in that hour. A missing file (HTTP 404)
    gives []. Other failures raise.
    """
    r = get(f"{BASE}/data/historical/stdmet/{station_id}h{year}.txt.gz")
    if r.status_code == 404:
        return []
    if r.status_code != 200:
        raise RuntimeError(f"NDBC history {station_id} {year}: HTTP {r.status_code}")
    by_hour = defaultdict(list)
    for t, c in parse(gzip.decompress(r.content).decode("utf-8")):
        by_hour[t.replace(minute=0)].append(c)
    return [(h, c_to_f(sum(v) / len(v))) for h, v in sorted(by_hour.items())]
