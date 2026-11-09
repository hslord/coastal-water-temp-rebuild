"""CO-OPS adapter: `date=latest` for `latest`, hourly (`interval=h`) year requests for `hourly_history`.

Formats and limits verified in docs/data_report.md and against tests/fixtures. Access rules
(docs/decisions.md): serial requests, 1 per second, stop on HTTP 403 or 429.
"""
import json
import time
from datetime import UTC, datetime
from pathlib import Path

import requests

BASE = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
HEADERS = {"User-Agent": "coastal-water-temp-rebuild"}
MIN_INTERVAL = 1.0
NO_DATA = "No data was found"
_last_request = [0.0]


class BlockedError(RuntimeError):
    """The API answered 403 or 429. Stop; a rerun resumes from the cache."""


def _get(params):
    wait = MIN_INTERVAL - (time.monotonic() - _last_request[0])
    if wait > 0:
        time.sleep(wait)
    _last_request[0] = time.monotonic()
    q = {"product": "water_temperature", "units": "english", "time_zone": "gmt", "format": "json", **params}
    return requests.get(BASE, params=q, headers=HEADERS, timeout=60)


def _json(resp, what):
    """Parsed body, or None for the 'no data' answer. 403/429 raise BlockedError; other problems raise."""
    if resp.status_code in (403, 429):
        raise BlockedError(f"CO-OPS {what}: HTTP {resp.status_code}")
    if resp.status_code != 200:
        raise RuntimeError(f"CO-OPS {what}: HTTP {resp.status_code}")
    body = json.loads(resp.text)
    if "error" in body:
        if NO_DATA in body["error"].get("message", ""):
            return None
        raise RuntimeError(f"CO-OPS {what}: {body['error']}")
    return body


def _time(s):
    return datetime.strptime(s, "%Y-%m-%d %H:%M").replace(tzinfo=UTC)


def latest(station_id, get=_get):
    """(observation_time_utc, temp_f) of the latest reading, or None if there is none."""
    body = _json(get({"station": station_id, "date": "latest"}), f"latest {station_id}")
    if body is None:
        return None
    rows = [r for r in body["data"] if r["v"] != ""]
    if not rows:
        return None
    r = rows[-1]
    return _time(r["t"]), float(r["v"])


def hourly_history(station_id, year, get=_get, cache_dir=None):
    """[(utc_hour, temp_f)] valid hourly values for the year; blank values are dropped.

    With cache_dir, a response that has data is saved as co_h_<station>_<year>.json and reused,
    so a rerun after a block does not refetch. 'No data' answers are not cached.
    """
    path = Path(cache_dir) / f"co_h_{station_id}_{year}.json" if cache_dir else None
    if path and path.exists():
        body = json.loads(path.read_text())
    else:
        resp = get({"station": station_id, "interval": "h", "begin_date": f"{year}0101", "end_date": f"{year}1231"})
        body = _json(resp, f"history {station_id} {year}")
        if body is None:
            return []
        if path:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(resp.text)
    return [(_time(r["t"]), float(r["v"])) for r in body["data"] if r["v"] != ""]
