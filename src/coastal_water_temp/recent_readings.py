"""Latest reading per station: data/recent/<region id>.csv."""
import csv
from datetime import UTC, datetime
from pathlib import Path

TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def read_recent(path):
    """{station_id: (observation_time_utc, temp_f)}; empty if the file does not exist."""
    p = Path(path)
    if not p.exists():
        return {}
    with p.open(newline="") as f:
        return {r["station_id"]: (datetime.strptime(r["observation_time_utc"], TIME_FORMAT).replace(tzinfo=UTC), float(r["temp_f"]))
                for r in csv.DictReader(f)}


def write_recent(path, recent):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(("station_id", "observation_time_utc", "temp_f"))
        for s, (t, v) in sorted(recent.items()):
            w.writerow((s, t.strftime(TIME_FORMAT), f"{v:.1f}"))
