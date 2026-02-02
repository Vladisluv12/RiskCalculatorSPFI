import streamlit as st
import numpy as np
import plotly.graph_objects as go
import compute.risk.var as var

st.title("📉 Анализ рисков (VaR)")

# Проверяем, выбран ли конкретный инструмент
selected_id = st.session_state.get('selected_id')

if selected_id:
    st.info(f"Анализ для инструмента: **{selected_id}**")
    st.subheader("Параметры расчета")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        type_of_var = st.selectbox("Метод расчета VaR", options=["Исторический", "Параметрический"], index=0)
    with col2:
        window = st.slider("Количество дней в истории", 252, 2520, 252, step=252)
    with col3:
        conf_level = st.selectbox("Доверительный уровень", options=[0.95, 0.99], index=0)
    with col4:
        horizon = st.number_input("Горизонт прогноза", min_value=1, max_value=30, value=1)
    
    st.divider()
    
    if type_of_var == "Исторический":
        pnl, var_cutoff = var.historical(selected_id, horizon=horizon, confidence_level=conf_level, window=window)
        var_index = round(len(pnl) * (1 - conf_level))

        # Создаем гистограмму распределения PnL
        fig = go.Figure()

        fig.add_trace(go.Bar(
            x=list(range(len(pnl))),
            y=pnl['curs'],
            name="Отсортированный PnL",
            hovertemplate="Доходность: %{y:.2%}<extra></extra>"
        ))

        # 4. Вертикальная линия на месте отсечки
        fig.add_vline(
            x=var_index, 
            line_dash="dash", 
            line_color="black", 
            line_width=2,
            annotation_text=f"Гранница VaR {conf_level*100:.0f}%",
            annotation_position="top left"
        )

        # Настройка осей
        fig.update_layout(
            title=f"Динамика PnL для {selected_id}",
            xaxis_title="Номер в отсортированной PnL",
            yaxis_title="PnL (%)",
            yaxis_tickformat='.4%',
            template="plotly_white",
            hovermode="x unified"
        )

        st.plotly_chart(fig, use_container_width=True)
    else:
        var_cutoff = var.parametric(selected_id, horizon=horizon, confidence_level=conf_level, window=window)
        st.write(f"Параметрический VaR: **{var_cutoff:.4f}**")
    # 4. Метрики внизу
    st.columns(3)[1].metric("Рассчитанный VaR", f"{abs(var_cutoff):.4f}", help="Максимальный ожидаемый убыток")
else:
    st.warning("Инструмент не выбран. Выберите его на странице портфеля или в списке ниже.")
    # Можно добавить selectbox и здесь