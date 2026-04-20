import traceback

import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go  # type: ignore
from dataclasses import replace
from datetime import datetime, time, timedelta

import compute.risk.var as var
from instruments.FXForward import CurrencyForwardContract
from instruments.FXSwap import CurrencySwapContract
from ui.sidebar import render_report_sidebar
from io.serializers import SERIALIZERS, FORMAT_LABELS
from io.results_exporter import ResultsExporter
render_report_sidebar()

st.title("📉 Анализ рисков (VaR)")

# Проверяем, выбран ли конкретный инструмент
selected_id = st.session_state.get('selected_id')

if selected_id:
    selected_instrument = next(
        (inst for inst in st.session_state.get('portfolio', []) if inst.instrument_id == selected_id),
        None
    )

    valuation_date = st.session_state.get('valuation_date')
    if valuation_date is None:
        valuation_date = datetime.today().date()

    if isinstance(selected_instrument, CurrencyForwardContract) or isinstance(selected_instrument, CurrencySwapContract):
        contract_start_date = selected_instrument.start_date.date()
    else:
        contract_start_date = valuation_date

    st.info(f"Анализ для инструмента: **{selected_id}**")
    st.subheader("Параметры расчета")
    row1_col1, row1_col2, row1_col3 = st.columns(3)

    with row1_col1:
        type_of_var = st.selectbox("Метод расчета VaR", options=["Исторический", "Параметрический"], index=0)
    with row1_col2:
        conf_level = st.selectbox("Доверительный уровень", options=[0.95, 0.99], index=0)
    with row1_col3:
        horizon = st.number_input("Горизонт прогноза", min_value=1, max_value=30, value=1)

    window = st.slider(
        "Количество дней в истории",
        min_value=252,
        max_value=2520,
        value=252,
        step=252,
    )

    calc_end_date = contract_start_date - timedelta(days=1)
    calc_start_date = calc_end_date - timedelta(days=int(window))

    row2_col1, row2_col2 = st.columns(2)
    with row2_col1:
        st.date_input("Дата начала расчета", value=calc_start_date, disabled=True)
    with row2_col2:
        st.date_input("Дата конца расчета", value=calc_end_date, disabled=True)

    range_days = (calc_end_date - calc_start_date).days
    if range_days < 0:
        st.error("Количество дней в истории не может быть отрицательным.")
        st.stop()
    
    st.divider()

    if selected_instrument is None:
        st.error("Выбранный инструмент не найден в портфеле.")
    elif not isinstance(selected_instrument, CurrencyForwardContract) and not isinstance(selected_instrument, CurrencySwapContract):
        st.warning("Расчет VaR сейчас доступен только для валютных форвардов и свопов.")
    else:
        try:
            data_provider = st.session_state.get('data_provider')
            if data_provider is None:
                st.error("Источник данных не инициализирован. Перейдите на страницу портфеля и нажмите 'Применить'.")
                st.stop()

            calc_start = datetime.combine(calc_start_date, time.min)
            calc_end = datetime.combine(calc_end_date, time.max)
            span_days = max(1, (calc_end_date - calc_start_date).days)

            # Ограничиваем длину PV-истории так, чтобы функция historical не падала на проверке window.
            var_instrument = replace(
                selected_instrument,
                start_date=calc_start,
                end_date=calc_end + timedelta(days=max(1, int(horizon)))
            )

            var_cutoff = np.nan
            es_cutoff = np.nan

            if type_of_var == "Исторический":
                pnl, _ = var.historical(
                    data_provider,
                    var_instrument,
                    calc_start,
                    calc_end,
                    confidence_level=conf_level,
                    window=window,
                )

                scale_span = np.sqrt(span_days)
                scale_horizon = np.sqrt(max(1, int(horizon)))
                pnl = (pnl / scale_span) * scale_horizon
                var_cutoff = pnl.quantile(1 - conf_level).abs().iloc[0]
                var_index = round(len(pnl) * (1 - conf_level))

                alpha = 1 - conf_level
                pnl_col = pnl.iloc[:, 0]
                tail = pnl_col[pnl_col <= float(pnl_col.quantile(alpha))]
                es_cutoff = abs(float(tail.mean())) if not tail.empty else np.nan

                # Создаем гистограмму распределения PnL
                fig = go.Figure()

                fig.add_trace(go.Bar(
                    x=list(range(len(pnl))),
                    y=pnl['price'],
                    name="Отсортированный PnL",
                    hovertemplate="Доходность: %{y:.2%}<extra></extra>"
                ))

                # 4. Вертикальная линия на месте отсечки
                fig.add_vline(
                    x=var_index,
                    line_dash="dash",
                    line_color="black",
                    line_width=2,
                    annotation_text=f"Граница VaR {conf_level * 100:.0f}%",
                    annotation_position="top left"
                )

                # Настройка осей
                fig.update_layout(
                    title=f"Динамика PnL для {selected_id}",
                    xaxis_title="Номер в отсортированной PnL",
                    yaxis_title="PnL (%)",
                    yaxis_tickformat='.4%',
                    template="plotly_white",
                    hovermode="x unified"
                )

                st.plotly_chart(fig, width="stretch")
            else:
                st.latex(r"VaR = \left|\left(-\mu + z_{\alpha}\sigma\right)\sqrt{horizon}\right|")
                raw_var = var.parametric(
                    data_provider,
                    var_instrument,
                    calc_start,
                    calc_end,
                    confidence_level=conf_level,
                    window=window,
                )
                var_cutoff = (raw_var / np.sqrt(span_days)) * np.sqrt(max(1, int(horizon)))
                st.write(f"Параметрический VaR: **{var_cutoff:.4f}**")

                raw_es = var.parametric_es(
                    data_provider,
                    var_instrument,
                    calc_start,
                    calc_end,
                    confidence_level=conf_level,
                    window=window,
                )
                es_cutoff = (raw_es / np.sqrt(span_days)) * np.sqrt(max(1, int(horizon)))
                st.write(f"Параметрический ES: **{es_cutoff:.4f}**")

            # Метрики внизу
            st.divider()
            mc1, mc2 = st.columns(2)
            mc1.metric("Рассчитанный VaR", f"{abs(var_cutoff):.4f}")
            mc2.metric("Рассчитанный ES", f"{abs(es_cutoff):.4f}" if not np.isnan(es_cutoff) else "—")

            st.divider()

            # ── Экспорт результатов ───────────────────────────────────────────
            exp_col1, exp_col2 = st.columns([1, 2])
            with exp_col1:
                res_fmt = st.selectbox("Формат", FORMAT_LABELS, key="var_res_fmt")
            with exp_col2:
                st.write("")
                st.write("")
                results_data = {
                    "pnl": pnl if type_of_var == "Исторический" else pd.DataFrame(),
                    "var": float(abs(var_cutoff)) if not np.isnan(var_cutoff) else 0.0,
                    "es": float(abs(es_cutoff)) if not np.isnan(es_cutoff) else 0.0,
                }
                serializer = SERIALIZERS[res_fmt]
                raw_res = ResultsExporter(serializer).export(results_data)
                st.download_button(
                    label=f"Скачать результаты (.{serializer.file_extension})",
                    data=raw_res,
                    file_name=f"var_{selected_id}.{serializer.file_extension}",
                    mime=serializer.mime_type,
                )

            # ── Добавить в отчёт ─────────────────────────────────────────────
            rb = st.session_state.get("report_builder")
            if rb is not None:
                page_id = f"var_{selected_id}"
                in_report = rb.has_section(page_id)
                label = "✓ Убрать из отчёта" if in_report else "+ Добавить в отчёт"
                if st.button(label, key="var_report_btn"):
                    if in_report:
                        rb.remove_section(page_id)
                    else:
                        rb.add_section(page_id, f"VaR: {selected_id}", results_data)
                    st.rerun()

            st.divider()
            if st.button("Перейти к расчёту VaR портфеля"):
                st.switch_page("ui/portfolio_var_page.py")
        except Exception as exc:
            st.error(f"Ошибка расчета VaR: {exc.with_traceback(None)}")
            err_stack = traceback.format_exc()
            with st.expander("Посмотреть детали ошибки"):
                st.code(err_stack)
else:
    st.warning("Инструмент не выбран. Выберите его на странице портфеля или в списке ниже.")
    # Можно добавить selectbox и здесь