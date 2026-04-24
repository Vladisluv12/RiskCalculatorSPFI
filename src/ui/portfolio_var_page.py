import traceback
from dataclasses import replace
from datetime import datetime, time, timedelta

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import compute.risk.portfolio_var as var
from instruments.FXForward import CurrencyForwardContract
from instruments.FXSwap import CurrencySwapContract
from instruments.IRSwap import InterestRateSwap
from ui.common.sidebar import render_report_sidebar
from ui.common.components import render_export_download, render_report_toggle
from ui.portfolio_common.ivar_cvar_section import render_ivar_cvar_section


render_report_sidebar()

st.title("📊 VaR портфеля")

portfolio = st.session_state.get("portfolio", [])
supported = [
    inst for inst in portfolio
    if isinstance(inst, (CurrencyForwardContract, CurrencySwapContract, InterestRateSwap))
]

if len(supported) < 2:
    st.warning(
        "Для расчета VaR портфеля необходимо минимум 2 инструмента "
        "(FX Forward, FX Swap или IRS/OIS) в портфеле."
    )
    st.stop()

# ── Параметры ─────────────────────────────────────────────────────────────────
st.subheader("Параметры расчета")
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

row2_col1, row2_col2 = st.columns(2)
with row2_col1:
    st.date_input("Дата начала расчета", value=calc_start_date, disabled=True)
with row2_col2:
    st.date_input("Дата конца расчета", value=calc_end_date, disabled=True)

st.divider()

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

_pvar_params_key = (
    type_of_var, conf_level, int(horizon), window,
    tuple(inst.instrument_id for inst in supported),
)

_cached = st.session_state.get("pvar_main")
_stale = _cached is not None and _cached.get("_params_key") != _pvar_params_key

if _stale:
    st.warning("Параметры изменились — результаты устарели. Нажмите «Рассчитать VaR» для обновления.")

# ── Кнопки действий ───────────────────────────────────────────────────────────
calc_clicked = st.button("▶ Рассчитать VaR портфеля", type="primary")

# ── Расчёт ────────────────────────────────────────────────────────────────────
if calc_clicked:
    try:
        with st.spinner("Расчёт VaR портфеля..."):
            if type_of_var == "Исторический":
                result = var.portfolio_historical(
                    data_provider, var_instruments, calc_start, calc_end,
                    confidence_level=conf_level, window=window, horizon=int(horizon),
                )
                portfolio_es = var.portfolio_historical_es(
                    data_provider, var_instruments, calc_start, calc_end,
                    confidence_level=conf_level, window=window, horizon=int(horizon),
                )
            else:
                result = var.portfolio_parametric(
                    data_provider, var_instruments, calc_start, calc_end,
                    confidence_level=conf_level, window=window, horizon=int(horizon),
                )
                portfolio_es = var.portfolio_parametric_es(
                    data_provider, var_instruments, calc_start, calc_end,
                    confidence_level=conf_level, window=window, horizon=int(horizon),
                )

        corr_matrix: pd.DataFrame = result["corr_matrix"]
        n = corr_matrix.shape[0]
        mask = ~np.eye(n, dtype=bool)
        off_diag = corr_matrix.values[mask]
        avg_abs_corr = float(np.mean(np.abs(off_diag)))
        if avg_abs_corr > 0.7:
            recommended = "undiversified"
        elif avg_abs_corr < 0.3:
            recommended = "uncorrelated"
        else:
            recommended = "diversified"

        st.session_state["pvar_main"] = {
            "_params_key": _pvar_params_key,
            "pnl_matrix": result["pnl_matrix"],
            "individual_vars": result["individual_vars"],
            "corr_matrix": corr_matrix,
            "diversified_var": result["diversified_var"],
            "undiversified_var": result["undiversified_var"],
            "uncorrelated_var": result["uncorrelated_var"],
            "portfolio_es": portfolio_es,
            "recommended": recommended,
            "type_of_var": type_of_var,
            "conf_level": conf_level,
            "horizon": horizon,
            "window": window,
        }
        # Сбрасываем CVaR/IVaR при пересчёте основного VaR
        st.session_state.pop("pvar_contrib", None)
        st.rerun()
    except Exception as exc:
        st.error(f"Ошибка расчета VaR портфеля: {exc.__class__.__name__}: {exc}")
        with st.expander("Посмотреть детали ошибки"):
            st.code(traceback.format_exc())

# ── Результаты ────────────────────────────────────────────────────────────────
if not st.session_state.get("pvar_main"):
    st.divider()
    if st.button("Перейти к расчёту LVaR портфеля"):
        st.switch_page("ui/lvar_page.py")
    st.stop()

r = st.session_state["pvar_main"]
pnl_matrix: pd.DataFrame = r["pnl_matrix"]
individual_vars: dict = r["individual_vars"]
corr_matrix: pd.DataFrame = r["corr_matrix"]
diversified_var: float = r["diversified_var"]
undiversified_var: float = r["undiversified_var"]
uncorrelated_var: float = r["uncorrelated_var"]
portfolio_es: float = r["portfolio_es"]
recommended: str = r["recommended"]

st.divider()

# Матрица экспозиций
st.subheader("Матрица экспозиций на факторы риска")
risk_factors = sorted({inst.currency_pair.value for inst in supported})
rows = []
for inst in supported:
    inst_pair = inst.currency_pair.value
    row = {"Инструмент": inst.instrument_id, "VaR инструмента": individual_vars.get(inst.instrument_id, 0.0)}
    for rf in risk_factors:
        row[rf] = individual_vars.get(inst.instrument_id, 0.0) if inst_pair == rf else 0.0
    rows.append(row)
total_row = {"Инструмент": "Портфель (итого)", "VaR инструмента": sum(individual_vars.values())}
for rf in risk_factors:
    total_row[rf] = sum(
        individual_vars.get(inst.instrument_id, 0.0)
        for inst in supported if inst.currency_pair.value == rf
    )
rows.append(total_row)
exposure_df = pd.DataFrame(rows).set_index("Инструмент")
exposure_df = exposure_df[risk_factors + ["VaR инструмента"]]
st.dataframe(exposure_df.style.format("{:.4f}"), width="stretch")

st.divider()

# Матрица корреляций
st.subheader("Матрица корреляций PnL")
labels = corr_matrix.columns.tolist()
fig_corr = go.Figure(go.Heatmap(
    z=corr_matrix.values, x=labels, y=labels,
    colorscale="RdBu", zmin=-1, zmax=1,
    text=np.round(corr_matrix.values, 2), texttemplate="%{text}", showscale=True,
))
fig_corr.update_layout(
    title="Корреляция доходностей инструментов", template="plotly_white",
    height=400, yaxis={"autorange": "reversed"},
)
st.plotly_chart(fig_corr, width="stretch")

n = corr_matrix.shape[0]
mask = ~np.eye(n, dtype=bool)
off_diag = corr_matrix.values[mask]
sc1, sc2, sc3 = st.columns(3)
sc1.metric("Средняя корреляция", f"{float(np.mean(off_diag)):.3f}")
sc2.metric("Минимальная корреляция", f"{float(np.min(off_diag)):.3f}")
sc3.metric("Максимальная корреляция", f"{float(np.max(off_diag)):.3f}")

st.divider()

# VaR портфеля
st.subheader("VaR портфеля")
if r["type_of_var"] == "Исторический":
    st.latex(r"VaR_P^{\text{диверс.}} = \sqrt{\vec{VaR}^{\,T} \cdot R \cdot \vec{VaR}}")
else:
    st.latex(r"VaR_P = Z_c \times \sqrt{w_1^2\sigma_1^2 + w_2^2\sigma_2^2 + 2w_1w_2\sigma_1\sigma_2\rho_{1,2}}")

hints = {
    "diversified": "ρ ∊ [0.3;0.7].",
    "undiversified": "ρ > 0.7",
    "uncorrelated": "ρ < 0.3.",
}
var_types = ["diversified", "undiversified", "uncorrelated"]
var_descs = ["Диверсифицированный VaR", "Недиверсифицированный VaR", "VaR (некоррел. позиции)"]
var_vals = [diversified_var, undiversified_var, uncorrelated_var]
rec_ind = var_types.index(recommended)

st.subheader("ES портфеля")
if r["type_of_var"] == "Исторический":
    st.latex(r"ES_P = \left|\,\mathbb{E}\left[PnL_P \mid PnL_P \leq Q_{\alpha}\right]\right|")
else:
    st.latex(r"ES_P = \left|-\mu_P + \sigma_P\,\frac{\varphi(z_{\alpha})}{\alpha}\right|\cdot\sqrt{horizon}")
st.divider()

m1, m2 = st.columns(2)
with m1:
    st.metric(var_descs[rec_ind], f"{var_vals[rec_ind]:.4f}")
    st.success(hints[var_types[rec_ind]])
with m2:
    st.metric("Expected Shortfall портфеля", f"{portfolio_es:.4f}")

st.caption(
    f"Метод: **{r['type_of_var']}** | "
    f"Доверительный уровень: **{r['conf_level'] * 100:.0f}%** | "
    f"Горизонт: **{r['horizon']} дн.** | "
    f"Окно: **{r['window']} дн.**"
)

st.divider()

# VaR по инструментам
st.subheader("VaR по инструментам")
detail_rows = [
    {
        "Инструмент": iid,
        "Метод": r["type_of_var"],
        "Доверительный уровень": f"{r['conf_level'] * 100:.0f}%",
        "Горизонт (дн.)": r["horizon"],
        "VaR": round(v, 6),
    }
    for iid, v in individual_vars.items()
]
st.dataframe(pd.DataFrame(detail_rows).set_index("Инструмент"), width="stretch")

# Гистограмма PnL
st.subheader("Распределение PnL портфеля")
portfolio_pnl = pnl_matrix.sum(axis=1).sort_values().reset_index(drop=True)
alpha_val = 1 - r["conf_level"]
var_cutoff_idx = round(len(portfolio_pnl) * alpha_val)
fig_pnl = go.Figure()
fig_pnl.add_trace(go.Bar(
    x=list(range(len(portfolio_pnl))), y=portfolio_pnl.values,
    name="Отсортированный PnL портфеля", hovertemplate="PnL: %{y:.4f}<extra></extra>",
))
fig_pnl.add_vline(
    x=var_cutoff_idx, line_dash="dash", line_color="#EF553B", line_width=2,
    annotation_text=f"Граница VaR {r['conf_level'] * 100:.0f}%", annotation_position="top left",
)
fig_pnl.update_layout(xaxis_title="Порядковый номер", yaxis_title="PnL", template="plotly_white", hovermode="x unified")
st.plotly_chart(fig_pnl, width="stretch")

st.divider()

# ── IVaR и CVaR ───────────────────────────────────────────────────────────────
recommended_var_value = {"diversified": diversified_var, "undiversified": undiversified_var, "uncorrelated": uncorrelated_var}[recommended]
method_key = "historical" if r["type_of_var"] == "Исторический" else "parametric"

contrib_df = render_ivar_cvar_section(
    data_provider=data_provider,
    var_instruments=var_instruments,
    calc_start=calc_start,
    calc_end=calc_end,
    individual_vars=individual_vars,
    pnl_matrix=pnl_matrix,
    recommended=recommended,
    recommended_var_value=recommended_var_value,
    conf_level=r["conf_level"],
    window=r["window"],
    horizon=int(r["horizon"]),
    method_key=method_key,
    params_key=_pvar_params_key,
)

st.divider()

# ── Экспорт и отчёт ───────────────────────────────────────────────────────────
pvar_results = {
    "individual_vars": pd.DataFrame.from_dict(individual_vars, orient="index", columns=["VaR"]),
    "corr_matrix": corr_matrix,
    "summary": {
        f"portfolio_{recommended}_var": var_vals[rec_ind],
        "portfolio_es": portfolio_es,
    },
}
if contrib_df is not None:
    pvar_results["contrib_ivar_cvar"] = contrib_df

render_export_download(pvar_results, "portfolio_var", "pvar_res_fmt")
render_report_toggle("portfolio_var_page", "Portfolio VaR / ES", pvar_results, "pvar_report_btn")

st.divider()
if st.button("Перейти к расчёту LVaR портфеля"):
    st.switch_page("ui/lvar_page.py")
