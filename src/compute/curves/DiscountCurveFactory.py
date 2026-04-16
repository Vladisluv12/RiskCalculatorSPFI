import pandas as pd
from compute.curves.DiscountCurve import DiscountCurve


class DiscountCurveFactory:
    """
    Фабрика для создания дисконтных кривых из CSV файла.
    """
    
    def __init__(self, csv_file):
        """
        Инициализация фабрики с данными из CSV.
        
        Parameters:
        -----------
        csv_file : str
            Путь к CSV файлу с данными
        """
        self.data = pd.read_csv(csv_file)
        self.curves = {}
        self._parse_data()
    
    def _parse_data(self):
        """
        Парсинг данных из CSV и создание кривых.
        """
        # Получаем все названия кривых (колонки кроме 'Тенор' и 'Время_в_годах')
        curve_names = [col for col in self.data.columns 
                      if col not in ['Тенор', 'Время_в_годах']]
        
        tenors_years = self.data['Время_в_годах'].values
        
        for curve_name in curve_names:
            discount_factors = self.data[curve_name].values
            self.curves[curve_name] = DiscountCurve(
                curve_name, 
                tenors_years, 
                discount_factors
            )
    
    def get_curve(self, curve_name):
        """
        Возвращает кривую по её названию.
        
        Parameters:
        -----------
        curve_name : str
            Название кривой (например, 'USD-DISCOUNT-USD-CSA')
            
        Returns:
        --------
        DiscountCurve
            Экземпляр класса DiscountCurve
        """
        if curve_name not in self.curves:
            # Пробуем найти похожую кривую (регистронезависимо)
            curve_name_lower = curve_name.lower()
            for name in self.curves:
                if name.lower() == curve_name_lower:
                    return self.curves[name]
        return self.curves[curve_name]
    
    def get_curves_by_ccy(self, currency):
        """
        Возвращает все кривые для указанной валюты.
        
        Parameters:
        -----------
        currency : str
            Код валюты (USD, RUB, EUR, CNY)
            
        Returns:
        --------
        dict
            Словарь {название_кривой: DiscountCurve}
        """
        currency = currency.upper()
        result = {}
        
        for name, curve in self.curves.items():
            if name.startswith(currency):
                result[name] = curve
        
        return result
    
    def get_curves_by_collateral(self, collateral):
        """
        Возвращает все кривые с указанным обеспечением (CSA).
        
        Parameters:
        -----------
        collateral : str
            Тип обеспечения (USD, RUB, EUR, CNY)
            
        Returns:
        --------
        dict
            Словарь {название_кривой: DiscountCurve}
        """
        collateral = collateral.upper()
        result = {}
        
        pattern = f"-{collateral}-CSA"
        for name, curve in self.curves.items():
            if name.endswith(pattern):
                result[name] = curve
        
        return result
