"""Settings shared by every region: config/settings.toml."""
import tomllib
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path


@dataclass(frozen=True)
class Source:
    base_url: str
    min_interval_seconds: float
    station_page_url: str
    no_data_message: str = ""


@dataclass(frozen=True)
class Settings:
    screening_max_gap_f: float
    screening_min_years: int
    recent_window: timedelta
    active_window: timedelta
    first_year: dict
    user_agent: str
    timeout_seconds: float
    sources: dict  # name -> Source, in display order


def default_path(region_path):
    """config/settings.toml next to the config/regions/ folder that holds the region file."""
    return Path(region_path).parent.parent / "settings.toml"


def load_settings(path) -> Settings:
    data = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    sources = {name: Source(**values) for name, values in data["sources"].items()}
    first_year = dict(data["history"]["first_year"])
    missing = set(sources) - set(first_year)
    if missing:
        raise ValueError(f"history.first_year has no entry for: {sorted(missing)}")
    return Settings(
        screening_max_gap_f=float(data["screening"]["max_gap_f"]),
        screening_min_years=int(data["screening"]["min_years"]),
        recent_window=timedelta(hours=data["display"]["recent_window_hours"]),
        active_window=timedelta(days=data["history"]["active_window_days"]),
        first_year=first_year,
        user_agent=data["http"]["user_agent"],
        timeout_seconds=data["http"]["timeout_seconds"],
        sources=sources,
    )
