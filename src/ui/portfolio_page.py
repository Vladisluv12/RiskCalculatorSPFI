import streamlit as st
from ui.sidebar import render_add_forward_form
from ui.table_view import render_portfolio_table

st.title("💼 Управление портфелем")

# Кнопка добавления актива
if st.button("➕ Добавить актив"):
    st.session_state.show_add_form = True

if st.session_state.get('show_add_form'):
    new_instrument = render_add_forward_form()
    if new_instrument:
        st.session_state.portfolio.append(new_instrument)
        st.session_state.show_add_form = False
        st.rerun()

# Таблица
if st.session_state.portfolio:
    render_portfolio_table(st.session_state.portfolio)
    
    # Кнопка перехода на VaR
    selected_id = st.selectbox("Выберите инструмент для анализа", [c.instrument_id for c in st.session_state.portfolio])
    if st.button("Перейти к расчету VaR"):
        st.session_state.selected_id = selected_id
        st.switch_page("ui/var_page.py") # Программное переключение
else:
    st.info("Портфель пуст")