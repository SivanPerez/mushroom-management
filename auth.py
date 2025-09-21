import streamlit as st

def simple_login() -> bool:
    """
    לוגין אחיד עם מקור אמת יחיד לסביבה:
    - DEV מזוהה לפי st.secrets["APP_ENV"] או APP_ENV במשתני סביבה.
    - אם DEV וגם AUTH_DEV_BYPASS=True => דילוג על לוגין.
    - משתמשים/סיסמאות נקראים מ-[USERS] ב-secrets (אם אין - fallback למילון קשיח).
    """
    # ---- זיהוי סביבה עקבי ----
    env_from_secret = str(st.secrets.get("APP_ENV", "")).strip().lower()
    env_from_os = str(os.getenv("APP_ENV", "")).strip().lower()
    env = env_from_secret or env_from_os
    is_dev = env in ("dev", "development", "local")

    dev_bypass = bool(st.secrets.get("AUTH_DEV_BYPASS", True))  # ברירת מחדל: לאפשר מעקף ב-DEV

    # ---- מעקף DEV (אם מותר) ----
    if is_dev and dev_bypass:
        st.session_state.authentication_status = True
        st.session_state.username = st.session_state.get("username", "dev")
        st.session_state["show_logout"] = True
        st.caption("🛠️ מצב פיתוח (DEV) פעיל — ללא התחברות")
        return True

    # ---- לוגין רגיל (כשלא ב-DEV, או כש-dev_bypass=False) ----
    # טען משתמשים מה-secrets אם קיימים, אחרת fallback למילון הקודם
    valid_users = dict(st.secrets.get("USERS", {})) or {
        "sivan": "mycospring", "ido": "mycospring", "rea": "mycospring",
        "pavel": "mycospring", "niv": "mycospring", "tania": "mycospring",
        "asia": "mycospring", "ron": "mycospring", "eyal": "mycospring"
    }

    if 'authentication_status' not in st.session_state:
        st.session_state.authentication_status = None

    if st.session_state.authentication_status is None:
        st.title("התחברות למערכת")
        with st.form("login_form"):
            username = st.text_input("שם משתמש")
            password = st.text_input("סיסמא", type="password")
            submit_button = st.form_submit_button("התחבר")

            if submit_button:
                u = (username or "").strip().lower()
                if u in valid_users and password == str(valid_users[u]):
                    st.session_state.authentication_status = True
                    st.session_state.username = u
                    st.session_state["show_logout"] = True
                    st.success(f"ברוכים הבאים {u}!")
                    st.rerun()
                else:
                    st.error("שם משתמש או סיסמא שגויים")
        return False
    else:
        st.session_state["show_logout"] = True
        return True

# בדיקת התחברות — השאירי כפי שהוא
if not simple_login():
    st.stop()

# בדיקת התחברות
if not simple_login():
    st.stop()
