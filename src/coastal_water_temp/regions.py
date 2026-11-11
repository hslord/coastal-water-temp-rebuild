"""Regions: one TOML file per region in config/regions/."""
import tomllib
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


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


def load_region(path, settings) -> Region:
    """Read a region TOML file. Stations come back sorted by source in the order of settings.sources
    (NDBC first, then CO-OPS), each source by ID."""
    order = list(settings.sources)
    data = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    stations = [Station(s["id"], s["source"], s["name"]) for s in data["stations"]]
    for s in stations:
        if s.source not in order:
            raise ValueError(f"station {s.id}: unknown source {s.source!r}")
    try:
        ZoneInfo(data["timezone"])
    except (ZoneInfoNotFoundError, ValueError) as e:
        raise ValueError(f"unknown time zone {data['timezone']!r}") from e
    ids = [s.id for s in stations]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate station id in region config")
    stations.sort(key=lambda s: (order.index(s.source), s.id))
    return Region(data["id"], data["title"], data["timezone"], tuple(stations))
