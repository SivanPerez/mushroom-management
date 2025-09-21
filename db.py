from __future__ import annotations
import os, json, time
from typing import List, Dict, Any
from collections.abc import Mapping
from datetime import date
import gspread
from gspread.exceptions import APIError, SpreadsheetNotFound, WorksheetNotFound
import streamlit as st
from oauth2client.service_account import ServiceAccountCredentials

# ======== הגדרות ברירת מחדל ========
DB_FILE_PROD_DEFAULT = "cordyceps-db"
DB_FILE_DEV_DEFAULT  = "cordyceps-db-DEV"

# מומלץ מאוד לשים את מזהה הגיליון (ID) ב-secrets:
# SHEETS_SPREADSHEET_ID  /  SHEETS_SPREADSHEET_ID_DEV
SHEET_ID_KEY_PROD = "SHEETS_SPREADSHEET_ID"
SHEET_ID_KEY_DEV  = "SHEETS_SPREADSHEET_ID_DEV"

# TTL למטמון נתונים (שניות). אפשר להגדיל ל-120 אם עדיין חוטפים 429.
DATA_TTL_SEC = int(st.secrets.get("DATA_CACHE_TTL", 60))

# סטטוסים שכדאי לנסות שוב עליהם
RETRY_STATUS = {429, 500, 503}
MAX_TRIES = 6
BASE_SLEEP = 0.7  # שניות


# ======== עזר: זיהוי סביבה ========
def is_prod() -> bool:
    env = st.secrets.get("APP_ENV", "").lower()
    if env in ("prod", "production"):
        return True
    if env in ("dev", "development", "local"):
        return False
    # בלי APP_ENV: אם יש מפתח פרוד – נניח PROD
    return "GOOGLE_SERVICE_ACCOUNT" in st.secrets


def _service_account_info() -> dict:
    key = "GOOGLE_SERVICE_ACCOUNT" if is_prod() else "GOOGLE_SERVICE_ACCOUNT_DEV"
    val = st.secrets[key]
    if isinstance(val, Mapping):
        return dict(val)  # כבר מילון
    if isinstance(val, str):
        return json.loads(val)  # נשמר כטקסט JSON
    raise RuntimeError(f"Unsupported secrets format for {key}: {type(val).__name__}")


def _spreadsheet_name() -> str:
    if is_prod():
        return st.secrets.get("BASE_SHEET_NAME", DB_FILE_PROD_DEFAULT)
    else:
        return st.secrets.get("BASE_SHEET_NAME_DEV", DB_FILE_DEV_DEFAULT)


def _spreadsheet_id() -> str | None:
    key = SHEET_ID_KEY_PROD if is_prod() else SHEET_ID_KEY_DEV
    return st.secrets.get(key)


# ======== Backoff כללי לקריאות GSpread ========
def _with_backoff(fn, *args, **kwargs):
    for attempt in range(1, MAX_TRIES + 1):
        try:
            return fn(*args, **kwargs)
        except APIError as e:
            # נסה לחלץ קוד סטטוס אם קיים
            status = getattr(e, "response", None)
            status_code = getattr(status, "status_code", None) or getattr(status, "status", None)
            if (status_code in RETRY_STATUS) and (attempt < MAX_TRIES):
                time.sleep(BASE_SLEEP * (2 ** (attempt - 1)))
                continue
            raise


# ======== התחברות ופתיחת גיליון – פעם אחת בלבד (Cache Resource) ========
@st.cache_resource(show_spinner=False)
def _authorize_client() -> gspread.Client:
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",  # ← עדכני
        "https://www.googleapis.com/auth/drive",
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(_service_account_info(), scope)
    return gspread.authorize(creds)


@st.cache_resource(show_spinner=False)
def _open_spreadsheet() -> gspread.Spreadsheet:
    client = _authorize_client()
    sid = _spreadsheet_id()
    if sid:
        return _with_backoff(client.open_by_key, sid)
    name = _spreadsheet_name()
    try:
        return _with_backoff(client.open, name)
    except SpreadsheetNotFound:
        return _with_backoff(client.create, name)



# גם ה-Worksheet עצמו כדאי להביא דרך פונקציה קטנה, ללא Cache (כי GSpread כבר מנהל)
def _get_or_create_ws(sh: gspread.Spreadsheet, species: str) -> gspread.Worksheet:
    try:
        return _with_backoff(sh.worksheet, species)
    except WorksheetNotFound:
        return _with_backoff(sh.add_worksheet, title=species, rows=2, cols=20)


# ======== כותרות – במטמון נפרד כדי לא למשוך כל פעם ========
@st.cache_data(ttl=600, show_spinner=False)
def _get_headers_cached(spreadsheet_id_or_name: str, species: str) -> List[str]:
    sh = _open_spreadsheet()
    ws = _get_or_create_ws(sh, species)
    headers = _with_backoff(ws.row_values, 1)
    if not headers:
        st.error(f"לא נמצאו כותרות בשורה 1 בגליון '{ws.title}'. אנא הוסיפי שורת כותרות.")
        raise ValueError("Worksheet has no header row")
    return [h.strip() for h in headers]


def _headers(ws: gspread.Worksheet) -> List[str]:
    # משתמשים במפתח קבוע למטמון: מזהה הגיליון (או השם) + שם טאב
    key = _spreadsheet_id() or _spreadsheet_name()
    return _get_headers_cached(key, ws.title)


# ======== קריאת נתונים – במטמון נתונים (TTL) ========
@st.cache_data(ttl=DATA_TTL_SEC, show_spinner=False)
def load_data(species: str) -> List[Dict[str, Any]]:
    """
    טוען רשומות עבור מין (ממפה לפי הכותרות בפועל), עם Cache לזמן קצר כדי לחסוך קריאות.
    """
    sh = _open_spreadsheet()
    ws = _get_or_create_ws(sh, species)

    # נמשוך בבת אחת את כל הערכים ונרכיב dicts
    values = _with_backoff(ws.get_all_values)
    if not values:
        return []

    headers = [h.strip() for h in (values[0] if values else [])]
    if not headers:
        st.error(f"לא נמצאו כותרות בשורה 1 בגליון '{ws.title}'.")
        raise ValueError("Worksheet has no header row")

    out: List[Dict[str, Any]] = []
    for row in values[1:]:
        if len(row) < len(headers):
            row = row + [""] * (len(headers) - len(row))
        out.append({headers[i]: row[i] for i in range(len(headers))})
    return out


# ======== next_id – נשען על הנתונים המטמונים כדי לא לקרוא שוב ========
def next_id(species: str) -> int:
    rows = load_data(species)  # מטמון DATA_TTL_SEC
    return max([int(r.get("id", 0) or 0) for r in rows], default=0) + 1


# ======== הוספת רשומה ========
def add_record(species: str, record: Dict[str, Any]):
    """
    מוסיף רשומה לפי סדר הכותרות בפועל.
    שאיפה: בקשה אחת ל-append_row.
    """
    sh = _open_spreadsheet()
    ws = _get_or_create_ws(sh, species)
    headers = _headers(ws)

    if not record.get("id"):
        record["id"] = next_id(species)

    row = [record.get(h, "") for h in headers]
    _with_backoff(ws.append_row, row)

    # ניקוי מטמון הנתונים כדי שהרענון הבא יראה את הרשומה החדשה מייד
    st.cache_data.clear()


# ======== עדכון לפי id (Batch Update במקום update_cell בלולאה) ========
def update_record_by_id(species: str, record_id: int, updates: Dict[str, Any]) -> bool:
    """
    מאתר שורה לפי id ומעדכן שדות קיימים באמצעות batch_update כדי לצמצם בקשות.
    מחזיר True אם נמצא עודכן, אחרת False.
    """
    sh = _open_spreadsheet()
    ws = _get_or_create_ws(sh, species)

    headers = _headers(ws)
    rows = load_data(species)  # מהמטמון – משיכה אחת
    # מציאת אינדקס שורה לוגי
    target_idx = None
    for idx, row in enumerate(rows):
        try:
            if int(row.get("id", 0) or 0) == int(record_id):
                target_idx = idx
                break
        except ValueError:
            continue

    if target_idx is None:
        return False

    sheet_row = target_idx + 2  # +1 לכותרות +1 לאינדקס 0-based

    # מסננים רק שדות שקיימים בכותרות
    items = [(k, v) for k, v in updates.items() if k in headers]
    if not items:
        return True  # אין מה לעדכן, אבל לא כישלון

    # יוצרים batch של טווחים לעדכון (אפשר לאחד רצפים, אבל גם בנפרד זה יעיל)
    data_requests = []
    for k, v in items:
        col = headers.index(k) + 1
        rng = gspread.utils.rowcol_to_a1(sheet_row, col)
        data_requests.append({
            "range": rng,
            "values": [[v]],
        })

    _with_backoff(ws.batch_update, data_requests)
    st.cache_data.clear()  # לנקות מטמון נתונים כדי לראות מייד את העדכון
    return True

def append_inventory_movement(species_en: str, stage: str,
                              delta_fresh_g: int = 0, delta_dry_g: int = 0,
                              when_ddmmyyyy: str | None = None, note: str = ""):
    """מוסיפה שורת תנועה ל-Inventory עם מאזנים לאחר הפעולה."""
    when = when_ddmmyyyy or date.today().strftime("%d/%m/%Y")

    inv_rows = load_data("Inventory") or []
    # מצא את השורה האחרונה למין הזה (אם אין – מאזן קודם אפס)
    sp_col = None
    if inv_rows:
        for k in inv_rows[0].keys():
            lk = str(k).strip().lower()
            if lk in ("מין", "species_en", "species"):
                sp_col = k; break

    prev_fresh = prev_dry = 0
    if sp_col:
        for r in reversed(inv_rows):
            if str(r.get(sp_col, "")).strip() == str(species_en).strip():
                prev_fresh = int(r.get("מלאי טרי (גרם)", 0) or 0)
                prev_dry   = int(r.get("מלאי יבש (גרם)", 0) or 0)
                break

    fresh_after = prev_fresh + int(delta_fresh_g or 0)
    dry_after   = prev_dry   + int(delta_dry_g   or 0)

    rec = {
        "id": next_id("Inventory"),
        "מין": species_en,            # או species_en אם זה השדה אצלך
        "species_en": species_en,     # בטוח לשים שניהם—ייקלט רק מה שקיים בכותרות
        "תאריך": when,
        "סוג תנועה": stage,
        "שינוי טרי (גרם)": int(delta_fresh_g or 0),
        "שינוי יבש (גרם)": int(delta_dry_g or 0),
        "מלאי טרי (גרם)": fresh_after,
        "מלאי יבש (גרם)": dry_after,
        "הערה": note or "",
    }
    add_record("Inventory", rec)  # add_record כבר מנקה cache

