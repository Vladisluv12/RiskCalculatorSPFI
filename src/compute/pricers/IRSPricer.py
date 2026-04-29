from datetime import datetime, timedelta
import pandas as pd

from instruments.IRSwap import InterestRateSwap
from instruments.enums import Direction, FloatingIndex
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
        if contract.start_date >= contract.end_date:
            return pd.DataFrame(dtype=float)

        ddt = timedelta(days=5)
        currency = contract.currency.value

        # Load OIS discount curve
        ois_data = dataProvider.get_ois_curve_data(currency, calc_start - ddt, calc_end)
        ois_data = ois_data[~ois_data.index.duplicated(keep='last')]
        full_index = pd.date_range(
            start=pd.Timestamp(calc_start - ddt),
            end=pd.Timestamp(calc_end),
            freq='D',
        )
        ois_daily = ois_data.reindex(full_index).ffill()

        if ois_daily.dropna(how='all').empty:
            return pd.DataFrame(dtype=float)

        payment_dates_fixed = swap_utils.generate_payment_schedule(
            contract.start_date, contract.end_date,
            contract.fixed_payment_timing,
            contract.fixed_offset_rule,
        )
        payment_dates_float = swap_utils.generate_payment_schedule(
            contract.start_date, contract.end_date,
            contract.floating_payment_timing,
            contract.floating_offset_rule,
        )

        # Fixed leg: PV_fixed = Σ N * r_fixed * dcf_i * DF_OIS(t, T_i)
        pv_fixed = pd.Series(0.0, index=full_index)
        prev_date = contract.start_date
        for pmt_date in payment_dates_fixed:
            pmt_ts = pd.Timestamp(pmt_date)
            future_mask = full_index < pmt_ts
            if not future_mask.any():
                prev_date = pmt_date
                continue
            dcf = swap_utils.year_fraction(prev_date, pmt_date, contract.fixed_day_count)
            tenor_i = pd.Series(
                [max(1.0 / self.days_in_year, (pmt_ts - t).days / self.days_in_year)
                 for t in full_index],
                index=full_index,
            )
            df_i = swap_utils.ois_discount_factor_series(tenor_i, ois_daily)
            coupon = pd.Series(0.0, index=full_index)
            coupon[future_mask] = (contract.notional * contract.fixed_rate * dcf * df_i)[future_mask]
            pv_fixed += coupon
            prev_date = pmt_date

        # Floating leg annuity: Σ dcf_float_i * DF_OIS(t, T_i)
        annuity = pd.Series(0.0, index=full_index)
        prev_date = contract.start_date
        for pmt_date in payment_dates_float:
            pmt_ts = pd.Timestamp(pmt_date)
            future_mask = full_index < pmt_ts
            if not future_mask.any():
                prev_date = pmt_date
                continue
            dcf = swap_utils.year_fraction(prev_date, pmt_date, contract.floating_day_count)
            tenor_i = pd.Series(
                [max(1.0 / self.days_in_year, (pmt_ts - t).days / self.days_in_year)
                 for t in full_index],
                index=full_index,
            )
            df_i = swap_utils.ois_discount_factor_series(tenor_i, ois_daily)
            contrib = pd.Series(0.0, index=full_index)
            contrib[future_mask] = (dcf * df_i)[future_mask]
            annuity += contrib
            prev_date = pmt_date

        # DF to start and end of swap (used in OIS par-float branch)
        start_ts = pd.Timestamp(contract.start_date)
        end_ts = pd.Timestamp(contract.end_date)

        tenor_end = pd.Series(
            [max(1.0 / self.days_in_year, (end_ts - t).days / self.days_in_year)
             for t in full_index],
            index=full_index,
        )
        df_end = swap_utils.ois_discount_factor_series(tenor_end, ois_daily)

        df_start = pd.Series(1.0, index=full_index)
        before_start_mask = full_index < start_ts
        if before_start_mask.any():
            tenor_start = pd.Series(
                [(start_ts - t).days / self.days_in_year for t in full_index],
                index=full_index,
            ).clip(lower=1.0 / self.days_in_year)
            df_start_pre = swap_utils.ois_discount_factor_series(tenor_start, ois_daily)
            df_start[before_start_mask] = df_start_pre[before_start_mask]

        floating_index = contract.floating_index
        spread_fraction = contract.floating_spread / 10000.0  # bp → fraction

        if floating_index.is_ois_based:
            # Par-float (exact when no basis): PV_float = N*(DF_start - DF_end) + N*spread*annuity
            pv_float = contract.notional * (df_start - df_end)
            pv_float += contract.notional * spread_fraction * annuity
        elif floating_index == FloatingIndex.OIS_FX:
            raise NotImplementedError(
                "OIS_FX requires a dedicated FX-basis pricer."
            )
        else:
            # ZC-curve-implied IBOR forward rates (EURIBOR, RUSFAR, RUB_KEY_RATE, etc.)
            float_currency = floating_index.currency
            zc_data = dataProvider.get_curve_data(float_currency, calc_start - ddt, calc_end)
            zc_data = zc_data[~zc_data.index.duplicated(keep='last')]
            zc_daily = zc_data.reindex(full_index).ffill()

            pv_float = pd.Series(0.0, index=full_index)
            prev_date = contract.start_date
            for pmt_date in payment_dates_float:
                pmt_ts = pd.Timestamp(pmt_date)
                prev_ts = pd.Timestamp(prev_date)
                future_mask = full_index < pmt_ts
                if not future_mask.any():
                    prev_date = pmt_date
                    continue
                dcf = swap_utils.year_fraction(prev_date, pmt_date, contract.floating_day_count)
                tenor_end_i = pd.Series(
                    [max(1.0 / self.days_in_year, (pmt_ts - t).days / self.days_in_year)
                     for t in full_index],
                    index=full_index,
                )
                tenor_start_i = pd.Series(
                    [max(1.0 / self.days_in_year, (prev_ts - t).days / self.days_in_year)
                     for t in full_index],
                    index=full_index,
                )
                df_ois_end = swap_utils.ois_discount_factor_series(tenor_end_i, ois_daily)
                fwd = swap_utils.ibor_forward_rate(
                    float_currency, tenor_start_i, tenor_end_i, dcf, zc_daily
                )
                coupon = pd.Series(0.0, index=full_index)
                coupon[future_mask] = (
                    contract.notional * (fwd + spread_fraction) * dcf * df_ois_end
                )[future_mask]
                pv_float += coupon
                prev_date = pmt_date

        if contract.direction == Direction.BUY:
            npv = pv_float - pv_fixed
        else:
            npv = pv_fixed - pv_float

        npv = npv[npv.index >= pd.Timestamp(calc_start)]
        return pd.DataFrame({'price': npv}).dropna()
