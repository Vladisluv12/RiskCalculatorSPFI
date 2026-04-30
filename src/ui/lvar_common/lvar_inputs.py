# Functionality moved to ui.lvar_common.liquidity_model (Strategy pattern).
# Kept for backward compatibility.

import os
import re
import traceback

import pandas as pd
import streamlit as st

from instruments.IRSwap import InterestRateSwap
from utils.liquidity_io import liquidity_dir_path, load_for_portfolio


def render_parametric_inputs(supported: list) -> tuple:
    """Render parametric liquidity model inputs.

    Returns (k, floor_spread, alpha, lambda_, T, avg_daily_volume, k_irs, floor_spread_bps).
    """
    st.subheader("Параметры ликвидности")
    lc1, lc2, lc3 = st.columns(3)
    with lc1:
        k = st.number_input(
            "k - масштаб спреда", value=3.0, min_value=0.1, step=0.1,
            help="Калибровочный коэффициент: s%(t) = max(k x sigma_ewma(t) x sqrt(tenor), s_floor).",
        )
        floor_spread = st.number_input(
            "s_floor - минимальный спред", value=0.001, min_value=0.0001, step=0.0001, format="%.4f",
            help="Нижняя граница спреда. 10 bps = 0.001, 50 bps = 0.005.",
        )
    with lc2:
        alpha = st.number_input(
            "alpha - асимметрия BUY/SELL", value=0.10, min_value=0.0, max_value=0.5, step=0.01,
            help="BUY: спред x (1+alpha), SELL: спред x (1-alpha). При alpha=0 — без асимметрии.",
        )
        lambda_ = st.number_input(
            "lambda - коэффициент затухания EWMA", value=0.94, min_value=0.50, max_value=0.999, step=0.01,
            help="sigma^2(t) = lambda*sigma^2(t-1) + (1-lambda)*r^2(t). Стандарт RiskMetrics — 0.94.",
        )
    with lc3:
        T = st.number_input(
            "T - дней на ликвидацию", value=1, min_value=1, max_value=30,
            help="Масштабирующий T-фактор: sqrt((1+T)(1+2T) / (6T)).",
        )

    has_irs = any(isinstance(inst, InterestRateSwap) for inst in supported)
    k_irs = 3.0
    floor_spread_bps = 2.0
    if has_irs:
        st.subheader("Параметры ликвидности IRS")
        st.caption(
            "Спред котируется в базисных пунктах фиксированной ставки. "
            "LC = ½ × DV01 × spread_bps."
        )
        irs_c1, irs_c2 = st.columns(2)
        with irs_c1:
            k_irs = st.number_input(
                "k_irs - масштаб спреда IRS", value=3.0, min_value=0.1, step=0.1,
                help="spread_bps(t) = max(k_irs × σ_rate_bps(t) × √tenor, floor_bps).",
            )
        with irs_c2:
            floor_spread_bps = st.number_input(
                "floor_bps - минимальный спред IRS (б.п.)", value=2.0, min_value=0.1, step=0.5,
                help="Нижняя граница bid-ask спреда IRS в базисных пунктах.",
            )

    st.subheader("Средний дневной объём торгов (ADV)")
    st.caption("0, чтобы не учитывать поправку на размер позиции.")
    unique_pairs = sorted({
        inst.currency.value if isinstance(inst, InterestRateSwap) else inst.currency_pair.value
        for inst in supported
    })
    adv_cols = st.columns(max(len(unique_pairs), 1))
    raw_adv: dict = {}
    for i, pair in enumerate(unique_pairs):
        with adv_cols[i]:
            raw_adv[pair] = st.number_input(pair, min_value=0.0, value=0.0, step=1_000_000.0, format="%.0f")
    avg_daily_volume = {k_: v for k_, v in raw_adv.items() if v > 0}

    return k, floor_spread, alpha, lambda_, T, avg_daily_volume, k_irs, floor_spread_bps


def render_csv_inputs(supported: list) -> int:
    """Auto-load liquidity batch files for the current portfolio from data/liquidity/.

    Stores loaded DataFrame in session_state['lvar_liquidity_df'].
    Returns T (liquidation days).
    """
    T = st.number_input(
        "T - дней на ликвидацию", value=1, min_value=1, max_value=30,
        key="lvar_csv_T",
        help="Масштабирующий T-фактор: sqrt((1+T)(1+2T) / (6T)).",
    )

    data_dir = st.session_state.get("data_dir", "src/data")
    liq_dir = liquidity_dir_path(data_dir)

    index_path = os.path.join(liq_dir, "index.csv")
    if not os.path.exists(index_path):
        st.warning(
            f"Файл index.csv не найден в {liq_dir}. "
            "Запустите `python utils/split_liquidity.py` для генерации файлов."
        )
        st.session_state.pop("lvar_liquidity_df", None)
        return int(T)

    try:
        liq_df = load_for_portfolio(liq_dir, supported)
        if liq_df.empty:
            st.info("Ни один файл не содержит котировок для инструментов портфеля.")
            st.session_state.pop("lvar_liquidity_df", None)
        else:
            st.session_state["lvar_liquidity_df"] = liq_df
            _render_csv_preview(liq_df, supported)
    except Exception as e:
        st.error(f"Ошибка загрузки ликвидности: {e}")
        st.session_state.pop("lvar_liquidity_df", None)
        with st.expander("Детали ошибки"):
            st.code(traceback.format_exc())

    return int(T)


def _render_csv_preview(liq_df: pd.DataFrame, supported: list) -> None:
    """Show matched tickers summary and warn about unmatched portfolio pairs."""
    _IRS_OIS_RE = r"_(?:OIS|IRS)_"

    fx_supported = [i for i in supported if hasattr(i, "currency_pair")]
    irs_supported = [i for i in supported if isinstance(i, InterestRateSwap)]

    def _pretty(ticker: str) -> str:
        return ticker.replace("_", " ")

    # --- FX section ---
    if fx_supported:
        portfolio_pairs = {inst.currency_pair.value.replace("/", "") for inst in fx_supported}
        fx_df = liq_df[~liq_df["ticker"].str.contains(_IRS_OIS_RE, regex=True, na=False)]
        csv_pairs = {t.split("_")[0] for t in fx_df["ticker"].tolist()}
        matched_pairs = portfolio_pairs & csv_pairs
        unmatched_pairs = portfolio_pairs - csv_pairs

        st.markdown("**Сопоставленные FX инструменты:**")
        matched_df = fx_df[fx_df["ticker"].str.split("_").str[0].isin(matched_pairs)]

        if "date" in matched_df.columns:
            summary = (
                matched_df.groupby("ticker")["spread_pct"]
                .agg(mean="mean", last="last", count="count")
                .reset_index()
                .rename(columns={"mean": "Средний спред", "last": "Последний спред", "count": "Дней"})
            )
            st.dataframe(
                summary.set_index("ticker").style.format({
                    "Средний спред": "{:.4%}", "Последний спред": "{:.4%}", "Дней": "{:.0f}",
                }),
                width="stretch",
            )
        else:
            st.dataframe(
                matched_df.reset_index(drop=True).style.format(
                    {"bid": "{:.4f}", "ask": "{:.4f}", "spread_pct": "{:.4%}"}
                ),
                width="stretch",
            )

        if unmatched_pairs:
            st.warning(
                f"Пары не найдены в CSV (будет использована параметрическая модель): "
                f"{', '.join(sorted(unmatched_pairs))}"
            )

    # --- IRS / OIS section ---
    if irs_supported:
        irs_df = liq_df[liq_df["ticker"].str.contains(_IRS_OIS_RE, regex=True, na=False)].copy()
        csv_irs_tickers = set(irs_df["ticker"].tolist())

        matched_irs = [
            i for i in irs_supported
            if any(re.match(rf"{i.currency.value}_(OIS|IRS)_", t) for t in csv_irs_tickers)
        ]
        unmatched_irs = [i for i in irs_supported if i not in matched_irs]

        if not irs_df.empty:
            # s_bps = (ask - bid) * 10_000 — absolute spread, valid even near zero rates
            irs_df = irs_df.assign(s_bps=(irs_df["ask"] - irs_df["bid"]) * 10_000)
            st.markdown("**IRS/OIS спреды bid/ask:**")
            if "date" in irs_df.columns:
                irs_summary = (
                    irs_df.groupby("ticker")["s_bps"]
                    .agg(mean="mean", last="last", count="count")
                    .reset_index()
                    .rename(columns={"mean": "Средний спред", "last": "Последний спред", "count": "Дней"})
                )
                irs_summary["ticker"] = irs_summary["ticker"].apply(_pretty)
                st.dataframe(
                    irs_summary.set_index("ticker").style.format({
                        "Средний спред": "{:.2f}", "Последний спред": "{:.2f}", "Дней": "{:.0f}",
                    }),
                    width="stretch",
                )
            else:
                display_df = irs_df[["ticker", "bid", "ask", "s_bps"]].copy()
                display_df = display_df.rename(columns={"s_bps": "Спред (bps)"})
                display_df["ticker"] = display_df["ticker"].apply(_pretty)
                st.dataframe(
                    display_df.reset_index(drop=True).style.format(
                        {"bid": "{:.6f}", "ask": "{:.6f}", "Спред (bps)": "{:.2f}"}
                    ),
                    width="stretch",
                )

        if unmatched_irs:
            st.warning(
                f"IRS/OIS без котировок в CSV (будет использована параметрическая модель): "
                f"{', '.join(i.instrument_id for i in unmatched_irs)}"
            )
