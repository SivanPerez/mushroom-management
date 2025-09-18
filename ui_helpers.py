import pandas as pd
import streamlit as st
from db import load_data

# ===================== הקשר UI אחיד =====================
class UIContext:
    def __init__(self, species_en: str, species_he: str, data: list[dict]):
        self.species_en = species_en
        self.species_he = species_he
        self.data = data

    def reload(self):
        self.data = load_data(self.species_en)

    def info(self, msg): st.info(msg)
    def success(self, msg): st.success(msg)
    def warning(self, msg): st.warning(msg)
    def error(self, msg): st.error(msg)

# ===================== עזר: טבלת שלב =====================
def _non_empty_cols_df(df):
    df = df.replace("", pd.NA)
    return df.dropna(axis=1, how="all")


def _show_stage_table(data: list[dict], stage_name: str, title: str | None = None, species_he: str | None = None):
    """מציג טבלה עבור שלב מסוים בלבד — ללא קריאות רנדר נוספות."""
    if title:
        st.subheader(title)

    # אם הועבר species_he נסנן גם לפי המין; אחרת נסנן רק לפי שלב
    if species_he:
        rows = [r for r in data if r.get("שלב") == stage_name and r.get("מין") == species_he]
    else:
        rows = [r for r in data if r.get("שלב") == stage_name]

    if not rows:
        st.info("אין נתונים להצגה.")
        return

    df = pd.DataFrame(rows).replace("", pd.NA).dropna(axis=1, how="all")
    st.dataframe(df, use_container_width=True)

def inject_base_css():
    """מזריק CSS בסיסי: צבעי מותג, RTL, טאבים, Alerts, multiselect, כפתורים."""
    st.markdown("""
    <style>
    :root {
      --brand-main:   #6E1B27;  /* בורדו כהה */
      --brand-strong: #7F2430;
      --brand-soft:   #F6ECEE;
      --sidebar-bg:   #F0F2F6;  /* רקע הסיידבר */
      --sidebar-text: #31333F;  /* טקסט כהה של הסיידבר */
      --primary-color: #6E1B27 !important;
    }

    /* ===== יישור לימין (RTL) ===== */
    html, body, [data-testid="stAppViewContainer"], .main, .block-container {
      direction: rtl;
      text-align: right;
    }
    [data-testid="stSidebar"] {
      text-align: right;
    }

    /* ===== כפתורים בסיידבר ===== */
    [data-testid="stSidebar"] .stButton>button {
      color: inherit;
      background: #fff;
      box-shadow: none;
      transition: all .15s ease;
      text-align: right;
    }
    [data-testid="stSidebar"] .stButton>button:hover {
      border-color: var(--brand-main);
      color: var(--brand-main) !important;
      background: var(--brand-soft) !important;
    }
    [data-testid="stSidebar"] .stButton>button:active {
      border-color: var(--brand-strong) !important;
      color: var(--brand-strong) !important;
      background: var(--brand-soft) !important;
      box-shadow: none !important;
    }
    [data-testid="stSidebar"] .stButton>button[kind="primary"] {
      background: var(--brand-soft) !important;
      border-color: var(--brand-main) !important;
      color: var(--brand-main) !important;
      font-weight: 600;
    }

    /* ===== טאבים ===== */
    .stTabs [data-baseweb="tab-highlight"] {
      background-color: var(--brand-main) !important;
      height: 2px !important;
    }
    .stTabs [role="tablist"] [role="tab"]:hover {
      color: var(--brand-main) !important;
    }
    .stTabs [role="tablist"] [role="tab"][aria-selected="true"] {
      color: var(--brand-main) !important;
    }

    /* ===== תיבות Alert ===== */
    .stAlert {
      background: var(--sidebar-bg) !important;
      border: 1px solid #e0e0e0 !important;
      color: var(--sidebar-text) !important;
      box-shadow: none !important;
      background-image: none !important;
      border-radius: 12px !important;
    }
    .stAlert > div,
    .stAlert [data-baseweb="notification"],
    .stAlert [role="alert"],
    .stAlert div[class*="emotion-"],
    .stAlert div[class*="st-emotion-"] {
      background: var(--sidebar-bg) !important;
      border: none !important;
      box-shadow: none !important;
      background-image: none !important;
      color: var(--sidebar-text) !important;
      border-radius: 12px !important;
    }
    .stAlert [data-baseweb="notification"]::before {
      background-color: var(--brand-main) !important;
    }
    .stAlert svg {
      fill: var(--brand-main) !important;
      color: var(--brand-main) !important;
    }
    .stAlert a {
      color: var(--brand-main) !important;
    }

    /* ===== תגיות multiselect ===== */
    .stMultiSelect [data-baseweb="tag"] {
      background-color: var(--brand-soft) !important;
      border-color: var(--brand-main) !important;
      color: var(--brand-main) !important;
    }
    .stMultiSelect [data-baseweb="tag"]:hover {
      background-color: #F3E8EC !important;
      border-color: var(--brand-strong) !important;
      color: var(--brand-strong) !important;
    }
    .stMultiSelect [data-baseweb="tag"] [data-baseweb="button"],
    .stMultiSelect [data-baseweb="tag"] svg {
      color: var(--brand-main) !important;
      fill: var(--brand-main) !important;
    }
    .stMultiSelect [data-baseweb="tag"] [data-baseweb="button"]:hover {
      color: var(--brand-strong) !important;
      fill: var(--brand-strong) !important;
    }

    /* ===== כפתורי הורדה / Outline ===== */
    .stDownloadButton > button,
    .stButton > button[kind="secondary"] {
      border-color: var(--brand-main) !important;
      color: var(--brand-main) !important;
      background: #fff !important;
      box-shadow: none !important;
    }
    .stDownloadButton > button:hover,
    .stButton > button[kind="secondary"]:hover {
      border-color: var(--brand-strong) !important;
      color: var(--brand-strong) !important;
      background: var(--brand-soft) !important;
    }
    .stDownloadButton > button:active,
    .stButton > button[kind="secondary"]:active {
      border-color: var(--brand-strong) !important;
      color: var(--brand-strong) !important;
      background: var(--brand-soft) !important;
      box-shadow: none !important;
    }
    </style>
    """, unsafe_allow_html=True)


def inject_sidebar_layout_css():
    """מזריק CSS פריסת סיידבר: גובה מלא, תיבה תחתונה (logout) צמודה לתחתית."""
    st.markdown("""
    <style>
    /* גובה מלא לסיידבר + פריסת עמודה */
    [data-testid="stSidebar"] > div:first-child {
        height: 100%;
        display: flex;
        flex-direction: column;
    }

    /* wrapper לכל התוכן */
    [data-testid="stSidebar"] .sb-flex {
        display: flex;
        flex-direction: column;
        height: 100%;
    }

    /* בלוק תחתון צמוד לתחתית */
    [data-testid="stSidebar"] .push-bottom.logout-box {
        margin-top: auto;            
        padding: 6px 6px 30px;       
        border-top: 1px solid #e2e2e2;
        direction: rtl;
    }

    /* שורה קטנה: טקסט+כפתור */
    .logout-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 8px;
    }

    /* טקסט קטן ורך */
    .logout-user {
        font-size: 0.82rem;
        color: #555;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    /* כפתור קטן יותר */
    .logout-box .stButton > button {
        font-size: 0.78rem !important;
        padding: 2px 8px !important;
        border-radius: 8px !important;
        min-height: 26px !important;
        line-height: 1.1 !important;
    }
    </style>
    """, unsafe_allow_html=True)
