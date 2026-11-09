"""Region config: one TOML file per region (see docs/spec.md, Region config)."""
import tomllib
from dataclasses import dataclass
from pathlib import Path

SOURCES = ("ndbc", "coops")  # display order: NDBC buoys first, then CO-OPS


@dataclass(frozen=True)
class Station:
    id: str
    source: str
    name: str


@dataclass(frozen=True)
class Region:
    id: str
    title: str
    timezone: str
    stations: tuple[Station, ...]


def load_region(path) -> Region:
    """Read a region TOML file. Stations come back sorted: NDBC first, then CO-OPS, each by ID."""
    data = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    stations = [Station(s["id"], s["source"], s["name"]) for s in data["stations"]]
    for s in stations:
        if s.source not in SOURCES:
            raise ValueError(f"station {s.id}: unknown source {s.source!r}")
    ids = [s.id for s in stations]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate station id in region config")
    stations.sort(key=lambda s: (SOURCES.index(s.source), s.id))
    return Region(data["id"], data["title"], data["timezone"], tuple(stations))
