import csv
import io
import subprocess
from datetime import datetime
from pathlib import Path

FRED_SERIES = {
    "SOFR": "SOFR_Comp",
    "SOFRINDEX": "SOFR_Index",
}

OUTPUT_DIR = Path(__file__).parent
FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}"


def fetch_fred(series_id: str) -> list[tuple[str, str]]:
    url = FRED_URL.format(series=series_id)
    result = subprocess.run(
        ["curl", "-s", "--max-time", "60", url],
        capture_output=True, text=True, check=True
    )
    rows = []
    reader = csv.reader(io.StringIO(result.stdout))
    next(reader)  # skip header
    for date_str, value in reader:
        if not value or value == ".":
            continue
        dt = datetime.strptime(date_str, "%Y-%m-%d").strftime("%d.%m.%Y")
        rows.append((dt, str(float(value) / 100)))
    return rows


def main():
    for series_id, name in FRED_SERIES.items():
        print(f"Fetching {name} ({series_id})...")
        rows = fetch_fred(series_id)
        filename = OUTPUT_DIR / f"{name}.csv"
        with open(filename, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Дата", "Фиксинг"])
            writer.writerows(rows)
        print(f"  → {filename.name} ({len(rows)} строк, {rows[0][0]} — {rows[-1][0]})")


if __name__ == "__main__":
    main()
