# src/data

Все CSV-данные, которыми питается калькулятор. Файлы здесь читаются преимущественно через `utils.DataProvider`, который кеширует результаты и нарезает их по диапазону дат. Часть данных является сырой выгрузкой из внешних источников, часть — производной, генерируемой скриптами проекта.

## fixings

Ежедневные фиксинги по плавающим индексам в формате CSV: RUONIA (Avg и Comp), RUSFAR (RUB 3m и O/N), RUSFAR CNY, RUB Key Rate, EURIBOR (1M, 3M, 6M), ESTR, SOFR, OIS FX. Каждому файлу соответствует значение из `instruments.enums.FloatingIndex`. Читается через `DataProvider.get_fixing_data(FloatingIndex)`. Используется прайсером IRS как для определения текущего фиксинга плавающей ноги, так и для бутстрапа OIS-кривых. В этой же папке лежат вспомогательные скрипты `parse.py`, `fetch_euribor.py`, `fetch_sofr.py` и исходный xlsx-файл от ЦБ.

## ois_curves

Преднасчитанные OIS term-кривые по валютам: `rub_ois.csv`, `eur_ois.csv`, `usd_ois.csv`, `cny_ois.csv`. Не являются сырыми данными — генерируются однократно функцией `utils.ois_bootstrap.build_and_save_ois_curves()` из соответствующих overnight-фиксингов. Читаются через `DataProvider.get_ois_curve_data(currency)` и используются прайсером IRS для дисконтирования всех денежных потоков и для расчёта форвардов через OIS плюс базис.

## curves

Параметрические описания zero-coupon yield curves. Для RUB и EUR хранятся параметры Nelson-Siegel (`rub_zcyc_params.csv`, `ecb_zcyc_params.csv`). Для USD и CNY — точки спот-кривой (`usd_zcyc.csv`, `cny_zcyc.csv`). Подпапка `china_curve_years/` содержит исторические годовые срезы китайской кривой (2012–2026). В `scripts/` лежат вспомогательные скрипты подготовки кривых: `parse.py`, `remake.py`, `stick.py`, `get_new_params.py`. Читается через `DataProvider.get_curve_data(currency)` и используется прайсерами IRS, FX-форвардов и валютных свопов.

## currency

Спот-курсы валютных пар: `USDRUB.csv`, `EURRUB.csv`, `CNYRUB.csv`, `EURUSD.csv`. Читается через `DataProvider.get_currency_data(ticker)`. Используется FX-прайсерами и при пересчёте NPV в отчётной валюте.

## liquidity

Данные по спредам ликвидности. Файлы вида `fx_<PAIR>.csv` содержат спреды для FX-инструментов, файлы `irs_<CCY>_<KIND>.csv` — для процентных свопов (например, `irs_RUB_OIS.csv`, `irs_EUR_IRS.csv`). Также есть сводные `liquidity.csv` и `irs_liquidity.csv` и индексный `index.csv`. Подпапка `legacy/` хранит старые версии этих файлов для обратной совместимости. Используется моделями из `compute.modelling.liquidity` и расчётом `compute.risk.lvar`.

## ir

Ключевые ставки центральных банков по валютам: `rub_key_rate.csv`, `eur_key_rate.csv`, `usd_key_rate.csv`, `cny_key_rate.csv`. Скрипт `parse.py` отвечает за парсинг исходных данных. Используется как фолбэк и в моделях, где требуется политика ЦБ.

## sample_portfolios

Готовые примеры портфелей в JSON для демонстрации UI: `pure_irs_rub.json`, `irs_dominated_rub.json`, `balanced_multiccy.json`, `fx_diversified.json`. Загружаются через `iolib.portfolio_io`.
