import streamlit as st
from ui.sidebar import render_add_instrument_form
from ui.table_view import render_portfolio_table

st.title("💼 Управление портфелем")

# Инициализация session_state
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = []
if 'show_add_form' not in st.session_state:
    st.session_state.show_add_form = False

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
else:
    st.info("Портфель пуст")