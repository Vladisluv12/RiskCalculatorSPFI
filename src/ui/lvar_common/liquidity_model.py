"""
Strategy pattern for liquidity model UI.

Two concrete implementations:
  ParametricLiquidityModel — EWMA-based spread estimation
  CsvLiquidityModel        — observed bid/ask spreads from batch files
"""

import os
import re
import traceback
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import pandas as pd
import streamlit as st

from instruments.IRSwap import InterestRateSwap
from utils.liquidity_io import liquidity_dir_path, load_for_portfolio


@dataclass
class LiquidityModelParams:
    T: int = 1
    k: float = 3.0
    floor_spread: float = 0.001
    alpha: float = 0.10
    lambda_: float = 0.94
    avg_daily_volume: dict = field(default_factory=dict)
    k_irs: float = 3.0
    floor_spread_bps: float = 2.0


class LiquidityModel(ABC):
    label: str

    @abstractmethod
    def render_description(self) -> None:
        """Render model description (called inside the 'Описание модели' expander)."""

    @abstractmethod
    def render_formulas(self) -> None:
        """Render LC / LVaR formula recap (called from the results section)."""

    @abstractmethod
    def render_inputs(self, supported: list) -> LiquidityModelParams:
        """Render input widgets and return collected parameters."""


# ---------------------------------------------------------------------------
# Parametric implementation
# ---------------------------------------------------------------------------

class ParametricLiquidityModel(LiquidityModel):
    label = "Параметрическая модель"

    def render_description(self) -> None:
        st.markdown(r"""
Спред bid/ask моделируется как случайная величина, зависящая от волатильности инструмента.
Liquidity cost - стоимость закрытия позиции через рынок.

---

**EWMA-волатильность**: $\sigma^2(t) = \lambda\,\sigma^2(t-1) + (1-\lambda)\,r^2(t)$

**Спред (FX)**: $s\%(t) = \max\!\bigl(k \cdot \sigma_\text{ewma}(t) \cdot \sqrt{\text{tenor}},\; s_\text{floor}\bigr)$

**Спред (IRS)**: $s_{bps}(t) = \max\!\bigl(k_{irs} \cdot \sigma_{rate,bps}(t) \cdot \sqrt{\text{tenor}},\; s_{\text{floor,bps}}\bigr)$

**LC (FX)**: $LC = \tfrac{1}{2}|PV| \cdot s\%$; $\quad LC_\text{stressed} = \tfrac{1}{2}|PV|(s\% + z_\alpha\,\sigma_{s\%})$

**LC (IRS)**: $LC = \tfrac{1}{2}\cdot DV01 \cdot s_{bps}$; $\quad LC_\text{stressed} = \tfrac{1}{2}\cdot DV01\cdot(s_{bps}+z_\alpha\,\sigma_{s_{bps}})$

**LVaR**: $LVaR_T = \dfrac{VaR + LC}{\sqrt{(1+T)(1+2T)/6T}}$
        """)

    def render_formulas(self) -> None:
        st.latex(r"LC^{FX} = \frac{1}{2}\,|PV|\cdot s\%")
        st.latex(r"LC^{IRS} = \frac{1}{2}\,DV01\cdot s_{bps}\quad(\text{руб.})")
        st.latex(r"LVaR_T = \frac{VaR + LC}{\sqrt{\dfrac{(1+T)(1+2T)}{6T}}}")

    def render_inputs(self, supported: list) -> LiquidityModelParams:
        st.subheader("Параметры ликвидности")
        lc1, lc2, lc3 = st.columns(3)
        with lc1:
            k = st.number_input(
                "k - масштаб спреда", value=3.0, min_value=0.1, step=0.1,
                help="Калибровочный коэффициент: s%(t) = max(k × σ_ewma(t) × √tenor, s_floor).",
            )
            floor_spread = st.number_input(
                "s_floor - минимальный спред", value=0.001, min_value=0.0001, step=0.0001, format="%.4f",
                help="Нижняя граница спреда. 10 bps = 0.001, 50 bps = 0.005.",
            )
        with lc2:
            alpha = st.number_input(
                "alpha - асимметрия BUY/SELL", value=0.10, min_value=0.0, max_value=0.5, step=0.01,
                help="BUY: спред × (1+alpha), SELL: спред × (1−alpha). При alpha=0 — без асимметрии.",
            )
            lambda_ = st.number_input(
                "lambda - коэффициент затухания EWMA", value=0.94, min_value=0.50, max_value=0.999, step=0.01,
                help="σ²(t) = λ·σ²(t-1) + (1−λ)·r²(t). Стандарт RiskMetrics — 0.94.",
            )
        with lc3:
            T = st.number_input(
                "T - дней на ликвидацию", value=1, min_value=1, max_value=30,
                help="Масштабирующий T-фактор: √((1+T)(1+2T) / (6T)).",
            )

        has_irs = any(isinstance(inst, InterestRateSwap) for inst in supported)
        k_irs = 3.0
        floor_spread_bps = 2.0
        if has_irs:
            st.subheader("Параметры ликвидности IRS")
            st.caption(
                "Спред в б.п., LC в рублях: LC = ½ × DV01 × spread_bps "
                "(DV01 в руб./б.п., LC в руб.)."
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
                raw_adv[pair] = st.number_input(
                    pair, min_value=0.0, value=0.0, step=1_000_000.0, format="%.0f",
                )
        avg_daily_volume = {k_: v for k_, v in raw_adv.items() if v > 0}

        return LiquidityModelParams(
            T=int(T),
            k=k, floor_spread=floor_spread, alpha=alpha, lambda_=lambda_,
            avg_daily_volume=avg_daily_volume,
            k_irs=k_irs, floor_spread_bps=floor_spread_bps,
        )


# ---------------------------------------------------------------------------
# CSV implementation
# ---------------------------------------------------------------------------

def _render_csv_preview(liq_df: pd.DataFrame, supported: list) -> None:
    """Show matched tickers summary and warn about unmatched portfolio pairs."""
    _IRS_OIS_RE = r"_(?:OIS|IRS)_"
    fx_supported = [i for i in supported if hasattr(i, "currency_pair")]
    irs_supported = [i for i in supported if isinstance(i, InterestRateSwap)]

    def _pretty(ticker: str) -> str:
        return ticker.replace("_", " ")

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
                f"Пары не найдены в CSV (параметрическая модель): "
                f"{', '.join(sorted(unmatched_pairs))}"
            )

    if irs_supported:
        irs_df = liq_df[liq_df["ticker"].str.contains(_IRS_OIS_RE, regex=True, na=False)].copy()
        csv_irs_tickers = set(irs_df["ticker"].tolist())
        matched_irs = [
            i for i in irs_supported
            if any(re.match(rf"{i.currency.value}_(OIS|IRS)_", t) for t in csv_irs_tickers)
        ]
        unmatched_irs = [i for i in irs_supported if i not in matched_irs]

        if not irs_df.empty:
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
                display_df = irs_df[["ticker", "bid", "ask", "s_bps"]].rename(
                    columns={"s_bps": "Спред (bps)"}
                ).copy()
                display_df["ticker"] = display_df["ticker"].apply(_pretty)
                st.dataframe(
                    display_df.reset_index(drop=True).style.format(
                        {"bid": "{:.6f}", "ask": "{:.6f}", "Спред (bps)": "{:.2f}"}
                    ),
                    width="stretch",
                )
        if unmatched_irs:
            st.warning(
                f"IRS/OIS без котировок в CSV (параметрическая модель): "
                f"{', '.join(i.instrument_id for i in unmatched_irs)}"
            )


class CsvLiquidityModel(LiquidityModel):
    label = "CSV-файл со спредами"

    def render_description(self) -> None:
        pass  # No expander shown for CSV mode

    def render_formulas(self) -> None:
        st.latex(r"LC^{FX} = \frac{1}{2}\,|PV|\cdot s\%,\quad"
                 r" s\% = \frac{ask - bid}{mid}")
        st.latex(r"LC^{IRS} = \frac{1}{2}\,DV01\cdot s_{bps}\quad(\text{руб.}),\quad"
                 r" s_{bps} = (ask - bid)\times 10^4")
        st.latex(r"LC_\text{stressed} = \frac{1}{2}\,(\bar{s} + z_\alpha\,\sigma_s)")
        st.latex(r"LVaR_T = \frac{VaR + LC}{\sqrt{\dfrac{(1+T)(1+2T)}{6T}}}")

    def render_inputs(self, supported: list) -> LiquidityModelParams:
        T = st.number_input(
            "T - дней на ликвидацию", value=1, min_value=1, max_value=30,
            key="lvar_csv_T",
            help="Масштабирующий T-фактор: √((1+T)(1+2T) / (6T)).",
        )

        default_liq_dir = liquidity_dir_path(
            st.session_state.get("data_dir", "src/data")
        )
        liq_dir = st.text_input(
            "Папка с данными ликвидности",
            value=default_liq_dir,
            key="lvar_liq_dir",
            help="Путь к папке, содержащей index.csv и файлы fx_*.csv / irs_*.csv.",
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
                raw_adv[pair] = st.number_input(
                    pair, min_value=0.0, value=0.0, step=1_000_000.0, format="%.0f",
                    key=f"lvar_csv_adv_{pair}",
                )
        avg_daily_volume = {k: v for k, v in raw_adv.items() if v > 0}

        index_path = os.path.join(liq_dir, "index.csv")
        if not os.path.exists(index_path):
            st.warning(
                f"Файл `index.csv` не найден в `{liq_dir}`. "
                "Запустите `python utils/split_liquidity.py` для генерации батч-файлов."
            )
            st.session_state.pop("lvar_liquidity_df", None)
            return LiquidityModelParams(T=int(T), avg_daily_volume=avg_daily_volume)

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

        return LiquidityModelParams(T=int(T), avg_daily_volume=avg_daily_volume)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

MODELS: list[LiquidityModel] = [ParametricLiquidityModel(), CsvLiquidityModel()]
MODELS_BY_LABEL: dict[str, LiquidityModel] = {m.label: m for m in MODELS}
