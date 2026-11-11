from datetime import UTC, datetime

import pytest
from helpers import SETTINGS

from coastal_water_temp import means
from coastal_water_temp.adapters import coops
from coastal_water_temp.jobs import monthly, recent
from coastal_water_temp.means import MeanRow

REGION = """id = "t"
title = "T"
timezone = "America/New_York"
[[stations]]
id = "44007"
source = "ndbc"
name = "Buoy"
[[stations]]
id = "44005"
source = "ndbc"
name = "Retired buoy"
[[stations]]
id = "8447930"
source = "coops"
name = "Woods Hole"
"""
NOW = datetime(2027, 1, 20, 12, 0, tzinfo=UTC)


def utc(*a):
    return datetime(*a, tzinfo=UTC)


class Fake:
    """hourly data per (station, year); records every request."""

    def __init__(self, data):
        self.data, self.calls = data, []

    def __call__(self, station, year):
        self.calls.append((station, year))
        return self.data.get((station, year), [])


def setup(tmp_path, recent_stations=("44007", "8447930"), rows=()):
    region = tmp_path / "t.toml"
    region.write_text(REGION)
    data = tmp_path / "data"
    recent.write_recent(data / "recent" / "t.csv", {s: (utc(2027, 1, 20, 10), 50.0) for s in recent_stations})
    if rows:
        means.write_means(data / "means" / "t.csv", list(rows))
    return region, data


def run(tmp_path, fake_ndbc, fake_coops, **kw):
    region, data = setup(tmp_path, **kw)
    fetch = {"ndbc": fake_ndbc, "coops": fake_coops}
    return monthly.run(region, data, tmp_path / "cache", tmp_path / "site", NOW, SETTINGS, fetch), data


def h(y, m=1):
    return [(utc(y, m, 1, 0), 40.0), (utc(y, m, 1, 1), 42.0)]


def test_first_run_backfills_and_uses_last_completed_year(tmp_path):
    ndbc = Fake({("44007", 2025): h(2025), ("44007", 2026): h(2026), ("44005", 2024): h(2024)})
    cps = Fake({("8447930", 2026): h(2026)})
    (end, n), data = run(tmp_path, ndbc, cps)
    assert end == 2026 and n == 4
    rows = means.read_means(data / "means" / "t.csv")
    assert {(r.station_id, r.year) for r in rows} == {("44007", 2025), ("44007", 2026), ("44005", 2024), ("8447930", 2026)}
    assert (tmp_path / "site" / "t.html").exists()


def test_year_waits_until_both_sources_have_it(tmp_path):
    ndbc = Fake({("44007", 2025): h(2025)})  # NDBC has no 2026 file yet
    cps = Fake({("8447930", 2025): h(2025), ("8447930", 2026): h(2026)})
    (end, _), data = run(tmp_path, ndbc, cps)
    assert end == 2025
    assert all(r.year <= 2025 for r in means.read_means(data / "means" / "t.csv"))


def test_retired_station_does_not_block_a_year(tmp_path):
    ndbc = Fake({("44007", 2026): h(2026)})
    cps = Fake({("8447930", 2026): h(2026)})
    (end, _), _ = run(tmp_path, ndbc, cps, recent_stations=("44007", "8447930"))  # 44005 has no recent reading
    assert end == 2026


def test_second_run_fetches_only_years_after_the_last_stored_year(tmp_path):
    rows = [MeanRow("44007", 2025, 1, 2, 41.0), MeanRow("8447930", 2025, 1, 2, 41.0), MeanRow("44005", 2024, 1, 2, 41.0)]
    ndbc = Fake({("44007", 2026): h(2026), ("44007", 2025): h(2025)})
    cps = Fake({("8447930", 2026): h(2026), ("8447930", 2025): h(2025)})
    (end, n), data = run(tmp_path, ndbc, cps, rows=rows)
    assert end == 2026 and n == 2
    # 2026 is probed to find the end year; no request reaches back to 2025 or earlier except 44005's 2025
    assert ("44007", 2025) not in ndbc.calls and ("8447930", 2025) not in cps.calls
    assert ("44005", 2025) in ndbc.calls and ("44005", 2024) not in ndbc.calls
    assert len(means.read_means(data / "means" / "t.csv")) == 5


def test_rerun_with_unchanged_input_gives_identical_means(tmp_path):
    ndbc = Fake({("44007", 2026): h(2026)})
    cps = Fake({("8447930", 2026): h(2026)})
    _, data = run(tmp_path, ndbc, cps)
    first = (data / "means" / "t.csv").read_bytes()
    region = tmp_path / "t.toml"
    monthly.run(region, data, tmp_path / "cache", tmp_path / "site", NOW, SETTINGS, {"ndbc": ndbc, "coops": cps})
    assert (data / "means" / "t.csv").read_bytes() == first


def test_block_leaves_stored_means_unchanged(tmp_path):
    rows = [MeanRow("44007", 2025, 1, 2, 41.0)]
    region, data = setup(tmp_path, rows=rows)
    before = (data / "means" / "t.csv").read_bytes()

    def blocked(station, year):
        raise coops.BlockedError("HTTP 403")

    with pytest.raises(coops.BlockedError):
        monthly.run(region, data, tmp_path / "cache", tmp_path / "site", NOW, SETTINGS, {"ndbc": Fake({("44007", 2026): h(2026)}), "coops": blocked})
    assert (data / "means" / "t.csv").read_bytes() == before


def test_no_active_station_for_a_source_is_an_error(tmp_path):
    with pytest.raises(RuntimeError, match="recent job"):
        run(tmp_path, Fake({}), Fake({}), recent_stations=("44007",))


def test_reading_stamped_in_the_previous_year_merges_into_one_december_row(tmp_path):
    rows = [MeanRow("44007", 2025, 12, 700, 40.0), MeanRow("8447930", 2025, 12, 700, 40.0), MeanRow("44005", 2024, 12, 700, 40.0)]
    spill = [(utc(2025, 12, 31, 23), 50.0)] + h(2026)  # the 2026 file carries one reading stamped 2025-12-31 23:xx
    ndbc = Fake({("44007", 2026): spill})
    cps = Fake({("8447930", 2026): h(2026)})
    _, data = run(tmp_path, ndbc, cps, rows=rows)
    stored = [r for r in means.read_means(data / "means" / "t.csv") if (r.station_id, r.year, r.month) == ("44007", 2025, 12)]
    assert len(stored) == 1 and stored[0].n_obs == 701


def test_year_not_yet_published_by_one_source_leaves_the_end_year_unchanged(tmp_path):
    rows = [MeanRow(s, 2025, 1, 2, 41.0) for s in ("44007", "8447930")] + [MeanRow("44005", 2024, 1, 2, 41.0)]
    ndbc = Fake({})  # NDBC has no 2026 file yet
    cps = Fake({("8447930", 2026): h(2026)})
    (end, _), data = run(tmp_path, ndbc, cps, rows=rows)
    assert end == 2025
    assert all(r.year <= 2025 for r in means.read_means(data / "means" / "t.csv"))
    # only the years after the stored end year were probed
    assert {y for _, y in ndbc.calls if y != 2025} == {2026}


def test_first_run_with_no_year_that_both_sources_have_is_an_error(tmp_path):
    with pytest.raises(RuntimeError, match="no completed year"):
        run(tmp_path, Fake({("44007", 2026): h(2026)}), Fake({("8447930", 2025): h(2025)}))
