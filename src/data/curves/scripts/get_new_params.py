from unittest import result

import pandas as pd

def process_ecb_parameters(input_file1, input_file2, output_file):
    df1 = pd.read_csv(input_file1)
    df2 = pd.read_csv(input_file2)
    df1.rename(columns={'observation_date': 'date'}, inplace=True)
    df1['date'] = pd.to_datetime(df1['date'])
    df2['date'] = pd.to_datetime(df2['date'])
    result = pd.merge(df1, df2, on='date', how='left')
    result = result.dropna(thresh=3)
    result.to_csv(output_file, index=False)
    print(f"Готово! Файл сохранен как: {output_file}")

process_ecb_parameters('fredgraph.csv', 'C:\\Users\\vladc\\Desktop\\projects\\course_work_risk_calc\\src\\data\\ir\\usd_key_rate.csv.', 'usd_zcyc.csv')