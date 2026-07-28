from __future__ import annotations

import sqlite3
from datetime import date, datetime, timezone
from hmac import compare_digest
from html import escape
from os import environ
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st


APP_DIR = Path(__file__).resolve().parent
DB_PATH = APP_DIR / "accounting_timeline.sqlite3"

ROLES = [
    "AR Specialist",
    "AP Specialist",
    "Treasury Accountant",
    "Senior Accountant",
    "Controller",
    "CFO",
]

AREAS = [
    "AR Activities",
    "AP Activities",
    "Treasury Accounting",
    "General Ledger",
    "Close Review",
]

MONTHS = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]

STATUS_COLORS = {
    "Completed": "#16a34a",
    "In progress": "#2563eb",
    "Not started": "#9ca3af",
}
VALID_STATUSES = list(STATUS_COLORS.keys())

RACI_COLUMNS = ["Activity", "Responsible", "Accountable", "Consulted", "Informed"]
SETUP_PAGES = ["Setup master", "RACI Matrix setup", "Timeline setup", "Change Log"]
RESULT_PAGES = ["RACI Matrix", "Timeline"]
PAGES = [*SETUP_PAGES, *RESULT_PAGES]

FINANCE_MODULES = [
    {"Name": "Accounting", "Status": "Available", "Description": "Ownership and timing live in this MVP."},
    {"Name": "FP&A", "Status": "Locked", "Description": "Planning, forecasting, and business reporting."},
    {"Name": "Treasury", "Status": "Locked", "Description": "Cash, banking, liquidity, and funding."},
    {"Name": "Accounts Payable", "Status": "Locked", "Description": "Supplier invoices, payments, and approvals."},
    {"Name": "Accounts Receivable", "Status": "Locked", "Description": "Customer billing, collections, and cash application."},
    {"Name": "Tax & Compliance", "Status": "Locked", "Description": "Filings, controls, policies, and regulatory tasks."},
    {"Name": "Procurement", "Status": "Locked", "Description": "Purchase requests, vendors, and spend governance."},
    {"Name": "Payroll", "Status": "Locked", "Description": "Payroll inputs, postings, and employee cost controls."},
]

RACI_DATA = [
    {"Area": "AR Activities", "Activity": "Customer invoice recording", "Responsible": "AR Specialist", "Accountable": "Controller", "Consulted": "Senior Accountant", "Informed": "CFO"},
    {"Area": "AR Activities", "Activity": "Revenue cut-off review", "Responsible": "AR Specialist", "Accountable": "Controller", "Consulted": "Senior Accountant", "Informed": "CFO"},
    {"Area": "AR Activities", "Activity": "Accounts receivable reconciliation", "Responsible": "AR Specialist", "Accountable": "Controller", "Consulted": "Senior Accountant", "Informed": "CFO"},
    {"Area": "AP Activities", "Activity": "Supplier invoice recording", "Responsible": "AP Specialist", "Accountable": "Controller", "Consulted": "Senior Accountant", "Informed": "CFO"},
    {"Area": "AP Activities", "Activity": "Month-end expense accruals review", "Responsible": "AP Specialist", "Accountable": "Controller", "Consulted": "Senior Accountant", "Informed": "CFO"},
    {"Area": "AP Activities", "Activity": "AP subledger to GL reconciliation", "Responsible": "AP Specialist", "Accountable": "Controller", "Consulted": "Senior Accountant", "Informed": "CFO"},
    {"Area": "Treasury Accounting", "Activity": "Bank statement import and coding", "Responsible": "Treasury Accountant", "Accountable": "Controller", "Consulted": "AP Specialist, AR Specialist", "Informed": "CFO"},
    {"Area": "Treasury Accounting", "Activity": "Bank reconciliation", "Responsible": "Treasury Accountant", "Accountable": "Controller", "Consulted": "Senior Accountant", "Informed": "CFO"},
    {"Area": "Treasury Accounting", "Activity": "Cash and bank GL postings", "Responsible": "Treasury Accountant", "Accountable": "Controller", "Consulted": "Senior Accountant", "Informed": "CFO"},
    {"Area": "General Ledger", "Activity": "Journal entries preparation", "Responsible": "Senior Accountant", "Accountable": "Controller", "Consulted": "AP Specialist, AR Specialist, Treasury Accountant", "Informed": "CFO"},
    {"Area": "General Ledger", "Activity": "Accruals and prepayments review", "Responsible": "Senior Accountant", "Accountable": "Controller", "Consulted": "AP Specialist", "Informed": "CFO"},
    {"Area": "General Ledger", "Activity": "Fixed assets accounting", "Responsible": "Senior Accountant", "Accountable": "Controller", "Consulted": "AP Specialist", "Informed": "CFO"},
    {"Area": "General Ledger", "Activity": "Balance sheet reconciliations", "Responsible": "Senior Accountant", "Accountable": "Controller", "Consulted": "AP Specialist, AR Specialist, Treasury Accountant", "Informed": "CFO"},
    {"Area": "General Ledger", "Activity": "Intercompany accounting", "Responsible": "Senior Accountant", "Accountable": "Controller", "Consulted": "Treasury Accountant", "Informed": "CFO"},
    {"Area": "Close Review", "Activity": "Trial balance review", "Responsible": "Controller", "Accountable": "CFO", "Consulted": "Senior Accountant", "Informed": "AR Specialist, AP Specialist, Treasury Accountant"},
    {"Area": "Close Review", "Activity": "Monthly financial statements preparation", "Responsible": "Controller", "Accountable": "CFO", "Consulted": "Senior Accountant", "Informed": "AR Specialist, AP Specialist, Treasury Accountant"},
    {"Area": "Close Review", "Activity": "Final monthly close approval", "Responsible": "Controller", "Accountable": "CFO", "Consulted": "Senior Accountant", "Informed": "AR Specialist, AP Specialist, Treasury Accountant"},
    {"Area": "Close Review", "Activity": "Financial statements submission", "Responsible": "Controller", "Accountable": "CFO", "Consulted": "Senior Accountant", "Informed": "CEO"},
]

TIMING_RULES = [
    {"Activity": "Customer invoice recording", "Start offset": -8, "End offset": -6, "Status": "In progress"},
    {"Activity": "Revenue cut-off review", "Start offset": -3, "End offset": -2, "Status": "Not started"},
    {"Activity": "Accounts receivable reconciliation", "Start offset": -1, "End offset": 1, "Status": "Not started"},
    {"Activity": "Supplier invoice recording", "Start offset": -8, "End offset": -5, "Status": "In progress"},
    {"Activity": "Month-end expense accruals review", "Start offset": -3, "End offset": -1, "Status": "Not started"},
    {"Activity": "AP subledger to GL reconciliation", "Start offset": 0, "End offset": 2, "Status": "Not started"},
    {"Activity": "Bank statement import and coding", "Start offset": -8, "End offset": -8, "Status": "Completed"},
    {"Activity": "Bank reconciliation", "Start offset": -7, "End offset": -4, "Status": "In progress"},
    {"Activity": "Cash and bank GL postings", "Start offset": -7, "End offset": -4, "Status": "In progress"},
    {"Activity": "Journal entries preparation", "Start offset": -2, "End offset": 0, "Status": "Not started"},
    {"Activity": "Accruals and prepayments review", "Start offset": -2, "End offset": 1, "Status": "Not started"},
    {"Activity": "Fixed assets accounting", "Start offset": -4, "End offset": -3, "Status": "Completed"},
    {"Activity": "Balance sheet reconciliations", "Start offset": 1, "End offset": 3, "Status": "Not started"},
    {"Activity": "Intercompany accounting", "Start offset": 1, "End offset": 3, "Status": "Not started"},
    {"Activity": "Trial balance review", "Start offset": 4, "End offset": 4, "Status": "Not started"},
    {"Activity": "Monthly financial statements preparation", "Start offset": 5, "End offset": 7, "Status": "Not started"},
    {"Activity": "Final monthly close approval", "Start offset": 8, "End offset": 8, "Status": "Not started"},
    {"Activity": "Financial statements submission", "Start offset": 9, "End offset": 10, "Status": "Not started"},
]


def main() -> None:
    st.set_page_config(
        page_title="Finance RACI Timeline",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    _init_db()
    _apply_theme()
    _show_queued_toast()

    finance_modules = _load_finance_modules()
    active_finance_area = "Accounting"
    roles = _load_roles()
    areas = _load_areas(active_finance_area)
    if "active_page" not in st.session_state:
        st.session_state["active_page"] = "Setup master"
    query_page = st.query_params.get("view")
    if query_page in PAGES:
        st.session_state["active_page"] = query_page

    nav_col, content_col = st.columns([0.22, 0.78], gap="large")
    with nav_col:
        page, selected_role, selected_area = _left_navigation(roles, areas, st.session_state["active_page"])

    with content_col:
        page = _render_result_navigation(page)
        if page == "Setup master":
            _render_setup_master(roles, areas, finance_modules)
        elif page == "RACI Matrix":
            source = _load_ownership_data()
            filtered = _filter_raci(source, selected_role, selected_area)
            _render_raci_matrix_page(filtered, selected_role, finance_modules)
        elif page == "RACI Matrix setup":
            source = _load_ownership_data()
            filtered = _filter_raci(source, selected_role, selected_area)
            _render_raci_setup_page(filtered, roles, areas)
        elif page == "Timeline":
            source = _load_ownership_data()
            filtered = _filter_timeline(source, selected_role, selected_area)
            _render_timeline(filtered)
        elif page == "Timeline setup":
            source = _load_ownership_data()
            filtered = _filter_timeline(source, selected_role, selected_area)
            _render_timeline_setup(filtered)
        else:
            _render_change_log_page()


def _init_db() -> None:
    _ensure_db_initialized(_database_url() or str(DB_PATH))


@st.cache_resource(show_spinner=False)
def _ensure_db_initialized(_cache_key: str) -> None:
    with _connect() as conn:
        for statement in _schema_statements():
            conn.execute(statement)
        conn.commit()


def _connect() -> Any:
    database_url = _database_url()
    if database_url:
        return _PostgresConnectionContext(database_url)
    return sqlite3.connect(DB_PATH)


class _PostgresConnectionContext:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    def __enter__(self) -> Any:
        return _postgres_connection(self.database_url)

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> bool:
        try:
            if exc_type is None:
                _postgres_connection(self.database_url).commit()
            else:
                _postgres_connection(self.database_url).rollback()
        except Exception:
            _postgres_connection.clear()
        return False


@st.cache_resource(show_spinner=False)
def _postgres_connection(database_url: str) -> Any:
    try:
        import psycopg
    except ModuleNotFoundError:
        st.error("Database driver missing. Install the project requirements before using the public database.")
        st.stop()
    try:
        return psycopg.connect(database_url)
    except Exception as exc:
        st.error(f"Could not connect to the configured database: {exc}")
        st.stop()


def _schema_statements() -> list[str]:
    finance_modules_table = """
        CREATE TABLE IF NOT EXISTS master_finance_modules (
            name TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            description TEXT NOT NULL,
            sort_order INTEGER NOT NULL
        )
    """
    roles_table = """
        CREATE TABLE IF NOT EXISTS master_roles (
            name TEXT PRIMARY KEY,
            sort_order INTEGER NOT NULL
        )
    """
    areas_table = """
        CREATE TABLE IF NOT EXISTS master_areas (
            name TEXT PRIMARY KEY,
            sort_order INTEGER NOT NULL
        )
    """
    department_areas_table = """
        CREATE TABLE IF NOT EXISTS master_department_areas (
            finance_area TEXT NOT NULL,
            name TEXT NOT NULL,
            sort_order INTEGER NOT NULL,
            PRIMARY KEY (finance_area, name)
        )
    """
    ownership_table = """
        CREATE TABLE IF NOT EXISTS ownership_overrides (
            activity TEXT PRIMARY KEY,
            area TEXT NOT NULL,
            responsible TEXT NOT NULL,
            accountable TEXT NOT NULL,
            consulted TEXT NOT NULL,
            informed TEXT NOT NULL
        )
    """
    timeline_table = """
        CREATE TABLE IF NOT EXISTS timeline_overrides (
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            activity TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            status TEXT NOT NULL,
            PRIMARY KEY (year, month, activity)
        )
    """
    if _using_postgres():
        change_log_table = """
            CREATE TABLE IF NOT EXISTS change_log (
                id BIGSERIAL PRIMARY KEY,
                changed_at TEXT NOT NULL,
                year INTEGER NOT NULL,
                month INTEGER NOT NULL,
                activity TEXT NOT NULL,
                field TEXT NOT NULL,
                old_value TEXT NOT NULL,
                new_value TEXT NOT NULL,
                action TEXT NOT NULL
            )
        """
    else:
        change_log_table = """
            CREATE TABLE IF NOT EXISTS change_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                changed_at TEXT NOT NULL,
                year INTEGER NOT NULL,
                month INTEGER NOT NULL,
                activity TEXT NOT NULL,
                field TEXT NOT NULL,
                old_value TEXT NOT NULL,
                new_value TEXT NOT NULL,
                action TEXT NOT NULL
            )
        """
    return [
        finance_modules_table,
        roles_table,
        areas_table,
        department_areas_table,
        ownership_table,
        timeline_table,
        change_log_table,
    ]


def _database_url() -> str | None:
    value = _secret_value("database_url") or environ.get("DATABASE_URL")
    if value is None:
        return None
    value = str(value).strip()
    if not value or "@host" in value or "user:password" in value:
        return None
    return value or None


def _using_postgres() -> bool:
    return _database_url() is not None


def _placeholders(count: int) -> str:
    marker = "%s" if _using_postgres() else "?"
    return ", ".join([marker] * count)


def _executemany(conn: Any, sql: str, rows: list[tuple[Any, ...]]) -> None:
    if not rows:
        return
    if _using_postgres():
        with conn.cursor() as cursor:
            cursor.executemany(sql, rows)
        return
    conn.executemany(sql, rows)


def _secret_value(name: str) -> Any:
    try:
        return st.secrets.get(name, None)
    except Exception:
        return None


def _queue_toast(message: str) -> None:
    st.session_state["toast_message"] = message


def _show_queued_toast() -> None:
    message = st.session_state.pop("toast_message", None)
    if message:
        st.toast(message)


def _clear_cached_data() -> None:
    st.cache_data.clear()


def _apply_theme() -> None:
    st.markdown(
        """
        <style>
        section[data-testid="stSidebar"] { background: #f7f8fb; }
        div[data-testid="stColumn"]:has(.left-nav-title),
        div[data-testid="column"]:has(.left-nav-title) {
            position: relative;
            border-right: 2px solid #cbd5e1;
            padding: 18px 30px 18px 0;
            min-height: 92vh;
            background: linear-gradient(90deg, #ffffff 0%, #ffffff 94%, #f8fafc 100%);
        }
        div[data-testid="stColumn"]:has(.left-nav-title)::after,
        div[data-testid="column"]:has(.left-nav-title)::after {
            content: "";
            position: absolute;
            top: 0;
            right: -16px;
            width: 1px;
            height: 100%;
            background: #e2e8f0;
        }
        div[data-testid="stColumn"]:has(.left-nav-title) + div[data-testid="stColumn"],
        div[data-testid="column"]:has(.left-nav-title) + div[data-testid="column"] {
            padding-left: 14px;
        }
        .top-nav-label {
            color: #667085;
            font-size: 0.72rem;
            font-weight: 900;
            letter-spacing: 0.08em;
            margin: 4px 0 10px;
            text-transform: uppercase;
        }
        .key-view-title {
            display: block;
            font-size: 2.15rem;
            font-weight: 900;
            line-height: 1.15;
            margin: 4px 0 10px;
            color: #1f2937;
            text-decoration: none !important;
        }
        .key-view-copy {
            display: block;
            color: #667085;
            font-size: 1.02rem;
            font-weight: 600;
            line-height: 1.25;
            text-decoration: none !important;
            max-width: 520px;
        }
        div[data-testid="stVerticalBlockBorderWrapper"] {
            border-radius: 14px;
            border-color: #d8dee9;
            background: linear-gradient(180deg, #ffffff 0%, #fbfdff 100%);
            box-shadow: 0 10px 28px rgba(15, 23, 42, 0.07);
        }
        div[data-testid="stVerticalBlockBorderWrapper"]:has(button[kind="primary"]) {
            border-color: #2563eb;
            background: #eff6ff;
            box-shadow: inset 6px 0 0 #2563eb, 0 14px 30px rgba(37, 99, 235, 0.14);
        }
        .left-nav-title {
            color: #2d3142;
            font-size: 1.35rem;
            font-weight: 900;
            margin: 4px 0 12px;
        }
        [data-testid="collapsedControl"],
        [data-testid="stSidebarCollapsedControl"] {
            visibility: visible !important;
            display: flex !important;
            position: fixed !important;
            top: 18px !important;
            left: 18px !important;
            z-index: 999999 !important;
            align-items: center !important;
            gap: 8px !important;
            border: 1px solid #bfdbfe !important;
            border-radius: 8px !important;
            background: #eff6ff !important;
            color: #1d4ed8 !important;
            padding: 8px 12px !important;
            box-shadow: 0 4px 12px rgba(37, 99, 235, 0.16) !important;
        }
        [data-testid="collapsedControl"]::after,
        [data-testid="stSidebarCollapsedControl"]::after {
            content: "Show menu";
            font-size: 0.9rem;
            font-weight: 800;
            color: #1d4ed8;
        }
        [data-testid="stToolbar"], [data-testid="stDecoration"], [data-testid="stStatusWidget"], #MainMenu {
            visibility: hidden;
            height: 0;
        }
        header {
            visibility: visible !important;
            background: transparent;
            height: 3.25rem;
            pointer-events: auto;
        }
        section[data-testid="stSidebar"] div[role="radiogroup"] { gap: 8px; }
        section[data-testid="stSidebar"] div[role="radiogroup"] label {
            background: #ffffff;
            border: 1px solid #e1e5ee;
            border-radius: 8px;
            padding: 0 16px;
            width: 100%;
            min-height: 64px;
            height: 64px;
            box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04);
            display: flex;
            align-items: center;
        }
        section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) {
            border-color: #2563eb;
            background: #eff6ff;
            box-shadow: inset 4px 0 0 #2563eb;
        }
        section[data-testid="stSidebar"] div[role="radiogroup"] label p {
            font-size: 1.08rem;
            font-weight: 800;
            color: #2d3142;
        }
        section[data-testid="stSidebar"] div[role="radiogroup"] label:nth-of-type(5) {
            margin-top: 28px;
            position: relative;
        }
        section[data-testid="stSidebar"] div[role="radiogroup"] label:nth-of-type(5)::before {
            content: "RESULTS";
            position: absolute;
            top: -24px;
            left: 0;
            color: #667085;
            font-size: 0.72rem;
            font-weight: 900;
            letter-spacing: 0.08em;
        }
        section[data-testid="stSidebar"] div[role="radiogroup"] label:nth-of-type(-n+4)::after {
            content: "Setup";
            margin-left: auto;
            border-radius: 999px;
            background: #f2f4f7;
            color: #667085;
            font-size: 0.68rem;
            font-weight: 800;
            padding: 3px 8px;
        }
        section[data-testid="stSidebar"] div[role="radiogroup"] label:nth-of-type(n+5) {
            border-color: #bfdbfe;
            background: #f8fbff;
            min-height: 74px;
            height: 74px;
            box-shadow: 0 2px 8px rgba(37, 99, 235, 0.08);
        }
        section[data-testid="stSidebar"] div[role="radiogroup"] label:nth-of-type(n+5) p {
            color: #174ea6;
            font-size: 1.14rem;
        }
        section[data-testid="stSidebar"] div[role="radiogroup"] label:nth-of-type(n+5)::after {
            content: "View";
            margin-left: auto;
            border-radius: 999px;
            background: #dbeafe;
            color: #1d4ed8;
            font-size: 0.68rem;
            font-weight: 900;
            padding: 3px 8px;
        }
        section[data-testid="stSidebar"] div[role="radiogroup"] label:nth-of-type(n+5):has(input:checked) {
            border-color: #2563eb;
            background: #eff6ff;
            box-shadow: inset 4px 0 0 #2563eb, 0 4px 12px rgba(37, 99, 235, 0.14);
        }
        .legend-card {
            border-radius: 8px;
            border-left: 6px solid;
            padding: 10px 12px;
            margin: 8px 0;
            background: #ffffff;
            box-shadow: 0 1px 2px rgba(16, 24, 40, 0.05);
        }
        .legend-card strong {
            display: block;
            color: #252936;
            font-size: 0.95rem;
            line-height: 1.2;
            margin-bottom: 2px;
        }
        .legend-card span {
            display: block;
            color: #666f80;
            font-size: 0.82rem;
            line-height: 1.25;
        }
        .responsible { border-left-color: #2563eb; background: #eff6ff; }
        .accountable { border-left-color: #7c3aed; background: #f5f3ff; }
        .consulted { border-left-color: #059669; background: #ecfdf5; }
        .informed { border-left-color: #d97706; background: #fffbeb; }
        .status-card { border-left-color: #d1d5db; background: #ffffff; }
        .status-card strong { display: flex; align-items: center; gap: 8px; }
        .finance-building {
            display: grid;
            grid-template-columns: repeat(4, minmax(160px, 1fr));
            gap: 10px;
            margin: 18px 0 28px;
        }
        .module-card {
            border: 1px solid #e6e8ef;
            border-radius: 8px;
            padding: 12px 14px;
            background: #ffffff;
            min-height: 92px;
            box-sizing: border-box;
        }
        .module-card.active { border-color: #2563eb; background: #eff6ff; }
        .module-card.locked { background: #f7f8fb; color: #7a8190; }
        .module-title {
            display: flex;
            justify-content: space-between;
            gap: 8px;
            align-items: center;
            color: #252936;
            font-weight: 800;
            margin-bottom: 6px;
        }
        .module-card.locked .module-title { color: #6b7280; }
        .module-badge {
            border-radius: 999px;
            padding: 3px 8px;
            font-size: 0.7rem;
            font-weight: 800;
            white-space: nowrap;
        }
        .module-badge.available { color: #1d4ed8; background: #dbeafe; }
        .module-badge.locked { color: #6b7280; background: #e5e7eb; }
        .module-description { color: #697386; font-size: 0.82rem; line-height: 1.3; }
        .table-scroll {
            max-height: 72vh;
            overflow: auto;
            padding-bottom: 8px;
        }
        .gantt-scroll { overflow-x: auto; padding-bottom: 8px; }
        .table-scroll table {
            border-collapse: collapse;
            min-width: 1180px;
            width: 100%;
            font-size: 0.92rem;
        }
        .table-scroll th {
            position: sticky;
            top: 0;
            z-index: 10;
            background: #f6f7f9;
            color: #6b7280;
            font-weight: 600;
            text-align: left;
            border: 1px solid #e6e8ef;
            padding: 10px 12px;
        }
        .table-scroll td {
            border: 1px solid #e6e8ef;
            color: #2d3142;
            padding: 10px 12px;
            vertical-align: top;
        }
        .selected-role { font-weight: 800; }
        .gantt {
            border: 1px solid #e6e8ef;
            border-radius: 8px;
            overflow: visible;
            background: #ffffff;
        }
        .gantt-row, .gantt-header {
            display: grid;
            grid-template-columns: 280px 1fr;
        }
        .gantt-header {
            background: #f6f7f9;
            color: #6b7280;
            font-weight: 700;
            border-bottom: 1px solid #e6e8ef;
        }
        .gantt-label, .gantt-scale { padding: 10px 12px; }
        .gantt-label {
            position: sticky;
            left: 0;
            z-index: 20;
            background: #f6f7f9;
            border-right: 1px solid #e6e8ef;
            box-shadow: 4px 0 0 #e6e8ef;
        }
        .gantt-row { min-height: 46px; border-bottom: 1px solid #edf0f4; }
        .gantt-row:last-child { border-bottom: 0; }
        .gantt-task {
            position: sticky;
            left: 0;
            z-index: 15;
            background: #ffffff;
            padding: 9px 12px;
            color: #2d3142;
            border-right: 1px solid #e6e8ef;
            box-shadow: 4px 0 0 #e6e8ef;
            font-size: 0.9rem;
            line-height: 1.25;
        }
        .gantt-track {
            position: relative;
            min-height: 46px;
            background-image: linear-gradient(to right, #eef1f6 1px, transparent 1px);
            background-size: calc(100% / var(--days)) 100%;
        }
        .gantt-today-line {
            position: absolute;
            top: 0;
            bottom: 0;
            width: 2px;
            background: #ef4444;
            box-shadow: 0 0 0 2px rgba(239, 68, 68, 0.10);
            z-index: 8;
        }
        .gantt-tick.today-tick {
            color: #ef4444;
            font-weight: 900;
            background: #fff1f2;
        }
        .today-pill {
            display: inline-block;
            margin-left: 6px;
            border-radius: 999px;
            background: #ef4444;
            color: #ffffff;
            font-size: 0.66rem;
            font-weight: 900;
            padding: 2px 7px;
            vertical-align: middle;
        }
        .gantt-bar {
            position: absolute;
            top: 10px;
            height: 26px;
            border-radius: 6px;
            color: #ffffff;
            font-weight: 700;
            font-size: 0.78rem;
            line-height: 26px;
            padding: 0 10px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            box-shadow: 0 1px 2px rgba(16, 24, 40, 0.12);
            z-index: 6;
        }
        .gantt-row.overdue .gantt-task {
            background: #fff1f2;
            color: #991b1b;
            font-weight: 800;
        }
        .gantt-row.overdue .gantt-bar {
            background: #dc2626 !important;
            box-shadow: 0 0 0 2px rgba(220, 38, 38, 0.18), 0 6px 12px rgba(220, 38, 38, 0.18);
        }
        .overdue-pill {
            display: inline-block;
            margin-top: 5px;
            border-radius: 999px;
            background: #fee2e2;
            color: #b91c1c;
            font-size: 0.68rem;
            font-weight: 900;
            padding: 2px 7px;
        }
        .gantt-ticks {
            display: grid;
            grid-template-columns: repeat(var(--days), minmax(42px, 1fr));
            gap: 0;
        }
        .gantt-tick {
            border-left: 1px solid #e6e8ef;
            padding-left: 6px;
            font-size: 0.78rem;
            color: #747c8f;
        }
        .gantt-dot {
            width: 10px;
            height: 10px;
            border-radius: 999px;
            display: inline-block;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _left_navigation(roles: list[str], areas: list[str], current_page: str) -> tuple[str, str, str]:
    st.markdown('<div class="left-nav-title">Navigation</div>', unsafe_allow_html=True)
    st.caption("Setup")
    for page_option in SETUP_PAGES:
        button_type = "primary" if current_page == page_option else "secondary"
        if st.button(page_option, key=f"left_nav_{page_option}", type=button_type, use_container_width=True):
            st.session_state["active_page"] = page_option
            st.query_params["view"] = page_option
            st.rerun()

    page = st.session_state.get("active_page", current_page)
    st.divider()
    st.selectbox("Finance module", ["Accounting"], disabled=True)
    if page in {"Setup master", "Change Log"}:
        selected_role = "All roles"
        selected_area = "All areas"
    else:
        selected_role = st.selectbox("Person / role", ["All roles", *roles])
        selected_area = st.selectbox("Department area", ["All areas", *areas])

    st.divider()
    if page in {"RACI Matrix", "RACI Matrix setup"}:
        _render_raci_legend()
    elif page in {"Timeline", "Timeline setup"}:
        _render_status_legend()

    return page, selected_role, selected_area


def _render_result_navigation(current_page: str) -> str:
    descriptions = {
        "RACI Matrix": "Who owns what across the finance process.",
        "Timeline": "When each activity happens in the selected period.",
    }
    st.markdown('<div class="top-nav-label">Key views</div>', unsafe_allow_html=True)
    cols = st.columns(2)
    for col, page in zip(cols, RESULT_PAGES):
        with col:
            with st.container(border=True):
                st.markdown(
                    f'<div class="key-view-title">{escape(page)}</div>'
                    f'<div class="key-view-copy">{escape(descriptions[page])}</div>',
                    unsafe_allow_html=True,
                )
                if st.button(
                    page,
                    key=f"result_nav_{page}",
                    type="primary" if page == current_page else "secondary",
                    use_container_width=True,
                ):
                    st.session_state["active_page"] = page
                    st.query_params["view"] = page
                    st.rerun()
    st.divider()
    return st.session_state.get("active_page", current_page)


def _render_raci_matrix_page(
    df: pd.DataFrame,
    selected_role: str,
    finance_modules: list[dict[str, str]],
) -> None:
    st.title("RACI Matrix")
    st.caption("Finance department structure prepared for ownership and timing.")
    _render_finance_building(finance_modules)
    _render_raci_colored_view(df, selected_role)


def _render_raci_setup_page(
    df: pd.DataFrame,
    roles: list[str],
    areas: list[str],
) -> None:
    st.title("RACI Matrix setup")
    st.caption("Configure financial activities and role ownership.")
    _render_ownership_editor(df, roles, areas)


def _render_change_log_page() -> None:
    st.title("Change Log")
    st.caption("Audit trail for saved changes in Setup master, RACI Matrix, and Timeline.")
    log = _load_change_log()
    if log.empty:
        st.info("No changes recorded yet.")
        return
    st.dataframe(log, hide_index=True, width="stretch")


def _render_timeline(df: pd.DataFrame) -> None:
    st.title("Timeline")
    st.caption("Recurring financial calendar view for the selected period.")
    year, month = _period_selector()
    st.markdown(f"**Selected period:** {MONTHS[month - 1]} {year}")
    gantt_df = _prepare_gantt_df(df, year, month)
    if gantt_df.empty:
        st.info("No activities match the selected filters.")
        return
    _render_gantt(gantt_df)


def _render_timeline_setup(df: pd.DataFrame) -> None:
    st.title("Timeline setup")
    st.caption("Configure dates and status for the selected period.")
    year, month = _period_selector()
    st.markdown(f"**Selected period:** {MONTHS[month - 1]} {year}")
    gantt_df = _prepare_gantt_df(df, year, month)
    if gantt_df.empty:
        st.info("No activities match the selected filters.")
        return
    _render_timing_editor(gantt_df, year, month)


def _render_setup_master(
    roles: list[str],
    areas: list[str],
    finance_modules: list[dict[str, str]],
) -> None:
    st.title("Setup master")
    st.caption("Configure the master roles and department areas used by RACI Matrix and Timeline filters.")

    st.subheader("Finance department areas")
    edited_modules = st.data_editor(
        pd.DataFrame(finance_modules).rename(
            columns={"Name": "Finance area", "Status": "Status", "Description": "Description"}
        ),
        hide_index=True,
        width="stretch",
        num_rows="dynamic",
        column_config={
            "Finance area": st.column_config.TextColumn("Finance area", required=True),
            "Status": st.column_config.SelectboxColumn("Status", options=["Available", "Locked"], required=True),
            "Description": st.column_config.TextColumn("Description", required=True),
        },
        key="master_finance_modules_editor",
    )

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Roles")
        edited_roles = st.data_editor(
            pd.DataFrame({"Role": roles}),
            hide_index=True,
            width="stretch",
            num_rows="dynamic",
            column_config={"Role": st.column_config.TextColumn("Role", required=True)},
            key="master_roles_editor",
        )
    with col2:
        st.subheader("Department areas")
        finance_area_names = [module["Name"] for module in finance_modules]
        default_index = finance_area_names.index("Accounting") if "Accounting" in finance_area_names else 0
        selected_area_module = st.selectbox(
            "Finance area",
            finance_area_names,
            index=default_index,
            key="department_area_finance_module",
        )
        selected_module_areas = _load_areas(selected_area_module)
        areas_frame = pd.DataFrame({"Area": pd.Series(selected_module_areas, dtype="string")})
        edited_areas = st.data_editor(
            areas_frame,
            hide_index=True,
            width="stretch",
            num_rows="dynamic",
            column_config={"Area": st.column_config.TextColumn("Area", required=True)},
            key="master_areas_editor",
        )

    pending_action_key = "pending_setup_master_action"
    save_col, reset_col, _ = st.columns([1, 1, 4])
    with save_col:
        if st.button("Save setup", type="primary", key="save_setup_master"):
            st.session_state[pending_action_key] = "save"
    with reset_col:
        if st.button("Reset setup", key="reset_setup_master"):
            st.session_state[pending_action_key] = "reset"

    _render_setup_password_confirmation(
        pd.DataFrame(edited_modules),
        pd.DataFrame(edited_roles),
        pd.DataFrame(edited_areas),
        selected_area_module,
        pending_action_key,
    )


def _period_selector() -> tuple[int, int]:
    years = list(range(date.today().year - 1, date.today().year + 3))
    col1, col2, _ = st.columns([1, 1, 4])
    with col1:
        selected_year = st.selectbox("Year", years, index=1)
    with col2:
        selected_month_name = st.selectbox("Month", MONTHS, index=date.today().month - 1)
    return selected_year, MONTHS.index(selected_month_name) + 1


def _render_finance_building(finance_modules: list[dict[str, str]]) -> None:
    cards = []
    for module in finance_modules:
        is_available = module["Status"] == "Available"
        card_class = "active" if is_available else "locked"
        badge_class = "available" if is_available else "locked"
        cards.append(
            f'<div class="module-card {card_class}">'
            f'<div class="module-title"><span>{escape(module["Name"])}</span>'
            f'<span class="module-badge {badge_class}">{escape(module["Status"])}</span></div>'
            f'<div class="module-description">{escape(module["Description"])}</div>'
            f'</div>'
        )
    st.markdown(f'<div class="finance-building">{"".join(cards)}</div>', unsafe_allow_html=True)


def _render_raci_legend() -> None:
    st.subheader("Legend")
    st.markdown(
        """
        <div class="legend-card responsible"><strong>Responsible</strong><span>Does the work</span></div>
        <div class="legend-card accountable"><strong>Accountable</strong><span>Owns the final outcome</span></div>
        <div class="legend-card consulted"><strong>Consulted</strong><span>Gives input before completion</span></div>
        <div class="legend-card informed"><strong>Informed</strong><span>Kept updated on progress</span></div>
        """,
        unsafe_allow_html=True,
    )


def _render_status_legend() -> None:
    st.subheader("Status")
    items = "".join(
        f'<div class="legend-card status-card"><strong><i class="gantt-dot" style="background:{color};"></i> {escape(status)}</strong></div>'
        for status, color in STATUS_COLORS.items()
    )
    st.markdown(items, unsafe_allow_html=True)


@st.cache_data(ttl=30, show_spinner=False)
def _load_roles() -> list[str]:
    return _load_master_items("master_roles", ROLES)


@st.cache_data(ttl=30, show_spinner=False)
def _load_areas(finance_area: str = "Accounting") -> list[str]:
    with _connect() as conn:
        rows = pd.read_sql_query(
            f"""
            SELECT name
            FROM master_department_areas
            WHERE finance_area = {_placeholders(1)}
            ORDER BY sort_order, name
            """,
            conn,
            params=(finance_area,),
        )
    if not rows.empty:
        return rows["name"].astype(str).tolist()
    if finance_area == "Accounting":
        return _load_master_items("master_areas", AREAS)
    return []


@st.cache_data(ttl=30, show_spinner=False)
def _load_finance_modules() -> list[dict[str, str]]:
    with _connect() as conn:
        rows = pd.read_sql_query(
            """
            SELECT
                name AS Name,
                status AS Status,
                description AS Description
            FROM master_finance_modules
            ORDER BY sort_order, name
            """,
            conn,
        )
    if rows.empty:
        return FINANCE_MODULES
    return rows.astype(str).to_dict("records")


@st.cache_data(ttl=30, show_spinner=False)
def _load_master_items(table: str, defaults: list[str]) -> list[str]:
    with _connect() as conn:
        rows = pd.read_sql_query(f"SELECT name FROM {table} ORDER BY sort_order, name", conn)
    if rows.empty:
        return defaults
    return rows["name"].astype(str).tolist()


def _render_setup_password_confirmation(
    edited_modules: pd.DataFrame,
    edited_roles: pd.DataFrame,
    edited_areas: pd.DataFrame,
    selected_area_module: str,
    pending_action_key: str,
) -> None:
    action = st.session_state.get(pending_action_key)
    if action not in {"save", "reset"}:
        return

    configured_password = _get_edit_password()
    if configured_password is None:
        st.warning("Saving is disabled until an edit password is configured in deployment secrets.")
        if st.button("Dismiss", key="dismiss_setup_password_prompt"):
            st.session_state.pop(pending_action_key, None)
            st.rerun()
        return

    verb = "save setup changes" if action == "save" else "reset setup to default roles and areas"
    st.info(f"Enter the edit password to {verb}.")
    with st.form(key=f"setup_password_form_{action}", clear_on_submit=False):
        entered_password = st.text_input("Edit password", type="password")
        confirm_col, cancel_col, _ = st.columns([1, 1, 4])
        with confirm_col:
            confirmed = st.form_submit_button("Confirm", type="primary")
        with cancel_col:
            cancelled = st.form_submit_button("Cancel")

    if cancelled:
        st.session_state.pop(pending_action_key, None)
        st.rerun()

    if confirmed:
        if not _can_edit(configured_password, entered_password):
            st.error("Incorrect edit password.")
            return
        if action == "save":
            if _save_setup_master(edited_modules, edited_roles, edited_areas, selected_area_module):
                st.session_state.pop(pending_action_key, None)
                _queue_toast("Setup master changes saved.")
                st.rerun()
        else:
            _reset_setup_master()
            st.session_state.pop(pending_action_key, None)
            _queue_toast("Setup master reset.")
            st.rerun()


def _save_setup_master(
    modules_df: pd.DataFrame,
    roles_df: pd.DataFrame,
    areas_df: pd.DataFrame,
    selected_area_module: str,
) -> bool:
    modules = _clean_finance_modules(modules_df)
    roles = _clean_master_values(roles_df, "Role")
    areas = _clean_master_values(areas_df, "Area")
    if not modules:
        st.error("Please keep at least one finance department area.")
        return False
    if not roles:
        st.error("Please keep at least one role.")
        return False
    if not areas:
        st.error("Please keep at least one accounting area.")
        return False
    duplicate_module = _first_duplicate([module["Name"] for module in modules])
    duplicate_role = _first_duplicate(roles)
    duplicate_area = _first_duplicate(areas)
    if duplicate_module:
        st.error(f"Finance department area names must be unique. Duplicate: {duplicate_module}.")
        return False
    if duplicate_role:
        st.error(f"Role names must be unique. Duplicate: {duplicate_role}.")
        return False
    if duplicate_area:
        st.error(f"Area names must be unique. Duplicate: {duplicate_area}.")
        return False

    changes = _finance_module_changes(_load_finance_modules(), modules, "Save")
    changes.extend(_master_changes("Setup Role", _load_roles(), roles, "Save"))
    changes.extend(_master_changes(f"Setup Department Area ({selected_area_module})", _load_areas(selected_area_module), areas, "Save"))
    with _connect() as conn:
        _replace_finance_modules(conn, modules)
        _replace_master_items(conn, "master_roles", roles)
        _replace_department_areas(conn, selected_area_module, areas)
        _insert_change_log(conn, 0, 0, changes)
        conn.commit()
    _clear_cached_data()
    return True


def _reset_setup_master() -> None:
    changes = _finance_module_changes(_load_finance_modules(), FINANCE_MODULES, "Reset")
    changes.extend(_master_changes("Setup Role", _load_roles(), ROLES, "Reset"))
    changes.extend(_master_changes("Setup Department Area (Accounting)", _load_areas("Accounting"), AREAS, "Reset"))
    with _connect() as conn:
        conn.execute("DELETE FROM master_finance_modules")
        conn.execute("DELETE FROM master_roles")
        conn.execute("DELETE FROM master_areas")
        conn.execute("DELETE FROM master_department_areas")
        _insert_change_log(conn, 0, 0, changes)
        conn.commit()
    _clear_cached_data()


def _clean_finance_modules(df: pd.DataFrame) -> list[dict[str, str]]:
    required_columns = ["Finance area", "Status", "Description"]
    if not all(column in df for column in required_columns):
        return []
    cleaned = []
    for _, row in df.dropna(how="all").iterrows():
        name = str(row["Finance area"]).strip()
        status = str(row["Status"]).strip()
        description = str(row["Description"]).strip()
        if not name and not status and not description:
            continue
        if not name or not status or not description:
            st.error("Please complete all finance department area fields.")
            return []
        if status not in {"Available", "Locked"}:
            st.error(f"Please select a valid status for {name}.")
            return []
        cleaned.append({"Name": name, "Status": status, "Description": description})
    return cleaned


def _clean_master_values(df: pd.DataFrame, column: str) -> list[str]:
    if column not in df:
        return []
    values = df[column].dropna().astype(str).str.strip()
    return [value for value in values.tolist() if value]


def _first_duplicate(values: list[str]) -> str | None:
    seen = set()
    for value in values:
        key = value.casefold()
        if key in seen:
            return value
        seen.add(key)
    return None


def _master_changes(
    field: str,
    old_values: list[str],
    new_values: list[str],
    action: str,
) -> list[tuple[str, str, str, str, str]]:
    changes = []
    max_len = max(len(old_values), len(new_values))
    for index in range(max_len):
        old_value = old_values[index] if index < len(old_values) else ""
        new_value = new_values[index] if index < len(new_values) else ""
        if old_value != new_value:
            changes.append(("Setup master", f"{field} {index + 1}", old_value, new_value, action))
    return changes


def _finance_module_changes(
    old_modules: list[dict[str, str]],
    new_modules: list[dict[str, str]],
    action: str,
) -> list[tuple[str, str, str, str, str]]:
    old_values = [_module_signature(module) for module in old_modules]
    new_values = [_module_signature(module) for module in new_modules]
    return _master_changes("Setup Finance Department Area", old_values, new_values, action)


def _module_signature(module: dict[str, str]) -> str:
    return f'{module["Name"]} | {module["Status"]} | {module["Description"]}'


def _replace_finance_modules(conn: Any, modules: list[dict[str, str]]) -> None:
    conn.execute("DELETE FROM master_finance_modules")
    _executemany(
        conn,
        f"""
        INSERT INTO master_finance_modules (name, status, description, sort_order)
        VALUES ({_placeholders(4)})
        """,
        [
            (module["Name"], module["Status"], module["Description"], index)
            for index, module in enumerate(modules)
        ],
    )


def _replace_master_items(conn: Any, table: str, values: list[str]) -> None:
    conn.execute(f"DELETE FROM {table}")
    _executemany(
        conn,
        f"INSERT INTO {table} (name, sort_order) VALUES ({_placeholders(2)})",
        [(value, index) for index, value in enumerate(values)],
    )


def _replace_department_areas(conn: Any, finance_area: str, values: list[str]) -> None:
    conn.execute(
        f"DELETE FROM master_department_areas WHERE finance_area = {_placeholders(1)}",
        (finance_area,),
    )
    _executemany(
        conn,
        f"INSERT INTO master_department_areas (finance_area, name, sort_order) VALUES ({_placeholders(3)})",
        [(finance_area, value, index) for index, value in enumerate(values)],
    )


@st.cache_data(ttl=30, show_spinner=False)
def _load_ownership_data() -> pd.DataFrame:
    base = pd.DataFrame(RACI_DATA)
    with _connect() as conn:
        overrides = pd.read_sql_query(
            """
            SELECT
                activity AS Activity,
                area AS Area,
                responsible AS Responsible,
                accountable AS Accountable,
                consulted AS Consulted,
                informed AS Informed
            FROM ownership_overrides
            """,
            conn,
        )
    if overrides.empty:
        return base

    merged = base.merge(overrides, on="Activity", how="left", suffixes=("", "_override"))
    for column in ["Area", "Responsible", "Accountable", "Consulted", "Informed"]:
        merged[column] = merged[f"{column}_override"].where(
            merged[f"{column}_override"].notna(),
            merged[column],
        )
    custom_rows = overrides[~overrides["Activity"].isin(base["Activity"])]
    result = pd.concat(
        [merged[["Area", "Activity", "Responsible", "Accountable", "Consulted", "Informed"]], custom_rows],
        ignore_index=True,
    )
    return result.sort_values(["Area", "Activity"]).reset_index(drop=True)


def _filter_raci(df: pd.DataFrame, selected_role: str, selected_area: str) -> pd.DataFrame:
    filtered = df.copy()
    if selected_area != "All areas":
        filtered = filtered[filtered["Area"] == selected_area]
    if selected_role != "All roles":
        mask = pd.Series(False, index=filtered.index)
        for column in ["Responsible", "Accountable", "Consulted", "Informed"]:
            mask = mask | filtered[column].str.contains(selected_role, regex=False)
        filtered = filtered[mask]
    return filtered.reset_index(drop=True)


def _filter_timeline(df: pd.DataFrame, selected_role: str, selected_area: str) -> pd.DataFrame:
    filtered = df.copy()
    if selected_area != "All areas":
        filtered = filtered[filtered["Area"] == selected_area]
    if selected_role != "All roles":
        filtered = filtered[filtered["Responsible"].str.contains(selected_role, regex=False)]
    return filtered.reset_index(drop=True)


def _role_options(df: pd.DataFrame, roles: list[str]) -> list[str]:
    options = list(roles)
    for column in ["Responsible", "Accountable", "Consulted", "Informed"]:
        for value in df[column].dropna().tolist():
            for role in _split_roles(value):
                if role and role not in options:
                    options.append(role)
    return options


def _split_roles(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value).split(",") if item.strip()]


def _format_role_value(value: Any) -> str:
    return ", ".join(_split_roles(value))


def _render_ownership_editor(
    df: pd.DataFrame,
    roles: list[str],
    areas: list[str],
) -> None:
    st.subheader("RACI Matrix")
    if df.empty:
        st.info("No activities match the selected filters.")
        return

    role_options = _role_options(df, roles)
    display = df[["Area", "Activity", "Responsible", "Accountable", "Consulted", "Informed"]].copy()
    display["Consulted"] = display["Consulted"].apply(_split_roles)
    display["Informed"] = display["Informed"].apply(_split_roles)

    edited = st.data_editor(
        display,
        hide_index=True,
        width="stretch",
        num_rows="dynamic",
        column_config={
            "Area": st.column_config.SelectboxColumn("Area", options=areas, required=True),
            "Activity": st.column_config.TextColumn("Activity", required=True),
            "Responsible": st.column_config.SelectboxColumn("Responsible", options=role_options, required=True),
            "Accountable": st.column_config.SelectboxColumn("Accountable", options=role_options, required=True),
            "Consulted": st.column_config.MultiselectColumn("Consulted", options=role_options, required=True),
            "Informed": st.column_config.MultiselectColumn("Informed", options=role_options, required=True),
        },
        key="ownership_editor",
    )

    pending_action_key = "pending_ownership_action"
    save_col, reset_col, _ = st.columns([1, 1, 4])
    with save_col:
        if st.button("Save ownership", type="primary", key="save_ownership"):
            st.session_state[pending_action_key] = "save"
    with reset_col:
        if st.button("Reset ownership", key="reset_ownership"):
            st.session_state[pending_action_key] = "reset"

    _render_ownership_password_confirmation(pd.DataFrame(edited), pending_action_key)


def _render_raci_colored_view(df: pd.DataFrame, selected_role: str) -> None:
    st.subheader("RACI Matrix")
    if df.empty:
        st.info("No activities match the selected filters.")
        return

    display = df[["Area", *RACI_COLUMNS]].copy()
    display = _highlight_selected_role(display, selected_role)
    styled = display.style.apply(_style_raci_columns, axis=None)
    st.markdown(
        f'<div class="table-scroll">{styled.hide(axis="index").to_html()}</div>',
        unsafe_allow_html=True,
    )


def _render_ownership_password_confirmation(edited: pd.DataFrame, pending_action_key: str) -> None:
    action = st.session_state.get(pending_action_key)
    if action not in {"save", "reset"}:
        return

    configured_password = _get_edit_password()
    if configured_password is None:
        st.warning("Saving is disabled until an edit password is configured in deployment secrets.")
        if st.button("Dismiss", key="dismiss_ownership_password_prompt"):
            st.session_state.pop(pending_action_key, None)
            st.rerun()
        return

    verb = "save these ownership changes" if action == "save" else "reset ownership to the default RACI"
    st.info(f"Enter the edit password to {verb}.")
    with st.form(key=f"ownership_password_form_{action}", clear_on_submit=False):
        entered_password = st.text_input("Edit password", type="password")
        confirm_col, cancel_col, _ = st.columns([1, 1, 4])
        with confirm_col:
            confirmed = st.form_submit_button("Confirm", type="primary")
        with cancel_col:
            cancelled = st.form_submit_button("Cancel")

    if cancelled:
        st.session_state.pop(pending_action_key, None)
        st.rerun()

    if confirmed:
        if not _can_edit(configured_password, entered_password):
            st.error("Incorrect edit password.")
            return
        if action == "save":
            if _save_ownership_overrides(edited):
                st.session_state.pop(pending_action_key, None)
                _queue_toast("RACI Matrix changes saved.")
                st.rerun()
        else:
            _reset_ownership_overrides()
            st.session_state.pop(pending_action_key, None)
            _queue_toast("RACI Matrix reset to default RACI.")
            st.rerun()


def _highlight_selected_role(df: pd.DataFrame, selected_role: str) -> pd.DataFrame:
    if selected_role == "All roles":
        return df

    highlighted = df.copy()
    for column in ["Responsible", "Accountable", "Consulted", "Informed"]:
        highlighted[column] = highlighted[column].apply(lambda value: _bold_role(value, selected_role))
    return highlighted


def _bold_role(value: str, selected_role: str) -> str:
    safe_value = escape(str(value))
    safe_role = escape(selected_role)
    return safe_value.replace(safe_role, f'<span class="selected-role">{safe_role}</span>')


def _style_raci_columns(df: pd.DataFrame) -> pd.DataFrame:
    styles = pd.DataFrame("", index=df.index, columns=df.columns)
    styles["Responsible"] = "background-color: #eff6ff; color: #1d4ed8;"
    styles["Accountable"] = "background-color: #f5f3ff; color: #6d28d9;"
    styles["Consulted"] = "background-color: #ecfdf5; color: #047857;"
    styles["Informed"] = "background-color: #fffbeb; color: #b45309;"
    return styles


def _prepare_gantt_df(raci_df: pd.DataFrame, year: int, month: int) -> pd.DataFrame:
    if raci_df.empty:
        return pd.DataFrame()

    timing = _load_timing_for_period(year, month)
    gantt_df = raci_df[["Area", "Activity", "Responsible"]].merge(timing, on="Activity", how="left")
    gantt_df["Start"] = pd.to_datetime(gantt_df["Start"]).dt.date
    gantt_df["End"] = pd.to_datetime(gantt_df["End"]).dt.date
    return gantt_df.sort_values(["Start", "End", "Area", "Activity"]).reset_index(drop=True)


def _render_gantt(gantt_df: pd.DataFrame) -> None:
    start_date = gantt_df["Start"].min()
    total_days = (gantt_df["End"].max() - start_date).days + 1

    st.subheader("Delivery Timeline")
    st.caption("Monthly financial timeline generated from recurring finance rules.")
    st.markdown(_gantt_html(gantt_df, start_date, total_days), unsafe_allow_html=True)


@st.cache_data(ttl=30, show_spinner=False)
def _load_timing_for_period(year: int, month: int) -> pd.DataFrame:
    timing = _build_timing_for_period(year, month)
    ownership_activities = _load_ownership_data()["Activity"].tolist()
    missing_activities = [activity for activity in ownership_activities if activity not in timing["Activity"].tolist()]
    if missing_activities:
        close_anchor = _nearest_business_day(_last_calendar_day(year, month))
        timing = pd.concat(
            [
                timing,
                pd.DataFrame(
                    [
                        {
                            "Activity": activity,
                            "Start": close_anchor,
                            "End": close_anchor,
                            "Status": "Not started",
                        }
                        for activity in missing_activities
                    ]
                ),
            ],
            ignore_index=True,
        )
    with _connect() as conn:
        overrides = pd.read_sql_query(
            f"""
            SELECT activity AS Activity, start_date AS Start, end_date AS End, status AS Status
            FROM timeline_overrides
            WHERE year = {_placeholders(1)} AND month = {_placeholders(1)}
            """,
            conn,
            params=(year, month),
        )

    if overrides.empty:
        return timing

    merged = timing.merge(overrides, on="Activity", how="left", suffixes=("", "_override"))
    for column in ["Start", "End", "Status"]:
        merged[column] = merged[f"{column}_override"].where(merged[f"{column}_override"].notna(), merged[column])
    return merged[["Activity", "Start", "End", "Status"]]


def _build_timing_for_period(year: int, month: int) -> pd.DataFrame:
    close_anchor = _nearest_business_day(_last_calendar_day(year, month))
    rows = []
    for rule in TIMING_RULES:
        rows.append(
            {
                "Activity": rule["Activity"],
                "Start": _business_day_offset(close_anchor, rule["Start offset"]),
                "End": _business_day_offset(close_anchor, rule["End offset"]),
                "Status": rule["Status"],
            }
        )
    return pd.DataFrame(rows)


def _last_calendar_day(year: int, month: int) -> date:
    first_next_month = (
        pd.Timestamp(year=year + 1, month=1, day=1)
        if month == 12
        else pd.Timestamp(year=year, month=month + 1, day=1)
    )
    return (first_next_month - pd.Timedelta(days=1)).date()


def _nearest_business_day(value: date) -> date:
    current = pd.Timestamp(value)
    while current.weekday() >= 5:
        current -= pd.Timedelta(days=1)
    return current.date()


def _business_day_offset(anchor: date, offset: int) -> date:
    current = pd.Timestamp(anchor)
    step = 1 if offset >= 0 else -1
    remaining = abs(offset)
    while remaining:
        current += pd.Timedelta(days=step)
        if current.weekday() < 5:
            remaining -= 1
    return current.date()


def _gantt_html(df: pd.DataFrame, start_date: date, total_days: int) -> str:
    gantt_width = 280 + (total_days * 54)
    today = date.today()
    today_line = ""
    end_date = (pd.Timestamp(start_date) + pd.Timedelta(days=total_days - 1)).date()
    if start_date <= today <= end_date:
        today_offset = (today - start_date).days + 0.5
        today_left = today_offset / total_days * 100
        today_line = f'<div class="gantt-today-line" style="left:{today_left:.3f}%;"></div>'
    ticks = ""
    for day in range(total_days):
        tick_date = (pd.Timestamp(start_date) + pd.Timedelta(days=day)).date()
        tick_label = tick_date.strftime("%d %b")
        if tick_date == today:
            ticks += f'<div class="gantt-tick today-tick">{tick_label}<span class="today-pill">Today</span></div>'
        else:
            ticks += f'<div class="gantt-tick">{tick_label}</div>'
    rows = "".join(_gantt_row_html(row, start_date, total_days, today_line) for _, row in df.iterrows())
    return (
        '<div class="gantt-scroll">'
        f'<div class="gantt" style="--days:{total_days}; min-width:{gantt_width}px;">'
        '<div class="gantt-header">'
        '<div class="gantt-label">Activity</div>'
        f'<div class="gantt-scale"><div class="gantt-ticks">{ticks}</div></div>'
        '</div>'
        f'{rows}'
        '</div>'
        '</div>'
    )


def _gantt_row_html(row: pd.Series, start_date: date, total_days: int, today_marker: str) -> str:
    start_offset = (row["Start"] - start_date).days
    duration = (row["End"] - row["Start"]).days + 1
    left = start_offset / total_days * 100
    width = duration / total_days * 100
    color = STATUS_COLORS.get(row["Status"], "#9ca3af")
    label = f'{row["Start"].strftime("%d %b")} - {row["End"].strftime("%d %b")}'
    is_overdue = row["End"] < date.today() and row["Status"] != "Completed"
    overdue_tag = '<br><span class="overdue-pill">Overdue</span>' if is_overdue else ""
    row_class = "gantt-row overdue" if is_overdue else "gantt-row"
    task = f'{escape(row["Activity"])}<br><span style="color:#7b8496;">{escape(row["Responsible"])}</span>{overdue_tag}'
    return (
        f'<div class="{row_class}">'
        f'<div class="gantt-task">{task}</div>'
        '<div class="gantt-track">'
        f'{today_marker}'
        f'<div class="gantt-bar" style="left:{left:.3f}%; width:{width:.3f}%; background:{color};">{escape(label)}</div>'
        '</div>'
        '</div>'
    )


def _render_timing_editor(gantt_df: pd.DataFrame, year: int, month: int) -> None:
    st.subheader("Execution Table")
    st.caption("Edit dates and status for this period. Changes are saved only for the selected month.")

    display = gantt_df[["Area", "Activity", "Responsible", "Start", "End", "Status"]].rename(
        columns={"Responsible": "Owner", "Start": "Start date", "End": "End date"}
    )
    display["Status"] = display["Status"].where(display["Status"].isin(VALID_STATUSES), "Not started")

    edited = st.data_editor(
        display,
        hide_index=True,
        width="stretch",
        disabled=["Area", "Activity", "Owner"],
        column_config={
            "Start date": st.column_config.DateColumn("Start date"),
            "End date": st.column_config.DateColumn("End date"),
            "Status": st.column_config.SelectboxColumn("Status", options=VALID_STATUSES, required=True),
        },
        key=f"timeline_editor_{year}_{month}",
    )

    pending_action_key = f"pending_timeline_action_{year}_{month}"
    save_col, reset_col, _ = st.columns([1, 1, 4])
    with save_col:
        if st.button(
            "Save period",
            type="primary",
            key=f"save_timeline_{year}_{month}",
        ):
            st.session_state[pending_action_key] = "save"
    with reset_col:
        if st.button(
            "Reset period",
            key=f"reset_timeline_{year}_{month}",
        ):
            st.session_state[pending_action_key] = "reset"

    _render_password_confirmation(pd.DataFrame(edited), year, month, pending_action_key)


def _render_password_confirmation(
    edited: pd.DataFrame,
    year: int,
    month: int,
    pending_action_key: str,
) -> None:
    action = st.session_state.get(pending_action_key)
    if action not in {"save", "reset"}:
        return

    configured_password = _get_edit_password()
    if configured_password is None:
        st.warning("Saving is disabled until an edit password is configured in deployment secrets.")
        if st.button("Dismiss", key=f"dismiss_password_prompt_{year}_{month}"):
            st.session_state.pop(pending_action_key, None)
            st.rerun()
        return

    verb = "save these changes" if action == "save" else "reset this period"
    st.info(f"Enter the edit password to {verb}.")
    with st.form(key=f"password_form_{year}_{month}_{action}", clear_on_submit=False):
        entered_password = st.text_input("Edit password", type="password")
        confirm_col, cancel_col, _ = st.columns([1, 1, 4])
        with confirm_col:
            confirmed = st.form_submit_button("Confirm", type="primary")
        with cancel_col:
            cancelled = st.form_submit_button("Cancel")

    if cancelled:
        st.session_state.pop(pending_action_key, None)
        st.rerun()

    if confirmed:
        if not _can_edit(configured_password, entered_password):
            st.error("Incorrect edit password.")
            return
        if action == "save":
            if _save_timing_overrides(edited, year, month):
                st.session_state.pop(pending_action_key, None)
                _queue_toast(f"Timeline changes saved for {MONTHS[month - 1]} {year}.")
                st.rerun()
        else:
            _reset_timing_overrides(year, month)
            st.session_state.pop(pending_action_key, None)
            _queue_toast(f"Timeline reset for {MONTHS[month - 1]} {year}.")
            st.rerun()


def _get_edit_password() -> str | None:
    password = _secret_value("edit_password") or environ.get("EDIT_PASSWORD")
    if password is None:
        return None
    password = str(password).strip()
    return password or None


def _can_edit(configured_password: str | None, entered_password: str) -> bool:
    if configured_password is None or not entered_password:
        return False
    return compare_digest(configured_password.strip(), entered_password.strip())


def _save_ownership_overrides(df: pd.DataFrame) -> bool:
    current = _load_ownership_data().set_index("Activity")
    df = df.dropna(how="all").copy()
    df["Activity"] = df["Activity"].astype(str).str.strip()
    if df["Activity"].eq("").any():
        st.error("Please add an activity name for every ownership row.")
        return False
    duplicated = df[df["Activity"].duplicated()]["Activity"].tolist()
    if duplicated:
        st.error(f"Activity names must be unique. Duplicate: {duplicated[0]}.")
        return False

    rows = []
    changes = []
    for _, row in df.iterrows():
        activity = str(row["Activity"])
        values = {
            "Area": str(row["Area"]).strip(),
            "Responsible": _format_role_value(row["Responsible"]),
            "Accountable": _format_role_value(row["Accountable"]),
            "Consulted": _format_role_value(row["Consulted"]),
            "Informed": _format_role_value(row["Informed"]),
        }
        if not all(values.values()):
            st.error(f"Please complete all ownership fields for {activity}.")
            return False
        for field, new_value in values.items():
            old_value = str(current.loc[activity, field]) if activity in current.index else ""
            if old_value != new_value:
                changes.append((activity, f"Ownership {field}", old_value, new_value, "Save"))
        rows.append(
            (
                activity,
                values["Area"],
                values["Responsible"],
                values["Accountable"],
                values["Consulted"],
                values["Informed"],
            )
        )

    with _connect() as conn:
        _executemany(
            conn,
            f"""
            INSERT INTO ownership_overrides (
                activity, area, responsible, accountable, consulted, informed
            )
            VALUES ({_placeholders(6)})
            ON CONFLICT(activity) DO UPDATE SET
                area = excluded.area,
                responsible = excluded.responsible,
                accountable = excluded.accountable,
                consulted = excluded.consulted,
                informed = excluded.informed
            """,
            rows,
        )
        _insert_change_log(conn, 0, 0, changes)
        conn.commit()
    _clear_cached_data()
    return True


def _reset_ownership_overrides() -> None:
    current = _load_ownership_data().set_index("Activity")
    default = pd.DataFrame(RACI_DATA).set_index("Activity")
    changes = []
    for activity in current.index:
        for field in ["Area", "Responsible", "Accountable", "Consulted", "Informed"]:
            old_value = str(current.loc[activity, field])
            new_value = str(default.loc[activity, field])
            if old_value != new_value:
                changes.append((activity, f"Ownership {field}", old_value, new_value, "Reset"))

    with _connect() as conn:
        conn.execute("DELETE FROM ownership_overrides")
        _insert_change_log(conn, 0, 0, changes)
        conn.commit()
    _clear_cached_data()


def _save_timing_overrides(df: pd.DataFrame, year: int, month: int) -> bool:
    rows = []
    current = _load_timing_for_period(year, month).set_index("Activity")
    changes = []
    for _, row in df.iterrows():
        start_date = pd.Timestamp(row["Start date"]).date()
        end_date = pd.Timestamp(row["End date"]).date()
        if end_date < start_date:
            st.error(f"End date cannot be before start date for {row['Activity']}.")
            return False
        if row["Status"] not in VALID_STATUSES:
            st.error(f"Please select a valid status for {row['Activity']}.")
            return False
        activity = row["Activity"]
        new_values = {
            "Start date": start_date.isoformat(),
            "End date": end_date.isoformat(),
            "Status": row["Status"],
        }
        old_values = {
            "Start date": pd.Timestamp(current.loc[activity, "Start"]).date().isoformat(),
            "End date": pd.Timestamp(current.loc[activity, "End"]).date().isoformat(),
            "Status": str(current.loc[activity, "Status"]),
        }
        for field, new_value in new_values.items():
            old_value = old_values[field]
            if old_value != str(new_value):
                changes.append((activity, field, old_value, str(new_value), "Save"))
        rows.append((year, month, row["Activity"], start_date.isoformat(), end_date.isoformat(), row["Status"]))

    with _connect() as conn:
        _executemany(
            conn,
            f"""
            INSERT INTO timeline_overrides (year, month, activity, start_date, end_date, status)
            VALUES ({_placeholders(6)})
            ON CONFLICT(year, month, activity) DO UPDATE SET
                start_date = excluded.start_date,
                end_date = excluded.end_date,
                status = excluded.status
            """,
            rows,
        )
        _insert_change_log(conn, year, month, changes)
        conn.commit()
    _clear_cached_data()
    return True


def _reset_timing_overrides(year: int, month: int) -> None:
    current = _load_timing_for_period(year, month).set_index("Activity")
    default = _build_timing_for_period(year, month).set_index("Activity")
    changes = []
    for activity in current.index:
        if activity not in default.index:
            continue
        comparisons = [
            ("Start date", pd.Timestamp(current.loc[activity, "Start"]).date().isoformat(), pd.Timestamp(default.loc[activity, "Start"]).date().isoformat()),
            ("End date", pd.Timestamp(current.loc[activity, "End"]).date().isoformat(), pd.Timestamp(default.loc[activity, "End"]).date().isoformat()),
            ("Status", str(current.loc[activity, "Status"]), str(default.loc[activity, "Status"])),
        ]
        for field, old_value, new_value in comparisons:
            if old_value != new_value:
                changes.append((activity, field, old_value, new_value, "Reset"))
    with _connect() as conn:
        conn.execute(
            f"DELETE FROM timeline_overrides WHERE year = {_placeholders(1)} AND month = {_placeholders(1)}",
            (year, month),
        )
        _insert_change_log(conn, year, month, changes)
        conn.commit()
    _clear_cached_data()


def _insert_change_log(
    conn: Any,
    year: int,
    month: int,
    changes: list[tuple[str, str, str, str, str]],
) -> None:
    if not changes:
        return
    changed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    _executemany(
        conn,
        f"""
        INSERT INTO change_log (
            changed_at, year, month, activity, field, old_value, new_value, action
        )
        VALUES ({_placeholders(8)})
        """,
        [
            (changed_at, year, month, activity, field, old_value, new_value, action)
            for activity, field, old_value, new_value, action in changes
        ],
    )


@st.cache_data(ttl=30, show_spinner=False)
def _load_change_log(year: int | None = None, month: int | None = None) -> pd.DataFrame:
    where_clause = ""
    params: tuple[int, int] | tuple[()] = ()
    if year is not None and month is not None:
        where_clause = f"WHERE year = {_placeholders(1)} AND month = {_placeholders(1)}"
        params = (year, month)

    with _connect() as conn:
        log = pd.read_sql_query(
            f"""
            SELECT
                changed_at AS "Changed at",
                year,
                month,
                action AS Action,
                activity AS Activity,
                field AS Field,
                old_value AS "Old value",
                new_value AS "New value"
            FROM change_log
            {where_clause}
            ORDER BY id DESC
            LIMIT 100
            """,
            conn,
            params=params,
        )
    if log.empty:
        return log

    log.insert(1, "Section", log.apply(_change_log_section, axis=1))
    log.insert(2, "Period", log.apply(_change_log_period, axis=1))
    return log.drop(columns=["year", "month"])


def _change_log_section(row: pd.Series) -> str:
    if int(row["year"]) != 0 or int(row["month"]) != 0:
        return "Timeline"
    field = str(row["Field"])
    return "RACI Matrix" if field.startswith("Ownership ") else "Setup master"


def _change_log_period(row: pd.Series) -> str:
    if int(row["year"]) == 0 and int(row["month"]) == 0:
        return "Global"
    return f'{MONTHS[int(row["month"]) - 1]} {int(row["year"])}'


if __name__ == "__main__":
    main()
