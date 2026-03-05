import csv
from datetime import datetime

def read_currency_file(filename):
    """Читает данные из CSV файла с курсом валюты"""
    data = []
    
    with open(filename, 'r', encoding='utf-8') as f:
        reader = csv.reader(f, delimiter=';')
        next(reader)  # Пропускаем заголовок
        
        for row in reader:
            if len(row) >= 4:
                nominal = int(row[0])
                date_str = row[1]
                curs = float(row[2].replace(',', '.'))
                currency = row[3]
                
                # Парсим дату
                date = datetime.strptime(date_str, '%d.%m.%Y')
                
                data.append({
                    'date': date,
                    'date_str': date_str,
                    'curs': curs,
                    'currency': currency
                })
    
    return data

def calculate_eurusd(euro_data, usd_data):
    """Рассчитывает курс EUR/USD"""
    eurusd_data = []
    
    # Создаем словари для быстрого доступа по дате
    euro_by_date = {item['date']: item for item in euro_data}
    usd_by_date = {item['date']: item for item in usd_data}
    
    # Находим общие даты
    common_dates = set(euro_by_date.keys()) & set(usd_by_date.keys())
    
    for date in sorted(common_dates, reverse=True):  # сортируем по убыванию даты
        euro = euro_by_date[date]
        usd = usd_by_date[date]
        
        # EUR/USD = курс EURRUB / курс USDRUB
        eurusd = euro['curs'] / usd['curs']
        
        eurusd_data.append({
            'date': euro['date_str'],
            'rate': eurusd
        })
    
    return eurusd_data

def save_to_csv(data, filename):
    """Сохраняет результат в CSV файл"""
    with open(filename, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f, delimiter=';')
        
        # Записываем заголовок
        writer.writerow(['nominal', 'data', 'curs', 'cdx'])
        
        # Записываем данные
        for item in data:
            # Форматируем курс с запятой (4 знака после запятой)
            rate_str = f"{item['rate']:.4f}".replace('.', ',')
            writer.writerow(['1', item['date'], rate_str, 'EUR/USD'])

# Основная программа
try:
    # Читаем данные из файлов
    print("Чтение файла EURRUB.csv...")
    euro_data = read_currency_file('EURRUB.csv')
    
    print("Чтение файла USDRUB.csv...")
    usd_data = read_currency_file('USDRUB.csv')
    
    print(f"Загружено {len(euro_data)} записей для EUR/RUB")
    print(f"Загружено {len(usd_data)} записей для USD/RUB")
    
    # Рассчитываем EUR/USD
    eurusd_data = calculate_eurusd(euro_data, usd_data)
    
    if eurusd_data:
        # Сохраняем в файл
        save_to_csv(eurusd_data, 'EURUSD.csv')
        
        # Выводим результат для проверки
        print(f"\n✅ Курс EUR/USD рассчитан и сохранен в файл EURUSD.csv")
        print(f"Найдено {len(eurusd_data)} общих дат")
        print("\nРезультаты:")
        for item in eurusd_data:
            print(f"Дата: {item['date']}, Курс: {item['rate']:.4f}")
    else:
        print("❌ Нет общих дат для расчета курса")
        
except FileNotFoundError as e:
    print(f"❌ Ошибка: Файл не найден - {e}")
except Exception as e:
    print(f"❌ Ошибка: {e}")