from datetime import datetime, timedelta
import pandas as pd

from instruments.IRSwap import InterestRateSwap
from instruments.enums import Direction
from utils.DataProvider import DataProvider
from compute.pricers import swap_utils


class IRSPricer:
    def __init__(self, days_in_year: int = 365):
        self.days_in_year = days_in_year

    def calculate_pv(
        self,
        contract: InterestRateSwap,
        dataProvider: DataProvider,
        calc_start: datetime,
        calc_end: datetime,
    ) -> pd.DataFrame:
        ddt = timedelta(days=5)
        currency = contract.currency.value

        curve_data = dataProvider.get_curve_data(currency, calc_start - ddt, calc_end)
        curve_data = curve_data[~curve_data.index.duplicated(keep='last')]

        full_index = pd.date_range(
            start=pd.Timestamp(calc_start - ddt),
            end=pd.Timestamp(calc_end),
            freq='D',
        )
        curve_daily = curve_data.reindex(full_index).ffill()

        if curve_daily.dropna(how='all').empty:
            return pd.DataFrame(dtype=float)

        payment_dates = swap_utils.generate_payment_schedule(
            contract.start_date, contract.end_date, contract.fixed_payment_timing
        )

        # Fixed leg: PV_fixed = sum over T_i of notional * fixed_rate * dcf_i * DF(t, T_i)
        pv_fixed = pd.Series(0.0, index=full_index)
        prev_date = contract.start_date
        for pmt_date in payment_dates:
            pmt_ts = pd.Timestamp(pmt_date)
            dcf = swap_utils.year_fraction(prev_date, pmt_date, contract.fixed_day_count)
            tenor_i = pd.Series(
                [max(1.0 / self.days_in_year, (pmt_ts - t).days / self.days_in_year)
                 for t in full_index],
                index=full_index,
            )
            df_i = swap_utils.discount_factor_series(currency, tenor_i, curve_daily)
            pv_fixed += contract.notional * contract.fixed_rate * dcf * df_i
            prev_date = pmt_date

        # Floating leg (par-float): PV_float = notional * (DF(t, start) - DF(t, end))
        # Note: floating_spread, floating_index, floating_day_count,
        # floating_payment_timing are NOT used — par-float ignores actual
        # floating cashflows and approximates the full floating leg NPV
        # using only discount factors.
        start_ts = pd.Timestamp(contract.start_date)
        end_ts = pd.Timestamp(contract.end_date)

        tenor_end = pd.Series(
            [max(1.0 / self.days_in_year, (end_ts - t).days / self.days_in_year)
             for t in full_index],
            index=full_index,
        )
        df_end = swap_utils.discount_factor_series(currency, tenor_end, curve_daily)

        # DF to start: 1.0 for t >= start_date, computed for t < start_date
        df_start = pd.Series(1.0, index=full_index)
        before_start_mask = full_index < start_ts
        if before_start_mask.any():
            tenor_start = pd.Series(
                [(start_ts - t).days / self.days_in_year for t in full_index],
                index=full_index,
            ).clip(lower=1.0 / self.days_in_year)
            df_start_pre = swap_utils.discount_factor_series(currency, tenor_start, curve_daily)
            df_start[before_start_mask] = df_start_pre[before_start_mask]

        pv_float = contract.notional * (df_start - df_end)

        if contract.direction == Direction.BUY:
            npv = pv_float - pv_fixed
        else:
            npv = pv_fixed - pv_float

        npv = npv[npv.index >= pd.Timestamp(calc_start)]
        return pd.DataFrame({'price': npv}).dropna()
