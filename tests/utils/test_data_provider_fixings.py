import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

import pytest
import pandas as pd
from datetime import datetime
from utils.DataProvider import DataProvider
from instruments.enums import FloatingIndex


DATA_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'data')


def test_get_fixing_data_returns_dataframe():
    dp = DataProvider(DATA_DIR)
    df = dp.get_fixing_data(
        FloatingIndex.RUONIA_COMP,
        datetime(2026, 1, 1),
        datetime(2026, 4, 30),
    )
    assert isinstance(df, pd.DataFrame)
    assert 'fixing' in df.columns
    assert len(df) > 0


def test_get_fixing_data_index_is_datetime():
    dp = DataProvider(DATA_DIR)
    df = dp.get_fixing_data(FloatingIndex.RUONIA_COMP, datetime(2026, 1, 1), datetime(2026, 4, 30))
    assert pd.api.types.is_datetime64_any_dtype(df.index)


def test_get_fixing_data_filtered_by_date():
    dp = DataProvider(DATA_DIR)
    start = datetime(2026, 4, 1)
    end = datetime(2026, 4, 15)
    df = dp.get_fixing_data(FloatingIndex.RUONIA_COMP, start, end)
    assert (df.index >= pd.Timestamp(start)).all()
    assert (df.index <= pd.Timestamp(end)).all()


def test_get_fixing_data_sofr():
    dp = DataProvider(DATA_DIR)
    df = dp.get_fixing_data(FloatingIndex.SOFR_COMP, datetime(2026, 1, 1), datetime(2026, 4, 30))
    assert 'fixing' in df.columns


def test_get_fixing_data_missing_file_raises():
    dp = DataProvider.__new__(DataProvider)
    dp.filepath = '/nonexistent_path'
    with pytest.raises(FileNotFoundError):
        dp.get_fixing_data(FloatingIndex.RUONIA_COMP, datetime(2026, 1, 1), datetime(2026, 4, 30))
