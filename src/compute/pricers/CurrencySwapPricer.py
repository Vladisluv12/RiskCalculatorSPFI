import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from instruments.BaseInstrument import Direction
from instruments.FXSwap import CurrencySwapContract
from utils.DataProvider import DataProvider
from compute.modelling.RiskFreeRate import get_risk_free_rate

class CurrencySwapPricer:
    """Оценщик для валютных свопов на основе предоставленных dataclasses."""
    
    def __init__(self, days_in_year: int = 365):
        self.days_in_year = days_in_year

    def calculate_pv(
        self, 
        contract: CurrencySwapContract, 
        dataProvider : DataProvider,
        calc_start: datetime, 
        calc_end: datetime,
    ) -> pd.DataFrame:
        """
                Реализует формулу PV свопа с учетом двух ног:

                PV_swap =
                        (N * S_t / (1 + r_base)^t_near - N * S_fixed_near / (1 + r_quote)^t_near)
                    + (N * K   / (1 + r_quote)^t_far  - N * S_t          / (1 + r_base)^t_far)

        где:
                N             - номинал в базовой валюте,
                S_fixed_near  - фиксированный курс near leg (spot_rate в контракте),
                S_t           - рыночный спот на дату t,
                K             - фиксированный курс far leg (reverse_rate или spot+swap_points),
                t_near/t_far  - время до near/far leg соответственно.
        """
        ddt = timedelta(days=5)
        base_curve_data = dataProvider.get_curve_data(contract.base_currency, calc_start - ddt, calc_end)
        quote_curve_data = dataProvider.get_curve_data(contract.quote_currency, calc_start - ddt, calc_end)
        currency_data = dataProvider.get_currency_data(contract.currency_pair.value.replace('/', ''), calc_start - ddt, calc_end)

        # Дедупликация индексов до reindex — pandas не позволяет reindex при дублях дат
        base_curve_data = base_curve_data[~base_curve_data.index.duplicated(keep='last')]
        quote_curve_data = quote_curve_data[~quote_curve_data.index.duplicated(keep='last')]
        currency_data = currency_data[~currency_data.index.duplicated(keep='last')]

        mask = (currency_data.index >= pd.to_datetime(calc_start - ddt)) & (currency_data.index <= pd.to_datetime(calc_end))
        period_data = currency_data.loc[mask].copy()

        if period_data.empty:
            return pd.DataFrame(dtype=float)

        full_index = pd.date_range(start=pd.to_datetime(calc_start - ddt), end=pd.to_datetime(calc_end), freq='D')

        s0 = period_data['curs'].reindex(full_index, method='nearest').ffill().bfill()

        # Скользящие теноры: для каждой даты оценки — оставшееся время до near/far leg
        near_dt = pd.Timestamp(contract.start_date)
        far_dt = pd.Timestamp(contract.end_date)
        near_tenor_series = pd.Series(
            [max(1 / self.days_in_year, (near_dt - d).days / self.days_in_year) for d in full_index],
            index=full_index,
        )
        far_tenor_series = pd.Series(
            [max(1 / self.days_in_year, (far_dt - d).days / self.days_in_year) for d in full_index],
            index=full_index,
        )

        # Кривые переиндексируем на ежедневную сетку
        base_curve_daily = base_curve_data.reindex(full_index).ffill()
        quote_curve_daily = quote_curve_data.reindex(full_index).ffill()

        r_quote_near_df = get_risk_free_rate(contract.quote_currency, near_tenor_series, quote_curve_daily)
        r_base_near_df = get_risk_free_rate(contract.base_currency, near_tenor_series, base_curve_daily)
        r_quote_far_df = get_risk_free_rate(contract.quote_currency, far_tenor_series, quote_curve_daily)
        r_base_far_df = get_risk_free_rate(contract.base_currency, far_tenor_series, base_curve_daily)

        if r_quote_near_df.empty or r_base_near_df.empty or r_quote_far_df.empty or r_base_far_df.empty:
            return pd.DataFrame(dtype=float)

        calc_df = pd.DataFrame(index=full_index)
        calc_df['s0'] = s0
        calc_df['r_quote_near'] = r_quote_near_df['rf_rate']
        calc_df['r_base_near'] = r_base_near_df['rf_rate']
        calc_df['r_quote_far'] = r_quote_far_df['rf_rate']
        calc_df['r_base_far'] = r_base_far_df['rf_rate']
        calc_df['t_near'] = near_tenor_series
        calc_df['t_far'] = far_tenor_series

        calc_df = calc_df[calc_df.index >= pd.to_datetime(calc_start)]
        if calc_df.empty:
            return pd.DataFrame(dtype=float)

        s0_final = calc_df['s0'].to_numpy(dtype=float)
        r_quote_near = calc_df['r_quote_near'].to_numpy(dtype=float)
        r_base_near = calc_df['r_base_near'].to_numpy(dtype=float)
        r_quote_far = calc_df['r_quote_far'].to_numpy(dtype=float)
        r_base_far = calc_df['r_base_far'].to_numpy(dtype=float)

        t_near = calc_df['t_near'].to_numpy(dtype=float)
        t_far = calc_df['t_far'].to_numpy(dtype=float)

        nominal_base = float(contract.notional)
        s_fixed_near = float(contract.spot_rate)
        k_rate = float(contract.forward_rate)

        near_leg = (nominal_base * s0_final) / np.power(1.0 + r_base_near, t_near)
        near_leg -= (nominal_base * s_fixed_near) / np.power(1.0 + r_quote_near, t_near)

        far_leg = (nominal_base * k_rate) / np.power(1.0 + r_quote_far, t_far)
        far_leg -= (nominal_base * s0_final) / np.power(1.0 + r_base_far, t_far)

        if contract.direction == Direction.BUY:
            pv_values = near_leg + far_leg
        else:
            near_leg_sell = -(nominal_base * s0_final) / np.power(1.0 + r_base_near, t_near)
            near_leg_sell += (nominal_base * s_fixed_near) / np.power(1.0 + r_quote_near, t_near)

            far_leg_sell = -(nominal_base * k_rate) / np.power(1.0 + r_quote_far, t_far)
            far_leg_sell += (nominal_base * s0_final) / np.power(1.0 + r_base_far, t_far)

            pv_values = near_leg_sell + far_leg_sell

        pv_series = pd.Series(pv_values, index=calc_df.index, name=contract.instrument_id)
        return pd.DataFrame({"price": pv_series}).dropna()
    

# d_start = datetime(2025, 2, 1)
# d_end = datetime(2025, 2, 28)

# pricer = ForwardPricer()
# dtPr = DataProvider(input_dir="data")
# forward = CurrencyForwardContract(
#     instrument_id="FWD1",
#     notional=100000,
#     direction=Direction.BUY,
#     start_date=d_start,
#     end_date=d_end,
#     currency_pair=CurrencyPair.CNY_RUB,
#     base_currency="CNY",
#     quote_currency="RUB",
#     forward_rate=12.0,
# )
# pv_history = pricer.calculate_pv(forward, dtPr, d_start, d_end)
# print(pv_history.round(2).head(10))