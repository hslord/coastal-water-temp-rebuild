"""Last-ever valid readings for the stations that failed the realtime check.
NDBC: from cached yearly files. CO-OPS: walk back year by year (hourly), then 6-minute within 31 days of that reading.
Serial, 1 request/second, stops at 403/429."""
import os, json, glob, gzip, time
from datetime import datetime, timedelta
import requests
ROOT = os.path.dirname(os.path.abspath(__file__)); RAW = f"{ROOT}/raw"
CO = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
S = requests.Session(); S.headers["User-Agent"] = "coastal-water-temp-rebuild-feasibility"
rt = json.load(open(f"{ROOT}/realtime_check.json"))["rows"]
failed = [r for r in rt if r["realtime"] != "PASS"]
out = {}

def get(params, path):
    if os.path.exists(path): return json.load(open(path))
    time.sleep(1.0)
    r = S.get(CO, params=dict(product="water_temperature", units="english", time_zone="gmt", format="json", **params), timeout=60)
    if r.status_code in (403, 429): raise SystemExit(f"BLOCKED {r.status_code}")
    d = r.json(); open(path, "w").write(json.dumps(d)); return d

for r in failed:
    s = r["station"]
    if r["source"] == "NDBC":
        last = None
        for p in sorted(glob.glob(f"{RAW}/nd_h_{s}_*.gz")):
            ls = gzip.open(p, "rt", errors="replace").read().splitlines()
            hdr = ls[0].lstrip("#").split(); wi = hdr.index("WTMP"); hasmm = "mm" in hdr
            for ln in ls:
                if ln.startswith("#"): continue
                f = ln.split()
                try:
                    y = int(f[0]); y = y + 1900 if y < 100 else y
                    t = datetime(y, int(f[1]), int(f[2]), int(f[3]), int(f[4]) if hasmm else 0); x = float(f[wi])
                except (ValueError, IndexError): continue
                if x < 90 and (last is None or t > last): last = t
        out[s] = dict(last_native=last.strftime("%Y-%m-%d %H:%M"), last_hourly=last.replace(minute=0).strftime("%Y-%m-%d %H:%M"))
    else:
        found = None
        for y in range(2025, 1989, -1):
            d = get(dict(station=s, interval="h", begin_date=f"{y}0101", end_date=f"{y}1231"), f"{RAW}/co_h_{s}_{y}.json")
            v = [x for x in d.get("data", []) if x["v"] != ""]
            if v: found = v[-1]["t"]; break
        if not found: out[s] = dict(last_native=None, last_hourly=None, note="no data 1990-2025"); continue
        t = datetime.strptime(found, "%Y-%m-%d %H:%M"); a = (t - timedelta(days=29)).date(); b = (t + timedelta(days=1)).date()
        d = get(dict(station=s, begin_date=f"{a:%Y%m%d}", end_date=f"{b:%Y%m%d}"), f"{RAW}/co_last6_{s}.json")
        v = [x for x in d.get("data", []) if x["v"] != ""]
        out[s] = dict(last_hourly=found, last_native=v[-1]["t"] if v else None)
    print(s, out[s], flush=True)
json.dump(out, open(f"{ROOT}/last_valid_failed.json", "w"), indent=1)
