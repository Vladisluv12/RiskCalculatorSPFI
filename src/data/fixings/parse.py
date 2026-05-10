import csv
import os
from collections import defaultdict

INPUT_FILE = os.path.join(os.path.dirname(__file__), "fixing.csv")
OUTPUT_DIR = os.path.dirname(__file__)


def safe_filename(name: str) -> str:
    return "".join(c if c.isalnum() or c in " _-." else "_" for c in name).strip()


def parse():
    data: dict[str, list[tuple[str, str]]] = defaultdict(list)

    with open(INPUT_FILE, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            index = row["Индекс"]
            data[index].append((row["Дата"], row["Фиксинг"]))

    for index, rows in data.items():
        filename = safe_filename(index) + ".csv"
        output_path = os.path.join(OUTPUT_DIR, filename)
        with open(output_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Дата", "Фиксинг"])
            writer.writerows(rows)
        print(f"Записан: {filename} ({len(rows)} строк)")


if __name__ == "__main__":
    parse()
