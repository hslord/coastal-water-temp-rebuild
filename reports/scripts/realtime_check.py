"""Realtime check for all 22 stations: any valid reading in the last 365 days?
Serial, ~1 request/second, stops at the first 403/429. Cached responses are reused."""
import os, sys, time, json
from datetime import datetime, timedelta, timezone
import requests

ROOT = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(ROOT, "raw")
NDBC = ["44005", "44007", "44008", "44011", "44013", "44018", "44020"]
COOPS = ["8410140", "8411060", "8413320", "8418150", "8447386", "8447435", "8447930",
         "8449130", "8452660", "8452944", "8454000", "8454049", "8461490", "8465705", "8467150"]
CO = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
ND = "https://www.ndbc.noaa.gov"
NOW = datetime.now(timezone.utc).replace(tzinfo=None)
START = (NOW - timedelta(days=365)).date()
S = requests.Session()
S.headers["User-Agent"] = "coastal-water-temp-rebuild-feasibility"


class Blocked(Exception):
    pass


def fetch(url, params, path):
    """Return (status, text). Cached when the file exists and is a 200 body."""
    if os.path.exists(path):
        return 200, open(path).read()
    time.sleep(1.0)
    r = S.get(url, params=params, timeout=60)
    if r.status_code in (403, 429):
        raise Blocked(f"{r.status_code} from {url}")
    if r.status_code == 200:
        open(path, "w").write(r.text)
    return r.status_code, r.text


rows = []
try:
    for s in NDBC:
        code, txt = fetch(f"{ND}/data/realtime2/{s}.txt", None, f"{RAW}/nd_rt_{s}.txt")
        if code != 200:
            import glob, gzip
            last = None
            for pth in sorted(glob.glob(f"{RAW}/nd_h_{s}_*.gz"))[-2:]:
                ls = gzip.open(pth, "rt", errors="replace").read().splitlines()
                wj = ls[0].lstrip("#").split().index("WTMP")
                for ln in ls:
                    if ln.startswith("#"): continue
                    f = ln.split()
                    try:
                        y = int(f[0]); y = y + 1900 if y < 100 else y
                        t = datetime(y, int(f[1]), int(f[2]), int(f[3])); x = float(f[wj])
                    except (ValueError, IndexError): continue
                    if x < 90 and (last is None or t > last): last = t
            ok = last is not None and (NOW - last).days <= 365
            rows.append(dict(station=s, source="NDBC",
                             realtime="PASS" if ok else "FAIL: no realtime file (HTTP %d); last valid reading in yearly history is older than 365 days" % code,
                             valid_hours=0, last_valid_hourly=last.strftime("%Y-%m-%d %H:%M") if last else None))
            continue
        lines = txt.splitlines()
        wi = lines[0].lstrip("#").split().index("WTMP")
        valid = []
        for ln in lines[2:]:
            f = ln.split()
            try:
                t = datetime(int(f[0]), int(f[1]), int(f[2]), int(f[3]), int(f[4]))
            except (ValueError, IndexError):
                continue
            if f[wi] != "MM":
                valid.append(t)
        hours = {t.replace(minute=0) for t in valid}
        rows.append(dict(station=s, source="NDBC", realtime="PASS" if valid else "FAIL: no valid readings in file",
                         valid_hours=len(hours), last_valid_hourly=max(valid).strftime("%Y-%m-%d %H:%M") if valid else None))
    for s in COOPS:
        p = dict(product="water_temperature", units="english", time_zone="gmt", format="json", interval="h",
                 station=s, begin_date=START.strftime("%Y%m%d"), end_date=NOW.strftime("%Y%m%d"))
        code, txt = fetch(CO, p, f"{RAW}/co_rt365_{s}.json")
        d = json.loads(txt)
        data = [r for r in d.get("data", []) if r["v"] != ""]
        if data:
            rows.append(dict(station=s, source="CO-OPS", realtime="PASS", valid_hours=len(data), last_valid_hourly=data[-1]["t"]))
        else:
            rows.append(dict(station=s, source="CO-OPS", realtime="FAIL: no valid readings in 365 days", valid_hours=0, last_valid_hourly=None))
except Blocked as e:
    print("BLOCKED, stopping:", e)

json.dump(dict(run_utc=NOW.strftime("%Y-%m-%d %H:%M"), window_start=str(START), rows=rows), open(f"{ROOT}/realtime_check.json", "w"), indent=1)
with open(f"{ROOT}/coverage_partial.md", "w") as f:
    f.write(f"Partial coverage table (realtime check only), run {NOW:%Y-%m-%d %H:%M} UTC, window {START} to today\n\n")
    f.write("| Station | Source | Realtime check | Valid hours (NDBC: last 45 days; CO-OPS: last 365 days) | Last valid hourly reading (UTC) |\n|---|---|---|---|---|\n")
    for r in rows:
        f.write(f"| {r['station']} | {r['source']} | {r['realtime']} | {r['valid_hours']} | {r['last_valid_hourly'] or ''} |\n")
print(open(f"{ROOT}/coverage_partial.md").read())
print("rows:", len(rows), "of 22")
