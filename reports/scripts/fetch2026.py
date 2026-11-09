"""CO-OPS 2026: 6-minute data in 31-day chunks (Jan 1 - Nov 9) and one hourly request (Jan 1 - Nov 8).
Serial, 1 request/second, stops at first 403/429, skips cached files."""
import os, time, json
from datetime import date, timedelta
import requests
ROOT = os.path.dirname(os.path.abspath(__file__)); RAW = f"{ROOT}/raw"
CO = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
stations = [r["station"] for r in json.load(open(f"{ROOT}/realtime_check.json"))["rows"] if r["source"] == "CO-OPS" and r["realtime"] == "PASS"]
S = requests.Session(); S.headers["User-Agent"] = "coastal-water-temp-rebuild-feasibility"
chunks, d = [], date(2026, 1, 1)
while d <= date(2026, 11, 9):
    e = min(d + timedelta(days=30), date(2026, 11, 9)); chunks.append((d, e)); d = e + timedelta(days=1)
jobs = []
for s in stations:
    for a, b in chunks:
        jobs.append((f"{RAW}/co_26_6min_{s}_{a:%Y%m%d}.json", dict(station=s, begin_date=f"{a:%Y%m%d}", end_date=f"{b:%Y%m%d}")))
    jobs.append((f"{RAW}/co_26_h_{s}.json", dict(station=s, interval="h", begin_date="20260101", end_date="20261108")))
todo = [j for j in jobs if not os.path.exists(j[0])]
print(len(chunks), "chunks;", len(todo), "requests to make", flush=True)
done = 0
for path, extra in todo:
    p = dict(product="water_temperature", units="english", time_zone="gmt", format="json", **extra)
    time.sleep(1.0)
    r = S.get(CO, params=p, timeout=60)
    if r.status_code in (403, 429):
        print(f"BLOCKED {r.status_code} at {os.path.basename(path)} after {done}; stopping"); break
    if r.status_code != 200:
        print("HTTP", r.status_code, path); continue
    open(path, "w").write(r.text); done += 1
print("finished; made", done, "remaining", len(todo) - done)
