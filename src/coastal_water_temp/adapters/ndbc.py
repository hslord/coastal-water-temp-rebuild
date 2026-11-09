"""NDBC adapter: realtime file for `latest`, yearly stdmet files for `hourly_history`.

Formats verified in docs/data_report.md and against tests/fixtures. Access rule (docs/decisions.md,
applied to NDBC too): serial requests, 1 per second.
"""
import gzip
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

import requests

BASE = "https://www.ndbc.noaa.gov"
HEADERS = {"User-Agent": "coastal-water-temp-rebuild"}


MIN_INTERVAL = 1.0
_last_request = [0.0]


def _get(url):
    wait = MIN_INTERVAL - (time.monotonic() - _last_request[0])
    if wait > 0:
        time.sleep(wait)
    _last_request[0] = time.monotonic()
    return requests.get(url, headers=HEADERS, timeout=60)


def c_to_f(c):
    return c * 9 / 5 + 32


def parse(text):
    """Yield (utc_datetime, wtmp_celsius) for rows with a valid WTMP. Columns are found by header name.

    Layouts seen in real files (tests/fixtures): header plus units line (2024, realtime); header
    only, no `#`, no units line (44005 for 1979, 1999, 2004); 2-digit year values (1979, 1998; the 2024 header also says YY but has 4 digits);
    no `mm` column (1979 to 2004), read as minute 0.
    """
    lines = text.splitlines()
    cols = lines[0].lstrip("#").split()
    year_col = "YYYY" if "YYYY" in cols else "YY"
    for need in (year_col, "MM", "DD", "hh", "WTMP"):
        if need not in cols:
            raise ValueError(f"unsupported NDBC format: no {need} column in {cols}")
    i = {name: cols.index(name) for name in (year_col, "MM", "DD", "hh", "WTMP")}
    i_min = cols.index("mm") if "mm" in cols else None
    for ln in lines[1:]:
        f = ln.split()
        if not f or not f[0].isdigit() or f[i["WTMP"]] in ("MM", "999.0"):
            continue
        year = int(f[i[year_col]])
        if year < 100:  # 2-digit years; the header says YY even when the values have 4 digits
            year += 1900
        minute = int(f[i_min]) if i_min is not None else 0
        yield datetime(year, int(f[i["MM"]]), int(f[i["DD"]]), int(f[i["hh"]]), minute, tzinfo=UTC), float(f[i["WTMP"]])


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


def hourly_history(station_id, year, get=_get, cache_dir=None):
    """[(utc_hour, temp_f)] for the year. A clock hour counts if it has at least one valid
    reading; its value is the mean of the valid readings in that hour. A missing file (HTTP 404)
    gives []. Other failures raise. With cache_dir, a downloaded file is kept as
    ndbc_<station>_<year>.txt.gz and reused; a 404 is not cached.
    """
    path = Path(cache_dir) / f"ndbc_{station_id}_{year}.txt.gz" if cache_dir else None
    if path and path.exists():
        raw = path.read_bytes()
    else:
        r = get(f"{BASE}/data/historical/stdmet/{station_id}h{year}.txt.gz")
        if r.status_code == 404:
            return []
        if r.status_code != 200:
            raise RuntimeError(f"NDBC history {station_id} {year}: HTTP {r.status_code}")
        raw = r.content
        if path:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
    by_hour = defaultdict(list)
    for t, c in parse(gzip.decompress(raw).decode("utf-8")):
        by_hour[t.replace(minute=0)].append(c)
    return [(h, c_to_f(sum(v) / len(v))) for h, v in sorted(by_hour.items())]
