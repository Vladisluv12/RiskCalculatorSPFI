# tests

Pytest-набор для калькулятора риска. `conftest.py` добавляет каталог `src/` в `sys.path` через `os.path.join(os.path.dirname(__file__), '..', 'src')`, то есть путь резолвится относительно самого `conftest.py`, а не текущего каталога. Тесты импортируют пакеты проекта так же, как это делает приложение, при запуске из любой директории.

## Запуск

Удобный пример запуска из `src/`:

```bash
cd src && ../venv/bin/pytest ../tests/ -v
```

Эквивалентно работает `pytest tests/ -v` из корня репозитория или `pytest tests/compute/ -v` для конкретной подпапки. Условия `cd src` нет — это лишь сложившаяся привычка.

## Покрытие

Набор покрывает три ключевых слоя проекта.

Слой расчётов (`tests/compute/`) проверяет прайсер процентных свопов и общие утилиты для свопов (`pricers/`), а также модели риск-метрик: Component VaR и Incremental VaR (`risk/test_cvar_ivar.py`) и liquidity-adjusted VaR с моделями спредов ликвидности (`risk/test_liquidity.py`).

Слой ввода-вывода (`tests/iolib/`) проверяет roundtrip портфелей в форматах JSON, YAML, CSV и Excel, сборку PDF-отчётов и экспорт результатов расчёта.

Слой утилит (`tests/utils/`) проверяет загрузку фиксингов через `DataProvider`: типы данных, фильтрацию по датам и обработку отсутствующих файлов.

## Структура

```
tests/
  conftest.py
  compute/
    pricers/    тесты IRSPricer и swap_utils
    risk/       тесты CVaR/IVaR и LVaR/liquidity
  iolib/        тесты portfolio_io, report_builder, results_exporter, serializers
  utils/        тесты DataProvider (fixings)
```
