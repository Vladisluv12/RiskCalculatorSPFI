import streamlit as st
from ui.sidebar import render_add_forward_form
from ui.table_view import render_portfolio_table

st.set_page_config(page_title="Terminal SPFI", layout="wide")

# Инициализируем состояние формы и портфеля
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = []
if 'show_add_form' not in st.session_state:
    st.session_state.show_add_form = False

# Шапка и кнопка добавления
col_title, col_btn = st.columns([0.8, 0.2])
with col_title:
    st.title("📊 Портфель форвардных контрактов")

with col_btn:
    # При нажатии меняем флаг на True
    if st.button("➕ Добавить актив", use_container_width=True):
        st.session_state.show_add_form = True
        st.rerun()

# Если флаг True — отрисовываем сайдбар
if st.session_state.show_add_form:
    new_contract = render_add_forward_form()
    
    # Если контракт получен (нажата кнопка "Сохранить")
    if new_contract:
        st.session_state.portfolio.append(new_contract)
        st.session_state.show_add_form = False # Закрываем после сохранения
        st.toast("Контракт добавлен!")
        st.rerun()

# Отрисовка таблицы
render_portfolio_table(st.session_state.portfolio)