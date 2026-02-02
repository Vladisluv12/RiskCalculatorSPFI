import pandas as pd
import streamlit as st
import os

@st.cache_data
def get_data(ticker: str, ctype: str, days: int):
    """
    Загружает данные по тикеру и возвращает последние N дней.
    """
    filepath = os.path.join(os.getcwd(), f'src\data\{ctype}', str(ticker).upper() + ".csv")
    print(filepath)

    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Файл для инструмента {ticker} не найден.")
    
    df = pd.read_csv(filepath, index_col="data", parse_dates=True, sep=';')
    df.drop(['nominal', 'cdx'], axis=1, inplace=True)
    df['curs'] = df['curs'].str.replace(',', '.').astype(float)
    print(df.head(10))
    return df.tail(days)