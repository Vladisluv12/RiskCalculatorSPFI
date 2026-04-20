from collections import OrderedDict
from datetime import date
import os

import pandas as pd
from fpdf import FPDF


def _find_unicode_font() -> str | None:
    candidates = [
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf",
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    return None


class ReportBuilder:
    def __init__(self) -> None:
        self._sections: OrderedDict[str, dict] = OrderedDict()

    def add_section(self, page_id: str, title: str, data: dict) -> None:
        self._sections[page_id] = {"title": title, "data": data}

    def remove_section(self, page_id: str) -> None:
        self._sections.pop(page_id, None)

    def has_section(self, page_id: str) -> bool:
        return page_id in self._sections

    def sections_count(self) -> int:
        return len(self._sections)

    def build(self) -> bytes:
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)

        font_path = _find_unicode_font()
        if font_path:
            pdf.add_font("DejaVu", "", font_path)
            _font = "DejaVu"
        else:
            _font = "Helvetica"

        pdf.add_page()
        pdf.set_font(_font, size=16)
        pdf.cell(0, 10, "Risk Analysis Report", new_x="LMARGIN", new_y="NEXT", align="C")
        pdf.set_font(_font, size=10)
        pdf.cell(0, 6, f"Generated: {date.today()}", new_x="LMARGIN", new_y="NEXT", align="C")
        pdf.ln(8)

        for section in self._sections.values():
            self._render_section(pdf, _font, section["title"], section["data"])

        return bytes(pdf.output())

    def _render_section(self, pdf: FPDF, font: str, title: str, data: dict) -> None:
        pdf.set_font(font, size=13)
        pdf.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

        for key, value in data.items():
            if isinstance(value, pd.DataFrame):
                self._render_dataframe(pdf, font, str(key), value)
            elif isinstance(value, float):
                pdf.set_font(font, size=10)
                pdf.cell(0, 6, f"{key}: {value:.6f}", new_x="LMARGIN", new_y="NEXT")
            elif isinstance(value, dict):
                pdf.set_font(font, size=10)
                pdf.multi_cell(0, 6, f"{key}: {value}")
        pdf.ln(4)

    def _render_dataframe(self, pdf: FPDF, font: str, title: str, df: pd.DataFrame) -> None:
        pdf.set_font(font, size=10)
        pdf.cell(0, 6, title, new_x="LMARGIN", new_y="NEXT")

        usable_width = pdf.w - pdf.l_margin - pdf.r_margin
        n_cols = len(df.columns) + 1  # +1 for index
        col_w = min(35, usable_width / max(n_cols, 1))

        pdf.set_font(font, size=7)
        pdf.cell(col_w, 5, "idx", border=1)
        for col in df.columns:
            pdf.cell(col_w, 5, str(col)[:14], border=1)
        pdf.ln()

        for idx, row in df.head(20).iterrows():
            pdf.cell(col_w, 5, str(idx)[:14], border=1)
            for val in row:
                text = f"{val:.4f}" if isinstance(val, float) else str(val)[:14]
                pdf.cell(col_w, 5, text, border=1)
            pdf.ln()
        pdf.ln(2)
