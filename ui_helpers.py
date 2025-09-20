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
def inject_rtl_safe_css():
    import streamlit as st
    st.markdown("""
    <style>
      /* RTL ויישור טקסט – ללא שינוי פריסה */
      .block-container { direction: rtl; text-align: right; }
      [data-testid="stSidebar"] { direction: rtl; }
      [data-testid="stSidebar"] * { text-align: right; }

      /* קלטים: כתיבה נוחה בעברית (מספרים נשארים הגיוניים) */
      textarea,
      input[type="text"], input[type="search"], input[type="email"], input[type="password"],
      [data-baseweb="input"] input {
        direction: rtl;
        unicode-bidi: plaintext;   /* שומר התנהגות תקינה של מספרים וסוגריים */
        text-align: right;
      }

      /* Select/MultiSelect טקסטים */
      [data-baseweb="select"] div { direction: rtl; text-align: right; }

      /* טבלאות ו-DataFrame */
      .stTable table, .stDataFrame table { direction: rtl; }
      .stTable th, .stTable td,
      .stDataFrame th, .stDataFrame td { text-align: right; }

      /* טאבים – רק כיווניות כותרות */
      .stTabs [role="tablist"] { direction: rtl; }
    </style>
    """, unsafe_allow_html=True)
