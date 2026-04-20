import traceback
from dataclasses import replace
from datetime import datetime, time, timedelta

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import compute.risk.var as var
from instruments.FXForward import CurrencyForwardContract
from instruments.FXSwap import CurrencySwapContract

st.title("📊 VaR портфеля")

portfolio = st.session_state.get("portfolio", [])

# Фильтруем инструменты, которые умеем оценивать
supported = [
    inst for inst in portfolio
    if isinstance(inst, (CurrencyForwardContract, CurrencySwapContract))
]

if len(supported) < 2:
    st.warning(
        "Для расчета VaR портфеля необходимо минимум 2 поддерживаемых инструмента "
        "(FX Forward или FX Swap) в портфеле."
    )
    st.stop()

# ──────────────────────────────────────────────
# Параметры расчета
# ──────────────────────────────────────────────
st.subheader("Параметры расчета")
row1_col1, row1_col2, row1_col3 = st.columns(3)

with row1_col1:
    type_of_var = st.selectbox(
        "Метод расчета VaR",
        options=["Исторический", "Параметрический"],
        index=0,
    )
with row1_col2:
    conf_level = st.selectbox("Доверительный уровень", options=[0.95, 0.99], index=0)
with row1_col3:
    horizon = st.number_input("Горизонт прогноза (дней)", min_value=1, max_value=30, value=1)

window = st.slider(
    "Количество дней в истории",
    min_value=252,
    max_value=2520,
    value=252,
    step=252,
)

# Дата расчёта берётся по первому инструменту в портфеле (самый ранний старт)
earliest_start = min(inst.start_date.date() for inst in supported)
calc_end_date = earliest_start - timedelta(days=1)
calc_start_date = calc_end_date - timedelta(days=int(window))

row2_col1, row2_col2 = st.columns(2)
with row2_col1:
    st.date_input("Дата начала расчета", value=calc_start_date, disabled=True)
with row2_col2:
    st.date_input("Дата конца расчета", value=calc_end_date, disabled=True)

st.divider()

# ──────────────────────────────────────────────
# Расчёт
# ──────────────────────────────────────────────
data_provider = st.session_state.get("data_provider")
if data_provider is None:
    st.error(
        "Источник данных не инициализирован. "
        "Перейдите на страницу портфеля и нажмите «Применить»."
    )
    st.stop()

calc_start = datetime.combine(calc_start_date, time.min)
calc_end = datetime.combine(calc_end_date, time.max)

# Подготавливаем инструменты с расширенным диапазоном (как в var_page)
horizon_td = timedelta(days=max(1, int(horizon)))
var_instruments = [
    replace(inst, start_date=calc_start, end_date=calc_end + horizon_td)
    for inst in supported
]

try:
    if type_of_var == "Исторический":
        result = var.portfolio_historical(
            data_provider,
            var_instruments,
            calc_start,
            calc_end,
            confidence_level=conf_level,
            window=window,
            horizon=int(horizon),
        )
    else:
        result = var.portfolio_parametric(
            data_provider,
            var_instruments,
            calc_start,
            calc_end,
            confidence_level=conf_level,
            window=window,
            horizon=int(horizon),
        )

    pnl_matrix: pd.DataFrame = result["pnl_matrix"]
    individual_vars: dict = result["individual_vars"]
    corr_matrix: pd.DataFrame = result["corr_matrix"]
    diversified_var: float = result["diversified_var"]
    undiversified_var: float = result["undiversified_var"]
    uncorrelated_var: float = result["uncorrelated_var"]

    # Расчёт ES портфеля
    if type_of_var == "Исторический":
        portfolio_es: float = var.portfolio_historical_es(
            data_provider, var_instruments, calc_start, calc_end,
            confidence_level=conf_level, window=window, horizon=int(horizon),
        )
    else:
        portfolio_es: float = var.portfolio_parametric_es(
            data_provider, var_instruments, calc_start, calc_end,
            confidence_level=conf_level, window=window, horizon=int(horizon),
        )

    # ──────────────────────────────────────────────
    # Таблица экспозиций
    # ──────────────────────────────────────────────
    st.subheader("Матрица экспозиций на факторы риска")

    # Уникальные валютные пары = факторы риска
    risk_factors = sorted({inst.currency_pair.value for inst in supported})

    rows = []
    for inst in supported:
        inst_pair = inst.currency_pair.value
        row = {"Инструмент": inst.instrument_id, "VaR инструмента": individual_vars.get(inst.instrument_id, 0.0)}
        for rf in risk_factors:
            row[rf] = individual_vars.get(inst.instrument_id, 0.0) if inst_pair == rf else 0.0
        rows.append(row)

    # Итоговая строка портфеля
    total_row = {"Инструмент": "Портфель (итого)", "VaR инструмента": sum(individual_vars.values())}
    for rf in risk_factors:
        total_row[rf] = sum(
            individual_vars.get(inst.instrument_id, 0.0)
            for inst in supported
            if inst.currency_pair.value == rf
        )
    rows.append(total_row)

    exposure_df = pd.DataFrame(rows).set_index("Инструмент")
    exposure_df = exposure_df[risk_factors + ["VaR инструмента"]]
    st.dataframe(
        exposure_df.style.format("{:.4f}"),
        width="stretch",
    )

    st.divider()

    # ──────────────────────────────────────────────
    # Матрица корреляций
    # ──────────────────────────────────────────────
    st.subheader("Матрица корреляций PnL")

    labels = corr_matrix.columns.tolist()
    fig_corr = go.Figure(
        go.Heatmap(
            z=corr_matrix.values,
            x=labels,
            y=labels,
            colorscale="RdBu",
            zmin=-1,
            zmax=1,
            text=np.round(corr_matrix.values, 2),
            texttemplate="%{text}",
            showscale=True,
        )
    )
    fig_corr.update_layout(
        title="Корреляция доходностей инструментов",
        template="plotly_white",
        height=400,
        yaxis={"autorange": "reversed"},
    )
    st.plotly_chart(fig_corr, width="stretch")

    # Статистика корреляций (внедиагональные элементы)
    n = corr_matrix.shape[0]
    mask = ~np.eye(n, dtype=bool)
    off_diag = corr_matrix.values[mask]
    avg_corr = float(np.mean(off_diag))
    min_corr = float(np.min(off_diag))
    max_corr = float(np.max(off_diag))
    avg_abs_corr = float(np.mean(np.abs(off_diag)))

    sc1, sc2, sc3 = st.columns(3)
    sc1.metric("Средняя корреляция", f"{avg_corr:.3f}")
    sc2.metric("Минимальная корреляция", f"{min_corr:.3f}")
    sc3.metric("Максимальная корреляция", f"{max_corr:.3f}")

    st.divider()

    # ──────────────────────────────────────────────
    # Выбор рекомендованного VaR по матрице корреляций
    # ──────────────────────────────────────────────
    if avg_abs_corr > 0.7:
        recommended = "undiversified"
    elif avg_abs_corr < 0.3:
        recommended = "uncorrelated"
    else:
        recommended = "diversified"

    # ──────────────────────────────────────────────
    # Три метрики VaR портфеля
    # ──────────────────────────────────────────────
    st.subheader("VaR портфеля")

    if type_of_var == "Исторический":
        st.latex(
            r"VaR_P^{\text{диверс.}} = \sqrt{\vec{VaR}^{\,T} \cdot R \cdot \vec{VaR}}"
            
        )
    else:
        st.latex(
            r"VaR_P = Z_c \times \sqrt{w_1^2\sigma_1^2 + w_2^2\sigma_2^2 + 2w_1w_2\sigma_1\sigma_2\rho_{1,2}}"
        )

    hints = {
        "diversified": "ρ ∊ [0.3;0.7].",
        "undiversified": "ρ > 0.7",
        "uncorrelated": "ρ < 0.3.",
    }

    # ES портфеля
    st.subheader("ES портфеля")
    if type_of_var == "Исторический":
        st.latex(r"ES_P = \left|\,\mathbb{E}\left[PnL_P \mid PnL_P \leq Q_{\alpha}\right]\right|")
    else:
        st.latex(r"ES_P = \left|-\mu_P + \sigma_P\,\frac{\varphi(z_{\alpha})}{\alpha}\right|\cdot\sqrt{horizon}")
    st.divider()

    m1, m2, m3 = st.columns(3)
    
    var_types = ["diversified", "undiversified", "uncorrelated"]
    var_descs = ["Диверсифицированный VaR", "Недиверсифицированный VaR", "VaR (некоррел. позиции)"]
    var_vals = [diversified_var, undiversified_var, uncorrelated_var]
    rec_ind = var_types.index(recommended)

    with m1:
        st.metric(
            var_descs[0],
            f"{var_vals[0]:.4f}",
        )
        st.success(hints[var_types[rec_ind]])



    st.metric("Expected Shortfall портфеля", f"{portfolio_es:.4f}")

    st.caption(
        f"Метод: **{type_of_var}** | "
        f"Доверительный уровень: **{conf_level * 100:.0f}%** | "
        f"Горизонт: **{horizon} дн.** | "
        f"Окно: **{window} дн.**"
    )

    st.divider()

    # ──────────────────────────────────────────────
    # Детализация по инструментам
    # ──────────────────────────────────────────────
    st.subheader("VaR по инструментам")
    detail_rows = [
        {
            "Инструмент": iid,
            "Метод": type_of_var,
            "Доверительный уровень": f"{conf_level * 100:.0f}%",
            "Горизонт (дн.)": horizon,
            "VaR": round(v, 6),
        }
        for iid, v in individual_vars.items()
    ]
    st.dataframe(pd.DataFrame(detail_rows).set_index("Инструмент"), width="stretch")

    # ──────────────────────────────────────────────
    # Гистограмма PnL портфеля
    # ──────────────────────────────────────────────
    st.subheader("Распределение PnL портфеля")
    portfolio_pnl = pnl_matrix.sum(axis=1).sort_values().reset_index(drop=True)
    alpha = 1 - conf_level
    var_cutoff_idx = round(len(portfolio_pnl) * alpha)

    fig_pnl = go.Figure()
    fig_pnl.add_trace(
        go.Bar(
            x=list(range(len(portfolio_pnl))),
            y=portfolio_pnl.values,
            name="Отсортированный PnL портфеля",
            hovertemplate="PnL: %{y:.4f}<extra></extra>",
        )
    )
    fig_pnl.add_vline(
        x=var_cutoff_idx,
        line_dash="dash",
        line_color="black",
        line_width=2,
        annotation_text=f"Граница VaR {conf_level * 100:.0f}%",
        annotation_position="top left",
    )
    fig_pnl.update_layout(
        xaxis_title="Порядковый номер",
        yaxis_title="PnL",
        template="plotly_white",
        hovermode="x unified",
    )
    st.plotly_chart(fig_pnl, width="stretch")

    # ──────────────────────────────────────────────
    # IVaR и CVaR
    # ──────────────────────────────────────────────
    st.divider()
    st.subheader("Вклад инструментов в риск портфеля")
    st.latex(r"CVaR_i = \rho_{i,P} \cdot VaR_i, \quad \sum_i CVaR_i \approx VaR_{portfolio}")
    st.latex(r"IVaR_i = VaR_{portfolio} - VaR_{portfolio \setminus i}")

    recommended_var_value = {
        "diversified": diversified_var,
        "undiversified": undiversified_var,
        "uncorrelated": uncorrelated_var,
    }[recommended]
    method_key = "historical" if type_of_var == "Исторический" else "parametric"

    if st.button("Рассчитать IVaR и CVaR"):
        with st.spinner("Расчёт..."):
            cvar_dict = var.compute_cvar(pnl_matrix, individual_vars)
            ivar_dict = var.portfolio_ivar(
                data_provider,
                var_instruments,
                calc_start,
                calc_end,
                confidence_level=conf_level,
                window=window,
                horizon=int(horizon),
                method=method_key,
                recommended_var_type=recommended,
                var_full=recommended_var_value,
            )

        contrib_rows = []
        for iid, var_i in individual_vars.items():
            cvar_i = cvar_dict.get(iid, 0.0)
            ivar_i = ivar_dict.get(iid, 0.0)
            contrib_rows.append({
                "Инструмент": iid,
                "VaR_i": var_i,
                "CVaR_i": cvar_i,
                "CVaR_i %": cvar_i / recommended_var_value * 100 if recommended_var_value else 0.0,
                "IVaR_i": ivar_i,
                "IVaR_i %": ivar_i / recommended_var_value * 100 if recommended_var_value else 0.0,
            })

        contrib_df = pd.DataFrame(contrib_rows).set_index("Инструмент")
        st.dataframe(
            contrib_df.style.format({
                "VaR_i": "{:.4f}",
                "CVaR_i": "{:.4f}",
                "CVaR_i %": "{:.1f}%",
                "IVaR_i": "{:.4f}",
                "IVaR_i %": "{:.1f}%",
            }),
            width="stretch",
        )

        cvar_sum = sum(cvar_dict.values())
        
    st.divider()
    if st.button("Перейти к расчёту LVaR портфеля"):
        st.switch_page("ui/lvar_page.py")        

except Exception as exc:
    st.error(f"Ошибка расчета VaR портфеля: {exc.__class__.__name__}: {exc}")
    with st.expander("Посмотреть детали ошибки"):
        st.code(traceback.format_exc())
