import streamlit as st
from datetime import date

from ui.sidebar import render_add_instrument_form, render_report_sidebar
from ui.table_view import render_portfolio_table
from utils.DataProvider import DataProvider
from iolib.serializers import SERIALIZERS, FORMAT_LABELS, EXT_TO_SERIALIZER
from iolib.portfolio_io import PortfolioImporter, PortfolioExporter
render_report_sidebar()

st.title("💼 Управление портфелем")

if 'portfolio' not in st.session_state:
    st.session_state.portfolio = []
if 'show_add_form' not in st.session_state:
    st.session_state.show_add_form = False
if 'show_import' not in st.session_state:
    st.session_state.show_import = False
if 'show_export' not in st.session_state:
    st.session_state.show_export = False
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

if st.button("➕ Добавить актив"):
    st.session_state.show_add_form = True

if st.session_state.get('show_add_form'):
    new_instrument = render_add_instrument_form()
    if new_instrument:
        st.session_state.portfolio.append(new_instrument)
        st.session_state.show_add_form = False
        st.rerun()

if st.session_state.portfolio:
    render_portfolio_table(st.session_state.portfolio)

    # ── Панель импорта ────────────────────────────────────────────────────────
    if st.session_state.get('show_import'):
        uploaded = st.file_uploader(
            "Выберите файл портфеля",
            type=list(EXT_TO_SERIALIZER.keys()),
            key="portfolio_upload",
        )
        if uploaded is not None:
            ext = uploaded.name.rsplit(".", 1)[-1].lower()
            serializer = EXT_TO_SERIALIZER.get(ext)
            if serializer is None:
                st.error(f"Неподдерживаемый формат файла: .{ext}")
            else:
                try:
                    raw = uploaded.read()
                    instruments, errors = PortfolioImporter(serializer).load(raw)
                    if instruments:
                        st.session_state.portfolio.extend(instruments)
                        st.success(f"Загружено инструментов: {len(instruments)}")
                    for e in errors:
                        st.error(e)
                    if not instruments and not errors:
                        st.warning("Файл не содержит инструментов.")
                    if instruments:
                        st.session_state.show_import = False
                        st.rerun()
                except Exception as exc:
                    st.error(f"Не удалось загрузить файл: {exc}")

    # ── Панель экспорта ───────────────────────────────────────────────────────
    if st.session_state.get('show_export'):
        exp_col1, exp_col2 = st.columns([1, 3])
        with exp_col1:
            export_fmt = st.selectbox("Формат", FORMAT_LABELS, key="export_fmt")
        serializer = SERIALIZERS[export_fmt]
        raw_export = PortfolioExporter(serializer).save(st.session_state.portfolio)
        with exp_col2:
            st.write("")
            st.download_button(
                label=f"⬇ Скачать портфель (.{serializer.file_extension})",
                data=raw_export,
                file_name=f"portfolio.{serializer.file_extension}",
                mime=serializer.mime_type,
            )

    # ── Навигация ─────────────────────────────────────────────────────────────
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

    # Импорт доступен и когда портфель пуст
    if st.session_state.get('show_import'):
        uploaded = st.file_uploader(
            "Выберите файл портфеля",
            type=list(EXT_TO_SERIALIZER.keys()),
            key="portfolio_upload_empty",
        )
        if uploaded is not None:
            ext = uploaded.name.rsplit(".", 1)[-1].lower()
            serializer = EXT_TO_SERIALIZER.get(ext)
            if serializer is None:
                st.error(f"Неподдерживаемый формат файла: .{ext}")
            else:
                try:
                    raw = uploaded.read()
                    instruments, errors = PortfolioImporter(serializer).load(raw)
                    if instruments:
                        st.session_state.portfolio.extend(instruments)
                        st.success(f"Загружено инструментов: {len(instruments)}")
                    for e in errors:
                        st.error(e)
                    if not instruments and not errors:
                        st.warning("Файл не содержит инструментов.")
                    if instruments:
                        st.session_state.show_import = False
                        st.rerun()
                except Exception as exc:
                    st.error(f"Не удалось загрузить файл: {exc}")
    else:
        if st.button("📥 Импорт портфеля"):
            st.session_state.show_import = True
            st.rerun()
