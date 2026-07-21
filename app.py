from __future__ import annotations

from datetime import date
from uuid import uuid4

import pandas as pd
import streamlit as st

from revenue_model import (
    MONTHS,
    ModelConfig,
    export_assumptions_workbook,
)


BILLING_TYPES = ["Monthly recurring", "One-off invoice"]
CUSTOMER_TYPES = ["Existing customer", "New customer"]


st.set_page_config(
    page_title="Budget Generator",
    layout="wide",
)


def main() -> None:
    st.title("Budget Generator")
    st.caption("Annual sales budget")

    with st.sidebar:
        st.header("Budget setup")
        budget_year = st.number_input(
            "Budget year",
            min_value=2024,
            max_value=2035,
            value=date.today().year,
            step=1,
        )

    st.subheader("1. Choose company type")
    company_type = st.radio(
        "The user first chooses:",
        options=["Services company", "Goods company"],
        horizontal=True,
    )
    item_label = "Product" if company_type == "Goods company" else "Service"

    _initialize_state(company_type, item_label)

    st.subheader("2. Define country and office location")
    _office_location_flow()

    st.subheader(f"3. Define customers and {item_label.lower()}s")
    customers, products = _master_data_flow(item_label)

    st.subheader("4. Input sales lines")
    st.caption(
        "One row = one customer, one product/service, one billing logic. "
        "For recurring sales, use Start Month and End Month. For one-off invoices, use Invoice Month."
    )

    st.session_state.sales_lines = _sanitize_sales_lines_against_master_data(
        st.session_state.sales_lines,
        customers,
        products,
    )
    existing_customers = _customers_by_type(st.session_state.customers, "Existing customer")
    new_customers = _customers_by_type(st.session_state.customers, "New customer")

    with st.form("sales_lines_form"):
        existing_lines = _sales_lines_editor(
            title="Existing customers",
            customer_type="Existing customer",
            customer_options=existing_customers,
            products=products,
            item_label=item_label,
            key="existing_sales_lines_editor",
        )
        new_lines = _sales_lines_editor(
            title="New customers",
            customer_type="New customer",
            customer_options=new_customers,
            products=products,
            item_label=item_label,
            key="new_sales_lines_editor",
        )
        sales_submitted = st.form_submit_button("Update sales budget", type="primary")

    if sales_submitted:
        normalized_lines = normalize_sales_lines(
            pd.concat([existing_lines, new_lines], ignore_index=True)
        )
        normalized_lines = _apply_customer_types_from_master(
            normalized_lines,
            st.session_state.customers,
        )
        st.session_state.sales_lines = normalized_lines

    units_by_month, prices_by_month, preview = build_monthly_sales_budget(
        st.session_state.sales_lines
    )

    st.subheader("5. Monthly revenue preview")
    format_map = {month: "{:,.0f}" for month in MONTHS}
    format_map["FY Total"] = "{:,.0f}"
    st.dataframe(preview.style.format(format_map), width="stretch")

    workbook_bytes = export_assumptions_workbook(
        units_by_month,
        prices_by_month,
        ModelConfig(
            budget_year=int(budget_year),
            company_type=company_type,
            revenue_model="Sales lines",
        ),
    )

    st.download_button(
        label="Download Excel assumptions sheet",
        data=workbook_bytes,
        file_name="budget_generator_sales_assumptions.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
    )


def _initialize_state(company_type: str, item_label: str) -> None:
    required_keys = ["offices", "customers", "products", "sales_lines"]
    has_required_state = all(key in st.session_state for key in required_keys)
    if (
        has_required_state
        and st.session_state.get("company_type") == company_type
    ):
        return

    st.session_state.company_type = company_type
    st.session_state.offices = pd.DataFrame(
        {"Country": ["Spain"], "Office Location": ["Madrid"]}
    )
    st.session_state.customers = pd.DataFrame(
        {"Customer": ["Customer 1", "New Customer 1"]}
    )
    st.session_state.products = pd.DataFrame(
        {"Product / Service": [f"{item_label} 1", f"{item_label} 2"]}
    )
    st.session_state.sales_lines = pd.DataFrame(
        [
            {
                "Line ID": _new_sales_line_id(),
                "Customer Type": "Existing customer",
                "Customer": "Customer 1",
                "Product / Service": f"{item_label} 1",
                "Billing Type": "Monthly recurring",
                "Start Month": "Jan",
                "End Month": "Dec",
                "Invoice Month": "Jan",
                "Units": 100.0,
                "Unit Price": 50.0,
            },
            {
                "Line ID": _new_sales_line_id(),
                "Customer Type": "New customer",
                "Customer": "New Customer 1",
                "Product / Service": f"{item_label} 2",
                "Billing Type": "One-off invoice",
                "Start Month": "Jan",
                "End Month": "Dec",
                "Invoice Month": "Sep",
                "Units": 20.0,
                "Unit Price": 1000.0,
            },
        ]
    )


def _office_location_flow() -> pd.DataFrame:
    offices_edited = st.data_editor(
        st.session_state.offices,
        num_rows="dynamic",
        width="stretch",
        hide_index=True,
        column_config={
            "Country": st.column_config.TextColumn("Country", required=True),
            "Office Location": st.column_config.TextColumn(
                "Office Location",
                required=True,
            ),
        },
        key="offices_editor",
    )
    offices = _normalize_offices(pd.DataFrame(offices_edited))
    st.session_state.offices = offices
    return offices


def _normalize_offices(df: pd.DataFrame) -> pd.DataFrame:
    clean = df.copy()
    if "Country" not in clean.columns:
        clean["Country"] = "Spain"
    if "Office Location" not in clean.columns:
        clean["Office Location"] = "Madrid"

    clean = clean[["Country", "Office Location"]]
    clean["Country"] = clean["Country"].fillna("").astype(str).str.strip()
    clean["Office Location"] = (
        clean["Office Location"].fillna("").astype(str).str.strip()
    )
    clean = clean[
        (clean["Country"] != "") & (clean["Office Location"] != "")
    ].drop_duplicates().reset_index(drop=True)
    if clean.empty:
        clean = pd.DataFrame({"Country": ["Spain"], "Office Location": ["Madrid"]})
    return clean


def _master_data_flow(item_label: str) -> tuple[list[str], list[str]]:
    st.markdown(f"**{item_label}s**")
    products_edited = st.data_editor(
        st.session_state.products,
        num_rows="dynamic",
        width="stretch",
        hide_index=True,
        column_config={
            "Product / Service": st.column_config.TextColumn(item_label, required=True),
        },
        key="products_editor",
    )

    st.markdown("**Customers**")
    customers_edited = st.data_editor(
        st.session_state.customers,
        num_rows="dynamic",
        width="stretch",
        hide_index=True,
        column_config={
            "Customer": st.column_config.TextColumn("Customer", required=True),
        },
        key="customers_editor",
    )

    customers_df = _normalize_customers(pd.DataFrame(customers_edited))
    products_df = _normalize_products(pd.DataFrame(products_edited), item_label)
    st.session_state.customers = customers_df
    st.session_state.products = products_df
    return customers_df["Customer"].tolist(), products_df["Product / Service"].tolist()


def _normalize_customers(df: pd.DataFrame) -> pd.DataFrame:
    clean = df.copy()
    if "Customer" not in clean.columns:
        clean["Customer"] = "Customer 1"

    clean = clean[["Customer"]]
    clean["Customer"] = clean["Customer"].fillna("").astype(str).str.strip()
    clean = clean[clean["Customer"] != ""].drop_duplicates("Customer").reset_index(drop=True)
    if clean.empty:
        clean = pd.DataFrame({"Customer": ["Customer 1"]})
    return clean


def _normalize_products(df: pd.DataFrame, item_label: str) -> pd.DataFrame:
    clean = df.copy()
    if item_label in clean.columns and "Product / Service" not in clean.columns:
        clean = clean.rename(columns={item_label: "Product / Service"})
    if "Product / Service" not in clean.columns:
        clean["Product / Service"] = f"{item_label} 1"

    clean = clean[["Product / Service"]]
    clean["Product / Service"] = (
        clean["Product / Service"].fillna("").astype(str).str.strip()
    )
    clean = clean[clean["Product / Service"] != ""].drop_duplicates().reset_index(drop=True)
    if clean.empty:
        clean = pd.DataFrame({"Product / Service": [f"{item_label} 1"]})
    return clean


def _sanitize_sales_lines_against_master_data(
    sales_lines: pd.DataFrame,
    customers: list[str],
    products: list[str],
) -> pd.DataFrame:
    clean = normalize_sales_lines(sales_lines)
    clean["Customer"] = clean["Customer"].where(clean["Customer"].isin(customers), customers[0])
    clean["Product / Service"] = clean["Product / Service"].where(
        clean["Product / Service"].isin(products),
        products[0],
    )
    return clean


def _customers_by_type(customers_df: pd.DataFrame, customer_type: str) -> list[str]:
    customers = customers_df["Customer"].tolist()
    if customers:
        return customers
    fallback = "Customer 1" if customer_type == "Existing customer" else "New Customer 1"
    return [fallback]


def _sales_lines_editor(
    title: str,
    customer_type: str,
    customer_options: list[str],
    products: list[str],
    item_label: str,
    key: str,
) -> pd.DataFrame:
    st.markdown(f"**{title}**")
    source = st.session_state.sales_lines[
        st.session_state.sales_lines["Customer Type"] == customer_type
    ].copy()
    if source.empty:
        source = pd.DataFrame(
            [
                {
                    "Line ID": _new_sales_line_id(),
                    "Customer Type": customer_type,
                    "Customer": customer_options[0],
                    "Product / Service": products[0],
                    "Billing Type": "Monthly recurring",
                    "Start Month": "Jan",
                    "End Month": "Dec",
                    "Invoice Month": "Jan",
                    "Units": 0.0,
                    "Unit Price": 0.0,
                }
            ]
        )

    source = _sanitize_sales_lines_against_master_data(source, customer_options, products)
    editable = source.drop(columns=["Customer Type"])
    edited = st.data_editor(
        editable,
        num_rows="dynamic",
        width="stretch",
        hide_index=True,
        column_config={
            "Line ID": None,
            "Customer": st.column_config.SelectboxColumn(
                "Customer",
                options=customer_options,
                required=True,
            ),
            "Product / Service": st.column_config.SelectboxColumn(
                item_label,
                options=products,
                required=True,
            ),
            "Billing Type": st.column_config.SelectboxColumn(
                "Billing Type",
                options=BILLING_TYPES,
                required=True,
            ),
            "Start Month": st.column_config.SelectboxColumn("Start Month", options=MONTHS),
            "End Month": st.column_config.SelectboxColumn("End Month", options=MONTHS),
            "Invoice Month": st.column_config.SelectboxColumn("Invoice Month", options=MONTHS),
            "Units": st.column_config.NumberColumn(
                "Units",
                min_value=0.0,
                step=1.0,
                format="%.2f",
            ),
            "Unit Price": st.column_config.NumberColumn(
                "Unit Price",
                min_value=0.0,
                step=1.0,
                format="%.2f",
            ),
        },
        key=key,
    )
    clean = normalize_sales_lines(pd.DataFrame(edited))
    clean["Customer Type"] = customer_type
    return clean


def _apply_customer_types_from_master(
    sales_lines: pd.DataFrame,
    customers_df: pd.DataFrame,
) -> pd.DataFrame:
    return sales_lines.copy()


def normalize_sales_lines(df: pd.DataFrame) -> pd.DataFrame:
    clean = df.copy()
    expected_columns = [
        "Line ID",
        "Customer Type",
        "Customer",
        "Product / Service",
        "Billing Type",
        "Start Month",
        "End Month",
        "Invoice Month",
        "Units",
        "Unit Price",
    ]

    defaults = {
        "Line ID": "",
        "Customer Type": "Existing customer",
        "Customer": "",
        "Product / Service": "",
        "Billing Type": "Monthly recurring",
        "Start Month": "Jan",
        "End Month": "Dec",
        "Invoice Month": "Jan",
        "Units": 0.0,
        "Unit Price": 0.0,
    }

    for column in expected_columns:
        if column not in clean.columns:
            clean[column] = defaults[column]

    clean = clean[expected_columns]
    for column in [
        "Customer Type",
        "Customer",
        "Product / Service",
        "Billing Type",
        "Start Month",
        "End Month",
        "Invoice Month",
    ]:
        clean[column] = clean[column].fillna(defaults[column]).astype(str)

    clean["Line ID"] = clean["Line ID"].fillna("").astype(str).str.strip()
    clean = _ensure_unique_sales_line_ids(clean)

    clean["Customer Type"] = clean["Customer Type"].where(
        clean["Customer Type"].isin(CUSTOMER_TYPES),
        "Existing customer",
    )
    clean["Billing Type"] = clean["Billing Type"].where(
        clean["Billing Type"].isin(BILLING_TYPES),
        "Monthly recurring",
    )
    for column in ["Start Month", "End Month", "Invoice Month"]:
        clean[column] = clean[column].where(clean[column].isin(MONTHS), defaults[column])

    clean["Units"] = pd.to_numeric(clean["Units"], errors="coerce").fillna(0)
    clean["Unit Price"] = pd.to_numeric(clean["Unit Price"], errors="coerce").fillna(0)
    return clean


def _new_sales_line_id() -> str:
    return f"line_{uuid4().hex}"


def _ensure_unique_sales_line_ids(sales_lines: pd.DataFrame) -> pd.DataFrame:
    clean = sales_lines.copy()
    seen: set[str] = set()
    stable_ids: list[str] = []
    for line_id in clean["Line ID"].tolist():
        if not line_id or line_id in seen:
            line_id = _new_sales_line_id()
        seen.add(line_id)
        stable_ids.append(line_id)
    clean["Line ID"] = stable_ids
    return clean


def build_monthly_sales_budget(
    sales_lines: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    lines = normalize_sales_lines(sales_lines)

    units = pd.DataFrame(
        {
            "Revenue Item": lines["Product / Service"],
            "Customer": lines["Customer"],
        }
    )
    prices = units.copy()
    preview = lines[
        ["Customer Type", "Customer", "Product / Service", "Billing Type"]
    ].copy()

    for month in MONTHS:
        units[month] = 0.0
        prices[month] = 0.0
        preview[month] = 0.0

    for row_index, row in lines.iterrows():
        active_months = _active_months(row)
        for month in active_months:
            units.loc[row_index, month] = row["Units"]
            prices.loc[row_index, month] = row["Unit Price"]
            preview.loc[row_index, month] = row["Units"] * row["Unit Price"]

    preview["FY Total"] = preview[MONTHS].sum(axis=1)
    total_row = pd.DataFrame(
        [
            {
                "Customer Type": "Total Revenue",
                "Customer": "",
                "Product / Service": "",
                "Billing Type": "",
                **{month: preview[month].sum() for month in MONTHS},
                "FY Total": preview["FY Total"].sum(),
            }
        ]
    )
    preview = pd.concat([preview, total_row], ignore_index=True)
    return units, prices, preview


def _active_months(row: pd.Series) -> list[str]:
    if row["Billing Type"] == "One-off invoice":
        return [row["Invoice Month"]]

    start_index = MONTHS.index(row["Start Month"])
    end_index = MONTHS.index(row["End Month"])
    if end_index < start_index:
        return []
    return MONTHS[start_index : end_index + 1]


if __name__ == "__main__":
    main()
