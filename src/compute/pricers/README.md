# compute/pricers

Пакет содержит прайсеры внебиржевых деривативов и диспетчер, маршрутизирующий контракт к подходящему прайсеру. Каждый прайсер строит ежедневный временной ряд NPV для одного инструмента на заданном диапазоне дат `[calc_start, calc_end]`. Эти ряды затем используются модулями из `compute/risk/` для оценки VaR, CVaR и LVaR на уровне портфеля.

## Общий контракт

Каждый прайсер принимает контракт-датакласс из `src/instruments/` и экземпляр `DataProvider`. Возвращаемое значение — серия NPV (внутри прайсеров — `pandas.DataFrame`, на уровне диспетчера — `pandas.Series`) по календарным датам в валюте контракта или в базовой валюте, в зависимости от инструмента. Дисконтирование во всех IRS-подобных инструментах единое: OIS-кривая через `compute.modelling.RiskFreeRate.get_ois_rate`. Параметры ZC-кривых берутся из `DataProvider.get_curve_data`, исторические фиксинги — из `DataProvider.get_fixing_data`, FX-споты — из `DataProvider.get_currency_data`.

## IRSPricer

`IRSPricer.calculate_pv(contract, dataProvider, calc_start, calc_end)` — мульти-кривый прайсер процентного свопа. Обрабатывает фиксированную ногу через приведённый поток купонов с OIS-дисконтированием и плавающую ногу по одной из двух схем.

Для индексов, помеченных `FloatingIndex.is_ois_based` (RUONIA, ESTR, SOFR, RUSFARCNY), используется тождество par-float: `PV_float = N * (DF_start − DF_end) + N * spread * annuity`. Это даёт точную репликацию плавающей ноги через дисконт-факторы и не требует прогноза форвардных ставок.

Для остальных IBOR-индексов (EURIBOR 1M/3M/6M, RUSFAR ON/3M, RUB_KEY_RATE) форвард строится через `swap_utils.ibor_forward_rate_with_basis`: берётся OIS-форвард соответствующего срока (`FloatingIndex.ibor_ois_tenor_years`) и к нему добавляется rolling-mean базис между историческим фиксингом и OIS-ставкой с окном 20 дней. После этого плавающая нога считается обычным дисконтированным потоком купонов. Никакого «flat-fixing» режима в коде нет.

Прайсер не использует мемоизации (`lru_cache`/внутренние кэши): расписания и дисконт-факторы пересчитываются на каждый вызов `calculate_pv`.

## CurrencySwapPricer

`CurrencySwapPricer` оценивает классический FX-своп с двумя точками обмена (near leg и far leg). Никаких купонных потоков нет: считаются дисконтированные стоимости двух точечных обменов номиналами по обеим валютам, near leg по `spot_rate`, far leg по `forward_rate`, после чего ноги приводятся к базовой валюте через текущий FX-спот `s0`. Дисконт-факторы для обеих валют берутся из их ZC-кривых через `DataProvider.get_curve_data`. Возвращает дневную серию NPV в базовой валюте контракта.

## ForwardPricer

`ForwardPricer` оценивает FX-форвард по разложению, эквивалентному формуле covered interest rate parity: `(N * K) / (1 + r_quote)^t − (N * S0) / (1 + r_base)^t`, где `K` — фиксированный `forward_rate` контракта, `S0` — текущий FX-спот, `r_base` и `r_quote` — ZC-ставки соответствующих валют, `t` — срок до расчётов в годах. Возвращает серию NPV до даты расчётов включительно.

## swap_utils

Модуль `swap_utils.py` собирает общую логику, переиспользуемую IRS- и валютным прайсерами.

| Функция / константа | Назначение |
|---|---|
| `generate_payment_schedule` | Построение расписания купонных дат с учётом частоты, сдвигов (`OffsetRule`, `_OFFSET_DAYS`) и тайминга платежа (`PaymentTiming`, `_TIMING_DELTA`). |
| `year_fraction` | Расчёт долей года между датами по нужной `DayCountConvention`. |
| `ois_discount_factor_series` | Серия OIS дисконт-факторов на даты расписания, поверх `modelling.RiskFreeRate.get_ois_rate`. |
| `ibor_forward_rate_with_basis` | Получение IBOR-форварда как OIS-форварда плюс скользящий базис (rolling-mean окна 20 дней); используется в `IRSPricer` для не-OIS индексов. |
| `irs_dv01` | Оценка DV01 свопа сдвигом кривой; используется в риск-модуле. |
| `_apply_offset` | Внутренний помощник для применения календарных сдвигов. |

## pricer_dispatch

`pricer_dispatch.get_pv_series(dataProvider, instrument, calc_start, calc_end, window)` — единая точка входа для UI и риск-модулей. Поддерживается ровно три типа контракта: `InterestRateSwap`, `CurrencyForwardContract`, `CurrencySwapContract`; на любой другой тип функция выбрасывает `ValueError`. Возвращает `pandas.Series` с именем `instrument.instrument_id` (NPV по дням). Это позволяет верхним слоям работать с портфелем единообразно, не зная деталей конкретного прайсера.
