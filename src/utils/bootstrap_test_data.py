# Decompiled with PyLingual (https://pylingual.io)
# Internal filename: 'C:\\Users\\vladc\\Desktop\\projects\\course_work_risk_calc\\src\\utils\\bootstrap_test_data.py'
# Bytecode version: 3.10.b1 (3439)
# Source timestamp: 2026-04-03 08:22:38 UTC (1775204558)

from datetime import date, datetime, timedelta
from instruments.BaseInstrument import CurrencyPair, Direction
from instruments.FXForward import CurrencyForwardContract
from instruments.FXSwap import CurrencySwapContract
from utils.DataProvider import DataProvider
def bootstrap_test_data(session_state) -> None:
    """Заполняет session_state тестовыми данными для быстрого запуска интерфейса.\n\n    Функция идемпотентна в рамках сессии Streamlit: повторно данные не добавляет.\n    """
    if session_state.get('_bootstrap_test_data_done'):
        return None
    else:
        today = date(2025, 4, 11)
        session_state.valuation_date = today
        if 'data_dir' not in session_state:
            session_state.data_dir = 'src/data'
        try:
            session_state.data_provider = DataProvider(input_dir=session_state.data_dir)
        except FileNotFoundError:
            session_state.data_dir = 'data'
            session_state.data_provider = DataProvider(input_dir=session_state.data_dir)
        forward_end = today + timedelta(days=30)
        swap_start = today + timedelta(days=2)
        swap_end = today + timedelta(days=92)
        test_forward = CurrencyForwardContract(instrument_id='TEST FWD USDRUB 30D', notional=100000.0, direction=Direction.BUY, start_date=datetime.combine(today, datetime.min.time()), end_date=datetime.combine(forward_end, datetime.min.time()), currency_pair=CurrencyPair.USD_RUB, base_currency='USD', quote_currency='RUB', forward_rate=95.0, is_ndf=True)
        test_swap = CurrencySwapContract(instrument_id='TEST SWAP USDRUB 90D', notional=100000.0, direction=Direction.BUY, start_date=datetime.combine(swap_start, datetime.min.time()), end_date=datetime.combine(swap_end, datetime.min.time()), currency_pair=CurrencyPair.USD_RUB, base_currency='USD', quote_currency='RUB', fixed_sum_currency='USD', fixed_sum=100000.0, spot_rate=92.5, swap_points=220, reverse_rate=92.522)
        session_state.portfolio = [test_forward, test_swap]
        session_state.selected_id = test_forward.instrument_id
        session_state._bootstrap_test_data_done = True