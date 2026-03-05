import pandas as pd
import numpy as np

# Загружаем данные из Excel файла
df = pd.read_excel('curveDiscount (2).xlsx', sheet_name='Дисконтные кривые')

# Переименовываем колонки для удобства
df.columns = ['Дата', 'Кривая', 'Тип', 'Тенор', 'Время_в_годах', 'Ставка']

# Фильтруем только нужные кривые
currencies = df['Кривая'].unique()  # Получаем уникальные валюты из колонки 'Кривая'

# Создаем пустой DataFrame для результата
result = pd.DataFrame()

# Для каждой валюты создаем колонку со ставками
for currency in currencies:
    # Фильтруем данные по текущей валюте
    currency_data = df[df['Кривая'] == currency].copy()
    
    # Сортируем по дате и тенору для правильной структуры
    currency_data = currency_data.sort_values(['Дата', 'Время_в_годах'])
    
    # Добавляем колонку с названием валюты
    currency_data = currency_data.rename(columns={'Ставка': currency})
    
    # Если result пустой, инициализируем его с нужными колонками
    if result.empty:
        result = currency_data[['Дата', 'Тенор', 'Время_в_годах', currency]]
    else:
        # Добавляем колонку с новой валютой
        result = pd.merge(result, 
                         currency_data[['Дата', 'Тенор', currency]],
                         on=['Дата', 'Тенор'],
                         how='outer')

# Сортируем результат по дате и времени
result = result.sort_values(['Дата', 'Время_в_годах'])

result = result[result['Дата'] >= pd.to_datetime('2026-03-02')]
result.drop(columns=['Дата'], inplace=True)

# Сохраняем результат в новый Excel файл
result.to_csv('дисконтные_ставки_по_валютам.csv', index=False)

# Выводим первые несколько строк для проверки
print("Первые 10 строк результата:")
print(result.head(10))