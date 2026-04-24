from datetime import datetime
from utils.liquidity_io import list_liquidity_files, load_liquidity_csv
from instruments.enums import FloatingIndex


import pandas as pd
import streamlit as st
import os

_FIXING_FILENAMES: dict = {
    FloatingIndex.RUONIA_AVG:      "RUONIA Avg..csv",
    FloatingIndex.RUONIA_COMP:     "RUONIA Comp..csv",
    FloatingIndex.ESTR_COMP:       "ESTR_Comp.csv",
    FloatingIndex.SOFR_COMP:       "SOFR_Comp.csv",
    FloatingIndex.OIS_FX:          "OIS FX.csv",
    FloatingIndex.EURIBOR_EUR_1M:  "Euribor_EUR_1m.csv",
    FloatingIndex.EURIBOR_EUR_3M:  "Euribor_EUR_3m.csv",
    FloatingIndex.EURIBOR_EUR_6M:  "Euribor_EUR_6m.csv",
    FloatingIndex.RUSFAR_RUB_3M:   "RUSFAR RUB 3m.csv",
    FloatingIndex.RUSFAR_RUB_ON:   "RusFar RUB O_N.csv",
    FloatingIndex.RUSFARCNY_COMP:  "RUSFARCNY_Comp.csv",
    FloatingIndex.RUB_KEY_RATE:    "RUB KeyRate.csv",
}

class DataProvider:
    """
    Класс для загрузки данных по финансовым инструментам из CSV файлов.
    """

    def __init__(self, input_dir: str = "src/data") -> None:
        if os.path.isabs(input_dir):
            self.filepath = input_dir
        else:
            self.filepath = os.path.join(os.getcwd(), input_dir)
        if not os.path.exists(self.filepath):
            raise FileNotFoundError(f"Директория {self.filepath} не найдена.")

    def _get_curve_filename(self, currency: str) -> str:
        if currency.upper() == 'USD':
            return "usd_zcyc"
        elif currency.upper() == 'RUB':
            return "rub_zcyc_params"
        elif currency.upper() == 'EUR':
            return "ecb_zcyc_params"
        elif currency.upper() == 'CNY':
            return "cny_zcyc"
        else:
            raise ValueError(f"Валюта {currency} не поддерживается.")
        
    def _process_currrency_data(self, filepath: str) -> pd.DataFrame:
        df = pd.read_csv(filepath, index_col="data", sep=';')
        df.index = pd.to_datetime(df.index, format='%d.%m.%Y')
        df.sort_index(inplace=True)
        df['curs'] = df['curs'].str.replace(',', '.').astype(float) / df['nominal']
        df.drop(['nominal', 'cdx'], axis=1, inplace=True)
        df = df.rename(columns={'data': 'date'})
        return df


    def get_currency_data(self, ticker: str, first_date: datetime, last_date: datetime) -> pd.DataFrame:
        """
        Загружает данные по тикеру и возвращает последние N дней.
        """
        filepath = os.path.join(self.filepath, f'currency', str(ticker).upper() + ".csv")

        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Файл для валюты {ticker} не найден.")

        df = self._process_currrency_data(filepath)
        start = first_date
        end = last_date
        mask = (df.index >= start) & (df.index <= end)
        return df.loc[mask]

    def list_liquidity_files(self) -> list[str]:
        return list_liquidity_files(self.filepath)

    def load_liquidity_data(self, filepath) -> pd.DataFrame:
        return load_liquidity_csv(filepath)

    def get_curve_data(self, currency_name: str, first_date: datetime, last_date: datetime) -> pd.DataFrame:
        """
        Загружает данные по кривой и возвращает DataFrame.
        """
        curve_filename = self._get_curve_filename(currency_name)
        filepath = os.path.join(self.filepath, f'curves', curve_filename + ".csv")

        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Файл кривой для {currency_name} не найден.")

        df = pd.read_csv(filepath, index_col='date')
        df.index = pd.to_datetime(df.index)

        start = first_date
        end = last_date
        mask = (df.index >= start) & (df.index <= end)
        return df.loc[mask]

    def get_fixing_data(
        self,
        index: FloatingIndex,
        first_date: datetime,
        last_date: datetime,
    ) -> pd.DataFrame:
        filename = _FIXING_FILENAMES[index]
        filepath = os.path.join(self.filepath, 'fixings', filename)
        if not os.path.exists(filepath):
            raise FileNotFoundError(f'Файл фиксингов для {index.value} не найден.')
        df = pd.read_csv(filepath)
        df.columns = ['date', 'fixing']
        df['date'] = pd.to_datetime(df['date'], format='%d.%m.%Y')
        df = df.set_index('date').sort_index()
        mask = (df.index >= pd.Timestamp(first_date)) & (df.index <= pd.Timestamp(last_date))
        return df.loc[mask]
