import streamlit as st

def simple_login() -> bool:
    # סביבה נקבעת *רק* מסודות (אפשר גם מה-OS אם את רוצה, אבל שיהיה אותו כלל)
    env = str(st.secrets.get("APP_ENV", "")).strip().lower()
    is_dev = env in ("dev", "development", "local")

    dev_bypass = bool(st.secrets.get("AUTH_DEV_BYPASS", True))  # אפשר להגדיר ל-False בפרוד

    if is_dev and dev_bypass:
        st.session_state.authentication_status = True
        st.session_state.username = st.session_state.get("username", "dev")
        st.session_state["show_logout"] = True
        st.caption("🛠️ מצב פיתוח (DEV) פעיל — ללא התחברות")
        return True

    users = dict(st.secrets.get("USERS", {})) or {
        "sivan":"mycospring","ido":"mycospring","rea":"mycospring",
        "pavel":"mycospring","niv":"mycospring","tania":"mycospring",
        "asia":"mycospring","ron":"mycospring","eyal":"mycospring"
    }

    if "authentication_status" not in st.session_state:
        st.session_state.authentication_status = None

    if st.session_state.authentication_status is None:
        st.title("התחברות למערכת")
        with st.form("login_form"):
            u = st.text_input("שם משתמש")
            p = st.text_input("סיסמה", type="password")
            if st.form_submit_button("התחבר"):
                u = (u or "").strip().lower()
                if u in users and p == str(users[u]):
                    st.session_state.authentication_status = True
                    st.session_state.username = u
                    st.session_state["show_logout"] = True
                    st.rerun()
                else:
                    st.error("שם משתמש או סיסמה שגויים")
        return False
    else:
        st.session_state["show_logout"] = True
        return True
