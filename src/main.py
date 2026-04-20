import streamlit as st
from datetime import date

from utils.DataProvider import DataProvider
from iolib.report_builder import ReportBuilder
from utils.bootstrap_test_data import bootstrap_test_data

# Инициализация состояния (обязательно до навигации)
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = []
if 'data_dir' not in st.session_state:
    st.session_state.data_dir = "src/data"
if 'valuation_date' not in st.session_state:
    st.session_state.valuation_date = date.today()
if 'data_provider' not in st.session_state:
    st.session_state.data_provider = DataProvider(input_dir=st.session_state.data_dir)

# Для отключения тестовой инициализации закомментируйте следующую строку.
bootstrap_test_data(st.session_state)

if 'report_builder' not in st.session_state:
    st.session_state.report_builder = ReportBuilder()

# Определяем страницы
portfolio_page = st.Page(
    "ui/portfolio_page.py", 
    title="Портфель", 
    icon="💼", 
    default=True
)
var_page = st.Page(
    "ui/var_page.py",
    title="Расчет VaR",
    icon="📉"
)
portfolio_var_page = st.Page(
    "ui/portfolio_var_page.py",
    title="VaR портфеля",
    icon="📊"
)
lvar_page = st.Page(
    "ui/lvar_page.py",
    title="LVaR портфеля",
    icon="💧"
)

# Создаем навигацию
pg = st.navigation([portfolio_page, var_page, portfolio_var_page, lvar_page])

# Запускаем приложение
pg.run()