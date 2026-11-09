"""Monthly means: per station, year, month rows (docs/spec.md, Monthly-means storage)."""
import csv
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

FIELDS = ("station_id", "year", "month", "n_obs", "mean_f")


@dataclass(frozen=True)
class MeanRow:
    station_id: str
    year: int
    month: int
    n_obs: int
    mean_f: float


def monthly_rows(station_id, hourly):
    """Group [(utc_hour, temp_f)] into one MeanRow per (year, month) that has a value."""
    groups = defaultdict(list)
    for t, f in hourly:
        groups[(t.year, t.month)].append(f)
    return [MeanRow(station_id, y, m, len(v), sum(v) / len(v)) for (y, m), v in sorted(groups.items())]


def read_means(path):
    p = Path(path)
    if not p.exists():
        return []
    with p.open(newline="") as f:
        return [MeanRow(r["station_id"], int(r["year"]), int(r["month"]), int(r["n_obs"]), float(r["mean_f"]))
                for r in csv.DictReader(f)]


def write_means(path, rows):
    """Write rows sorted by station, year, month, so unchanged input gives an identical file."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(FIELDS)
        for r in sorted(rows, key=lambda r: (r.station_id, r.year, r.month)):
            w.writerow([r.station_id, r.year, r.month, r.n_obs, f"{r.mean_f:.3f}"])


def stored_years(rows):
    """Set of (station_id, year) that already have rows."""
    return {(r.station_id, r.year) for r in rows}


def aggregate(rows, end_year):
    """{station_id: {month: weighted mean °F}} over years up to end_year. Months with no data are absent."""
    total = defaultdict(float)
    count = defaultdict(int)
    for r in rows:
        if r.year <= end_year:
            total[(r.station_id, r.month)] += r.mean_f * r.n_obs
            count[(r.station_id, r.month)] += r.n_obs
    out = defaultdict(dict)
    for (s, m), n in count.items():
        out[s][m] = total[(s, m)] / n
    return dict(out)
