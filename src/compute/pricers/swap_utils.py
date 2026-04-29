import calendar
from datetime import datetime
import numpy as np
import pandas as pd
from dateutil.relativedelta import relativedelta

from instruments.enums import DayCountConvention, FloatingIndex, OffsetRule, PaymentTiming
from compute.modelling.RiskFreeRate import get_risk_free_rate, get_ois_rate


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


def discount_factor_series(
    currency: str,
    tenor_series: pd.Series,
    curve_daily: pd.DataFrame,
) -> pd.Series:
    r_df = get_risk_free_rate(currency, tenor_series, curve_daily)
    r = r_df['rf_rate']
    return (1.0 / (1.0 + r) ** tenor_series).rename('df')


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


def ibor_forward_rate(
    currency: str,
    tenor_start: pd.Series,
    tenor_end: pd.Series,
    dcf: float,
    zc_curve_daily: pd.DataFrame,
) -> pd.Series:
    """
    Simply-compounded IBOR forward rate L(t; T1, T2) implied from ZC curve.
    L = [P(t,T1)/P(t,T2) - 1] / dcf,  P(t,T) = 1/(1+z(T))^T
    where z(T) is the annually-compounded ZC rate from get_risk_free_rate.
    """
    r1 = get_risk_free_rate(currency, tenor_start, zc_curve_daily)['rf_rate']
    r2 = get_risk_free_rate(currency, tenor_end,   zc_curve_daily)['rf_rate']
    p1 = 1.0 / (1.0 + r1) ** tenor_start
    p2 = 1.0 / (1.0 + r2) ** tenor_end
    if dcf <= 0:
        raise ValueError(f"dcf must be positive; got {dcf!r} — indicates a schedule generation bug")
    return (p1 / p2 - 1.0) / dcf


def ibor_forward_rate_with_basis(
    floating_index: FloatingIndex,
    tenor_start: pd.Series,
    tenor_end: pd.Series,
    dcf: float,
    ois_daily: pd.DataFrame,
    fixing_daily: pd.Series,
) -> pd.Series:
    """
    IBOR forward rate = OIS forward(T1,T2) + basis,
    where basis = ibor_fixing - ois_spot_at_ibor_tenor.

    Preserves the actual IBOR market level (fixing) while using OIS
    for the term-structure shape. Better than flat-fixing (ignores term
    structure) or ZC-proxy (wrong credit level).
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

    # basis = current fixing − OIS spot (both fraction)
    basis = fixing_daily.reindex(tenor_start.index).ffill() - ois_spot

    return ois_fwd + basis
