from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from coastal_water_temp.adapters import coops

FIX = Path(__file__).parent / "fixtures"
LATEST = (FIX / "coops_latest_8447930.json").read_text()
HOURLY = (FIX / "coops_hourly_8447930_2024.json").read_text()
NO_DATA = (FIX / "coops_nodata.json").read_text()


def resp(text="", status=200):
    return SimpleNamespace(status_code=status, text=text)


def utc(*a):
    return datetime(*a, tzinfo=UTC)


def test_latest_returns_time_and_fahrenheit():
    assert coops.latest("8447930", get=lambda p: resp(LATEST)) == (utc(2026, 11, 9, 21, 48), 57.2)


def test_latest_none_for_no_data_answer_and_blank_value():
    assert coops.latest("8447435", get=lambda p: resp(NO_DATA)) is None
    blank = '{"metadata":{},"data":[{"t":"2026-11-09 21:48","v":"","f":"1,1,1"}]}'
    assert coops.latest("x", get=lambda p: resp(blank)) is None


def test_hourly_history_drops_blank_values():
    out = coops.hourly_history("8447930", 2024, get=lambda p: resp(HOURLY))
    assert [h for h, _ in out] == [
        utc(2024, 1, 1, 0), utc(2024, 1, 1, 1), utc(2024, 1, 1, 2), utc(2024, 3, 10, 11), utc(2024, 3, 10, 13),
    ]
    assert out[0][1] == 44.4


def test_hourly_history_requests_the_full_year_hourly():
    seen = {}
    coops.hourly_history("8447930", 2024, get=lambda p: seen.update(p) or resp(HOURLY))
    assert seen == {"station": "8447930", "interval": "h", "begin_date": "20240101", "end_date": "20241231"}


def test_hourly_history_no_data_year_is_empty():
    assert coops.hourly_history("8447930", 1994, get=lambda p: resp(NO_DATA)) == []


@pytest.mark.parametrize("status", [403, 429])
def test_blocked_stops_with_blocked_error(status):
    with pytest.raises(coops.BlockedError):
        coops.latest("8447930", get=lambda p: resp("{}", status))


def test_other_failures_raise():
    with pytest.raises(RuntimeError):
        coops.latest("8447930", get=lambda p: resp("", 500))
    with pytest.raises(RuntimeError):
        coops.latest("8447930", get=lambda p: resp('{"error":{"message":"Something else"}}'))


def test_cache_is_reused_so_a_rerun_makes_no_request(tmp_path):
    calls = []

    def get(p):
        calls.append(p)
        return resp(HOURLY)

    a = coops.hourly_history("8447930", 2024, get=get, cache_dir=tmp_path)
    b = coops.hourly_history("8447930", 2024, get=get, cache_dir=tmp_path)
    assert a == b and len(calls) == 1


def test_no_data_answer_is_not_cached(tmp_path):
    coops.hourly_history("8447930", 1994, get=lambda p: resp(NO_DATA), cache_dir=tmp_path)
    assert list(tmp_path.iterdir()) == []
