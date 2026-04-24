import streamlit as st
import pandas as pd
from instruments.FXForward import CurrencyForwardContract
from instruments.FXSwap import CurrencySwapContract
from instruments.IRSwap import InterestRateSwap

def render_portfolio_table(portfolio: list):
    """Отрисовывает таблицу с контрактами."""
    if not portfolio:
        st.info('В портфеле пока нет контрактов. Используйте боковую панель для добавления.')
        return None
    else:
        rows = []
        for instrument in portfolio:
            if isinstance(instrument, InterestRateSwap):
                inst_type = 'IRS/OIS'
                pair_str = instrument.currency.value
            elif isinstance(instrument, CurrencyForwardContract):
                inst_type = 'Форвард'
                pair_str = instrument.currency_pair.value if hasattr(instrument.currency_pair, 'value') else instrument.currency_pair
            else:
                inst_type = 'Своп'
                pair_str = instrument.currency_pair.value if hasattr(instrument.currency_pair, 'value') else instrument.currency_pair
            row = {
                'ID': instrument.instrument_id,
                'Тип': inst_type,
                'Валюта / Пара': pair_str,
                'Направление': instrument.direction.value if hasattr(instrument.direction, 'value') else str(instrument.direction),
                'Номинал': instrument.notional,
                'Дата начала': instrument.start_date.date() if hasattr(instrument.start_date, 'date') else instrument.start_date,
                'Дата окончания': instrument.end_date.date() if hasattr(instrument.end_date, 'date') else instrument.end_date,
            }
            if isinstance(instrument, CurrencyForwardContract):
                row['Форвардный курс'] = instrument.forward_rate
                row['Тип расчета'] = 'NDF' if instrument.is_ndf else 'Поставочный'
            elif isinstance(instrument, CurrencySwapContract):
                row['Курс спот'] = instrument.spot_rate
                row['Swap points'] = instrument.swap_points
            elif isinstance(instrument, InterestRateSwap):
                row['Фикс. ставка'] = f"{instrument.fixed_rate * 100:.2f}%"
                row['Плав. индекс'] = instrument.floating_index.value
            rows.append(row)
        df = pd.DataFrame(rows)
        column_config = {
            'ID': st.column_config.TextColumn('ID', width='medium'),
            'Тип': st.column_config.TextColumn('Тип', width='small'),
            'Валюта / Пара': st.column_config.TextColumn('Пара/Валюта', width='small'),
            'Направление': st.column_config.TextColumn('Направление', width='small'),
            'Номинал': st.column_config.NumberColumn('Номинал', format='%.2f'),
            'Дата начала': st.column_config.DateColumn('Начало', format='DD.MM.YYYY'),
            'Дата окончания': st.column_config.DateColumn('Окончание', format='DD.MM.YYYY'),
        }
        if 'Форвардный курс' in df.columns:
            column_config['Форвардный курс'] = st.column_config.NumberColumn('Fwd курс', format='%.4f')
        if 'Тип расчета' in df.columns:
            column_config['Тип расчета'] = st.column_config.TextColumn('Расчет', width='small')
        if 'Курс спот' in df.columns:
            column_config['Курс спот'] = st.column_config.NumberColumn('Спот', format='%.4f')
        if 'Swap points' in df.columns:
            column_config['Swap points'] = st.column_config.NumberColumn('Пункты', format='%.2f')
        if 'Фикс. ставка' in df.columns:
            column_config['Фикс. ставка'] = st.column_config.TextColumn('Фикс. ставка', width='small')
        if 'Плав. индекс' in df.columns:
            column_config['Плав. индекс'] = st.column_config.TextColumn('Плав. индекс', width='medium')
        st.dataframe(df, width="stretch", hide_index=True, column_config=column_config)
        col1, col2, col3, _ = st.columns([1.2, 0.8, 0.8, 1.5])
        with col1:
            if st.button('Очистить портфель', type='primary'):
                st.session_state.portfolio = []
                st.session_state.show_import = False
                st.session_state.show_export = False
                st.rerun()
        with col2:
            if st.button('📥 Импорт'):
                st.session_state.show_import = not st.session_state.get('show_import', False)
                st.session_state.show_export = False
        with col3:
            if st.button('📤 Экспорт'):
                st.session_state.show_export = not st.session_state.get('show_export', False)
                st.session_state.show_import = False
