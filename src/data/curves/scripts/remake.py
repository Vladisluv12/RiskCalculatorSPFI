import pandas as pd

def process_ecb_parameters(input_file, output_file):
    # 1. Загружаем CSV
    # ЕЦБ иногда использует специфические разделители, но стандартный pd.read_csv обычно справляется
    df = pd.read_csv(input_file)

    # 2. Оставляем только те столбцы, которые нам нужны для расчетов
    # TIME_PERIOD - дата
    # DATA_TYPE_FM - название параметра (BETA0, TAU1 и т.д.)
    # OBS_VALUE - числовое значение
    cols_to_keep = ['TIME_PERIOD', 'DATA_TYPE_FM', 'OBS_VALUE']
    df = df[cols_to_keep]

    # 3. Делаем Pivot (разворот) таблицы
    # index - что станет строками (даты)
    # columns - что станет названиями столбцов (типы параметров)
    # values - что будет внутри ячеек
    pivot_df = df.pivot(index='TIME_PERIOD', columns='DATA_TYPE_FM', values='OBS_VALUE')

    # 4. Приводим в порядок названия столбцов и индекс
    # Сбрасываем индекс, чтобы 'TIME_PERIOD' стал обычной колонкой 'date'
    pivot_df = pivot_df.reset_index()
    pivot_df.rename(columns={'TIME_PERIOD': 'date'}, inplace=True)

    # 5. Сортируем по дате для удобства (от старых к новым)
    pivot_df['date'] = pd.to_datetime(pivot_df['date'])
    pivot_df = pivot_df.sort_values('date')

    # 6. Сохраняем результат
    pivot_df.to_csv(output_file, index=False)
    print(f"Готово! Файл сохранен как: {output_file}")
    
    return pivot_df

result = process_ecb_parameters('data.csv', 'ecb_zcyc.csv')