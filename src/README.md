# src

Корневой пакет приложения. Содержит весь исходный код калькулятора риска: описание контрактов, прайсеры, риск-метрики, загрузку данных, ввод-вывод портфелей, Streamlit-интерфейс и сами CSV-данные. Точка входа Streamlit — `main.py`.

## Поток данных

CSV-файлы из `data/` загружаются через `utils.DataProvider`, который кеширует результаты и умеет нарезать выборку по датам. Прайсеры из `compute/pricers/` принимают контракт (датакласс из `instruments/`) и `DataProvider`, возвращая ежедневный временной ряд NPV. Диспетчер `compute/pricers/pricer_dispatch.py` маршрутизирует инструмент к нужному прайсеру. Полученные ряды агрегируются в `compute/risk/` и превращаются в VaR, CVaR и LVaR на уровне портфеля. Слой `iolib/` отвечает за загрузку и сохранение портфелей, построение отчётов и экспорт результатов. Streamlit-страницы из `ui/` собирают всё это в интерактивный интерфейс.

## Подпакеты

### instruments
Датаклассы контрактов и общие перечисления. Базовый класс `BaseInstrument` (`BaseInstrument.py`) задаёт минимальный набор полей контракта; от него наследуются конкретные инструменты `InterestRateSwap` (`IRSwap.py`), `CurrencyForwardContract` (`FXForward.py`) и `CurrencySwapContract` (`FXSwap.py`). Файлы `XCCY.py` и `CapFloor.py` зарезервированы под кросс-валютный своп и опционы Cap/Floor, но в текущей версии это пустые заглушки без датаклассов. Файл `enums.py` содержит типы Currency, FloatingIndex, DayCountConvention, PaymentTiming, OffsetRule, Direction и используется как единый словарь типов для всех остальных слоёв.

### compute
Вычислительное ядро. Делится на три подпакета. `pricers/` содержит прайсеры по типам инструментов плюс общие утилиты `swap_utils.py` (генерация графика платежей, year fraction, OIS дисконт-факторы, форварды IBOR с rolling-mean базисом, DV01) и диспетчер. `modelling/` отвечает за интерполяцию ZC-кривых (`RiskFreeRate.py`: модель Свенссона для EUR, расширенный Nelson-Siegel с гауссовыми корректорами для RUB, линейная интерполяция для USD и CNY) и за модели спредов ликвидности (`liquidity.py`). `risk/` реализует исторический и параметрический VaR/ES (`var.py`), Component VaR и Incremental VaR (`civar.py`), liquidity-adjusted VaR (`lvar.py`) и портфельную агрегацию с разложением на диверсифицированный, недиверсифицированный и некоррелированный VaR (`portfolio_var.py`).

### utils
Сервисный слой. `DataProvider.py` — единая точка доступа к CSV-данным с методами `get_ois_curve_data`, `get_curve_data`, `get_fixing_data`, `get_currency_data` (каждый принимает диапазон дат `(first_date, last_date)`). `ois_bootstrap.py` строит OIS-термкривые из овернайт-фиксингов и сохраняет их в `data/ois_curves/`. `validate.py` зарезервирован под будущие валидаторы портфеля и сейчас пуст. Также здесь лежат генераторы синтетических данных (`generate_irs_liquidity.py`, `generate_liquidity.py`, `generate_sample_portfolios.py`), утилиты ввода-вывода ликвидности (`liquidity_io.py`, `split_liquidity.py`) и `bootstrap_test_data.py`.

### iolib
Ввод-вывод портфелей и отчётов. `portfolio_io.py` загружает и сохраняет портфели в форматах JSON, YAML, CSV и Excel (поддерживаемые типы: `IRS`, `FXForward`, `FXSwap`). `report_builder.py` собирает PDF-отчёты по результатам расчёта. `results_exporter.py` экспортирует результаты в нужный формат. Подпакет `serializers/` содержит формат-специфичные реализации (`json_serializer.py`, `yaml_serializer.py`, `csv_serializer.py`, `excel_serializer.py`) поверх общего интерфейса `BaseSerializer`.

### ui
Streamlit-страницы и общие компоненты. Каждая страница (`var_page`, `lvar_page`, `portfolio_var_page` и др.) реализует один сценарий калькуляции, переиспользуя компоненты из `common/`.

### backtest
Заготовка под бэктестинг рисковых метрик. На текущий момент содержит только `__init__.py`.

### data
CSV-данные: фиксинги индексов, ZC- и OIS-кривые, FX-курсы, спреды ликвидности и примеры портфелей. Подробное описание подпапок — в `data/README.md`.

## Запуск

```bash
cd src && streamlit run main.py
```
