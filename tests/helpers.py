"""Shared test helper: the real settings file."""
from pathlib import Path

from coastal_water_temp.settings import load_settings

ROOT = Path(__file__).parent.parent
SETTINGS = load_settings(ROOT / "config" / "settings.toml")
