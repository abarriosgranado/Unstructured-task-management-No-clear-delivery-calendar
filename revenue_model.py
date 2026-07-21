from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

import pandas as pd


MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


@dataclass(frozen=True)
class ModelConfig:
    budget_year: int
    company_type: str = "Services company"
    revenue_model: str = "Sales by units and price"

    @property
    def item_label(self) -> str:
        if self.company_type == "Goods company":
            return "Product"
        return "Service"


DEFAULT_MONTHLY_ROWS = [
    {
        "Revenue Item": "Service 1",
        "Customer": "Customer 1",
        "Monthly Units": 100,
        "Unit Price": 100.0,
    },
    {
        "Revenue Item": "Service 2",
        "Customer": "Customer 2",
        "Monthly Units": 75,
        "Unit Price": 140.0,
    },
]


def build_default_monthly_assumptions() -> pd.DataFrame:
    return pd.DataFrame(DEFAULT_MONTHLY_ROWS)


def normalize_monthly_assumptions(df: pd.DataFrame) -> pd.DataFrame:
    clean = df.copy()
    if "Product" in clean.columns and "Revenue Item" not in clean.columns:
        clean = clean.rename(columns={"Product": "Revenue Item"})

    expected_columns = ["Revenue Item", "Customer", "Monthly Units", "Unit Price"]
    for column in expected_columns:
        if column not in clean.columns:
            clean[column] = 0 if column not in ["Revenue Item", "Customer"] else ""

    clean = clean[expected_columns]
    clean["Revenue Item"] = clean["Revenue Item"].fillna("").astype(str)
    clean["Customer"] = clean["Customer"].fillna("").astype(str)
    clean["Monthly Units"] = pd.to_numeric(clean["Monthly Units"], errors="coerce").fillna(0)
    clean["Unit Price"] = pd.to_numeric(clean["Unit Price"], errors="coerce").fillna(0)
    return clean


def expand_same_every_month(monthly_assumptions: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    clean = normalize_monthly_assumptions(monthly_assumptions)
    id_cols = clean[["Revenue Item", "Customer"]].copy()

    units = id_cols.copy()
    prices = id_cols.copy()
    for month in MONTHS:
        units[month] = clean["Monthly Units"]
        prices[month] = clean["Unit Price"]

    return units, prices


def normalize_monthly_matrix(df: pd.DataFrame) -> pd.DataFrame:
    clean = df.copy()
    expected_columns = ["Revenue Item", "Customer"] + MONTHS
    for column in expected_columns:
        if column not in clean.columns:
            clean[column] = 0 if column in MONTHS else ""

    clean = clean[expected_columns]
    clean["Revenue Item"] = clean["Revenue Item"].fillna("").astype(str)
    clean["Customer"] = clean["Customer"].fillna("").astype(str)
    for month in MONTHS:
        clean[month] = pd.to_numeric(clean[month], errors="coerce").fillna(0)

    return clean


def build_revenue_preview(units_by_month: pd.DataFrame, prices_by_month: pd.DataFrame) -> pd.DataFrame:
    units = normalize_monthly_matrix(units_by_month)
    prices = normalize_monthly_matrix(prices_by_month)
    preview = units[["Revenue Item", "Customer"]].copy()

    for month in MONTHS:
        preview[month] = units[month] * prices[month]

    preview["FY Total"] = preview[MONTHS].sum(axis=1)
    total_row = pd.DataFrame(
        [
            {
                "Revenue Item": "Total Revenue",
                "Customer": "",
                **{month: preview[month].sum() for month in MONTHS},
                "FY Total": preview["FY Total"].sum(),
            }
        ]
    )
    return pd.concat([preview, total_row], ignore_index=True)


def export_assumptions_workbook(
    units_by_month: pd.DataFrame,
    prices_by_month: pd.DataFrame,
    config: ModelConfig,
) -> bytes:
    output = BytesIO()
    units = normalize_monthly_matrix(units_by_month)
    prices = normalize_monthly_matrix(prices_by_month)

    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        workbook = writer.book
        workbook.set_calc_mode("auto")
        worksheet = workbook.add_worksheet("Assumptions")
        writer.sheets["Assumptions"] = worksheet

        formats = _build_formats(workbook)
        _write_assumptions_sheet(worksheet, units, prices, config, formats)

    output.seek(0)
    return output.getvalue()


def _build_formats(workbook):
    return {
        "title": workbook.add_format(
            {"bold": True, "font_size": 16, "font_color": "#17324D"}
        ),
        "subtitle": workbook.add_format({"italic": True, "font_color": "#5E6A75"}),
        "section": workbook.add_format(
            {
                "bold": True,
                "font_color": "#FFFFFF",
                "bg_color": "#17324D",
                "border": 1,
                "border_color": "#17324D",
            }
        ),
        "header": workbook.add_format(
            {
                "bold": True,
                "bg_color": "#D9EAF7",
                "border": 1,
                "border_color": "#B8C7D3",
                "align": "center",
                "valign": "vcenter",
            }
        ),
        "input": workbook.add_format(
            {"bg_color": "#FFF2CC", "border": 1, "border_color": "#D9D9D9"}
        ),
        "input_number": workbook.add_format(
            {
                "bg_color": "#FFF2CC",
                "border": 1,
                "border_color": "#D9D9D9",
                "num_format": "#,##0",
            }
        ),
        "input_currency": workbook.add_format(
            {
                "bg_color": "#FFF2CC",
                "border": 1,
                "border_color": "#D9D9D9",
                "num_format": "#,##0.00",
            }
        ),
        "formula": workbook.add_format(
            {
                "bg_color": "#E2F0D9",
                "border": 1,
                "border_color": "#D9D9D9",
                "num_format": "#,##0",
            }
        ),
        "formula_currency": workbook.add_format(
            {
                "bg_color": "#E2F0D9",
                "border": 1,
                "border_color": "#D9D9D9",
                "num_format": "#,##0.00",
            }
        ),
        "total": workbook.add_format(
            {
                "bold": True,
                "bg_color": "#D9EAD3",
                "border": 1,
                "border_color": "#93C47D",
                "num_format": "#,##0",
            }
        ),
    }


def _write_assumptions_sheet(worksheet, units, prices, config, formats):
    worksheet.hide_gridlines(2)
    worksheet.freeze_panes(8, 2)
    worksheet.set_column("A:A", 3)
    worksheet.set_column("B:C", 18)
    worksheet.set_column("D:P", 12)

    worksheet.write("B2", "Annual Budget - Revenue Assumptions", formats["title"])
    worksheet.write(
        "B3",
        "Monthly revenue budget by revenue item and customer. Yellow cells are inputs; green cells are formulas.",
        formats["subtitle"],
    )
    worksheet.write("B5", "Company type", formats["section"])
    worksheet.write("C5", config.company_type, formats["input"])
    worksheet.write("D5", "Budget year", formats["section"])
    worksheet.write_number("E5", config.budget_year, formats["input_number"])
    worksheet.write("F5", "Revenue model", formats["section"])
    worksheet.write("G5", config.revenue_model, formats["input"])

    units_title = "Units"
    units_total = "FY Units"
    price_title = "Unit Price"
    price_total = "Avg Price"
    if config.revenue_model == "Recurring revenue (MRR)":
        units_title = "Recurring Lines"
        units_total = "Active Months"
        price_title = "MRR"
        price_total = "Avg MRR"

    units_start = 7
    price_start = _write_monthly_input_block(
        worksheet,
        title=units_title,
        start_row=units_start,
        data=units,
        month_format=formats["input_number"],
        total_header=units_total,
        total_formula_kind="sum",
        formats=formats,
    )
    revenue_start = _write_monthly_input_block(
        worksheet,
        title=price_title,
        start_row=price_start + 3,
        data=prices,
        month_format=formats["input_currency"],
        total_header=price_total,
        total_formula_kind="average",
        formats=formats,
    )
    _write_revenue_block(
        worksheet,
        start_row=revenue_start + 3,
        rows=len(units),
        units_start=units_start,
        price_start=price_start + 3,
        formats=formats,
    )


def _write_monthly_input_block(
    worksheet,
    title: str,
    start_row: int,
    data: pd.DataFrame,
    month_format,
    total_header: str,
    total_formula_kind: str,
    formats,
) -> int:
    start_col = 1
    headers = ["Revenue Item", "Customer"] + MONTHS + [total_header]

    worksheet.write(start_row, start_col, title, formats["section"])
    worksheet.write_row(start_row + 1, start_col, headers, formats["header"])

    for row_index, row in data.iterrows():
        excel_row = start_row + 2 + row_index
        worksheet.write(excel_row, start_col, row["Revenue Item"], formats["input"])
        worksheet.write(excel_row, start_col + 1, row["Customer"], formats["input"])
        for month_index, month in enumerate(MONTHS):
            worksheet.write_number(
                excel_row,
                start_col + 2 + month_index,
                row[month],
                month_format,
            )

        first_month_col = _xlsx_col(start_col + 2)
        last_month_col = _xlsx_col(start_col + 1 + len(MONTHS))
        formula = f"=SUM({first_month_col}{excel_row + 1}:{last_month_col}{excel_row + 1})"
        if total_formula_kind == "average":
            formula = f"=AVERAGE({first_month_col}{excel_row + 1}:{last_month_col}{excel_row + 1})"
        worksheet.write_formula(
            excel_row,
            start_col + 2 + len(MONTHS),
            formula,
            formats["formula_currency"] if total_formula_kind == "average" else formats["formula"],
        )

    total_row = start_row + 2 + len(data)
    worksheet.write(total_row, start_col, f"Total {title}", formats["total"])
    worksheet.write(total_row, start_col + 1, "", formats["total"])
    for month_index, _month in enumerate(MONTHS):
        col_number = start_col + 2 + month_index
        col_letter = _xlsx_col(col_number)
        first_data_row = start_row + 3
        last_data_row = start_row + 2 + len(data)
        formula = "0" if len(data) == 0 else f"=SUM({col_letter}{first_data_row}:{col_letter}{last_data_row})"
        worksheet.write_formula(total_row, col_number, formula, formats["total"])

    total_col = start_col + 2 + len(MONTHS)
    total_col_letter = _xlsx_col(total_col)
    first_data_row = start_row + 3
    last_data_row = start_row + 2 + len(data)
    formula = "0" if len(data) == 0 else f"=SUM({total_col_letter}{first_data_row}:{total_col_letter}{last_data_row})"
    if total_formula_kind == "average":
        worksheet.write_blank(total_row, total_col, None, formats["total"])
    else:
        worksheet.write_formula(total_row, total_col, formula, formats["total"])
    return total_row


def _write_revenue_block(worksheet, start_row, rows, units_start, price_start, formats):
    start_col = 1
    headers = ["Revenue Item", "Customer"] + MONTHS + ["FY Revenue"]

    worksheet.write(start_row, start_col, "Revenue", formats["section"])
    worksheet.write_row(start_row + 1, start_col, headers, formats["header"])

    for row_index in range(rows):
        excel_row = start_row + 2 + row_index
        units_row = units_start + 3 + row_index
        price_row = price_start + 3 + row_index
        worksheet.write_formula(excel_row, start_col, f"=B{units_row}", formats["formula"])
        worksheet.write_formula(excel_row, start_col + 1, f"=C{units_row}", formats["formula"])

        for month_index, _month in enumerate(MONTHS):
            col_number = start_col + 2 + month_index
            col_letter = _xlsx_col(col_number)
            worksheet.write_formula(
                excel_row,
                col_number,
                f"={col_letter}{units_row}*{col_letter}{price_row}",
                formats["formula"],
            )

        first_month_col = _xlsx_col(start_col + 2)
        last_month_col = _xlsx_col(start_col + 1 + len(MONTHS))
        worksheet.write_formula(
            excel_row,
            start_col + 2 + len(MONTHS),
            f"=SUM({first_month_col}{excel_row + 1}:{last_month_col}{excel_row + 1})",
            formats["formula"],
        )

    total_row = start_row + 2 + rows
    worksheet.write(total_row, start_col, "Total Revenue", formats["total"])
    worksheet.write(total_row, start_col + 1, "", formats["total"])
    first_data_row = start_row + 3
    last_data_row = start_row + 2 + rows
    for month_index in range(len(MONTHS) + 1):
        col_number = start_col + 2 + month_index
        col_letter = _xlsx_col(col_number)
        formula = "0" if rows == 0 else f"=SUM({col_letter}{first_data_row}:{col_letter}{last_data_row})"
        worksheet.write_formula(total_row, col_number, formula, formats["total"])


def _xlsx_col(zero_based_col: int) -> str:
    letters = ""
    col = zero_based_col
    while col >= 0:
        col, remainder = divmod(col, 26)
        letters = chr(65 + remainder) + letters
        col -= 1
    return letters
