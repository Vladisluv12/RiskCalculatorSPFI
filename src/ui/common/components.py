import streamlit as st
from iolib.serializers import SERIALIZERS, FORMAT_LABELS
from iolib.results_exporter import ResultsExporter


def render_var_params(key_prefix: str = "") -> tuple:
    """Renders the standard VaR parameter widgets and returns (type_of_var, conf_level, horizon, window)."""
    row1_col1, row1_col2, row1_col3 = st.columns(3)
    with row1_col1:
        type_of_var = st.selectbox(
            "Метод расчета VaR",
            options=["Исторический", "Параметрический"],
            index=0,
            key=f"{key_prefix}type_of_var" if key_prefix else None,
        )
    with row1_col2:
        conf_level = st.selectbox(
            "Доверительный уровень",
            options=[0.95, 0.975, 0.99],
            index=0,
            key=f"{key_prefix}conf_level" if key_prefix else None,
        )
    with row1_col3:
        horizon = st.number_input(
            "Горизонт прогноза",
            min_value=1,
            max_value=30,
            value=1,
            key=f"{key_prefix}horizon" if key_prefix else None,
        )

    window = st.slider(
        "Количество дней в истории",
        min_value=252,
        max_value=2520,
        value=252,
        step=252,
        key=f"{key_prefix}window" if key_prefix else None,
    )

    if horizon > 10:
        st.warning(
            f"Горизонт прогноза {horizon} дн. выходит за пределы стандартного "
            "регуляторного диапазона (Basel III: 10 дней, МосБиржа: 1 день). "
            "Используйте значение > 10 только для внутренней аналитики."
        )

    return type_of_var, conf_level, horizon, window


def render_export_download(data: dict, file_prefix: str, fmt_key: str) -> None:
    """Renders a 2-column row: format selectbox on the left, download_button on the right."""
    exp_col1, exp_col2 = st.columns([1, 2])
    with exp_col1:
        res_fmt = st.selectbox("Формат", FORMAT_LABELS, key=fmt_key)
    serializer = SERIALIZERS[res_fmt]
    raw_res = ResultsExporter(serializer).export(data)
    with exp_col2:
        st.write("")
        st.write("")
        st.download_button(
            label=f"Скачать результаты (.{serializer.file_extension})",
            data=raw_res,
            file_name=f"{file_prefix}.{serializer.file_extension}",
            mime=serializer.mime_type,
        )


def render_report_toggle(page_id: str, section_title: str, data: dict, btn_key: str) -> None:
    """Renders the 'Добавить в отчёт' / 'Убрать из отчёта' toggle button."""
    rb = st.session_state.get("report_builder")
    if rb is not None:
        in_report = rb.has_section(page_id)
        label = "Убрать из отчёта" if in_report else "Добавить в отчёт"
        if st.button(label, key=btn_key):
            if in_report:
                rb.remove_section(page_id)
            else:
                rb.add_section(page_id, section_title, data)
            st.rerun()
