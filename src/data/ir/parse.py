import argparse
from pathlib import Path
import pandas as pd


def fill_missing_dates(path: str | Path = None, date_col: str = None, value_col: str = None, freq: str = "D", inplace: bool = False, date_format: str = None):
	path = Path(path) if path is not None else Path(__file__).parent / "usd_key_rate.csv"
	df = pd.read_csv(path)

	if date_col is None:
		date_col = df.columns[0]
	if value_col is None:
		nums = df.select_dtypes(include=["number"]).columns.tolist()
		if nums:
			value_col = nums[0]
		elif len(df.columns) > 1:
			value_col = df.columns[1]
		else:
			raise ValueError("Cannot determine value column to fill")

	df[date_col] = pd.to_datetime(df[date_col], format=date_format, errors="coerce")
	df = df.sort_values(date_col).dropna(subset=[date_col])
	df = df.set_index(date_col)

	full_index = pd.date_range(start=df.index.min(), end=df.index.max(), freq=freq)
	df = df.reindex(full_index)

	df[value_col] = df[value_col].ffill()

	df.index.name = date_col
	out_path = path if inplace else path.with_name(path.stem + "_filled" + path.suffix)
	df.reset_index().to_csv(out_path, index=False)
	return out_path


def _cli():
	parser = argparse.ArgumentParser(description="Fill missing dates by previous value in CSV")
	parser.add_argument("--path", "-p", help="CSV file path (default: rub_key_rate.csv in this folder)")
	parser.add_argument("--date-col", help="Name of the date column (default: first column)")
	parser.add_argument("--value-col", help="Name of the value column to fill (default: numeric or second)")
	parser.add_argument("--freq", default="D", help="Date range frequency (default: D - daily). Use B for business days")
	parser.add_argument("--inplace", action="store_true", help="Overwrite the original file")
	parser.add_argument("--date-format", help="Optional date format for parsing, e.g. %%Y-%%m-%%d")
	args = parser.parse_args()
	out = fill_missing_dates(path=args.path, date_col=args.date_col, value_col=args.value_col, freq=args.freq, inplace=args.inplace, date_format=args.date_format)
	print(f"Output written to: {out}")


if __name__ == "__main__":
	_cli()