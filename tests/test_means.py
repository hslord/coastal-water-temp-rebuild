from datetime import UTC, datetime

import pytest

from coastal_water_temp import means
from coastal_water_temp.means import MeanRow

GAP = 15.0  # parameters passed explicitly: these tests check the algorithm, not the settings file
YEARS = 8


def h(y, m, d, hr):
    return datetime(y, m, d, hr, tzinfo=UTC)


def test_monthly_rows_groups_by_year_and_month():
    rows = means.monthly_rows("S", [(h(2020, 1, 1, 0), 10.0), (h(2020, 1, 2, 5), 20.0), (h(2020, 2, 1, 0), 40.0)])
    assert rows == [MeanRow("S", 2020, 1, 2, 15.0), MeanRow("S", 2020, 2, 1, 40.0)]


def test_aggregate_is_weighted_by_observation_count():
    rows = [MeanRow("S", 2020, 1, 2, 15.0), MeanRow("S", 2021, 1, 1, 30.0)]
    # hand computed: (15*2 + 30*1) / 3 = 20.0 (an unweighted mean of the two years would be 22.5)
    assert means.aggregate(rows, 2021, GAP, YEARS)["S"][1] == pytest.approx(20.0)


def test_aggregate_ignores_years_after_end_year_and_leaves_missing_months_out():
    rows = [MeanRow("S", 2020, 1, 2, 15.0), MeanRow("S", 2021, 1, 1, 30.0), MeanRow("S", 2021, 3, 4, 50.0)]
    out = means.aggregate(rows, 2020, GAP, YEARS)
    assert out == {"S": {1: 15.0}}


def test_csv_round_trip_is_sorted_and_identical_on_rerun(tmp_path):
    rows = [MeanRow("B", 2021, 2, 3, 12.3456), MeanRow("A", 2020, 12, 1, 1.0), MeanRow("A", 2020, 1, 2, 2.5)]
    p = tmp_path / "m" / "r.csv"
    means.write_means(p, rows)
    first = p.read_text()
    assert first.splitlines()[0] == "station_id,year,month,n_obs,mean_f"
    assert [r.split(",")[:3] for r in first.splitlines()[1:]] == [["A", "2020", "1"], ["A", "2020", "12"], ["B", "2021", "2"]]
    means.write_means(p, means.read_means(p))
    assert p.read_text() == first


def test_read_missing_file_is_empty_and_stored_years(tmp_path):
    assert means.read_means(tmp_path / "none.csv") == []
    assert means.stored_years([MeanRow("S", 2020, 1, 1, 1.0), MeanRow("S", 2020, 2, 1, 1.0)]) == {("S", 2020)}


def jan(year, mean, n=100):
    return MeanRow("S", year, 1, n, mean)


def test_merge_duplicates_combines_same_key_weighted():
    rows = [MeanRow("S", 2008, 12, 700, 40.0), MeanRow("S", 2008, 12, 1, 80.0), MeanRow("S", 2009, 12, 5, 41.0)]
    out = means.merge_duplicates(rows)
    assert len(out) == 2
    merged = next(r for r in out if r.year == 2008)
    assert merged.n_obs == 701 and merged.mean_f == pytest.approx((700 * 40 + 80) / 701)


def test_screen_excludes_months_15f_or_more_from_the_station_median():
    rows = [jan(2000 + i, 40.0 + i * 0.1) for i in range(8)] + [jan(2010, 56.0), jan(2011, 54.9)]
    # median of the ten values is about 40.5; 56.0 is 15.5 away (excluded), 54.9 is 14.4 away (kept)
    kept, excluded = means.screen(rows, 2025, GAP, YEARS)
    assert [r.year for r in excluded] == [2010]
    assert len(kept) == 9
    assert means.aggregate(rows, 2025, GAP, YEARS)["S"][1] == pytest.approx(sum(r.mean_f for r in kept) / 9)


def test_screen_gap_of_exactly_15_is_excluded():
    rows = [jan(2000 + i, 40.0) for i in range(8)] + [jan(2020, 55.0)]
    assert [r.year for r in means.screen(rows, 2025, GAP, YEARS)[1]] == [2020]


def test_screen_needs_at_least_8_years_and_ignores_years_after_end_year():
    few = [jan(2000 + i, 40.0) for i in range(6)] + [jan(2020, 90.0)]
    assert means.screen(few, 2025, GAP, YEARS)[1] == []
    many = [jan(2000 + i, 40.0) for i in range(8)] + [jan(2026, 90.0)]
    kept, excluded = means.screen(many, 2025, GAP, YEARS)
    assert excluded == [] and len(kept) == 8
