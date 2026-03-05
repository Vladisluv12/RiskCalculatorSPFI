import streamlit as st
from datetime import date, datetime
from instruments.BaseInstrument import Direction
from instruments.FXForward import SpotRateMethod, CurrencyForwardContract
from instruments.FXSwap import CurrencySwapContract, CurrencyPair

def render_add_instrument_form():
    """Отрисовывает форму добавления инструмента в боковой панели."""
    with st.sidebar:
        st.header("⚙️ Параметры контракта")
        
        # Кнопка закрытия без сохранения
        if st.button("❌ Закрыть меню"):
            st.session_state.show_add_form = False
            st.rerun()
            
        st.divider()
        
        # Выбор типа инструмента
        instrument_type = st.radio(
            "Тип инструмента",
            options=["Валютный форвард", "Валютный своп"],
            horizontal=True
        )
        
        st.divider()
        
        if instrument_type == "Валютный форвард":
            return render_forward_form()
        else:
            return render_swap_form()
    
    return None

def render_forward_form():
    """Отрисовывает форму добавления форварда."""
    with st.form("forward_form", clear_on_submit=True):
        st.subheader("Основные параметры")
        inst_id = st.text_input("ID инструмента", value="FX")
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
            return CurrencyForwardContract(
                instrument_id=inst_id + (" NDF" if is_ndf else " FWD") + f" {(start_d - datetime.today().date()).days}D",
                notional=notional,
                start_date=datetime.combine(start_d, datetime.min.time()),
                end_date=datetime.combine(end_d, datetime.min.time()),
                currency_pair=pair,
                base_currency=pair.split('/')[0],
                quote_currency=pair.split('/')[1],
                direction=Direction.BUY if direction == "Buy" else Direction.SELL,
                forward_rate=rate,
                spot_rate_method=SpotRateMethod(method) if is_ndf else None,
                is_ndf=is_ndf
            )
    return None

def render_swap_form():
    """Отрисовывает форму добавления валютного свопа."""
    with st.form("swap_form", clear_on_submit=True):
        st.subheader("Основные параметры")
        
        # ID инструмента
        inst_id = st.text_input("ID инструмента", value="SWAP")
        
        # Валютная пара
        pair_str = st.selectbox(
            "Валютная пара",
            ["USD/RUB", "EUR/RUB", "CNY/RUB", "EUR/USD"],
            key="swap_pair"
        )
        pair = CurrencyPair(pair_str)
        
        # Первая и вторая валюта
        base_currency = pair_str.split('/')[0]
        quote_currency = pair_str.split('/')[1]
        
        # Направление сделки
        col1, col2 = st.columns(2)
        direction = col1.selectbox("Направление", ["Buy", "Sell"], key="swap_dir")
        
        fixed_sum = st.number_input(
            "Cумма в базовой валюте",
            min_value=0.0,
            value=100000.0,
            format="%.2f",
            key="fixed_sum"
        )
        
        st.divider()
        st.subheader("Рыночные параметры")
        
        col1, col2 = st.columns(2)
        spot_rate = col1.number_input(
            "Курс спот",
            min_value=0.0001,
            value=90.0,
            format="%.4f",
            key="spot_rate"
        )
        
        swap_points = col2.number_input(
            "Swap points",
            value=100,
            key="swap_points",
            help="1 пункт = 0.0001"
        )
        
        st.divider()
        st.subheader("Даты")
        
        col1, col2 = st.columns(2)
        start_date = col1.date_input("Near leg", value=date.today(), key="swap_start")
        end_date = col2.date_input("Far leg", value=date.today(), key="swap_end")
        
        st.divider()
        st.subheader("Доп. платеж")
        
        # Чекбокс для показа дополнительных полей
        show_additional = st.checkbox(
            "Доп. платеж",
            value=False,
            key="additional_checkbox"
        )
        
        # Показываем дополнительные поля только если чекбокс отмечен
        additional_payment = None
        additional_payment_direction = None
    
        col1, col2 = st.columns(2)
        with col1:
            additional_payment = st.number_input(
                "Сумма",
                min_value=0.0,
                value=1000.0,
                format="%.2f",
                key="additional_sum"
            )
        with col2:
            additional_dir = st.selectbox(
                "Направление",
                ["Pay", "Receive"],
                key="additional_dir"
            )
            additional_payment_direction = Direction.BUY if additional_dir == "Receive" else Direction.BUY
        submitted = st.form_submit_button("Добавить в портфель", use_container_width=True)
        
        if submitted:
            return CurrencySwapContract(
                instrument_id=f"{inst_id} {pair_str} {start_date.strftime('%d%m%y')}-{end_date.strftime('%d%m%y')}",
                notional=fixed_sum,  # Используем фиксированную сумму как номинал
                start_date=datetime.combine(start_date, datetime.min.time()),
                end_date=datetime.combine(end_date, datetime.min.time()),
                currency_pair=pair,
                first_currency=base_currency,
                second_currency=quote_currency,
                fixed_sum_currency=base_currency,
                fixed_sum=fixed_sum,
                spot_rate=spot_rate,
                swap_points=swap_points,
                direction=Direction.BUY if direction == "Buy" else Direction.SELL,
                additional_payment=additional_payment if show_additional else None,
                additional_payment_direction=additional_payment_direction if show_additional else None
            )
    return None