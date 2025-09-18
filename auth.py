import streamlit as st

def simple_login():
    # ---- מעקף DEV: אם ENV=dev ב-secrets או APP_ENV=dev במשתני סביבה ----
    is_dev = (
        str(st.secrets.get("ENV", "prod")).lower() == "dev"
        or str(os.getenv("APP_ENV", "")).lower() == "dev"
    )
    if is_dev:
        # אוטומטית מחובר כ"dev" – בלי טופס
        st.session_state.authentication_status = True
        st.session_state.username = st.session_state.get("username", "dev")
        st.session_state["show_logout"] = True
        # תווית קטנה שתזכיר שזה DEV
        st.caption("🛠️ מצב פיתוח פעיל (ללא התחברות)")
        return True
    # --------------------------------------------------------------------

    # ---- לוגין רגיל (כשלא ב-DEV) ----
    if 'authentication_status' not in st.session_state:
        st.session_state.authentication_status = None

    if st.session_state.authentication_status is None:
        st.title("התחברות למערכת")
        with st.form("login_form"):
            username = st.text_input("שם משתמש")
            password = st.text_input("סיסמא", type="password")
            submit_button = st.form_submit_button("התחבר")

            if submit_button:
                valid_users = {
                    "sivan": "mycospring", "ido": "mycospring", "rea": "mycospring",
                    "pavel": "mycospring", "niv": "mycospring", "tania": "mycospring",
                    "asia": "mycospring", "ron": "mycospring", "eyal": "mycospring"
                }
                u = username.strip().lower()
                if u in valid_users and password == valid_users[u]:
                    st.session_state.authentication_status = True
                    st.session_state.username = u
                    st.success(f"ברוכים הבאים {u}!")
                    st.rerun()
                else:
                    st.error("שם משתמש או סיסמא שגויים")
        return False
    else:
        st.session_state["show_logout"] = True
        return True

# בדיקת התחברות
if not simple_login():
    st.stop()
