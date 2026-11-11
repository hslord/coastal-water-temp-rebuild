from datetime import UTC, datetime
from html.parser import HTMLParser

from helpers import SETTINGS

from coastal_water_temp.means import MeanRow
from coastal_water_temp.regions import Region, Station
from coastal_water_temp.render import COLUMNS, render_page, table_rows

REGION = Region("test-coast", "Test Coast", "America/New_York", (
    Station("44007", "ndbc", "BUOY & Co"),
    Station("8447930", "coops", "Woods Hole"),
    Station("8454049", "coops", "Quonset Point"),
))
MEANS = [MeanRow("44007", 2020, 1, 2, 15.0), MeanRow("44007", 2021, 1, 1, 30.0), MeanRow("8447930", 2020, 7, 1, 70.04)]
NOW = datetime(2026, 1, 15, 18, 0, tzinfo=UTC)


class Cells(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows, self.links, self.caption, self._in = [], [], "", None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.rows.append([])
        if tag in ("td", "th", "caption"):
            self._in = tag
            if tag != "caption":
                self.rows[-1].append("")
        if tag == "a" and self._in == "td":  # table cells only, not the footer
            self.links.append(dict(attrs)["href"])

    def handle_endtag(self, tag):
        if tag in ("td", "th", "caption"):
            self._in = None

    def handle_data(self, data):
        if self._in == "caption":
            self.caption += data
        elif self._in:
            self.rows[-1][-1] += data


def page(recent, now=NOW):
    p = Cells()
    p.feed(render_page(REGION, MEANS, 2021, recent, now, SETTINGS))
    return p


def test_title_columns_and_one_row_per_station_in_config_order():
    p = page({})
    assert p.caption == "Monthly Average Temperature (°F) for Test Coast"
    assert p.rows[0] == list(COLUMNS)
    assert [r[0] for r in p.rows[1:]] == ["44007", "8447930", "8454049"]


def test_station_names_link_to_station_pages_and_temperatures_are_plain_text():
    recent = {"44007": (datetime(2026, 1, 15, 17, 18, tzinfo=UTC), 41.234), "8447930": (datetime(2026, 1, 15, 17, 0, tzinfo=UTC), 40.0)}
    p = page(recent)
    assert p.links == ["https://www.ndbc.noaa.gov/station_page.php?station=44007",
                       "https://tidesandcurrents.noaa.gov/physocean.html?id=8447930",
                       "https://tidesandcurrents.noaa.gov/physocean.html?id=8454049"]
    assert p.rows[1][1] == "BUOY & Co"
    assert p.rows[1][2:4] == ["41.2", "2026-01-15 12:18 EST"]


def test_no_reading_or_reading_older_than_48_hours_is_blank_and_keeps_means():
    old = datetime(2026, 1, 13, 17, 59, tzinfo=UTC)
    p = page({"44007": (old, 41.0)})
    assert p.rows[1][2:4] == ["", ""] and p.rows[3][2:4] == ["", ""]
    assert len(p.links) == 3  # names still link when there is no recent reading
    assert p.rows[1][4] == "20.0"  # January weighted mean, still shown


def test_reading_exactly_48_hours_old_is_shown():
    t = datetime(2026, 1, 13, 18, 0, tzinfo=UTC)
    assert page({"44007": (t, 41.0)}).rows[1][2] == "41.0"


def test_time_uses_edt_in_summer():
    now = datetime(2026, 7, 15, 18, 0, tzinfo=UTC)
    t = datetime(2026, 7, 15, 17, 18, tzinfo=UTC)
    assert page({"44007": (t, 60.0)}, now).rows[1][3] == "2026-07-15 13:18 EDT"


def test_monthly_values_and_blank_months():
    rows = table_rows(REGION, MEANS, 2021, {}, NOW, SETTINGS)
    assert [c[0] for c in rows[0][4:]] == ["20.0"] + [""] * 11
    assert rows[1][4 + 6][0] == "70.0"
    assert all(c[0] == "" for c in rows[2][4:])


def test_page_has_csv_download_button():
    html = render_page(REGION, MEANS, 2021, {}, NOW, SETTINGS)
    assert "downloadCsv()" in html and "test-coast.csv" in html


def test_home_region_page_is_also_written_as_index(tmp_path):
    from dataclasses import replace

    from coastal_water_temp.render import write_site

    html = render_page(REGION, MEANS, 2021, {}, NOW, SETTINGS)
    write_site(tmp_path / "a", REGION, html, replace(SETTINGS, home_region="test-coast"))
    assert (tmp_path / "a" / "index.html").read_text() == html == (tmp_path / "a" / "test-coast.html").read_text()
    write_site(tmp_path / "b", REGION, html, replace(SETTINGS, home_region="other"))
    assert not (tmp_path / "b" / "index.html").exists() and (tmp_path / "b" / "test-coast.html").exists()
