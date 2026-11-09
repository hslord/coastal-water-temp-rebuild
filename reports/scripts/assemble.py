import os, json, glob, csv
from datetime import datetime, timezone
ROOT = os.path.dirname(os.path.abspath(__file__)); RAW = f"{ROOT}/raw"
hist = {r["station"]: r for r in json.load(open(f"{ROOT}/history_cols.json"))}
rtc = {r["station"]: r for r in json.load(open(f"{ROOT}/realtime_check.json"))["rows"]}
CUT = datetime(2026, 11, 9)           # 2026 window ends at end of 2026-11-08
DAYS26 = 312                          # Jan 1 .. Nov 8
rows = []
for s, h in hist.items():
    r = dict(station=s, source=h["source"], realtime=h["realtime"])
    if h["source"] == "CO-OPS": r["interval_min"] = 6
    else: r["interval_min"] = 10
    if h["realtime"] != "PASS":
        lv = json.load(open(f"{ROOT}/last_valid_failed.json"))[s]
        r["last_native"], r["last_hourly"] = lv["last_native"], lv["last_hourly"]
        r["note"] = "no valid reading in the last 365 days: excluded from region table"; rows.append(r); continue
    if h["source"] == "CO-OPS":
        nat = []
        for p in sorted(glob.glob(f"{RAW}/co_26_6min_{s}_*.json")):
            nat += [(datetime.strptime(x["t"], "%Y-%m-%d %H:%M")) for x in json.load(open(p)).get("data", []) if x["v"] != ""]
        hr = [datetime.strptime(x["t"], "%Y-%m-%d %H:%M") for x in json.load(open(f"{RAW}/co_26_h_{s}.json")).get("data", []) if x["v"] != ""]
        r["last_native"] = max(nat).strftime("%Y-%m-%d %H:%M")
        r["last_hourly"] = rtc[s]["last_valid_hourly"]
        r["native26"] = round(100 * len([t for t in nat if t < CUT]) / (DAYS26 * 240), 1)
        r["hourly26"] = round(100 * len([t for t in hr if t < CUT]) / (DAYS26 * 24), 1)
        r["window26"] = "2026-01-01..2026-11-08"
    else:
        lines = open(f"{RAW}/nd_rt_{s}.txt").read().splitlines()
        wi = lines[0].lstrip("#").split().index("WTMP"); v = []
        for ln in lines[2:]:
            f = ln.split()
            if f[wi] == "MM": continue
            v.append(datetime(int(f[0]), int(f[1]), int(f[2]), int(f[3]), int(f[4])))
        win = [t for t in v if datetime(2026, 9, 25) <= t < CUT]
        r["last_native"] = max(v).strftime("%Y-%m-%d %H:%M")
        r["last_hourly"] = max(v).replace(minute=0).strftime("%Y-%m-%d %H:%M")
        r["native26"] = round(100 * len(win) / (45 * 144), 1)
        r["hourly26"] = round(100 * len({t.replace(minute=0) for t in win}) / (45 * 24), 1)
        r["window26"] = "last 45 days (2026-09-25..2026-11-08)"
    for k in ("oldest_hourly", "full", "last5", "last10", "last20", "last30"): r[k] = h.get(k)
    rows.append(r)
cols = [("station","Station ID"),("source","Source"),("interval_min","Native interval (min)"),("realtime","Realtime check"),
        ("last_native","Last valid native reading (UTC)"),("last_hourly","Last valid hourly reading (UTC)"),
        ("native26","2026 native % non-null"),("hourly26","2026 hourly % non-null"),("window26","2026 window"),
        ("oldest_hourly","Oldest hourly reading"),("full","Full history % (excl. 2026)"),("last5","Last 5 yr %"),
        ("last10","Last 10 yr %"),("last20","Last 20 yr %"),("last30","Last 30 yr %"),("note","Note")]
with open(f"{ROOT}/coverage_table.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow([c[1] for c in cols])
    for r in rows: w.writerow([r.get(k, "") if r.get(k) is not None else "" for k, _ in cols])
with open(f"{ROOT}/coverage_table.md", "w") as f:
    f.write(f"Coverage table, run {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC. Blank = not applicable (see plan).\n\n")
    f.write("| " + " | ".join(c[1] for c in cols) + " |\n|" + "---|" * len(cols) + "\n")
    for r in rows: f.write("| " + " | ".join("" if r.get(k) is None else str(r.get(k, "")) for k, _ in cols) + " |\n")
print(open(f"{ROOT}/coverage_table.md").read())
