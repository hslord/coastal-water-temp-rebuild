from pathlib import Path

import pytest

from coastal_water_temp.config import load_region

REGION = Path(__file__).parent.parent / "config" / "regions" / "northern-atlantic-coast.toml"


def write(tmp_path, body):
    p = tmp_path / "r.toml"
    p.write_text(body, encoding="utf-8")
    return p


def test_northern_atlantic_coast_has_22_stations():
    r = load_region(REGION)
    assert r.title == "Northern Atlantic Coast"
    assert r.timezone == "America/New_York"
    assert len(r.stations) == 22


def test_order_is_ndbc_first_then_coops_ascending():
    ids = [s.id for s in load_region(REGION).stations]
    assert ids[:7] == ["44005", "44007", "44008", "44011", "44013", "44018", "44020"]
    assert ids[7:] == sorted(ids[7:]) and len(ids[7:]) == 15


def test_second_region_loads_from_config_only_and_is_sorted(tmp_path):
    p = write(tmp_path, '''
id = "dummy"
title = "Dummy Coast"
timezone = "America/Chicago"
[[stations]]
id = "9999999"
source = "coops"
name = "B"
[[stations]]
id = "44999"
source = "ndbc"
name = "A"
[[stations]]
id = "1111111"
source = "coops"
name = "C"
''')
    r = load_region(p)
    assert [s.id for s in r.stations] == ["44999", "1111111", "9999999"]


def test_unknown_source_rejected(tmp_path):
    p = write(tmp_path, 'id="x"\ntitle="X"\ntimezone="UTC"\n[[stations]]\nid="1"\nsource="foo"\nname="n"\n')
    with pytest.raises(ValueError, match="unknown source"):
        load_region(p)


def test_duplicate_id_rejected(tmp_path):
    s = '[[stations]]\nid="1"\nsource="ndbc"\nname="n"\n'
    p = write(tmp_path, 'id="x"\ntitle="X"\ntimezone="UTC"\n' + s + s)
    with pytest.raises(ValueError, match="duplicate"):
        load_region(p)
