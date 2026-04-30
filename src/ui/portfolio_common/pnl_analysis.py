import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st


def render_pnl_chart(pnl_series: pd.Series, title: str) -> None:
    """Time-series bar chart of PnL. pnl_series must have DatetimeIndex."""
    colors = ["#00CC96" if v >= 0 else "#EF553B" for v in pnl_series.values]
    fig = go.Figure(go.Bar(
        x=pnl_series.index,
        y=pnl_series.values,
        marker_color=colors,
        name="PnL",
        hovertemplate="%{x|%Y-%m-%d}: %{y:.4%}<extra></extra>",
    ))
    fig.update_layout(
        title=f"Динамика PnL — {title}",
        xaxis_title="Дата",
        yaxis_title="PnL",
        yaxis_tickformat=".2%",
        template="plotly_white",
        hovermode="x unified",
    )
    st.plotly_chart(fig, width="stretch")


def render_profit_confidence_intervals(pnl_series: pd.Series) -> None:
    """
    Table of profit confidence intervals: P(PnL >= q_p) = p => q_p = Q_{1-p}(PnL).
    Shows at what minimum PnL level the portfolio lands with a given probability.
    """
    probs = [0.50, 0.75, 0.90, 0.95, 0.99]
    rows = []
    for p in probs:
        q = float(pnl_series.quantile(1 - p))
        rows.append({
            "Вероятность": f"{p * 100:.0f}%",
            "Минимальный PnL": f"{q:.4%}",
            "Результат": "прибыль" if q >= 0 else "убыток",
        })
    st.dataframe(pd.DataFrame(rows).set_index("Вероятность"), width="stretch")


def render_pnl_analysis(pnl_series: pd.Series, title: str) -> None:
    """PnL time-series chart + profit confidence interval table."""
    st.subheader("Анализ PnL")
    render_pnl_chart(pnl_series, title)

    st.subheader("Доверительные интервалы прибыли")
    st.latex(r"P\!\left(\mathrm{PnL} \geq q_p\right) = p \;\Longrightarrow\; q_p = Q_{1-p}(\mathrm{PnL})")
    st.caption(
        "С вероятностью p портфель покажет PnL не хуже q_p. "
        "Отрицательные значения означают убыток даже на данном уровне уверенности."
    )
    render_profit_confidence_intervals(pnl_series)
