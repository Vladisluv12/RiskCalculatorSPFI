import traceback
import pandas as pd
import streamlit as st
import compute.risk.civar as var


def render_ivar_cvar_section(
    data_provider,
    var_instruments: list,
    calc_start,
    calc_end,
    individual_vars: dict,
    pnl_matrix,
    recommended: str,
    recommended_var_value: float,
    conf_level: float,
    window: int,
    horizon: int,
    method_key: str,
    params_key: tuple,
) -> "pd.DataFrame | None":
    """
    Renders the IVaR/CVaR subsection for the portfolio VaR page.

    Shows stale warning if params changed, a calculate button, and if results
    exist in session_state renders the contributions dataframe.

    Returns contrib_df if available, else None.
    """
    st.subheader("Вклад инструментов в риск портфеля")
    st.latex(r"CVaR_i = \rho_{i,P} \cdot VaR_i, \quad \sum_i CVaR_i \approx VaR_{portfolio}")
    st.latex(r"IVaR_i = VaR_{portfolio} - VaR_{portfolio \setminus i}")

    _contrib_stale = (
        "pvar_contrib" in st.session_state
        and st.session_state["pvar_contrib"].get("_params_key") != params_key
    )
    if _contrib_stale:
        st.warning("Параметры изменились — CVaR/IVaR устарели. Нажмите «Рассчитать IVaR и CVaR» для обновления.")

    if st.button("Рассчитать IVaR и CVaR"):
        try:
            with st.spinner("Расчёт..."):
                cvar_dict = var.compute_cvar(pnl_matrix, individual_vars)
                ivar_dict = var.portfolio_ivar(
                    data_provider, var_instruments, calc_start, calc_end,
                    confidence_level=conf_level, window=window, horizon=int(horizon),
                    method=method_key, recommended_var_type=recommended, var_full=recommended_var_value,
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
            st.session_state["pvar_contrib"] = {
                "_params_key": params_key,
                "contrib_df": pd.DataFrame(contrib_rows).set_index("Инструмент"),
                "cvar_sum": sum(cvar_dict.values()),
            }
            st.rerun()
        except Exception as exc:
            st.error(f"Ошибка расчета CVaR/IVaR: {exc.__class__.__name__}: {exc}")
            with st.expander("Детали ошибки"):
                st.code(traceback.format_exc())

    contrib_df = None
    if "pvar_contrib" in st.session_state:
        contrib_df = st.session_state["pvar_contrib"]["contrib_df"]
        cvar_sum = st.session_state["pvar_contrib"]["cvar_sum"]
        st.dataframe(
            contrib_df.style.format({
                "VaR_i": "{:.4f}", "CVaR_i": "{:.4f}",
                "CVaR_i %": "{:.1f}%", "IVaR_i": "{:.4f}", "IVaR_i %": "{:.1f}%",
            }),
            width="stretch",
        )
        st.caption(f"Сумма CVaR: {cvar_sum:.4f}")

    return contrib_df
