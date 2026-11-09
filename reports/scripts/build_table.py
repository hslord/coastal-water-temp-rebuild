"""History columns of the coverage table from cached raw files (no requests)."""
import os, json, gzip, glob
from datetime import datetime, timedelta
ROOT = os.path.dirname(os.path.abspath(__file__)); RAW = f"{ROOT}/raw"
rt = json.load(open(f"{ROOT}/realtime_check.json"))["rows"]
END = datetime(2025, 12, 31, 23)

def coops_valid(s):
    v = set()
    for y in range(1990, 2026):
        p = f"{RAW}/co_h_{s}_{y}.json"
        d = json.load(open(p)) if os.path.exists(p) else {}
        for r in d.get("data", []):
            if r["v"] != "":
                v.add(datetime.strptime(r["t"], "%Y-%m-%d %H:%M").replace(minute=0))
    return v

def ndbc_valid(s):
    v = set()
    for p in sorted(glob.glob(f"{RAW}/nd_h_{s}_*.gz")):
        lines = gzip.open(p, "rt", errors="replace").read().splitlines()
        wi = lines[0].lstrip("#").split().index("WTMP")
        for ln in lines:
            if ln.startswith("#"): continue
            f = ln.split()
            try:
                y = int(f[0]); y = y + 1900 if y < 100 else y
                t = datetime(y, int(f[1]), int(f[2]), int(f[3])); x = float(f[wi])
            except (ValueError, IndexError): continue
            if x < 90: v.add(t)
    return v

def cov(valid, start):
    total = int((END - start).total_seconds() // 3600) + 1
    n = sum(1 for h in valid if start <= h <= END)
    return n / total

out = []
for r in rt:
    s = r["station"]
    row = dict(station=s, source=r["source"], realtime=r["realtime"].split(":")[0])
    v = coops_valid(s) if r["source"] == "CO-OPS" else ndbc_valid(s)
    first = min(v)
    row["oldest_hourly"] = first.strftime("%Y-%m-%d")
    row["full"] = round(100 * cov(v, first), 1)
    for n in (5, 10, 20, 30):
        ws = datetime(2025 - n + 1, 1, 1)
        row[f"last{n}"] = round(100 * cov(v, ws), 1) if first <= ws else None
    out.append(row)
json.dump(out, open(f"{ROOT}/history_cols.json", "w"), indent=1)
print("station source rt oldest full 5y 10y 20y 30y")
for r in out:
    print(r["station"], r["source"], r["realtime"], r.get("oldest_hourly", ""), r.get("full", ""), *(r.get(f"last{n}", "") if r.get("full") is not None else "" for n in (5,10,20,30)))
