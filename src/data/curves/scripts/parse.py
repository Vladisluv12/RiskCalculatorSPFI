import requests
import pandas as pd
import io
import time
from datetime import datetime, timedelta

START_DATE = datetime(2016, 2, 10)
END_DATE = datetime(2026, 2, 20)
BASE_URL = "https://iss.moex.com/iss/engines/stock/zcyc.csv"
BASE_PARAMS = {
    'iss.meta': 'off',
    'iss.only': 'params'
}
OUTPUT_FILE = "zcyc_params_2016-02-10_2026-02-20.csv"
REQUEST_DELAY = 0.5

def download_data_for_date(date_obj):
    """
    Скачивает данные для конкретной даты.
    Возвращает DataFrame с параметрами или None, если данных нет (или ошибка).
    """
    date_str = date_obj.strftime("%Y-%m-%d")
    params = BASE_PARAMS.copy()
    params['date'] = date_str
    try:
        response = requests.get(BASE_URL, params=params, timeout=10)
        response.raise_for_status()
        if not response.text.strip():
            print(f"Нет данных за {date_str} (пустой ответ)")
            return None

        columns = ['date', 'time', 'B1', 'B2', 'B3', 'T1', 'G1', 'G2', 'G3', 'G4', 'G5', 'G6', 'G7', 'G8', 'G9']

        no_header = str(';').join(columns) + '\n' + response.text.replace('params', '').strip()
        # print(no_header)

        df = pd.read_csv(io.StringIO(no_header), sep=';')

        df.drop(columns=['time'], inplace=True)

        # print(f"Успешно загружено: {date_str}")
        return df

    except requests.exceptions.RequestException as e:
        print(f"Ошибка загрузки для {date_str}: {e}")
        return None
    except pd.errors.EmptyDataError:
        print(f"Нет данных за {date_str} (пустой CSV)")
        return None
    except Exception as e:
        print(f"Неожиданная ошибка для {date_str}: {e}")
        return None

def main():
    current_date = START_DATE

    print(f"Начинаем загрузку данных с {START_DATE.strftime('%Y-%m-%d')} по {END_DATE.strftime('%Y-%m-%d')}")
    print("Соблюдается задержка в 0.5 секунды между запросами.")

    final_df = pd.DataFrame()
    i = 1
    while current_date <= END_DATE:
        df_day = download_data_for_date(current_date)

        if df_day is not None:
            final_df = pd.concat([final_df, df_day], ignore_index=True)

        current_date += timedelta(days=1)
        time.sleep(REQUEST_DELAY)
        print(i)
        i += 1

    if not final_df.empty:
        final_df.to_csv(OUTPUT_FILE, index=False, date_format='%Y-%m-%d')
        print(f"\nГотово! Итоговый файл сохранён как: {OUTPUT_FILE}")
        print(f"Всего записей (дней с данными): {len(final_df)}")

if __name__ == "__main__":
    main()