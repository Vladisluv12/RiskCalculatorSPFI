"""
Results display and export for the LVaR page.
"""

import pandas as pd
import streamlit as st

from compute.modelling.liquidity import LiquidityParams
from ui.common.components import render_export_download, render_report_toggle
from ui.lvar_common.lvar_spreads import build_observed_spreads, build_observed_spreads_irs


def build_liquidity_params(
    liquidity_source: str,
    csv_label: str,
    lvar_instruments: list,
    calc_end,
    k: float,
    floor_spread: float,
    alpha: float,
    lambda_: float,
    avg_daily_volume: dict,
    k_irs: float = 3.0,
    floor_spread_bps: float = 2.0,
) -> LiquidityParams:
    """Build LiquidityParams for the selected liquidity source."""
    if liquidity_source == csv_label:
        liquidity_df = st.session_state.get("lvar_liquidity_df")
        if liquidity_df is None:
            st.error("Загрузите файл с данными по ликвидности.")
            st.stop()
        return LiquidityParams(
            observed_spreads=build_observed_spreads(liquidity_df, lvar_instruments, calc_end),
            observed_spreads_irs=build_observed_spreads_irs(liquidity_df, lvar_instruments, calc_end),
            avg_daily_volume={},
            k_irs=k_irs,
            floor_spread_bps=floor_spread_bps,
        )
    return LiquidityParams(
        k=k, floor_spread=floor_spread, alpha=alpha, lambda_=lambda_,
        avg_daily_volume=avg_daily_volume,
        k_irs=k_irs,
        floor_spread_bps=floor_spread_bps,
    )


def build_lc_dataframe(supported: list, instrument_lc: dict) -> pd.DataFrame:
    """Build per-instrument liquidity cost DataFrame."""
    rows = [
        {
            "Инструмент": inst.instrument_id,
            "Направление": inst.direction.value,
            "Номинал": inst.notional,
            "s (adj)": (
                instrument_lc.get(inst.instrument_id, {}).get("s_bps")
                or instrument_lc.get(inst.instrument_id, {}).get("s_pct", 0.0)
            ),
            "LC (normal)": instrument_lc.get(inst.instrument_id, {}).get("normal", 0.0),
            "LC (stressed)": instrument_lc.get(inst.instrument_id, {}).get("stressed", 0.0),
        }
        for inst in supported
    ]
    return pd.DataFrame(rows).set_index("Инструмент")


def render_lvar_results(res: dict) -> None:
    """Render formulas, LC table, and summary metrics."""
    from ui.lvar_common.liquidity_model import MODELS_BY_LABEL
    model = MODELS_BY_LABEL.get(res.get("liquidity_source", ""))
    st.subheader("Формулы")
    if model:
        model.render_formulas()
    else:
        st.latex(r"LC = \frac{1}{2}\,|PV|\,\cdot\,s\%")
        st.latex(r"LVaR_T = \frac{VaR + LC}{\sqrt{\frac{(1+T)(1+2T)}{6T}}}")

    st.subheader("LC по инструментам")
    st.dataframe(
        res["instrument_lc"].style.format({
            "Номинал": "{:,.0f}", "s% adj": "{:.4%}",
            "LC (normal)": "{:.4f}", "LC (stressed)": "{:.4f}",
        }),
        width="stretch",
    )

    st.subheader("LVaR портфеля (в абсолютных значениях)")
    mc1, mc2, mc3 = st.columns(3)
    mc1.metric(
        f"VaR портфеля ({res['recommended']})", f"{res['var_portfolio_abs']:,.2f}",
        help=f"Абсолютный VaR. Относительный: {res['var_portfolio_rel']:.4f}",
    )
    mc2.metric("LC_total (normal)", f"{res['lc_total_normal']:,.2f}")
    mc3.metric("LC_total (stressed)", f"{res['lc_total_stressed']:,.2f}")

    ml1, ml2, ml3 = st.columns(3)
    ml1.metric("LVaR (normal)", f"{res['lvar_normal']:,.2f}")
    ml2.metric("LVaR (stressed)", f"{res['lvar_stressed']:,.2f}")
    ml3.metric(f"T-фактор (T={res['T']})", f"{res['t_factor']:.4f}")

    st.caption(
        f"Метод VaR: **{res['type_of_var']}** | "
        f"Уровень: **{res['conf_level']*100:.0f}%** | "
        f"Горизонт: **{res['horizon']} дн.** | "
        f"Окно: **{res['window']} дн.** | "
        f"Выбран VaR: **{res['recommended']}** | "
        f"|PV| портфеля: **{res['total_abs_pv']:,.0f}**"
    )


def render_export_section(res: dict) -> None:
    """Render export download and report toggle."""
    lvar_export_data = {
        "instrument_lc": res["instrument_lc"],
        "lvar_normal": res["lvar_normal"],
        "lvar_stressed": res["lvar_stressed"],
        "var_portfolio_abs": res["var_portfolio_abs"],
        "lc_total_normal": res["lc_total_normal"],
        "lc_total_stressed": res["lc_total_stressed"],
    }
    render_export_download(lvar_export_data, "lvar", "lvar_res_fmt")
    render_report_toggle("lvar_page", "LVaR Portfolio", lvar_export_data, "lvar_report_btn")
