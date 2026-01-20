import streamlit as st
import pandas as pd
from dataclasses import asdict
from datetime import date, datetime
from src.instruments.FXForward import CurrencyForwardContract, SpotRateMethod

st.set_page_config(page_title="Портфель СПФИ", layout="wide")

# Инициализация хранилища в сессии
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = []

## Заголовок интерфейса
st.title("📊 Управление портфелем СПФИ")

# Разметка: Центральная часть и кнопка добавления
col_main, col_btn = st.columns([0.85, 0.15])

with col_main:
    st.subheader("Текущие контракты в портфеле")

with col_btn:
    # Кнопка для открытия формы добавления
    add_clicked = st.button("➕ Добавить актив")

# --- БОКОВОЕ МЕНЮ (САЙДБАР) ---
if add_clicked or st.session_state.get('show_form', False):
    st.session_state.show_form = True
    
    with st.sidebar:
        st.header("Новый Форвард")
        with st.form("add_instrument_form", clear_on_submit=True):
            # Основные параметры
            id_inst = st.text_input("ID инструмента", value=f"FWD-{datetime.now().strftime('%H%M%S')}")
            pair = st.text_input("Валютная пара", value="USD/RUB")
            
            c1, c2 = st.columns(2)
            base_cur = c1.text_input("Базовая валюта", value="USD")
            quote_cur = c2.text_input("Валюта расчета", value="RUB")
            
            direction = st.selectbox("Направление", ["Buy", "Sell"])
            notional = st.number_input("Номинал (notional)", value=1000.0)
            fwd_rate = st.number_input("Форвардный курс", value=90.0)
            
            st.divider()
            
            # Даты
            d1, d2 = st.columns(2)
            start_dt = d1.date_input("Дата начала", value=date.today())
            end_dt = d2.date_input("Дата окончания", value=date.today())
            pay_dt = st.date_input("Дата платежа", value=date.today())
            
            # Специфические параметры
            is_ndf = st.checkbox("Расчетный (NDF)")
            method = st.selectbox("Метод Spot Rate", [m.value for m in SpotRateMethod])
            
            # Кнопки формы
            submit = st.form_submit_button("Сохранить в портфель")
            cancel = st.form_submit_button("Отмена")

            if submit:
                new_fwd = CurrencyForwardContract(
                    instrument_id=id_inst,
                    base_asset1_id=base_cur,
                    base_asset2_id=quote_cur,
                    notional=notional,
                    start_date=start_dt,
                    end_date=end_dt,
                    payment_date=pay_dt,
                    currency_pair=pair,
                    base_currency=base_cur,
                    quote_currency=quote_cur,
                    direction=direction,
                    nominal_amount_base=notional,
                    forward_rate=fwd_rate,
                    spot_rate_method=SpotRateMethod(method),
                    is_ndf=is_ndf
                )
                st.session_state.portfolio.append(new_fwd)
                st.session_state.show_form = False
                st.rerun()
            
            if cancel:
                st.session_state.show_form = False
                st.rerun()

# --- ОСНОВНАЯ ТАБЛИЦА ---
if st.session_state.portfolio:
    # Превращаем список dataclass в DataFrame для удобного отображения
    df = pd.DataFrame([asdict(i) for i in st.session_state.portfolio])
    
    # Выбираем важные колонки для отображения, чтобы не перегружать экран
    display_cols = ['instrument_id', 'currency_pair', 'direction', 'notional', 'forward_rate', 'payment_date', 'is_ndf']
    st.dataframe(df[display_cols], use_container_width=True, hide_index=True)
    
    # Кнопка очистки
    if st.button("Очистить портфель"):
        st.session_state.portfolio = []
        st.rerun()
else:
    st.info("Портфель пуст. Нажмите 'Добавить актив', чтобы создать первый контракт.")