"""Build a region's static HTML page (docs/spec.md, Output). The CSV is built in the browser on click."""
from datetime import timedelta
from html import escape
from zoneinfo import ZoneInfo

from coastal_water_temp.means import aggregate

MONTHS = ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC")
COLUMNS = ("Station ID", "Station name", "Recent temperature (°F)", "Observation time", *MONTHS)
STATION_URL = {
    "ndbc": "https://www.ndbc.noaa.gov/station_page.php?station={}",
    "coops": "https://tidesandcurrents.noaa.gov/physocean.html?id={}",
}
RECENT_WINDOW = timedelta(hours=48)


def table_rows(region, means_rows, end_year, recent, now):
    """One row per configured station, in config order: a list of (text, href or None) cells.

    `recent` maps station id to (observation_time_utc, temp_f) or None. A reading older than
    48 hours is shown as blank cells, like no reading.
    """
    monthly = aggregate(means_rows, end_year)
    tz = ZoneInfo(region.timezone)
    rows = []
    for s in region.stations:
        cells = [(s.id, None), (s.name, None)]
        r = recent.get(s.id)
        if r and now - r[0] <= RECENT_WINDOW:
            cells += [(f"{r[1]:.1f}", STATION_URL[s.source].format(s.id)), (r[0].astimezone(tz).strftime("%Y-%m-%d %H:%M %Z"), None)]
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


def render_page(region, means_rows, end_year, recent, now):
    title = f"Monthly Average Temperature (°F) for {region.title}"
    head = "".join(_cell("th", c, None) for c in COLUMNS)
    body = "\n".join("<tr>" + "".join(_cell("td", t, h) for t, h in row) + "</tr>"
                     for row in table_rows(region, means_rows, end_year, recent, now))
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 16px; }}
.wrap {{ overflow-x: auto; }}
table {{ border-collapse: collapse; font-size: 14px; }}
caption {{ font-weight: bold; text-align: left; padding-bottom: 8px; }}
th, td {{ border: 1px solid #999; padding: 4px 8px; white-space: nowrap; }}
td:nth-child(n+3) {{ text-align: right; }}
td:nth-child(2) {{ text-align: left; }}
button {{ margin-top: 12px; }}
</style>
</head>
<body>
<div class="wrap">
<table id="t">
<caption>{escape(title)}</caption>
<thead><tr>{head}</tr></thead>
<tbody>
{body}
</tbody>
</table>
</div>
<button type="button" onclick="downloadCsv()">Download CSV</button>
<script>
function csvField(s) {{ return /[",\\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s; }}
function csvText() {{
  const rows = [...document.querySelectorAll('#t tr')].map(tr =>
    [...tr.children].map(c => csvField(c.textContent.trim())).join(','));
  return rows.join('\\n') + '\\n';
}}
function downloadCsv() {{
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([csvText()], {{type: 'text/csv'}}));
  a.download = '{escape(region.id)}.csv';
  a.click();
  URL.revokeObjectURL(a.href);
}}
</script>
</body>
</html>
"""
