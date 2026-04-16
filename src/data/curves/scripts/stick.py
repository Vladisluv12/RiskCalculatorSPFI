import pandas as pd
import numpy as np
import os

# 1. Определяем структуру целевых колонок
target_columns = ['date', '0d', '1m', '2m', '3m', '6m', '9m', '1y', '2y', '3y', '4y', '5y', '6y', '7y', '8y', '9y', '10y']

# Словарь для перевода названий колонок в числовое значение (в днях)
# Это нужно для правильного "расстояния" между точками при интерполяции
tenor_to_days = {
    '0d': 0, '1m': 30, '2m': 60, '3m': 90, '6m': 180, '9m': 270,
    '1y': 365, '2y': 730, '3y': 1095, '4y': 1460, '5y': 1825,
    '6y': 2190, '7y': 2555, '8y': 2920, '9y': 3285, '10y': 3650
}

def process_files(output_filename):

    all_files = []
    for i in range(2012, 2027): all_files.append(f"{i}.csv")
    combined_data = []

    for file in all_files:
        df = pd.read_csv(file)
        df['date'] = pd.to_datetime(df['date'])
        combined_data.append(df)

    # Объединяем все файлы в один DataFrame
    full_df = pd.concat(combined_data, ignore_index=True)
    
    # Добавляем недостающие колонки из target_columns, заполняя их NaN
    for col in target_columns:
        if col not in full_df.columns:
            full_df[col] = np.nan

    # Сортируем по дате и переупорядочиваем колонки
    full_df = full_df[target_columns].sort_values('date').reset_index(drop=True)

    # 2. Интерполяция
    # Нам нужно интерполировать значения построчно (axis=1)
    # Но стандартный interpolate не знает, что между '1m' и '1y' разное расстояние.
    # Поэтому используем значения из tenor_to_days как координаты X.
    
    data_cols = target_columns[1:] # все кроме date
    x_values = [tenor_to_days[col] for col in data_cols]

    def interpolate_row(row):
        # Берем только числовые значения
        y_values = row[data_cols].values.astype(float)
        # Маска существующих значений
        mask = ~np.isnan(y_values)
        
        if mask.any():
            # Линейная интерполяция на основе дней
            row[data_cols] = np.interp(x_values, 
                                       np.array(x_values)[mask], 
                                       y_values[mask])
        return row

    # Применяем интерполяцию к каждой строке
    full_df = full_df.apply(interpolate_row, axis=1)

    # Сохраняем результат
    full_df.to_csv(output_filename, index=False)
    print(f"Готово! Файл сохранен как {output_filename}")

# process_files('china_yield_curve_final.csv')

df = pd.read_csv('china_yield_curve_final.csv')
print(df.isnull().sum().sum())