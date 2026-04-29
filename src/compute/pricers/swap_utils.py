import calendar
from datetime import datetime
import numpy as np
import pandas as pd
from dateutil.relativedelta import relativedelta

from instruments.enums import DayCountConvention, FloatingIndex, OffsetRule, PaymentTiming
from instruments.IRSwap import InterestRateSwap
from compute.modelling.RiskFreeRate import get_ois_rate


_TIMING_DELTA = {
    PaymentTiming.MONTHLY: relativedelta(months=1),
    PaymentTiming.QUARTERLY: relativedelta(months=3),
    PaymentTiming.SEMI_ANNUALLY: relativedelta(months=6),
    PaymentTiming.ANNUALLY: relativedelta(years=1),
}


_OFFSET_DAYS: dict[OffsetRule, int] = {
    OffsetRule.ONE_DAY: 1,
    OffsetRule.TWO_DAYS: 2,
}


def _apply_offset(d: datetime, rule: OffsetRule) -> datetime:
    """
    Apply a business-day offset to a date.

    Convention for non-business-day inputs: the date is first rolled to the
    following Monday (roll='following'), which counts as the first offset step.
    The remaining (n-1) business days are then added. So Saturday + ONE_DAY = Monday,
    Saturday + TWO_DAYS = Tuesday.
    """
    if rule == OffsetRule.NONE:
        return d
    n = _OFFSET_DAYS[rule]
    dt64 = np.datetime64(d.date(), 'D')
    if np.is_busday(dt64):
        bd = np.busday_offset(dt64, n)
    else:
        bd = np.busday_offset(dt64, 0, roll='following')
        if n > 1:
            bd = np.busday_offset(bd, n - 1)
    ts = pd.Timestamp(bd)
    return datetime(ts.year, ts.month, ts.day)


def generate_payment_schedule(
    start: datetime,
    end: datetime,
    timing: PaymentTiming,
    offset_rule: OffsetRule = OffsetRule.NONE,
) -> list[datetime]:
    if timing == PaymentTiming.END_OF_PERIOD:
        return [_apply_offset(end, offset_rule)]
    delta = _TIMING_DELTA[timing]
    dates: list[datetime] = []
    current = start + delta
    while current < end:
        dates.append(_apply_offset(current, offset_rule))
        current = current + delta
    dates.append(_apply_offset(end, offset_rule))
    return dates


def year_fraction(
    start: datetime,
    end: datetime,
    convention: DayCountConvention,
) -> float:
    days = (end - start).days
    if convention == DayCountConvention.ACT_360:
        return days / 360.0
    elif convention == DayCountConvention.ACT_365:
        return days / 365.0
    elif convention == DayCountConvention.ACT_ACT:
        if start.year == end.year:
            diy = 366 if calendar.isleap(start.year) else 365
            return days / diy
        result = 0.0
        cur = start
        while cur.year < end.year:
            next_year = datetime(cur.year + 1, 1, 1)
            diy = 366 if calendar.isleap(cur.year) else 365
            result += (next_year - cur).days / diy
            cur = next_year
        diy = 366 if calendar.isleap(end.year) else 365
        result += (end - cur).days / diy
        return result
    elif convention == DayCountConvention._30E_360:
        y1, m1, d1 = start.year, start.month, start.day
        y2, m2, d2 = end.year, end.month, end.day
        d1 = min(d1, 30)
        d2 = min(d2, 30)
        return (360 * (y2 - y1) + 30 * (m2 - m1) + (d2 - d1)) / 360.0
    else:
        raise ValueError(f'Неизвестная конвенция подсчёта дней: {convention}')



def ois_discount_factor_series(
    tenor_series: pd.Series,
    ois_curve_daily: pd.DataFrame,
) -> pd.Series:
    """
    OIS discount factor for each (date, tenor).

    Parameters
    ----------
    tenor_series : pd.Series
        Index = dates, values = tenor in years.
    ois_curve_daily : pd.DataFrame
        OIS curve (daily reindex already done by caller).
        Columns = ["1w","1m",...,"10y"], values = % per annum.

    Returns
    -------
    pd.Series : DF = 1 / (1 + r)^T, values in (0, 1].
    """
    r = get_ois_rate(tenor_series, ois_curve_daily)  # fraction
    return (1.0 / (1.0 + r) ** tenor_series).rename('ois_df')


def ibor_forward_rate_with_basis(
    floating_index: FloatingIndex,
    tenor_start: pd.Series,
    tenor_end: pd.Series,
    dcf: float,
    ois_daily: pd.DataFrame,
    fixing_daily: pd.Series,
    basis_window: int = 20,
) -> pd.Series:
    """
    IBOR forward rate = OIS forward(T1,T2) + basis,
    where basis = rolling mean of (ibor_fixing - ois_spot_at_ibor_tenor).

    The rolling mean over `basis_window` days smooths out day-to-day noise
    in the fixing and gives a more stable estimate of the credit spread
    without requiring FRA or basis-swap market data.
    """
    if dcf <= 0:
        raise ValueError(f"dcf must be positive; got {dcf!r}")

    # OIS forward for period [T1, T2]
    df1 = ois_discount_factor_series(tenor_start, ois_daily)
    df2 = ois_discount_factor_series(tenor_end,   ois_daily)
    ois_fwd = (df1 / df2 - 1.0) / dcf

    # OIS spot at the IBOR index tenor (e.g. 90/365 for 3M)
    ibor_tenor_yrs = floating_index.ibor_ois_tenor_years
    tenor_ibor = pd.Series(ibor_tenor_yrs, index=tenor_start.index)
    ois_spot = get_ois_rate(tenor_ibor, ois_daily)  # already fraction

    # Rolling-mean basis: reduces fixing noise without requiring FRA data.
    # min_periods=1 avoids NaN at the start of short series.
    raw_basis = fixing_daily.reindex(tenor_start.index).ffill() - ois_spot
    basis = raw_basis.rolling(window=basis_window, min_periods=1).mean()

    return ois_fwd + basis


def irs_dv01(
    contract: InterestRateSwap,
    ois_curve_row: pd.Series,
    calc_date: datetime,
) -> float:
    """
    DV01 = N × Σ_i [dcf_i × DF_OIS(calc_date, T_i)] × 0.0001

    Sums over remaining fixed-leg payment dates only (those strictly after calc_date).
    Returns 0.0 if no future payments remain.

    Parameters
    ----------
    contract      : InterestRateSwap — fixed-leg fields used: start_date, end_date,
                    fixed_payment_timing, fixed_offset_rule, fixed_day_count, notional.
    ois_curve_row : pd.Series — one date's OIS curve; index = tenor labels
                    ('1w','1m',...,'10y'), values = % per annum.
    calc_date     : valuation date.
    """
    calc_ts = pd.Timestamp(calc_date)
    payment_dates = generate_payment_schedule(
        contract.start_date, contract.end_date,
        contract.fixed_payment_timing, contract.fixed_offset_rule,
    )

    ois_df = pd.DataFrame(
        [ois_curve_row.values],
        columns=ois_curve_row.index,
        index=[calc_ts],
    )

    days_in_year = 365.0
    annuity = 0.0
    prev_date = contract.start_date

    for pmt_date in payment_dates:
        pmt_ts = pd.Timestamp(pmt_date)
        if pmt_ts <= calc_ts:
            prev_date = pmt_date
            continue
        dcf = year_fraction(prev_date, pmt_date, contract.fixed_day_count)
        tenor = max(1.0 / days_in_year, (pmt_ts - calc_ts).days / days_in_year)
        r = get_ois_rate(pd.Series([tenor], index=[calc_ts]), ois_df)
        df_i = 1.0 / (1.0 + float(r.iloc[0])) ** tenor
        annuity += dcf * df_i
        prev_date = pmt_date

    return float(contract.notional) * annuity * 0.0001
