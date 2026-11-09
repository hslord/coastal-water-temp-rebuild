"""History + 2026 data for CO-OPS stations that failed the 365-day check (8447435, 8454049). Serial, stop on 403/429, skip cached."""
import os, time, json
from datetime import date, timedelta
import requests
ROOT = os.path.dirname(os.path.abspath(__file__)); RAW = f"{ROOT}/raw"
CO = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
S = requests.Session(); S.headers["User-Agent"] = "coastal-water-temp-rebuild-feasibility"
jobs = []
for s in ("8447435", "8454049"):
    for y in range(1990, 2026):
        jobs.append((f"{RAW}/co_h_{s}_{y}.json", dict(station=s, interval="h", begin_date=f"{y}0101", end_date=f"{y}1231")))
    d = date(2026, 1, 1)
    while d <= date(2026, 11, 9):
        e = min(d + timedelta(days=30), date(2026, 11, 9))
        jobs.append((f"{RAW}/co_26_6min_{s}_{d:%Y%m%d}.json", dict(station=s, begin_date=f"{d:%Y%m%d}", end_date=f"{e:%Y%m%d}"))); d = e + timedelta(days=1)
    jobs.append((f"{RAW}/co_26_h_{s}.json", dict(station=s, interval="h", begin_date="20260101", end_date="20261108")))
todo = [j for j in jobs if not os.path.exists(j[0])]
print(len(todo), "requests to make", flush=True); n = 0
for path, extra in todo:
    time.sleep(1.0)
    r = S.get(CO, params=dict(product="water_temperature", units="english", time_zone="gmt", format="json", **extra), timeout=60)
    if r.status_code in (403, 429): print("BLOCKED", r.status_code, os.path.basename(path), "after", n); break
    if r.status_code != 200: print("HTTP", r.status_code, path); continue
    open(path, "w").write(r.text); n += 1
print("made", n, "remaining", len(todo) - n)
