"""
Bootstrap term OIS curves from overnight fixing series.

For each valuation date t and tenor T, compounds actual realized
overnight rates from t to t+T. Requires future overnight data,
so the last T days of the series will be missing for each tenor.
"""
import os
import numpy as np
import pandas as pd

TENORS_DAYS: dict[str, int] = {
    "1w": 7,
    "1m": 30,
    "3m": 90,
    "6m": 180,
    "1y": 365,
    "2y": 730,
    "3y": 1095,
    "5y": 1825,
    "7y": 2555,
    "10y": 3650,
}

MIN_COVERAGE = 0.85  # minimum fraction of days that must be present in window


def bootstrap_ois_curve(overnight_pct: pd.Series) -> pd.DataFrame:
    """
    Parameters
    ----------
    overnight_pct : pd.Series
        Daily overnight fixing in % per annum (e.g. 14.44 means 14.44%).
        Index must be DatetimeIndex. May have gaps (weekends/holidays).

    Returns
    -------
    pd.DataFrame
        Index = valuation dates (same as overnight_pct.index).
        Columns = tenor labels: "1w", "1m", ..., "10y".
        Values = annualized OIS rate in % per annum.
        NaN where insufficient future data is available.
    """
    # Expand to daily calendar frequency, forward-fill gaps (weekends/holidays)
    daily = overnight_pct.asfreq('D').ffill()
    daily_factor = 1.0 + daily / 100.0 / 365.0

    # Vectorized approach: compute cumulative log-product once,
    # then extract any window as exp(cumlog[end] - cumlog[start-1]).
    log_factors = np.log(daily_factor.values)
    # cumlog[i] = sum of log_factors[0..i-1] (shifted so cumlog[0]=0)
    cumlog = np.zeros(len(log_factors) + 1)
    cumlog[1:] = np.cumsum(log_factors)

    dates_arr = daily.index  # full daily DatetimeIndex after reindex
    date_to_idx = {d: i for i, d in enumerate(dates_arr)}

    result_cols: dict[str, dict] = {col: {} for col in TENORS_DAYS}

    for date in overnight_pct.index:
        if date not in date_to_idx:
            continue
        start_idx = date_to_idx[date]

        for col_name, T_days in TENORS_DAYS.items():
            # Window is [date, date + T_days - 1] inclusive → T_days calendar days
            end_idx = start_idx + T_days  # exclusive upper bound in cumlog

            if end_idx > len(log_factors):
                # Not enough future data
                result_cols[col_name][date] = np.nan
                continue

            # Count actual non-NaN days in window for coverage check
            # (NaN in log_factors means the overnight data was entirely missing there)
            window_len = end_idx - start_idx
            if window_len < T_days * MIN_COVERAGE:
                result_cols[col_name][date] = np.nan
                continue

            compound = np.exp(cumlog[end_idx] - cumlog[start_idx])
            T_years = T_days / 365.0
            annualized = (compound ** (1.0 / T_years) - 1.0) * 100.0
            result_cols[col_name][date] = annualized

    return pd.DataFrame(
        {col: pd.Series(data) for col, data in result_cols.items()}
    )


def _load_overnight_pct(filepath: str) -> pd.Series:
    """Load overnight fixing CSV (decimal fraction format) and return as % Series."""
    df = pd.read_csv(filepath)
    df.columns = df.columns.str.strip()
    df = df.rename(columns={df.columns[0]: 'date', df.columns[1]: 'fixing'})
    df['date'] = pd.to_datetime(df['date'], format='%d.%m.%Y')
    df = df.set_index('date').sort_index()
    return df['fixing'] * 100.0  # fraction → %


def build_and_save_ois_curves(fixing_dir: str, output_dir: str) -> None:
    """
    Build OIS term curves for RUB, EUR, USD, CNY from overnight fixings
    and save to output_dir as CSV files.
    """
    os.makedirs(output_dir, exist_ok=True)

    configs = [
        ("rub_ois.csv", os.path.join(fixing_dir, "RUONIA Avg..csv")),
        ("eur_ois.csv", os.path.join(fixing_dir, "ESTR_Comp.csv")),
        ("usd_ois.csv", os.path.join(fixing_dir, "SOFR_Comp.csv")),
        ("cny_ois.csv", os.path.join(fixing_dir, "RUSFARCNY_Comp.csv")),
    ]

    for out_filename, src_path in configs:
        print(f"Bootstrapping {out_filename} from {os.path.basename(src_path)}...")
        overnight_pct = _load_overnight_pct(src_path)
        ois_df = bootstrap_ois_curve(overnight_pct)
        ois_df.index.name = 'date'
        out_path = os.path.join(output_dir, out_filename)
        ois_df.to_csv(out_path)
        n_rows = len(ois_df)
        date_min = ois_df.index.min().date()
        last_10y = ois_df['10y'].dropna()
        date_10y = last_10y.index.max().date() if not last_10y.empty else 'N/A'
        print(f"  {n_rows} rows saved → {out_path}")
        print(f"  Date range: {date_min} … {date_10y} (10y tenor)")
