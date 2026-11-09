from datetime import UTC, datetime

import pytest

from coastal_water_temp import means
from coastal_water_temp.means import MeanRow


def h(y, m, d, hr):
    return datetime(y, m, d, hr, tzinfo=UTC)


def test_monthly_rows_groups_by_year_and_month():
    rows = means.monthly_rows("S", [(h(2020, 1, 1, 0), 10.0), (h(2020, 1, 2, 5), 20.0), (h(2020, 2, 1, 0), 40.0)])
    assert rows == [MeanRow("S", 2020, 1, 2, 15.0), MeanRow("S", 2020, 2, 1, 40.0)]


def test_aggregate_is_weighted_by_observation_count():
    rows = [MeanRow("S", 2020, 1, 2, 15.0), MeanRow("S", 2021, 1, 1, 30.0)]
    # hand computed: (15*2 + 30*1) / 3 = 20.0 (an unweighted mean of the two years would be 22.5)
    assert means.aggregate(rows, 2021)["S"][1] == pytest.approx(20.0)


def test_aggregate_ignores_years_after_end_year_and_leaves_missing_months_out():
    rows = [MeanRow("S", 2020, 1, 2, 15.0), MeanRow("S", 2021, 1, 1, 30.0), MeanRow("S", 2021, 3, 4, 50.0)]
    out = means.aggregate(rows, 2020)
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
