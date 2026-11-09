"""CO-OPS hourly history 1990-2025 for stations that passed the realtime check.
Serial, 1 request/second, stops at the first 403/429, skips cached files."""
import os, sys, time, json
import requests
ROOT = os.path.dirname(os.path.abspath(__file__)); RAW = f"{ROOT}/raw"
CO = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
rt = json.load(open(f"{ROOT}/realtime_check.json"))["rows"]
stations = [r["station"] for r in rt if r["source"] == "CO-OPS" and r["realtime"] == "PASS"]
S = requests.Session(); S.headers["User-Agent"] = "coastal-water-temp-rebuild-feasibility"
todo = [(s, y) for s in stations for y in range(1990, 2026) if not os.path.exists(f"{RAW}/co_h_{s}_{y}.json")]
print(len(stations), "stations;", len(todo), "requests to make", flush=True)
done = 0
for s, y in todo:
    p = dict(product="water_temperature", units="english", time_zone="gmt", format="json", interval="h",
             station=s, begin_date=f"{y}0101", end_date=f"{y}1231")
    time.sleep(1.0)
    try:
        r = S.get(CO, params=p, timeout=60)
    except requests.RequestException as e:
        print("network error, stopping:", e); break
    if r.status_code in (403, 429):
        print(f"BLOCKED with {r.status_code} at {s} {y} after {done} requests; stopping"); break
    if r.status_code != 200:
        print("HTTP", r.status_code, s, y); continue
    open(f"{RAW}/co_h_{s}_{y}.json", "w").write(r.text)
    done += 1
    if done % 50 == 0:
        print(done, "done", flush=True)
print("finished; requests made:", done, "remaining:", len(todo) - done)
