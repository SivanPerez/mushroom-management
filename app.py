import streamlit as st
from db import is_prod, _spreadsheet_name, load_data
from ui_helpers import UIContext, inject_base_css, inject_sidebar_layout_css
from renderers import build_renderers
from config import species_order, species_labels_he, WORKFLOW

#להשאיר למעלה
st.set_page_config(page_title="ניהול גידול פטריות", layout="wide")
inject_base_css()
inject_sidebar_layout_css()

_env = "PROD" if is_prod() else "DEV"
st.caption(f"מצב עבודה: **{_env}** {_spreadsheet_name()}")

qp = st.query_params
if "species" in qp:
    st.session_state.species = qp.get("species")
elif "species" not in st.session_state:
    st.session_state.species = species_order[0]

def rows(stage_name: str):
    """מסנן מהרשומות לפי הערך בעמודת 'שלב'."""
    return [r for r in data_all if (r.get("שלב") or "").strip() == stage_name]

# ===== ציור הסיידבר =====
with st.sidebar:
    # פותחים wrapper גמיש
    st.markdown('<div class="sb-flex">', unsafe_allow_html=True)

    for sp in species_order:
        is_selected = (st.session_state.species == sp)
        label = species_labels_he.get(sp, sp)
        if st.button(label, key=f"sp_{sp}", use_container_width=True,
                     type=("primary" if is_selected else "secondary")):
            st.session_state.species = sp
            st.query_params["species"] = sp
            st.rerun()

    # --- תחתית הסיידבר: משתמש + התנתקות (קטן ובצד) ---
    st.markdown('<div class="push-bottom logout-box">', unsafe_allow_html=True)
    st.markdown('<div class="logout-row">', unsafe_allow_html=True)

    # טקסט משתמש קטן
    username = st.session_state.get('username', '')
    st.markdown(f'<div class="logout-user">משתמש: {username}</div>', unsafe_allow_html=True)

    # כפתור קטן (נפרד מהתפריט)
    if st.button("התנתק", key="logout_sb_small"):
        st.session_state.authentication_status = None
        st.session_state.username = None
        st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)  # .logout-row
    st.markdown('</div>', unsafe_allow_html=True)  # .logout-box
    st.markdown('</div>', unsafe_allow_html=True)  # .sb-flex

# ===================== Router אחיד =====================
def get_workflow_key_from_session():
    current_key = st.session_state.species
    workflow_key = species_labels_he.get(current_key, current_key)
    return workflow_key, current_key

def render_species(species_en: str, data: list[dict]):
    workflow_key_he, current_key_en = get_workflow_key_from_session()
    current_he = species_labels_he.get(current_key_en, workflow_key_he)
    ctx = UIContext(species_en=current_key_en, species_he=current_he, data=data)

    stages = WORKFLOW.get(current_he, [])
    if not stages:
        st.error(f"לא הוגדר WORKFLOW עבור {current_he}")
        return

    st.markdown(f"<h1 style='text-align:center;'>נתוני גידול {current_he}</h1>", unsafe_allow_html=True)
    tabs = st.tabs(stages)

    for i, stage_name in enumerate(stages):
        with tabs[i]:
            fn = RENDERERS.get(stage_name)
            if fn:
                fn(ctx)
            else:
                st.subheader(stage_name)
                st.info("שלב זה עוד לא חובר לפונקציה.")

species_en = st.session_state.species  # לדוגמה: "Cordyceps"
data = load_data(species_en)
data_all = load_data(species_en)
RENDERERS = build_renderers(data_all)
render_species(species_en, data_all)

