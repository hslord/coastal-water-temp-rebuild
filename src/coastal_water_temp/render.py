"""Build a region's static HTML page. The CSV is built in the browser on click."""
from html import escape
from importlib import resources
from pathlib import Path
from string import Template
from zoneinfo import ZoneInfo

from coastal_water_temp.means import aggregate

MONTHS = ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC")
COLUMNS = ("Station ID", "Station name", "Recent temperature (°F)", "Observation time", *MONTHS)


def table_rows(region, means_rows, end_year, recent, now, settings):
    """One row per configured station, in config order: a list of (text, href or None) cells.

    `recent` maps station id to (observation_time_utc, temp_f) or None. A reading older than
    the recent window in settings is shown as blank cells, like no reading.
    """
    monthly = aggregate(means_rows, end_year, settings.screening_max_gap_f, settings.screening_min_years)
    tz = ZoneInfo(region.timezone)
    rows = []
    for s in region.stations:
        cells = [(s.id, None), (s.name, settings.sources[s.source].station_page_url.format(id=s.id))]
        r = recent.get(s.id)
        if r and now - r[0] <= settings.recent_window:
            cells += [(f"{r[1]:.1f}", None), (r[0].astimezone(tz).strftime("%Y-%m-%d %H:%M %Z"), None)]
        else:
            cells += [("", None), ("", None)]
        by_month = monthly.get(s.id, {})
        cells += [(f"{by_month[m]:.1f}" if m in by_month else "", None) for m in range(1, 13)]
        rows.append(cells)
    return rows


def _cell(tag, text, href):
    body = escape(text)
    if href:
        body = f'<a href="{escape(href)}">{body}</a>'
    return f"<{tag}>{body}</{tag}>"


def render_page(region, means_rows, end_year, recent, now, settings):
    title = f"Monthly Average Temperature (°F) for {region.title}"
    head = "".join(_cell("th", c, None) for c in COLUMNS)
    body = "\n".join("<tr>" + "".join(_cell("td", t, h) for t, h in row) + "</tr>"
                     for row in table_rows(region, means_rows, end_year, recent, now, settings))
    template = resources.files("coastal_water_temp").joinpath("templates/page.html").read_text(encoding="utf-8")
    return Template(template).substitute(title=escape(title), head=head, body=body, region_id=escape(region.id))


def write_site(site_dir, region, html, settings):
    """Write <region id>.html, and also index.html when this is the home region in the settings."""
    out = Path(site_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{region.id}.html").write_text(html, encoding="utf-8")
    if region.id == settings.home_region:
        (out / "index.html").write_text(html, encoding="utf-8")
