from datetime import timedelta

import pytest
from helpers import ROOT, SETTINGS

from coastal_water_temp.settings import default_path, load_settings

MINIMAL = """
[screening]
max_gap_f = 10
min_years = 5
[display]
recent_window_hours = 12
[history]
active_window_days = 30
first_year = { a = 1990 }
[site]
home_region = "a-region"
[http]
user_agent = "test"
timeout_seconds = 5
[sources.a]
base_url = "https://example.test"
min_interval_seconds = 0.5
station_page_url = "https://example.test/{id}"
"""


def test_real_settings_file_loads_with_both_sources_in_display_order():
    assert list(SETTINGS.sources) == ["ndbc", "coops"]
    assert set(SETTINGS.first_year) == {"ndbc", "coops"}
    assert SETTINGS.sources["coops"].no_data_message
    assert "{id}" in SETTINGS.sources["ndbc"].station_page_url


def test_values_are_read_from_the_file(tmp_path):
    p = tmp_path / "settings.toml"
    p.write_text(MINIMAL)
    s = load_settings(p)
    assert (s.screening_max_gap_f, s.screening_min_years) == (10.0, 5)
    assert s.recent_window == timedelta(hours=12) and s.active_window == timedelta(days=30)
    assert s.first_year == {"a": 1990} and s.home_region == "a-region"
    assert s.sources["a"].min_interval_seconds == 0.5 and s.sources["a"].no_data_message == ""


def test_source_without_a_first_year_is_rejected(tmp_path):
    p = tmp_path / "settings.toml"
    p.write_text(MINIMAL.replace("first_year = { a = 1990 }", "first_year = { }"))
    with pytest.raises(ValueError, match="first_year"):
        load_settings(p)


def test_default_path_is_next_to_the_regions_folder():
    region = ROOT / "config" / "regions" / "northern-atlantic-coast.toml"
    assert default_path(region) == ROOT / "config" / "settings.toml"
