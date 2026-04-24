import calendar
from datetime import datetime
import pandas as pd
from dateutil.relativedelta import relativedelta

from instruments.enums import DayCountConvention, PaymentTiming
from compute.modelling.RiskFreeRate import get_risk_free_rate

_TIMING_DELTA = {
    PaymentTiming.MONTHLY: relativedelta(months=1),
    PaymentTiming.QUARTERLY: relativedelta(months=3),
    PaymentTiming.SEMI_ANNUALLY: relativedelta(months=6),
    PaymentTiming.ANNUALLY: relativedelta(years=1),
}


def generate_payment_schedule(
    start: datetime,
    end: datetime,
    timing: PaymentTiming,
) -> list[datetime]:
    if timing == PaymentTiming.END_OF_PERIOD:
        return [end]
    delta = _TIMING_DELTA[timing]
    dates: list[datetime] = []
    current = start + delta
    while current < end:
        dates.append(current)
        current = current + delta
    dates.append(end)
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
