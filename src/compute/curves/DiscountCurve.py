import numpy as np
from scipy import interpolate
from datetime import datetime

class DiscountCurve:
    """
    Класс для работы с дисконтной кривой.
    Поддерживает интерполяцию дисконт-факторов для произвольных дат.
    """
    
    def __init__(self, curve_name, tenors_years, discount_factors, base_date=None):
        """
        Инициализация кривой.
        
        Parameters:
        -----------
        curve_name : str
            Название кривой (например, 'USD-DISCOUNT-USD-CSA')
        tenors_years : array-like
            Массив сроков в годах
        discount_factors : array-like
            Массив дисконт-факторов
        base_date : datetime, optional
            Базовая дата (дата, для которой дисконт-фактор = 1)
        """
        self.curve_name = curve_name
        
        # Удаляем NaN значения
        valid_mask = ~np.isnan(discount_factors)
        self.tenors_years = np.array(tenors_years)[valid_mask]
        self.discount_factors = np.array(discount_factors)[valid_mask]
        
        # Сортируем по возрастанию теноров
        sort_idx = np.argsort(self.tenors_years)
        self.tenors_years = self.tenors_years[sort_idx]
        self.discount_factors = self.discount_factors[sort_idx]
        
        # Добавляем точку (0, 1) если её нет
        if self.tenors_years[0] > 0:
            self.tenors_years = np.concatenate([[0], self.tenors_years])
            self.discount_factors = np.concatenate([[1], self.discount_factors])
        
        self.base_date = base_date or datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Создаем интерполяторы
        log_df = np.log(self.discount_factors)
        self.log_interpolator = interpolate.interp1d(
            self.tenors_years, 
            log_df,
            kind='linear',
            bounds_error=False,
            fill_value=(log_df[0], log_df[-1])
        )
    
    def discount_factor(self, t):
        """
        Возвращает дисконт-фактор для заданного времени t (в годах).
        
        Parameters:
        -----------
        t : float или array-like
            Время в годах от базовой даты
            
        Returns:
        --------
        Дисконт-фактор(ы)
        """
        t = np.array(t, dtype=float)
        scalar_input = t.ndim == 0
        t = np.atleast_1d(t)
        
        # Для отрицательных t возвращаем 1/DF(-t) (форвардный дисконт-фактор)
        result = np.zeros_like(t, dtype=float)
        
        # Обработка t >= 0
        mask_forward = t >= 0
        if np.any(mask_forward):
            t_forward = t[mask_forward]
            log_df = self.log_interpolator(t_forward)
            result[mask_forward] = np.exp(log_df)
        
        # Обработка t < 0 (экстраполяция в прошлое)
        mask_backward = t < 0
        if np.any(mask_backward):
            t_backward = -t[mask_backward]
            log_df = self.log_interpolator(t_backward)
            result[mask_backward] = 1.0 / np.exp(log_df)
        
        return result[0] if scalar_input else result
    
    def spot_rate(self, t):
        """
        Возвращает спотовую процентную ставку.
        
        Parameters:
        -----------
        t : float
            Время в годах
            
        Returns:
        --------
        Спотовая ставка
        """
        df = self.discount_factor(t)
        
        if t <= 0:
            return self.spot_rate(1e-10)  # Избегаем деления на ноль
        return -np.log(df) / t
    
    def forward_rate(self, t1, t2):
        """
        Возвращает форвардную ставку между t1 и t2.
        
        Parameters:
        -----------
        t1, t2 : float
            Начальное и конечное время в годах
            
        Returns:
        --------
        Форвардная ставка
        """
        df1 = self.discount_factor(t1)
        df2 = self.discount_factor(t2)
        
        if t2 <= t1:
            raise ValueError("t2 должно быть больше t1")
        tau = t2 - t1
        return -np.log(df2/df1) / tau
    
    def get_date_factor(self, target_date):
        """
        Возвращает дисконт-фактор для конкретной даты.
        
        Parameters:
        -----------
        target_date : datetime or str
            Целевая дата
            
        Returns:
        --------
        Дисконт-фактор для указанной даты
        """
        if isinstance(target_date, str):
            target_date = datetime.strptime(target_date, '%Y-%m-%d')
        
        # Вычисляем время в годах от базовой даты
        days_diff = (target_date - self.base_date).days
        t = days_diff / 365.25  # Учитываем високосные годы
        
        return self.discount_factor(t)
