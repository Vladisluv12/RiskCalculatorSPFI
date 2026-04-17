import traceback
from dataclasses import replace
from datetime import datetime, time, timedelta

import numpy as np
import pandas as pd
import streamlit as st
from scipy.stats import norm

import compute.risk.var as var
from compute.risk.liquidity import LiquidityParams
from instruments.FXForward import CurrencyForwardContract
from instruments.FXSwap import CurrencySwapContract

st.title("💧 LVaR (Liquidity-adjusted VaR)")

portfolio = st.session_state.get("portfolio", [])
supported = [
    inst for inst in portfolio
    if isinstance(inst, (CurrencyForwardContract, CurrencySwapContract))
]

if len(supported) < 1:
    st.warning("Для расчёта LVaR необходим хотя бы 1 инструмент (FX Forward или FX Swap) в портфеле.")
    st.stop()

# ──────────────────────────────────────────────
# Параметры VaR
# ──────────────────────────────────────────────
st.subheader("Параметры VaR")
row1_col1, row1_col2, row1_col3 = st.columns(3)
with row1_col1:
    type_of_var = st.selectbox("Метод расчета VaR", options=["Исторический", "Параметрический"], index=0)
with row1_col2:
    conf_level = st.selectbox("Доверительный уровень", options=[0.95, 0.99], index=0)
with row1_col3:
    horizon = st.number_input("Горизонт прогноза (дней)", min_value=1, max_value=30, value=1)

window = st.slider("Количество дней в истории", min_value=252, max_value=2520, value=252, step=252)

earliest_start = min(inst.start_date.date() for inst in supported)
calc_end_date = earliest_start - timedelta(days=1)
calc_start_date = calc_end_date - timedelta(days=int(window))

r2c1, r2c2 = st.columns(2)
with r2c1:
    st.date_input("Дата начала расчета", value=calc_start_date, disabled=True)
with r2c2:
    st.date_input("Дата конца расчета", value=calc_end_date, disabled=True)

st.divider()

# ──────────────────────────────────────────────
# Параметры ликвидности
# ──────────────────────────────────────────────
st.subheader("Параметры ликвидности")
lc1, lc2, lc3 = st.columns(3)
with lc1:
    k = st.number_input("k (калибровка)", value=3.0, min_value=0.1, step=0.1,
                         help="Коэффициент волатильность→спред. Дефолт 3.0 для российского рынка.")
    floor_spread = st.number_input("floor_spread (мин. спред)", value=0.001,
                                    min_value=0.0001, step=0.0001, format="%.4f",
                                    help="Минимальный спред (10 bps = 0.001).")
with lc2:
    alpha = st.number_input("α (асимметрия BUY/SELL)", value=0.10,
                             min_value=0.0, max_value=0.5, step=0.01,
                             help="BUY получает спред ×(1+α), SELL ×(1-α).")
    lambda_ = st.number_input("λ (EWMA decay)", value=0.94,
                               min_value=0.50, max_value=0.999, step=0.01,
                               help="RiskMetrics: 0.94 для дневных данных.")
with lc3:
    T = st.number_input("T (дней на ликвидацию)", value=1, min_value=1, max_value=30,
                         help="Равномерный выход за T дней. T=1 → нет масштабирования.")

st.subheader("Средний дневной объём торгов (ADV)")
st.caption("Оставьте 0 чтобы не учитывать поправку на размер позиции.")
unique_pairs = sorted({inst.currency_pair.value for inst in supported})
adv_cols = st.columns(max(len(unique_pairs), 1))
raw_adv: dict = {}
for i, pair in enumerate(unique_pairs):
    with adv_cols[i]:
        raw_adv[pair] = st.number_input(
            pair, min_value=0.0, value=0.0, step=1_000_000.0, format="%.0f",
        )
avg_daily_volume = {k_: v for k_, v in raw_adv.items() if v > 0}

st.divider()

# ──────────────────────────────────────────────
# Расчёт
# ──────────────────────────────────────────────
data_provider = st.session_state.get("data_provider")
if data_provider is None:
    st.error("Источник данных не инициализирован. Перейдите на страницу портфеля и нажмите «Применить».")
    st.stop()

calc_start = datetime.combine(calc_start_date, time.min)
calc_end = datetime.combine(calc_end_date, time.max)
horizon_td = timedelta(days=max(1, int(horizon)))
var_instruments = [
    replace(inst, start_date=calc_start, end_date=calc_end + horizon_td)
    for inst in supported
]
# Для LVaR сохраняем оригинальный end_date инструмента (нужен для расчёта тенора спреда),
# но заменяем start_date на calc_start, чтобы приценщик генерировал PV с исторического начала.
lvar_instruments = [
    replace(inst, start_date=calc_start)
    for inst in supported
]

if st.button("Рассчитать LVaR"):
    try:
        # Сначала рассчитываем портфельный VaR (как на portfolio_var_page)
        with st.spinner("Расчёт VaR портфеля..."):
            if type_of_var == "Исторический":
                var_result = var.portfolio_historical(
                    data_provider, var_instruments, calc_start, calc_end,
                    confidence_level=conf_level, window=window, horizon=int(horizon),
                )
            else:
                var_result = var.portfolio_parametric(
                    data_provider, var_instruments, calc_start, calc_end,
                    confidence_level=conf_level, window=window, horizon=int(horizon),
                )

        corr_matrix = var_result["corr_matrix"]
        diversified_var = var_result["diversified_var"]
        undiversified_var = var_result["undiversified_var"]
        uncorrelated_var = var_result["uncorrelated_var"]

        n = corr_matrix.shape[0]
        mask = ~np.eye(n, dtype=bool)
        avg_abs_corr = float(np.mean(np.abs(corr_matrix.values[mask])))

        if avg_abs_corr > 0.7:
            recommended = "undiversified"
        elif avg_abs_corr < 0.3:
            recommended = "uncorrelated"
        else:
            recommended = "diversified"

        var_portfolio = {
            "diversified": diversified_var,
            "undiversified": undiversified_var,
            "uncorrelated": uncorrelated_var,
        }[recommended]

        params = LiquidityParams(
            k=float(k),
            floor_spread=float(floor_spread),
            alpha=float(alpha),
            lambda_=float(lambda_),
            avg_daily_volume=avg_daily_volume,
        )

        with st.spinner("Расчёт LVaR..."):
            lvar_result = var.portfolio_lvar(
                var_portfolio=var_portfolio,
                instruments=lvar_instruments,
                dataProvider=data_provider,
                calc_start=calc_start,
                calc_end=calc_end,
                params=params,
                T=int(T),
                confidence_level=conf_level,
                window=window,
            )

        # ──────────────────────────────────────────────
        # Формулы
        # ──────────────────────────────────────────────
        st.subheader("Формулы")
        st.latex(r"LC^{normal} = \frac{1}{2}\,|PV|\,\cdot\,s\%")
        st.latex(r"LC^{stressed} = \frac{1}{2}\,|PV|\,\cdot\,(s\% + z_\alpha \cdot \sigma_{spread})")
        st.latex(r"LVaR_T = \frac{VaR + LC}{\sqrt{\frac{(1+T)(1+2T)}{6T}}}")

        # ──────────────────────────────────────────────
        # Таблица по инструментам
        # ──────────────────────────────────────────────
        st.subheader("LC по инструментам")
        rows = []
        instrument_lc = lvar_result["instrument_lc"]
        for inst in supported:
            lc = instrument_lc.get(inst.instrument_id, {'normal': 0.0, 'stressed': 0.0})
            rows.append({
                "Инструмент": inst.instrument_id,
                "Направление": inst.direction.value,
                "Номинал": inst.notional,
                "LC (normal)": lc['normal'],
                "LC (stressed)": lc['stressed'],
            })
        lc_df = pd.DataFrame(rows).set_index("Инструмент")
        st.dataframe(
            lc_df.style.format({
                "Номинал": "{:,.0f}",
                "LC (normal)": "{:.4f}",
                "LC (stressed)": "{:.4f}",
            }),
            width="stretch",
        )

        # ──────────────────────────────────────────────
        # Метрики портфеля
        # ──────────────────────────────────────────────
        st.subheader("LVaR портфеля")
        lc_total = lvar_result["lc_total"]
        mc1, mc2, mc3 = st.columns(3)
        mc1.metric(f"VaR портфеля ({recommended})", f"{var_portfolio:.4f}")
        mc2.metric("LC_total (normal)", f"{lc_total['normal']:.4f}")
        mc3.metric("LC_total (stressed)", f"{lc_total['stressed']:.4f}")

        ml1, ml2, ml3 = st.columns(3)
        ml1.metric("LVaR (normal)", f"{lvar_result['lvar_normal']:.4f}")
        ml2.metric("LVaR (stressed)", f"{lvar_result['lvar_stressed']:.4f}")
        ml3.metric(f"T-фактор (T={T})", f"{lvar_result['t_factor']:.4f}")

        st.caption(
            f"Метод VaR: **{type_of_var}** | "
            f"Уровень: **{conf_level*100:.0f}%** | "
            f"Горизонт: **{horizon} дн.** | "
            f"Окно: **{window} дн.** | "
            f"Рекомендован: **{recommended}**"
        )

    except Exception as exc:
        st.error(f"Ошибка расчёта LVaR: {exc.__class__.__name__}: {exc}")
        with st.expander("Детали ошибки"):
            st.code(traceback.format_exc())
