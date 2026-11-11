from datetime import UTC, datetime
from pathlib import Path

import pytest
from helpers import SETTINGS

from coastal_water_temp import means
from coastal_water_temp.adapters.errors import BlockedError
from coastal_water_temp.jobs import recent
from coastal_water_temp.means import MeanRow
from coastal_water_temp.recent_readings import read_recent, write_recent

REGION = """id = "t"
title = "T"
timezone = "America/New_York"
[[stations]]
id = "44007"
source = "ndbc"
name = "Buoy"
[[stations]]
id = "8447930"
source = "coops"
name = "Woods Hole"
[[stations]]
id = "8454000"
source = "coops"
name = "Providence"
"""
NOW = datetime(2026, 11, 9, 21, 0, tzinfo=UTC)


def utc(*a):
    return datetime(*a, tzinfo=UTC)


def setup(tmp_path, stored=None):
    region = tmp_path / "t.toml"
    region.write_text(REGION)
    data = tmp_path / "data"
    means.write_means(data / "means" / "t.csv", [MeanRow("44007", 2025, 1, 2, 15.0)])
    if stored:
        write_recent(data / "recent" / "t.csv", stored)
    return region, data


def adapters(ndbc_latest, coops_latest):
    return {"ndbc": ndbc_latest, "coops": coops_latest}


def run(tmp_path, ad, stored=None):
    region, data = setup(tmp_path, stored)
    w = recent.run(region, data, tmp_path / "site", NOW, SETTINGS, ad)
    return w, read_recent(data / "recent" / "t.csv"), (tmp_path / "site" / "t.html").read_text()


def test_fresh_readings_are_stored_and_shown(tmp_path):
    ad = adapters(lambda i: (utc(2026, 11, 9, 20, 30), 52.7), lambda i: (utc(2026, 11, 9, 20, 18), 57.2))
    w, recent, page = run(tmp_path, ad)
    assert w == [] and set(recent) == {"44007", "8447930", "8454000"}
    assert "57.2" in page and "52.7" in page


def test_failed_fetch_keeps_stored_reading_within_48_hours(tmp_path):
    def boom(i):
        if i == "8447930":
            raise RuntimeError("down")

    stored = {"8447930": (utc(2026, 11, 9, 9, 0), 55.0)}
    w, recent, page = run(tmp_path, adapters(lambda i: None, boom), stored)
    assert recent["8447930"] == (utc(2026, 11, 9, 9, 0), 55.0)
    assert "55.0" in page and any("8447930" in x for x in w)


def test_stored_reading_older_than_48_hours_is_blank_on_the_page(tmp_path):
    stored = {"8447930": (utc(2026, 11, 7, 20, 0), 55.0)}
    _, recent, page = run(tmp_path, adapters(lambda i: None, lambda i: None), stored)
    assert "8447930" in recent and "55.0" not in page


def test_block_stops_that_source_and_fails_the_run(tmp_path):
    calls = []

    def blocked(i):
        calls.append(i)
        raise BlockedError("HTTP 403")

    region, data = setup(tmp_path)
    with pytest.raises(RuntimeError, match="every coops station fetch failed"):
        recent.run(region, data, tmp_path / "site", NOW, SETTINGS,
                   adapters(lambda i: (utc(2026, 11, 9, 20, 30), 52.7), blocked))
    assert calls == ["8447930"] and not (data / "recent").exists()


def test_older_reading_from_source_does_not_replace_a_newer_stored_one(tmp_path):
    stored = {"44007": (utc(2026, 11, 9, 20, 0), 50.0)}
    _, recent, _ = run(tmp_path, adapters(lambda i: (utc(2026, 11, 9, 19, 0), 49.0), lambda i: None), stored)
    assert recent["44007"] == (utc(2026, 11, 9, 20, 0), 50.0)


def test_means_file_is_not_touched(tmp_path):
    region, data = setup(tmp_path)
    p = Path(data) / "means" / "t.csv"
    before = p.read_bytes()
    recent.run(region, data, tmp_path / "site", NOW, SETTINGS, adapters(lambda i: None, lambda i: None))
    assert p.read_bytes() == before


def test_recent_csv_round_trip(tmp_path):
    p = tmp_path / "r.csv"
    write_recent(p, {"b": (utc(2026, 1, 1, 5, 6), 1.25), "a": (utc(2026, 1, 1, 0, 0), 2.0)})
    assert p.read_text().splitlines()[1].startswith("a,2026-01-01T00:00:00Z")
    assert read_recent(p)["b"][0] == utc(2026, 1, 1, 5, 6)


def test_one_station_failing_in_a_source_only_warns(tmp_path):
    def coops(i):
        if i == "8447930":
            raise RuntimeError("down")
        return utc(2026, 11, 9, 20, 18), 57.2

    w, recent, _ = run(tmp_path, adapters(lambda i: None, coops))
    assert len(w) == 1 and set(recent) == {"8454000"}


def test_every_station_failing_raises_and_writes_nothing(tmp_path):
    def boom(i):
        raise RuntimeError("down")

    region, data = setup(tmp_path)
    with pytest.raises(RuntimeError, match="station fetch failed"):
        recent.run(region, data, tmp_path / "site", NOW, SETTINGS, adapters(boom, boom))
    assert not (data / "recent").exists() and not (tmp_path / "site").exists()
