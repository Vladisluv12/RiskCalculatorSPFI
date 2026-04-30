import traceback
from dataclasses import replace
from datetime import datetime, time, timedelta

import numpy as np
import streamlit as st
import compute.risk.lvar as lvar
import compute.risk.portfolio_var as pvar
from instruments.FXForward import CurrencyForwardContract
from instruments.FXSwap import CurrencySwapContract
from instruments.IRSwap import InterestRateSwap
from ui.common.sidebar import render_report_sidebar
from ui.lvar_common.liquidity_model import MODELS, MODELS_BY_LABEL, ParametricLiquidityModel
from ui.lvar_common.lvar_results import build_liquidity_params, build_lc_dataframe, render_lvar_results, render_export_section
from ui.lvar_common.lvar_spreads import liquidity_spreads_key

_CSV_LABEL = next(
    m.label for m in MODELS if not isinstance(m, ParametricLiquidityModel)
)

render_report_sidebar()
st.title("💧 LVaR (Liquidity-adjusted VaR)")

portfolio = st.session_state.get("portfolio", [])
supported = [
    inst for inst in portfolio
    if isinstance(inst, (CurrencyForwardContract, CurrencySwapContract, InterestRateSwap))
]
if len(supported) < 1:
    st.warning("Для расчёта LVaR необходим хотя бы 1 инструмент (FX Forward, FX Swap или IRS/OIS) в портфеле.")
    st.stop()

# Параметры VaR
st.subheader("Параметры VaR")
c1, c2, c3 = st.columns(3)
with c1:
    type_of_var = st.selectbox("Метод расчета VaR", options=["Исторический", "Параметрический"], index=0)
with c2:
    conf_level = st.selectbox("Доверительный уровень", options=[0.95, 0.99], index=1)
with c3:
    horizon = st.number_input("Горизонт прогноза (дней)", min_value=1, max_value=30, value=5)

window = st.slider("Количество дней в истории", min_value=252, max_value=2520, value=252, step=252)

earliest_start = min(inst.start_date.date() for inst in supported)
calc_end_date = earliest_start - timedelta(days=1)
calc_start_date = calc_end_date - timedelta(days=int(window))

dc1, dc2 = st.columns(2)
with dc1:
    st.date_input("Дата начала расчета", value=calc_start_date, disabled=True)
with dc2:
    st.date_input("Дата конца расчета", value=calc_end_date, disabled=True)

st.divider()

# Источник данных по ликвидности
liquidity_source = st.radio(
    "Источник данных по ликвидности",
    [m.label for m in MODELS],
    horizontal=True,
    key="lvar_liquidity_source",
)
model = MODELS_BY_LABEL[liquidity_source]

# Описание модели — только для параметрической (CSV-режим описывает себя в результатах)
if isinstance(model, ParametricLiquidityModel):
    with st.expander("Описание используемой модели ликвидности"):
        model.render_description()

# Параметры ликвидности
p = model.render_inputs(supported)

st.divider()

# Подготовка инструментов
data_provider = st.session_state.get("data_provider")
if data_provider is None:
    st.error("Источник данных не инициализирован. Перейдите на страницу портфеля и нажмите «Применить».")
    st.stop()

calc_start = datetime.combine(calc_start_date, time.min)
calc_end = datetime.combine(calc_end_date, time.max)
horizon_td = timedelta(days=max(1, int(horizon)))

var_instruments = [replace(inst, start_date=calc_start, end_date=calc_end + horizon_td) for inst in supported]
lvar_instruments = [replace(inst, start_date=calc_start) for inst in supported]

_params_key = (
    type_of_var, conf_level, int(horizon), window,
    liquidity_source,
    float(p.k), float(p.floor_spread), float(p.alpha), float(p.lambda_), int(p.T),
    float(p.k_irs), float(p.floor_spread_bps),
    tuple(sorted(p.avg_daily_volume.items())),
    liquidity_spreads_key(liquidity_source, _CSV_LABEL),
    tuple(inst.instrument_id for inst in supported),
)

_stale_warning = st.empty()
if (
    "lvar_results" in st.session_state
    and st.session_state["lvar_results"].get("_params_key") != _params_key
):
    _stale_warning.warning("Параметры изменились — результаты устарели. Нажмите «Рассчитать LVaR» для обновления.")

# Расчёт
if st.button("Рассчитать LVaR"):
    _stale_warning.empty()
    try:
        with st.spinner("Расчёт VaR портфеля..."):
            if type_of_var == "Исторический":
                var_result = pvar.portfolio_historical(
                    data_provider, var_instruments, calc_start, calc_end,
                    confidence_level=conf_level, window=window, horizon=int(horizon),
                )
            else:
                var_result = pvar.portfolio_parametric(
                    data_provider, var_instruments, calc_start, calc_end,
                    confidence_level=conf_level, window=window, horizon=int(horizon),
                )

        corr_matrix = var_result["corr_matrix"]
        n = corr_matrix.shape[0]
        avg_abs_corr = float(np.nan_to_num(np.mean(np.abs(corr_matrix.values[~np.eye(n, dtype=bool)]))))
        recommended = (
            "undiversified" if avg_abs_corr > 0.7
            else "uncorrelated" if avg_abs_corr < 0.3
            else "diversified"
        )

        params = build_liquidity_params(
            liquidity_source, _CSV_LABEL, lvar_instruments, calc_end,
            p.k, p.floor_spread, p.alpha, p.lambda_, p.avg_daily_volume,
            k_irs=p.k_irs, floor_spread_bps=p.floor_spread_bps,
        )

        with st.spinner("Расчёт LVaR..."):
            lvar_result = lvar.portfolio_lvar(
                instruments=lvar_instruments,
                dataProvider=data_provider,
                calc_start=calc_start,
                calc_end=calc_end,
                params=params,
                T=int(p.T),
                confidence_level=conf_level,
                window=window,
            )

        st.session_state["lvar_results"] = {
            "_params_key": _params_key,
            "instrument_lc": build_lc_dataframe(supported, lvar_result["instrument_lc"]),
            "lvar_normal": lvar_result["lvar_normal"],
            "lvar_stressed": lvar_result["lvar_stressed"],
            "var_portfolio_abs": lvar_result["var_portfolio_abs"],
            "lc_total_normal": lvar_result["lc_total"]["normal"],
            "lc_total_stressed": lvar_result["lc_total"]["stressed"],
            "t_factor": lvar_result["t_factor"],
            "total_abs_pv": lvar_result["total_abs_pv"],
            "recommended": recommended,
            "var_portfolio_rel": var_result[f"{recommended}_var"],
            "type_of_var": type_of_var,
            "conf_level": conf_level,
            "horizon": horizon,
            "window": window,
            "liquidity_source": liquidity_source,
            "T": p.T,
        }

    except Exception as exc:
        st.error(f"Ошибка расчёта LVaR: {exc.__class__.__name__}: {exc}")
        with st.expander("Детали ошибки"):
            st.code(traceback.format_exc())

# Результаты
if "lvar_results" in st.session_state:
    render_lvar_results(st.session_state["lvar_results"])
    st.divider()
    render_export_section(st.session_state["lvar_results"])
