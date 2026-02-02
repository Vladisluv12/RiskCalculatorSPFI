import streamlit as st

# Инициализация состояния (обязательно до навигации)
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = []

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

# Создаем навигацию
pg = st.navigation([portfolio_page, var_page])

# Запускаем приложение
pg.run()