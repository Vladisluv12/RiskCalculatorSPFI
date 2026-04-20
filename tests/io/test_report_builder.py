import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

import pandas as pd
from io.report_builder import ReportBuilder


DATA = {
    "pnl": pd.DataFrame({"price": [-0.01, 0.02]}),
    "var": 0.023,
    "es": 0.031,
}


def test_add_and_has_section():
    rb = ReportBuilder()
    assert not rb.has_section("var_page")
    rb.add_section("var_page", "VaR Analysis", DATA)
    assert rb.has_section("var_page")
    assert rb.sections_count() == 1


def test_remove_section():
    rb = ReportBuilder()
    rb.add_section("var_page", "VaR Analysis", DATA)
    rb.remove_section("var_page")
    assert not rb.has_section("var_page")
    assert rb.sections_count() == 0


def test_build_returns_pdf_bytes():
    rb = ReportBuilder()
    rb.add_section("var_page", "VaR Analysis", DATA)
    rb.add_section("portfolio_var_page", "Portfolio VaR", DATA)
    pdf_bytes = rb.build()
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes[:4] == b"%PDF"  # PDF magic bytes


def test_build_empty_returns_pdf():
    rb = ReportBuilder()
    pdf_bytes = rb.build()
    assert pdf_bytes[:4] == b"%PDF"
