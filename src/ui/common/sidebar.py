import streamlit as st
from datetime import date, datetime
from instruments.enums import Direction, CurrencyPair, Currency, DayCountConvention, PaymentTiming, OffsetRule, FloatingIndex
from instruments.FXForward import CurrencyForwardContract
from instruments.FXSwap import CurrencySwapContract
from instruments.IRSwap import InterestRateSwap


_INDEX_BY_CURRENCY: dict[str, list[FloatingIndex]] = {
    'RUB': [
        FloatingIndex.RUONIA_AVG, FloatingIndex.RUONIA_COMP,
        FloatingIndex.RUSFAR_RUB_3M, FloatingIndex.RUSFAR_RUB_ON,
        FloatingIndex.RUB_KEY_RATE,
    ],
    'USD': [FloatingIndex.SOFR_COMP],
    'EUR': [
        FloatingIndex.ESTR_COMP,
        FloatingIndex.EURIBOR_EUR_1M,
        FloatingIndex.EURIBOR_EUR_3M,
        FloatingIndex.EURIBOR_EUR_6M,
    ],
    'CNY': [FloatingIndex.RUSFARCNY_COMP],
}


def _get_global_valuation_date() -> date:
    valuation_date = st.session_state.get('valuation_date')
    if isinstance(valuation_date, datetime):
        return valuation_date.date()
    else:
        if isinstance(valuation_date, date):
            return valuation_date
        else:
            return date.today()


def render_add_instrument_form():
    """Отрисовывает форму добавления инструмента в боковой панели."""
    with st.sidebar:
        st.header('⚙️ Параметры контракта')
        if st.button('❌ Закрыть меню'):
            st.session_state.show_add_form = False
            st.rerun()
            
        st.divider()
        instrument_type = st.radio(
            'Тип инструмента',
            options=['Валютный форвард', 'Валютный своп', 'Процентный своп (IRS/OIS)'],
            horizontal=True,
        )
        st.divider()
        if instrument_type == 'Валютный форвард':
            return render_forward_form()
        elif instrument_type == 'Валютный своп':
            return render_swap_form()
        else:
            return render_irs_form()


def render_forward_form():
    """Отрисовывает форму добавления форварда."""
    default_date = _get_global_valuation_date()
    st.subheader('Основные параметры')
    inst_id = st.text_input('ID инструмента', value='FX', key='fwd_inst_id')
    pair = st.selectbox('Валютная пара', ['USD/RUB', 'EUR/RUB', 'CNY/RUB', 'EUR/USD'], key='fwd_pair')
    col1, col2 = st.columns(2)
    direction = col1.selectbox('Направление', ['Buy', 'Sell'], key='fwd_direction')
    notional = col2.number_input('Номинал', min_value=0.0, value=100000.0, key='fwd_notional')
    rate = st.number_input('Форвардный курс', min_value=0.0, format='%.4f', value=90.0, key='fwd_rate')
    start_d = default_date
    end_d = st.date_input('Дата платежа', value=default_date, key='fwd_end_date')
    submitted = st.button('Добавить в портфель', width='stretch', key='fwd_submit')
    return CurrencyForwardContract(instrument_id=inst_id + ' ' + pair + f' {(end_d - default_date).days}D', notional=notional, start_date=datetime.combine(start_d, datetime.min.time()), end_date=datetime.combine(end_d, datetime.min.time()), currency_pair=CurrencyPair(pair), base_currency=pair.split('/')[0], quote_currency=pair.split('/')[1], direction=Direction.BUY if direction == 'Buy' else Direction.SELL, forward_rate=rate) if submitted else None


def render_swap_form():
    """Отрисовывает форму добавления валютного свопа."""
    default_date = _get_global_valuation_date()
    st.subheader('Основные параметры')
    inst_id = st.text_input('ID инструмента', value='SWAP')
    pair_str = st.selectbox('Валютная пара', ['USD/RUB', 'EUR/RUB', 'CNY/RUB', 'EUR/USD'], key='swap_pair')
    pair = CurrencyPair(pair_str)
    base_currency = pair_str.split('/')[0]
    quote_currency = pair_str.split('/')[1]
    col1, col2 = st.columns(2)
    direction = col1.selectbox('Направление', ['Buy', 'Sell'], key='swap_dir')
    fixed_sum = st.number_input('Cумма в базовой валюте', min_value=0.0, value=100000.0, format='%.2f', key='fixed_sum')
    st.divider()
    st.subheader('Рыночные параметры')
    col1, col2 = st.columns(2)
    spot_rate = col1.number_input('Курс спот', min_value=0.0001, value=90.0, format='%.4f', key='spot_rate')
    swap_points = col2.number_input('Swap points', value=100, key='swap_points', help='1 пункт = 0.0001')
    reverse_rate = float(spot_rate + swap_points * 0.0001)
    st.metric('Reverse rate (K)', f'{reverse_rate:.4f}', help='Пересчитывается сразу при изменении swap_points/spot_rate')
    st.divider()
    st.subheader('Даты')
    col1, col2 = st.columns(2)
    start_date = col1.date_input('Near leg', value=default_date, key='swap_start')
    end_date = col2.date_input('Far leg', value=default_date, key='swap_end')
    submitted = st.button('Добавить в портфель', width="stretch", key='swap_submit')
    if submitted:
        return CurrencySwapContract(instrument_id=f"{inst_id} {pair_str} {start_date.strftime('%d%m%y')}-{end_date.strftime('%d%m%y')}", notional=fixed_sum, start_date=datetime.combine(start_date, datetime.min.time()), end_date=datetime.combine(end_date, datetime.min.time()), currency_pair=pair, base_currency=base_currency, quote_currency=quote_currency, fixed_sum_currency=base_currency, fixed_sum=fixed_sum, spot_rate=spot_rate, swap_points=swap_points, reverse_rate=reverse_rate, direction=Direction.BUY if direction == 'Buy' else Direction.SELL)


def render_irs_form():
    """Отрисовывает форму добавления процентного свопа (IRS/OIS)."""
    default_date = _get_global_valuation_date()

    st.subheader('Основные параметры')
    inst_id = st.text_input('ID инструмента', value='IRS', key='irs_inst_id')
    col1, col2 = st.columns(2)
    direction = col1.selectbox('Направление', ['Buy', 'Sell'], key='irs_direction',
                               help='Buy = Payer (платит fixed), Sell = Receiver (платит float)')
    notional = col2.number_input('Номинал', min_value=0.0, value=1_000_000.0,
                                 format='%.0f', key='irs_notional')
    col1, col2 = st.columns(2)
    start_date = col1.date_input('Дата начала', value=default_date, key='irs_start')
    end_date = col2.date_input('Дата окончания', value=default_date, key='irs_end')

    st.divider()
    st.subheader('Плавающая нога')
    currency_str = st.selectbox(
        'Валюта свопа', [c.value for c in Currency], key='irs_currency'
    )
    available_indices = _INDEX_BY_CURRENCY.get(currency_str, list(FloatingIndex))
    floating_index_val = st.selectbox(
        'Плавающий индекс',
        options=[idx.value for idx in available_indices],
        key='irs_float_index',
    )
    floating_index = FloatingIndex(floating_index_val)
    floating_spread = st.number_input(
        'Спред (bp)', value=0.0, step=0.1, format='%.1f', key='irs_float_spread'
    )
    col1, col2 = st.columns(2)
    float_dc = col1.selectbox(
        'Day count', [dc.value for dc in DayCountConvention], key='irs_float_dc'
    )
    float_timing = col2.selectbox(
        'Частота', [pt.value for pt in PaymentTiming], key='irs_float_timing'
    )
    float_offset = st.selectbox(
        'Offset', [o.value for o in OffsetRule], key='irs_float_offset'
    )

    st.divider()
    st.subheader('Фиксированная нога')
    fixed_rate = st.number_input(
        'Фиксированная ставка (%)', min_value=0.0, max_value=100.0,
        value=16.0, step=0.01, format='%.2f', key='irs_fixed_rate'
    )
    col1, col2 = st.columns(2)
    fixed_dc = col1.selectbox(
        'Day count', [dc.value for dc in DayCountConvention], key='irs_fixed_dc'
    )
    fixed_timing = col2.selectbox(
        'Частота', [pt.value for pt in PaymentTiming], key='irs_fixed_timing'
    )
    fixed_offset = st.selectbox(
        'Offset', [o.value for o in OffsetRule], key='irs_fixed_offset'
    )

    submitted = st.button('Добавить в портфель', width='stretch', key='irs_submit')
    if submitted:
        auto_id = f"{inst_id} {currency_str} {start_date.strftime('%d%m%y')}-{end_date.strftime('%d%m%y')}"
        return InterestRateSwap(
            instrument_id=auto_id,
            notional=notional,
            direction=Direction.BUY if direction == 'Buy' else Direction.SELL,
            start_date=datetime.combine(start_date, datetime.min.time()),
            end_date=datetime.combine(end_date, datetime.min.time()),
            currency=Currency(currency_str),
            fixed_rate=fixed_rate / 100.0,
            fixed_day_count=DayCountConvention(fixed_dc),
            fixed_payment_timing=PaymentTiming(fixed_timing),
            fixed_offset_rule=OffsetRule(fixed_offset),
            floating_index=floating_index,
            floating_spread=floating_spread,
            floating_day_count=DayCountConvention(float_dc),
            floating_payment_timing=PaymentTiming(float_timing),
            floating_offset_rule=OffsetRule(float_offset),
        )
    return None


def render_report_sidebar() -> None:
    from iolib.report_builder import ReportBuilder
    with st.sidebar:
        st.divider()
        rb: ReportBuilder = st.session_state.get("report_builder")
        if rb is None:
            return
        count = rb.sections_count()
        st.caption(f"📄 Отчёт: {count} {'секция' if count == 1 else 'секций'}")
        if count > 0:
            pdf_bytes = rb.build()
            st.download_button(
                label="Скачать PDF отчёт",
                data=pdf_bytes,
                file_name="risk_report.pdf",
                mime="application/pdf",
                width="stretch",
            )
        else:
            st.button("Скачать PDF отчёт", disabled=True, width="stretch")