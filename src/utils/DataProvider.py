from datetime import datetime
from utils.liquidity_io import list_liquidity_files, load_liquidity_csv
from instruments.enums import FloatingIndex


import pandas as pd
import streamlit as st
import os

_FIXING_FILENAMES: dict[FloatingIndex, str] = {
    FloatingIndex.RUONIA_AVG:      "RUONIA Avg..csv",
    FloatingIndex.RUONIA_COMP:     "RUONIA Comp..csv",
    FloatingIndex.ESTR_COMP:       "ESTR_Comp.csv",
    FloatingIndex.SOFR_COMP:       "SOFR_Comp.csv",
    FloatingIndex.EURIBOR_EUR_1M:  "Euribor_EUR_1m.csv",
    FloatingIndex.EURIBOR_EUR_3M:  "Euribor_EUR_3m.csv",
    FloatingIndex.EURIBOR_EUR_6M:  "Euribor_EUR_6m.csv",
    FloatingIndex.RUSFAR_RUB_3M:   "RUSFAR RUB 3m.csv",
    FloatingIndex.RUSFAR_RUB_ON:   "RusFar RUB O_N.csv",
    FloatingIndex.RUSFARCNY_COMP:  "RUSFARCNY_Comp.csv",
    FloatingIndex.RUB_KEY_RATE:    "RUB KeyRate.csv",
}

_OIS_FILENAMES: dict[str, str] = {
    'RUB': 'rub_ois.csv',
    'EUR': 'eur_ois.csv',
    'USD': 'usd_ois.csv',
    'CNY': 'cny_ois.csv',
}

_CURVE_FILENAMES : dict[str, str] = {
    'RUB': 'rub_zcyc_params.csv',
    'EUR': 'ecb_zcyc_params.csv',
    'USD': 'usd_zcyc.csv',
    'CNY': 'cny_zcyc.csv',
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
        filename =  _CURVE_FILENAMES.get(currency.upper())
        if filename is None:
            raise ValueError(f"Файл кривой для {currency} не найден.")
        return filename
    
    def _get_fixing_filename(self, index: FloatingIndex) -> str:
        filename = _FIXING_FILENAMES.get(index)
        if filename is None:
            raise ValueError(f"Файл фиксингов для {index.value} не найден.")
        return filename
    
    def _process_currrency_data(self, filepath: str) -> pd.DataFrame:
        df = pd.read_csv(filepath, index_col="data", sep=';')
        df.index = pd.to_datetime(df.index, format='%d.%m.%Y')
        df.sort_index(inplace=True)
        df['curs'] = df['curs'].str.replace(',', '.').astype(float) / df['nominal']
        df.drop(['nominal', 'cdx'], axis=1, inplace=True)
        df = df.rename(columns={'data': 'date'})
        return df
    
    def _process_dataframe(self, df: pd.DataFrame, start: datetime, end: datetime) -> pd.DataFrame:
        mask = (df.index >= start) & (df.index <= end)
        return df.loc[mask]

    def get_currency_data(self, ticker: str, first_date: datetime, last_date: datetime) -> pd.DataFrame:
        """
        Загружает данные по тикеру и возвращает последние N дней.
        """
        filepath = os.path.join(self.filepath, f'currency', str(ticker).upper() + ".csv")

        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Файл для валюты {ticker} не найден.")

        df = self._process_currrency_data(filepath)
        return self._process_dataframe(df, first_date, last_date)

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

        return self._process_dataframe(df, first_date, last_date)

    def get_ois_curve_data(
        self,
        currency: str,
        first_date: datetime,
        last_date: datetime,
    ) -> pd.DataFrame:
        """
        Загружает бутстрапированную OIS кривую для валюты.

        Returns DataFrame: index=date, columns=["1w","1m","3m","6m","1y","2y","3y","5y","7y","10y"]
        Values in % per annum.
        """
        filename = _OIS_FILENAMES.get(currency.upper())
        if filename is None:
            raise ValueError(f"OIS curve not available for currency {currency}.")
        filepath = os.path.join(self.filepath, 'ois_curves', filename)
        if not os.path.exists(filepath):
            raise FileNotFoundError(
                f"OIS curve file not found: {filepath}. "
                f"Run ois_bootstrap.build_and_save_ois_curves() first."
            )
        df = pd.read_csv(filepath, index_col='date')
        df.index = pd.to_datetime(df.index)
        ddt = pd.Timedelta(days=5)
        return self._process_dataframe(df, pd.Timestamp(first_date) - ddt, pd.Timestamp(last_date))

    def get_fixing_data(
        self,
        index: FloatingIndex,
        first_date: datetime,
        last_date: datetime,
    ) -> pd.DataFrame:
        """
        Загружает исторические фиксинги для указанного плавающего индекса.
        """
        filename = self._get_fixing_filename(index)
        filepath = os.path.join(self.filepath, 'fixings', filename)
        if not os.path.exists(filepath):
            raise FileNotFoundError(f'Файл фиксингов для {index.value} не найден.')
        df = pd.read_csv(filepath)
        df.columns = df.columns.str.strip()
        df = df.rename(columns={df.columns[0]: 'date', df.columns[1]: 'fixing'})
        df['date'] = pd.to_datetime(df['date'], format='%d.%m.%Y')
        df = df.set_index('date').sort_index()
        return self._process_dataframe(df, first_date, last_date)
