import gzip
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from coastal_water_temp.adapters import ndbc

FIX = Path(__file__).parent / "fixtures"
REALTIME = (FIX / "ndbc_realtime_44007.txt").read_text()
YEARLY = (FIX / "ndbc_yearly_44007_2024.txt").read_text()


def resp(status=200, text="", content=b""):
    return SimpleNamespace(status_code=status, text=text, content=content)


def utc(*a):
    return datetime(*a, tzinfo=UTC)


def test_latest_returns_newest_valid_reading_in_fahrenheit():
    t, f = ndbc.latest("44007", get=lambda url: resp(text=REALTIME))
    assert t == utc(2026, 11, 9, 20, 40)
    assert f == pytest.approx(11.5 * 9 / 5 + 32)


def test_latest_skips_mm_rows():
    head = REALTIME.splitlines()[:2]
    mm = "2026 11 09 21 00 270 1.0 2.0 0.6 MM 4.7 133 1003.7 11.6 MM 7.4 MM MM MM"
    text = "\n".join(head + [mm, REALTIME.splitlines()[2]])
    t, _ = ndbc.latest("44007", get=lambda url: resp(text=text))
    assert t == utc(2026, 11, 9, 20, 40)


def test_latest_none_when_no_valid_reading_or_no_file():
    head = "\n".join(REALTIME.splitlines()[:2])
    assert ndbc.latest("x", get=lambda url: resp(text=head)) is None
    assert ndbc.latest("44005", get=lambda url: resp(status=404)) is None


def test_latest_raises_on_failure():
    with pytest.raises(RuntimeError):
        ndbc.latest("44007", get=lambda url: resp(status=500))


def test_hourly_history_counts_hours_with_a_valid_reading():
    gz = gzip.compress(YEARLY.encode())
    out = ndbc.hourly_history("44007", 2024, get=lambda url: resp(content=gz))
    # Jan 1 00h (six readings of 5.6 C) and Jul 15 12h; the two 999.0 rows on Jan 2 are dropped.
    assert [h for h, _ in out] == [utc(2024, 1, 1, 0), utc(2024, 7, 15, 12)]
    assert out[0][1] == pytest.approx(5.6 * 9 / 5 + 32)
    assert out[1][1] == pytest.approx((17.4 * 3 + 17.3 * 3) / 6 * 9 / 5 + 32)


def test_hourly_history_missing_file_is_empty_and_failure_raises():
    assert ndbc.hourly_history("44005", 2013, get=lambda url: resp(status=404)) == []
    with pytest.raises(RuntimeError):
        ndbc.hourly_history("44007", 2024, get=lambda url: resp(status=503))


def test_old_layouts_parse(tmp_path):
    # 1979: no '#', no units line, 2-digit year, no minute column; 3-hourly rows; WTMP 06.9
    r = list(ndbc.parse((FIX / "ndbc_yearly_44005_1979.txt").read_text()))
    assert r[0] == (utc(1979, 1, 1, 0), 6.9) and len(r) == 5
    # 1999: 4-digit year, no minute column; the first row has WTMP 999.0 and is dropped
    r = list(ndbc.parse((FIX / "ndbc_yearly_44005_1999.txt").read_text()))
    assert r[0] == (utc(1999, 1, 1, 1), 5.6)
    r = list(ndbc.parse((FIX / "ndbc_yearly_44005_2004.txt").read_text()))
    assert r[0] == (utc(2004, 1, 1, 0), 6.8) and len(r) == 3


def test_hourly_history_cache_is_reused(tmp_path):
    gz = gzip.compress(YEARLY.encode())
    calls = []

    def get(url):
        calls.append(url)
        return resp(content=gz)

    a = ndbc.hourly_history("44007", 2024, get=get, cache_dir=tmp_path)
    b = ndbc.hourly_history("44007", 2024, get=get, cache_dir=tmp_path)
    assert a == b and len(calls) == 1
    ndbc.hourly_history("44005", 2013, get=lambda u: resp(status=404), cache_dir=tmp_path)
    assert not (tmp_path / "ndbc_44005_2013.txt.gz").exists()


def test_unsupported_format_raises():
    with pytest.raises(ValueError):
        list(ndbc.parse("FOO BAR\n1 2\n"))
