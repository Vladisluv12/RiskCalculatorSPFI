import streamlit as st
from datetime import date

from ui.sidebar import render_add_instrument_form, render_report_sidebar
from ui.table_view import render_portfolio_table
from utils.DataProvider import DataProvider
from iolib.serializers import SERIALIZERS, FORMAT_LABELS
from iolib.portfolio_io import PortfolioImporter, PortfolioExporter
render_report_sidebar()

st.title("💼 Управление портфелем")

# Инициализация session_state
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = []
if 'show_add_form' not in st.session_state:
    st.session_state.show_add_form = False
if 'valuation_date' not in st.session_state:
    st.session_state.valuation_date = date.today()
if 'data_dir' not in st.session_state:
    st.session_state.data_dir = "src/data"

st.subheader("Параметры данных")
cfg_col1, cfg_col2, cfg_col3 = st.columns([1, 2, 1])

with cfg_col1:
    valuation_date = st.date_input("Дата расчета", value=st.session_state.valuation_date)
with cfg_col2:
    data_dir = st.text_input("Папка с данными", value=st.session_state.data_dir)
with cfg_col3:
    st.write("")
    st.write("")
    apply_settings = st.button("Применить")

if apply_settings:
    try:
        st.session_state.data_provider = DataProvider(input_dir=data_dir)
        st.session_state.data_dir = data_dir
        st.session_state.valuation_date = valuation_date
        st.success("Параметры обновлены.")
    except Exception as exc:
        st.error(f"Не удалось обновить источник данных: {exc}")

st.caption(f"Текущая дата расчета: {st.session_state.valuation_date}")
st.caption(f"Текущая папка данных: {st.session_state.data_dir}")

st.divider()

# ── Импорт портфеля ──────────────────────────────────────────────────────────
with st.expander("📥 Импорт портфеля из файла"):
    import_fmt = st.selectbox("Формат", FORMAT_LABELS, key="import_fmt")
    uploaded = st.file_uploader(
        "Загрузить файл",
        type=["json", "yaml", "yml", "csv", "xlsx"],
        key="portfolio_upload",
    )
    if st.button("Загрузить в портфель") and uploaded is not None:
        raw = uploaded.read()
        instruments, errors = PortfolioImporter(SERIALIZERS[import_fmt]).load(raw)
        if instruments:
            st.session_state.portfolio.extend(instruments)
            st.success(f"Загружено инструментов: {len(instruments)}")
        if errors:
            st.warning(f"Пропущено строк с ошибками: {len(errors)}")
            with st.expander("Детали ошибок"):
                for e in errors:
                    st.text(e)
        if instruments:
            st.rerun()

# ── Экспорт портфеля ─────────────────────────────────────────────────────────
if st.session_state.get("portfolio"):
    with st.expander("📤 Экспорт портфеля"):
        export_fmt = st.selectbox("Формат", FORMAT_LABELS, key="export_fmt")
        serializer = SERIALIZERS[export_fmt]
        raw = PortfolioExporter(serializer).save(st.session_state.portfolio)
        st.download_button(
            label=f"Скачать портфель (.{serializer.file_extension})",
            data=raw,
            file_name=f"portfolio.{serializer.file_extension}",
            mime=serializer.mime_type,
        )

# Кнопка добавления актива
if st.button("➕ Добавить актив"):
    st.session_state.show_add_form = True

if st.session_state.get('show_add_form'):
    new_instrument = render_add_instrument_form()
    if new_instrument:
        st.session_state.portfolio.append(new_instrument)
        st.session_state.show_add_form = False
        st.rerun()

# Таблица
if st.session_state.portfolio:
    render_portfolio_table(st.session_state.portfolio)
    
    # Кнопка перехода на VaR
    if len(st.session_state.portfolio) > 0:
        selected_id = st.selectbox(
            "Выберите инструмент для анализа",
            [c.instrument_id for c in st.session_state.portfolio]
        )
        if st.button("Перейти к расчету VaR"):
            st.session_state.selected_id = selected_id
            st.switch_page("ui/var_page.py")
        if st.button("📊 Перейти к расчету VaR портфеля"):
            st.switch_page("ui/portfolio_var_page.py")
else:
    st.info("Портфель пуст")