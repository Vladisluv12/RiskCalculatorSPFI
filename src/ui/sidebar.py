import streamlit as st
from datetime import date, datetime
from instruments.FXForward import SpotRateMethod
from instruments.FXForward import CurrencyForwardContract

def render_add_forward_form():
    """Отрисовывает форму добавления форварда в боковой панели."""
    with st.sidebar:
        st.header("⚙️ Параметры контракта")
        # Кнопка закрытия без сохранения
        if st.button("❌ Закрыть меню"):
            st.session_state.show_add_form = False
            st.rerun()
            
        st.divider()
        
        # Используем форму, чтобы данные отправлялись только по нажатию кнопки
        with st.form("forward_form", clear_on_submit=True):
            st.subheader("Основные параметры")
            inst_id = st.text_input("ID инструмента", value=f"FX")
            pair = st.selectbox("Валютная пара", ["USD/RUB", "EUR/RUB", "CNY/RUB", "EUR/USD"])
            
            col1, col2 = st.columns(2)
            direction = col1.selectbox("Направление", ["Buy", "Sell"])
            notional = col2.number_input("Номинал", min_value=0.0, value=100000.0)
            
            rate = st.number_input("Форвардный курс", min_value=0.0, format="%.4f", value=90.0)
            
            start_d = st.date_input("Дата платежа", value=date.today())
            end_d = start_d
            
            st.divider()
            st.subheader("Параметры для NDF")
            is_ndf = st.checkbox("Расчетный (NDF)", value=True)
            method = st.selectbox("Метод фиксации", [m.value for m in SpotRateMethod])
            
            submitted = st.form_submit_button("Добавить в портфель", use_container_width=True)
            
            if submitted:
                # Возвращаем объект контракта
                return CurrencyForwardContract(
                    instrument_id=inst_id + (" Ndf" if is_ndf else " Fwd") + f" {(start_d - datetime.today().date()).days}D",
                    notional=notional,
                    start_date=start_d,
                    end_date=end_d,
                    currency_pair=pair,
                    base_currency=pair.split('/')[0],
                    quote_currency=pair.split('/')[1],
                    direction=direction,
                    forward_rate=rate,
                    spot_rate_method=SpotRateMethod(method),
                    is_ndf=is_ndf
                )
    return None