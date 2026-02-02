import streamlit as st
import pandas as pd
from dataclasses import asdict

def render_portfolio_table(portfolio: list):
    """Отрисовывает таблицу с контрактами."""
    if not portfolio:
        st.info("В портфеле пока нет контрактов. Используйте боковую панель для добавления.")
        return

    # Преобразуем список dataclass в DataFrame
    data = [asdict(c) for c in portfolio]
    df = pd.DataFrame(data)

    # Оставляем только важные колонки для пользователя
    columns_to_show = {
        'instrument_id': 'ID',
        'currency_pair': 'Валютная пара',
        'direction': 'Направление',
        'notional': 'Номинал',
        'forward_rate': 'Форвардный курс',
        'start_date': 'Дата платежа',
    }
    
    df_display = df[columns_to_show.keys()].rename(columns=columns_to_show)

    # Настройка отображения (стилизация)
    st.dataframe(
        df_display,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Форвардный курс": st.column_config.NumberColumn(format="%.4f"),
            "Дата платежа": st.column_config.DateColumn(format="DD.MM.YYYY"),
        }
    )

    # Кнопка быстрой очистки
    if st.button("🗑️ Очистить весь портфель"):
        st.session_state.portfolio = []
        st.rerun()