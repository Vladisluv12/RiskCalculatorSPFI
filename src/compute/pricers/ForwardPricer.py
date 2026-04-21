import pandas as pd
from datetime import datetime, timedelta

from instruments.BaseInstrument import CurrencyPair, Direction
from instruments.FXForward import CurrencyForwardContract
from utils.DataProvider import DataProvider
from compute.modelling.RiskFreeRate import get_risk_free_rate

class ForwardPricer:
    """Оценщик для валютных форвардов на основе предоставленных dataclasses"""
    
    def __init__(self, days_in_year: int = 365):
        self.days_in_year = days_in_year

    def calculate_pv(
        self, 
        contract: CurrencyForwardContract, 
        dataProvider : DataProvider,
        calc_start: datetime, 
        calc_end: datetime,
    ) -> pd.DataFrame:
        """
        Реализует формулу PV с учетом направления сделки (Buy/Sell).
        
        Формула адаптирована под параметры контракта:
        PV = [Notional * Forward_Rate / (1 + r_rub)^t] - [Notional * Spot / (1 + r_foreign)^t]
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

        s0 = period_data['curs'].reindex(full_index).ffill()

        # Скользящий тенор: для каждой даты оценки t — оставшееся время до погашения
        end_dt = pd.Timestamp(contract.end_date)
        tenor_series = pd.Series(
            [max(1 / self.days_in_year, (end_dt - d).days / self.days_in_year) for d in full_index],
            index=full_index,
        )

        # Кривые переиндексируем на ежедневную сетку, затем передаём скользящий тенор
        base_curve_daily = base_curve_data.reindex(full_index).ffill()
        quote_curve_daily = quote_curve_data.reindex(full_index).ffill()

        r_quote_df = get_risk_free_rate(contract.quote_currency, tenor_series, quote_curve_daily)
        r_base_df = get_risk_free_rate(contract.base_currency, tenor_series, base_curve_daily)

        if r_quote_df.empty or r_base_df.empty:
            return pd.DataFrame(dtype=float)

        calc_df = pd.DataFrame(index=full_index)
        calc_df['s0'] = s0
        calc_df['rf_rate'] = r_quote_df['rf_rate']
        calc_df['rf_base'] = r_base_df['rf_rate']
        calc_df['tenor'] = tenor_series
        calc_df = calc_df[calc_df.index >= pd.to_datetime(contract.start_date)]

        s0_final = calc_df['s0'].values
        r_quote = calc_df['rf_rate'].values
        r_base = calc_df['rf_base'].values
        tenors = calc_df['tenor'].values  # скользящий тенор, свой для каждой даты

        rub_part = (contract.notional * contract.forward_rate) / (1 + r_quote)**tenors
        foreign_part = (contract.notional * s0_final) / (1 + r_base)**tenors

        if contract.direction == Direction.BUY:
            pv_values = foreign_part - rub_part
        else:
            pv_values = rub_part - foreign_part

        pv_series = pd.Series(pv_values, index=calc_df.index, name=contract.instrument_id)
        return pd.DataFrame({"price": pv_series}).dropna()
    

if __name__ == "__main__":
    d_start = datetime(2025, 2, 1)
    d_end = datetime(2025, 2, 28)

    pricer = ForwardPricer()
    dtPr = DataProvider(input_dir="data")
    forward = CurrencyForwardContract(
        instrument_id="FWD1",
        notional=100000,
        direction=Direction.BUY,
        start_date=d_start,
        end_date=d_end,
        currency_pair=CurrencyPair.EUR_USD,
        base_currency="EUR",
        quote_currency="USD",
        forward_rate=1.1
    )
    pv_history = pricer.calculate_pv(forward, dtPr, d_start, d_end)
    print(pv_history.round(2).head(10))