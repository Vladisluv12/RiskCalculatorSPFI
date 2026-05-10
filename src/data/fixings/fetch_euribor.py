import csv
import json
import time
import urllib.request
from datetime import datetime, date
from pathlib import Path

BASE_URL = "https://www.euribor-rates.eu/umbraco/api/chartpageapi/highchartsdata"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://www.euribor-rates.eu/en/euribor-charts/",
    "sec-fetch-site": "same-origin",
    "sec-fetch-mode": "cors",
    "sec-fetch-dest": "empty",
}

SERIES = {
    1: "Euribor EUR 1m",
    2: "Euribor EUR 3m",
    3: "Euribor EUR 6m",
    4: "Euribor EUR 12m",
    5: "Euribor EUR 1w",
}

OUTPUT_DIR = Path(__file__).parent


def ts_ms(d: date) -> int:
    return int(datetime(d.year, d.month, d.day).timestamp() * 1000)


def fetch_year(series_id: int, year: int) -> list[tuple[str, float]]:
    min_ts = ts_ms(date(year, 1, 1))
    max_ts = ts_ms(date(year, 12, 31))
    url = f"{BASE_URL}?series={series_id}&minTicks={min_ts}&maxTicks={max_ts}"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read())
    points = data[0]["Data"]
    return [
        (datetime.fromtimestamp(p[0] / 1000).strftime("%d.%m.%Y"), p[1])
        for p in points
    ]


def fetch_all():
    start_year = 1999
    end_year = date.today().year

    for sid, name in SERIES.items():
        print(f"\nFetching {name} (id={sid})...")
        all_rows: list[tuple[str, float]] = []

        for year in range(start_year, end_year + 1):
            try:
                rows = fetch_year(sid, year)
                all_rows.extend(rows)
                print(f"  {year}: {len(rows)} points")
                time.sleep(0.3)
            except Exception as e:
                print(f"  {year}: ERROR - {e}")

        filename = OUTPUT_DIR / f"{name.replace(' ', '_')}.csv"
        with open(filename, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Дата", "Фиксинг"])
            writer.writerows(all_rows)

        print(f"  → {filename.name} ({len(all_rows)} total rows)")


if __name__ == "__main__":
    fetch_all()
