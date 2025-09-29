import os
import pandas as pd
import streamlit as st
from datetime import date, datetime, timedelta
import datetime as dt
from dashboard import create_dashboard
from db import add_record, update_record_by_id, next_id, load_data, append_inventory_movement, _open_spreadsheet
from labels import create_labels_pdf, create_liquid_labels_pdf
from types import SimpleNamespace
from ui_helpers import UIContext, _show_stage_table
from config import species_labels_he

# ===================== רנדררים =====================
# ==== Adapters / Helpers ====
def ctx_get(ctx, name, default=None):
    if ctx is not None:
        if hasattr(ctx, name):
            return getattr(ctx, name)
        if isinstance(ctx, dict) and name in ctx:
            return ctx[name]
    return globals().get(name, default)

def get_ops(ctx):
    """מאחד גישה לפעולות כתיבה/קריאה דרך ctx, עם חתימות עקביות."""
    species_en = ctx_get(ctx, "species_en", "unknown")

    add_record_fn = ctx_get(ctx, "add_record", globals().get("add_record"))
    update_record_by_id_fn = ctx_get(ctx, "update_record_by_id", globals().get("update_record_by_id"))
    ctx_next_id_fn = ctx_get(ctx, "next_id", globals().get("next_id"))  # עשוי להיות None
    reload_fn = ctx_get(ctx, "reload", globals().get("load_data"))

    # חייבים לפחות add/update; next_id נספק לבד אם חסר
    if not add_record_fn or not update_record_by_id_fn:
        st.error("חסרות פונקציות לוגיקה ב־ctx (add_record/update_record_by_id).")
        return None

    # עטיפות לחתימה אחידה
    def update_record(id_, fields: dict):
        try:
            return update_record_by_id_fn(species_en, id_, fields)
        except TypeError:
            return update_record_by_id_fn(id_, fields)

    def add_record(record: dict):
        try:
            return add_record_fn(species_en, record)
        except TypeError:
            return add_record_fn(record)

    # פולבק ל-next_id אם חסר
    def _fallback_next_id_from_data():
        data = ctx_get(ctx, "data", []) or []
        numeric_ids = []
        for c in data:
            v = c.get("id")
            s = "" if v is None else str(v).strip()
            if s.isdigit():
                numeric_ids.append(int(s))
        return (max(numeric_ids) + 1) if numeric_ids else 1

    def next_id_op():
        # 1) אם יש ב-ctx (או גלובלי שהושחל דרך globals().get)
        if ctx_next_id_fn:
            try:
                return ctx_next_id_fn(species_en)
            except TypeError:
                return ctx_next_id_fn()
        # 2) חישוב מה-data
        return _fallback_next_id_from_data()

    return {
        "species_en": species_en,
        "add": add_record,
        "update": update_record,
        "next_id": next_id_op,
        "reload": reload_fn,
    }

def _ops_for_sheet(ctx, sheet_name: str, loader_attr: str | None = None):
    # אם אין loader בקונטקסט – נטען ישירות דרך load_data(sheet_name)
    fallback_loader = (lambda: load_data(sheet_name))
    loader = getattr(ctx, loader_attr, None) or globals().get(loader_attr) or fallback_loader
    try:
        preload = loader() if callable(loader) else []
    except Exception:
        preload = []
    subctx = SimpleNamespace(species_en=sheet_name, reload=loader, data=preload)
    return get_ops(subctx)

def _norm(s):
    return str(s or "").replace("\u00a0"," ").strip().lower()

def _pick_latest_inventory_row(rows, species, sp_col):
    def parse_date(s):
        try: return datetime.strptime(str(s), "%d/%m/%Y").toordinal()
        except: return -1
    def to_int(x):
        s = str(x or "").strip()
        return int(s) if s.isdigit() else -1

    cands = [r for r in rows if _norm(r.get(sp_col)) == _norm(species)]
    if not cands:
        return None
    # עדכני לפי תאריך, ואם שווה—לפי id גבוה יותר
    return max(cands, key=lambda r: (parse_date(r.get("תאריך עדכון מלאי")), to_int(r.get("id"))))

def _kg_to_g(x):
    # קולט float בק"ג -> int בגרם
    return int(round(float(x) * 1000))

def _g_to_kg(x):
    # מציג בק"ג עם 2 ספרות אחרי הנקודה
    return round((int(x or 0)) / 1000.0, 2)

def _today_ddmmyyyy(d: date | None = None):
    return (d or date.today()).strftime("%d/%m/%Y")

def _find_row_by_species(rows, species_en):
    # מאתר שורת מלאי/ייבוש לפי מין (תמיכה גם ב-'מין' וגם ב-'species_en')
    for r in rows or []:
        if str(r.get("מין", "")).strip() == str(species_en).strip():
            return r
        if str(r.get("species_en", "")).strip() == str(species_en).strip():
            return r
    return None

def render_dashboard_generic(ctx, data=None, **kwargs):
    if data is None:
        data = load_data(ctx.species_en)
    create_dashboard(data)

def render_plate_generic(ctx, data=None, **kwargs):
    if data is None:
        data = load_data(ctx.species_en)

    st.header("צלחות פטרי")
    # --- טופס: הוספת צלחת חדשה ---
    st.subheader("הוספת צלחת חדשה")
    with st.form("add_plate", clear_on_submit=True):
        strain = st.text_input("שם התרבית")
        passage_num = st.number_input("מספר העברה (P)", min_value=0, value=0, step=1)
        plate_date = st.date_input("תאריך צלחת", value=date.today())
        msg = st.empty()  # placeholder להודעות
        submitted = st.form_submit_button("הוסף")

        if submitted:
            if not (strain or "").strip():
                msg("חסר שם תרבית.") #                msg.error("חסר שם תרבית.")

            else:
                ops = get_ops(ctx)
                if not ops:
                    return

                new_entry = {
                    "id": ops["next_id"](),
                    "שלב": "צלחות פטרי",
                    "תרבית": strain.strip(),
                    "תאריך צלחת": plate_date.strftime("%d/%m/%Y"),
                    "מספר העברה": f"P{int(passage_num)}",
                }
                ops["add"](new_entry)
                st.success("הצלחת נוספה בהצלחה!")

                st.rerun()

    # --- טבלה: צלחות קיימות ---
    plates = [c for c in data if (c.get("שלב") or "").strip() == "צלחות פטרי"]
    if plates:
        st.subheader("צלחות קיימות במלאי")
        df_plates = pd.DataFrame(plates).replace("", pd.NA).dropna(axis=1, how="all")

        # ודא שהעמודה קיימת ותמיד מיוצגת כטקסט "P<number>"
        if "מספר העברה" not in df_plates.columns:
            df_plates["מספר העברה"] = ""

        def _to_P(v):
            if pd.isna(v):
                return ""
            s = str(v).strip()
            if not s or s in ("None", "nan", "NaN"):
                return ""
            if s.upper().startswith("P"):
                # מנרמל ל-P גדולה ומשאיר את המספר
                return "P" + s[1:]
            if s.isdigit():
                return f"P{int(s)}"
            return s  # ערך חריג - מציג כמו שהוא

        df_plates["מספר העברה"] = df_plates["מספר העברה"].apply(_to_P)

        # סדר עמודות נעים: id, מספר העברה, ואז השאר
        ordered_cols = ["id", "מספר העברה"] + [c for c in df_plates.columns if c not in ("id", "מספר העברה")]
        st.dataframe(df_plates[ordered_cols], use_container_width=True)
    else:
        st.info("אין צלחות פטרי במלאי כרגע.")

def render_liquid_generic(ctx, data=None, **kwargs):
       # ===== בקבוקים במלאי =====
    liquid_stage = [
        c for c in data
        if (c.get("שלב") or "").strip() == "בקבוקי תרבית נוזלית"
           and int(c.get("מספר בקבוקים", 0) or 0) > 0
    ]

    if liquid_stage:
        st.subheader("בקבוקים במלאי")

        # טבלת שורות מלאה (פר תרבית/אצווה)
        df = (
            pd.DataFrame(liquid_stage)
            .replace("", pd.NA)
            .dropna(axis=1, how="all")
        )

        # מציג עמודות עיקריות אם קיימות
        preferred_cols = ["id", "תרבית", "תאריך בקבוקים", "מספר בקבוקים", "מספר העברות לצלחת פטרי"]
        cols_to_show = [c for c in preferred_cols if c in df.columns] or df.columns.tolist()
        st.dataframe(df[cols_to_show].sort_values(by=cols_to_show[2] if len(cols_to_show) > 2 else cols_to_show[0],
                                                  ascending=False),
                     use_container_width=True)

    else:
        st.info("אין בקבוקים זמינים במלאי בשלב תרבית נוזלית.")

    if data is None:
        data = load_data(ctx.species_en)

    st.header("תרבית נוזלית")

    ops = get_ops(ctx)
    if not ops:
        st.stop()

    update      = ops["update"]
    add         = ops["add"]
    next_id     = ops["next_id"]


    # ===== העברה מצלחות → תרבית נוזלית (+יצירת בנות) =====
    plates = [c for c in data if c.get("שלב") == "צלחות פטרי"]
    if plates:
        st.subheader("הוספת בקבוקים מצלחת")
        options = {f"#{c['id']} {c['תרבית']} ({c.get('תאריך צלחת','-')})": c["id"] for c in plates if "id" in c}

        def _parse_passage(val):
            s = str(val or "").strip().upper()
            if s.startswith("P"):
                s = s[1:]
            return int(s) if s.isdigit() else 0

        with st.form("add_liquid", clear_on_submit=True):
            selected     = st.selectbox("בחר צלחת", list(options.keys()))
            bottle_date  = st.date_input("תאריך הכנת בקבוקים", value=date.today())
            bottle_count = st.number_input("מספר בקבוקים", min_value=1, value=15, step=1)
            transfers    = st.number_input("מספר העברות לצלחת פטרי", min_value=0, value=2, step=1)

            if st.form_submit_button("צור בקבוקים"):
                plate_id = options[selected]
                plate = next((p for p in data if p.get("id") == plate_id), None)
                if not plate:
                    st.error("הצלחת שנבחרה לא נמצאה.")
                    return

                # 1) מעדכן את הצלחת לשלב תרבית נוזלית
                update(plate_id, {
                    "שלב": "בקבוקי תרבית נוזלית",
                    "תאריך בקבוקים": bottle_date.strftime("%d/%m/%Y"),
                    "מספר בקבוקים": int(bottle_count),
                    "מספר העברות לצלחת פטרי": int(transfers),
                })

                # 2) יוצר צלחות בנות (אם ביקשו)
                if transfers >= 0:
                    parent_passage = _parse_passage(plate.get("מספר העברה"))
                    daughters_passage = f"P{parent_passage + 1}"
                    nid = next_id()  # מחשבים פעם אחת ומעלים ידנית כדי למנוע התנגשויות
                    daughters_date = bottle_date.strftime("%d/%m/%Y")  # אפשר להשתמש ב-today() אם מעדיפים
                    for j in range(1, int(transfers) + 1):
                        daughter = {
                            "id": nid,
                            "שלב": "צלחות פטרי",
                            "תרבית": f"{plate.get('תרבית','?')}-{j}",
                            "תאריך צלחת": daughters_date,
                            "מספר העברה": daughters_passage
                        }
                        add(daughter)         # התמדה ל-DB
                        nid += 1

                st.success("נוצרו בקבוקים ובהתאם נוספו צלחות בנות.")
                st.rerun()
    else:
        st.info("אין צלחות זמינות ליצירת בקבוקים.")


    # ===== הדפסת מדבקות לבקבוקים =====
    st.header("הדפסת מדבקות – תרבית נוזלית")

    liquid_cultures = [
        c for c in data
        if (c.get("שלב") or "").strip() == "בקבוקי תרבית נוזלית"
           and int(c.get("מספר בקבוקים", 0) or 0) > 0
    ]

    if not liquid_cultures:
        st.info("אין תרביות בשלב תרבית נוזלית ליצירת מדבקות.")
        return

    opt_labels = {
        f"#{c.get('id','-')} {c.get('תרבית','?')} ({c.get('תאריך בקבוקים','-')})": c["id"]
        for c in liquid_cultures if "id" in c
    }
    selected_keys = st.multiselect("בחר תרביות (אצוות) לייצור מדבקות", list(opt_labels.keys()))
    selected_ids = [opt_labels[k] for k in selected_keys]
    selected_cultures = [c for c in liquid_cultures if c.get("id") in selected_ids]

    if selected_cultures and st.button("צור מדבקות (PDF)"):
        if not create_liquid_labels_pdf:
            st.error("הפונקציה create_liquid_labels_pdf לא נמצאה.")
            return

        today_str = datetime.today().strftime("%Y-%m-%d")
        filename = f"{today_str}_Liquid_Labels.pdf"
        create_liquid_labels_pdf(selected_cultures, filename)

        try:
            with open(filename, "rb") as f:
                st.download_button(
                    label="הורדה",
                    data=f,
                    file_name=filename,
                    mime="application/pdf"
                )
        finally:
            # אם הקובץ נוצר—ננקה אחרי ההורדה/ניסיון הורדה
            if os.path.exists(filename):
                os.remove(filename)

def render_incubation_generic(ctx: UIContext, show_labels: bool = True, data=None, **kwargs):

    ops = get_ops(ctx)
    if not ops:
        return

    st.header("אינקובציה")
    from db import load_data  # בחלק ה-imports של הקובץ אם לא קיים
    if data is None:
        data = load_data(ctx.species_en)

    bottles = [
        c for c in data
        if (c.get("שלב") or "").strip() == "בקבוקי תרבית נוזלית" and int(c.get("מספר בקבוקים", 0) or 0) > 0
    ]

    if bottles:
        st.subheader("ביצוע אינקובציה")

        substrate_value = st.selectbox("סוג מצע", ["כוסמין אורגני + נוזל חדש", "רותה + נוזל חדש", "אחר"])
        if substrate_value == "אחר":
            substrate_value = st.text_input("ציין סוג מצע אחר").strip()

        sterilization_value = st.text_input("קיטור xx(yy)").strip()

        box_type_value = st.selectbox("סוג קופסא", ["קופסא שחורה עגולה", "קופסא מלבנית 4.5 ליטר", "אחר"])
        if box_type_value == "אחר":
            box_type_value = st.text_input("פרט סוג קופסא").strip()

        options = {
            f"#{c['id']} {c.get('תרבית','?')} - {int(c.get('מספר בקבוקים',0) or 0)} בקבוקים": c["id"]
            for c in bottles
        }
        selected_label = st.selectbox("בחר תרבית מתאימה", list(options.keys()))

        state_key = f"last_selected_inc_{ctx.species_en}"
        if st.session_state.get(state_key) != selected_label:
            st.session_state[state_key] = selected_label
            st.rerun()

        bottle_id = options[selected_label]
        bottle = next((p for p in data if p["id"] == bottle_id), {})
        total_bottles = int(bottle.get("מספר בקבוקים", 0) or 0)

        st.markdown(f"**נשארו במלאי: {total_bottles} בקבוקים**")

        with st.form("add_inoc_generic", clear_on_submit=True):
            box_date = st.date_input("תאריך אינקובציה", value=date.today())
            inoc_bottles = int(st.number_input(
                "כמה בקבוקים להעביר לאינקובציה",
                min_value=1,
                max_value=max(1, total_bottles),
                value=max(1, total_bottles),
                step=1
            ))
            box_count = int(st.number_input("כמה קופסאות להכין מהבקבוקים האלו", min_value=1, value=1))

            submitted = st.form_submit_button("בצע אינקובציה")
            if submitted:
                if inoc_bottles > total_bottles:
                    st.error("אין מספיק בקבוקים!")
                else:
                    # 1) עדכון מלאי בקבוקים
                    ops["update"](bottle_id, {"מספר בקבוקים": total_bottles - inoc_bottles})

                    # 2) יצירת רשומה בשלב אינקובציה
                    new_culture = {
                        "id": ops["next_id"](),
                        "שלב": "אינקובציה",
                        "תרבית": bottle.get("תרבית"),
                        "תאריך אינקובציה": box_date.strftime("%d/%m/%Y"),
                        "מצע": substrate_value or "לא צוין",
                        "משך קיטור בשעות": sterilization_value or "לא צוין",
                        "סוג קופסא": box_type_value or "לא צוין",
                        "מספר בקבוקים": inoc_bottles,
                        "מספר קופסאות": box_count,
                    }
                    bottle_date_val = bottle.get("תאריך בקבוקים") or bottle.get("תאריך בקבוק")
                    if bottle_date_val:
                        new_culture["תאריך בקבוקים"] = bottle_date_val

                    plate_date_val = bottle.get("תאריך צלחת")
                    if plate_date_val:
                        new_culture["תאריך צלחת"] = plate_date_val

                    passage_val = bottle.get("מספר העברה")
                    if passage_val:
                        new_culture["מספר העברה"] = passage_val

                    ops["add"](new_culture)
                    st.success(f"אינקובציה בוצעה! {inoc_bottles} בקבוקים → {box_count} קופסאות")
                    st.rerun()
    else:
        st.info("אין בקבוקים זמינים לאינקובציה.")

    # טבלת אינקובציה
    incubations = [c for c in data if (c.get("שלב") or "").strip() == "אינקובציה"]
    if incubations:
        st.subheader("תרביות בשלב אינקובציה")
        df_inc = pd.DataFrame(incubations).replace("", pd.NA).dropna(axis=1, how="all")
        st.dataframe(df_inc, use_container_width=True)

    # מדבקות (אופציונלי)
    if show_labels:
        st.subheader("הדפסת מדבקות (אינקובציה)")
        if not incubations:
            st.info("אין תרביות בשלב אינקובציה ליצירת מדבקות.")
        else:
            opts = {f"#{c['id']} {c.get('תרבית','?')}": c["id"] for c in incubations}
            sel_keys = st.multiselect("בחר תרביות להדפסה", list(opts.keys()))
            selected_ids = [opts[k] for k in sel_keys]
            selected_cultures = [c for c in incubations if c["id"] in selected_ids]
            if selected_cultures and st.button("צור מדבקות"):
                today_str = datetime.today().strftime("%Y-%m-%d")
                filename = f"{today_str}_Labels.pdf"
                create_labels_pdf(selected_cultures, filename)
                with open(filename, "rb") as f:
                    st.download_button("הורדה", data=f, file_name=filename, mime="application/pdf")
                os.remove(filename)

def render_p2g_generic(ctx: UIContext, data=None, **kwargs):
    import os
    from datetime import date, datetime

    st.header("צלחת לגריין")

    # --- טעינת נתונים ---
    if data is None:
        data = load_data(ctx.species_en)

    # --- פעולות DB סטנדרטיות (כמו בתרבית נוזלית) ---
    ops = get_ops(ctx)
    if not ops:
        st.stop()
    update  = ops["update"]
    add     = ops["add"]
    next_id = ops["next_id"]

    # ===== יצירת שקיות מ"צלחות פטרי" + יצירת בנות =====
    plates = [c for c in data if c.get("שלב") == "צלחות פטרי" and "id" in c]
    if plates:
        st.subheader("הוספת גריין מצלחת")

        plate_options = {
            f"#{c['id']} {c.get('תרבית','?')} ({c.get('תאריך צלחת','-')})": c["id"]
            for c in plates
        }

        def _parse_passage(val):
            s = str(val or "").strip().upper()
            if s.startswith("P"):
                s = s[1:]
            return int(s) if s.isdigit() else 0

        with st.form("add_p2g_from_plate", clear_on_submit=True):
            selected_label = st.selectbox("בחר צלחת", list(plate_options.keys()))
            p2g_date       = st.date_input("תאריך אכלוס גריין", value=date.today())
            bag_count      = st.number_input("כמות שקיות גריין", min_value=1, value=4, step=1)
            transfers      = st.number_input("מספר העברות לצלחת פטרי", min_value=0, value=8, step=1)

            if st.form_submit_button("צור גריין"):
                plate_id = plate_options[selected_label]
                plate    = next((p for p in data if p.get("id") == plate_id), None)
                if not plate:
                    st.error("הצלחת שנבחרה לא נמצאה.")
                    return

                # 1) מעדכן את רשומת הצלחת לשלב P2G
                update(plate_id, {
                    "שלב": "P2G",
                    "תאריך P2G": p2g_date.strftime("%d/%m/%Y"),
                    "כמות שקיות גריין": int(bag_count),
                })

                # 2) יוצר צלחות בנות (כמו בתרבית נוזלית)
                if int(transfers) >= 0:
                    parent_passage    = _parse_passage(plate.get("מספר העברה"))
                    daughters_passage = f"P{parent_passage + 1}"
                    daughters_date    = p2g_date.strftime("%d/%m/%Y")

                    nid = next_id()
                    for j in range(1, int(transfers) + 1):
                        daughter = {
                            "id": nid,
                            "שלב": "צלחות פטרי",
                            "תרבית": f"{plate.get('תרבית','?')}-{j}",
                            "תאריך צלחת": daughters_date,
                            "מספר העברה": daughters_passage,
                        }
                        add(daughter)
                        nid += 1

                st.success("נוצרו שקיות גריין ונוספו צלחות בנות.")
                st.rerun()
    else:
        st.info("אין צלחות זמינות ליצירת גריין.")

    # ===== טבלת מלאי P2G =====
    p2g_items = [c for c in data if c.get("שלב") == "P2G"]
    if p2g_items:
        st.subheader("גריין במלאי")
        try:
            df = pd.DataFrame(p2g_items).replace("", pd.NA).dropna(axis=1, how="all")
            st.dataframe(df, use_container_width=True)
        except Exception:
            for row in p2g_items:
                st.write(f"#{row.get('id','-')} | {row.get('תרבית','?')} | שקיות: {row.get('כמות שקיות','-')} | תאריך P2G: {row.get('תאריך P2G','-')}")

    # ===== הדפסת מדבקות – P2G (שימוש זמני ב־create_liquid_labels_pdf) =====
    st.header("הדפסת מדבקות")
    p2g_for_labels = [c for c in data if c.get("שלב") == "P2G" and "id" in c]

    if not p2g_for_labels:
        st.info("אין תרביות בשלב P2G ליצירת מדבקות.")
        return

    opt_labels = {
        f"#{c.get('id','-')} {c.get('תרבית','?')} ({c.get('תאריך P2G','-')})": c["id"]
        for c in p2g_for_labels
    }
    selected_keys = st.multiselect("בחר גריין לייצור מדבקות", list(opt_labels.keys()))
    selected_ids  = [opt_labels[k] for k in selected_keys]
    selected_rows = [c for c in p2g_for_labels if c.get("id") in selected_ids]

    if selected_rows and st.button("צור מדבקות (PDF)"):
        if 'create_liquid_labels_pdf' not in globals():
            st.error("הפונקציה create_liquid_labels_pdf לא נמצאה.")
            return

        # התאמת השדות שמצפה להם היוצר של המדבקות של בקבוקים:
        # נעתיק כל רשומה ונמפה 'תאריך P2G' לשדה 'תאריך בקבוקים'
        adapted = []
        for c in selected_rows:
            cc = dict(c)  # העתק כדי לא לשנות את המקור
            if not cc.get("תאריך בקבוקים") and cc.get("תאריך P2G"):
                cc["תאריך בקבוקים"] = cc["תאריך P2G"]
            adapted.append(cc)

        today_str = datetime.today().strftime("%Y-%m-%d")
        filename  = f"{today_str}_P2G_Labels.pdf"

        create_liquid_labels_pdf(adapted, filename)

        try:
            with open(filename, "rb") as f:
                st.download_button(
                    label="הורדה",
                    data=f,
                    file_name=filename,
                    mime="application/pdf"
                )
        finally:
            if os.path.exists(filename):
                os.remove(filename)

def render_g2g_generic(ctx: UIContext, data=None, **kwargs):

    st.header("גריין לגריין")
    st.subheader("הוספת מחזור גריין")

    # --- טעינה ופעולות DB ---
    if data is None:
        data = load_data(ctx.species_en)

    ops = get_ops(ctx)
    if not ops:
        st.stop()
    update  = ops["update"]
    add     = ops["add"]
    next_id = ops["next_id"]

    # --- מקורות זמינים: P2G ו-G2G ---
    def _available_grain(row):
        stage = (row.get("שלב") or "").strip()
        if stage == "P2G":
            return int(row.get("כמות שקיות גריין", 0) or 0), "כמות שקיות גריין"
        if stage == "G2G":
            # ב-G2G המקור הזמין לשימוש הוא "כמות גריין חדש"
            return int(row.get("כמות גריין חדש", 0) or 0), "כמות גריין חדש"
        return 0, None

    candidates = []
    for c in data:
        avail, field = _available_grain(c)
        if field and avail > 0 and "id" in c:
            candidates.append((c, avail, field))

    if not candidates:
        st.info("אין גריין זמין")
        return

    # בונים את אפשרויות הבחירה (ללא רכיבי UI)
    options = {
        f"#{c['id']} {c.get('תרבית','?')} — שלב: {c.get('שלב')} — זמין: {avail}": c["id"]
        for (c, avail, field) in candidates
    }

    # -------- כל ה-UI בתוך הטופס --------
    with st.form("simple_g2g_form", clear_on_submit=True):
        selected_label = st.selectbox("בחר מקור", list(options.keys()))

        # נשלוף את המקור שנבחר ואת הזמינות שלו
        src_id = options[selected_label]
        src = next((p for p in data if p.get("id") == src_id), {})
        available, source_field = _available_grain(src)

        g2g_date = st.date_input("תאריך", value=date.today())

        used_colonized = int(st.number_input(
            "כמות גריין מקור",
            min_value=1,
            max_value=max(1, available),
            value=min(4, max(1, available)),
            step=1
        ))
        produced_new = int(st.number_input(
            "כמות גריין חדש",
            min_value=1,
            value=40,
            step=1
        ))

        submitted = st.form_submit_button("צור G2G")
        if submitted:
            if used_colonized > available:
                st.error("אין מספיק גריין מאוכלס במקור.")
            else:
                # 1) הפחתה מן המקור
                update(src_id, {source_field: available - used_colonized})

                # 2) יצירת רשומת G2G חדשה
                new_row = {
                    "id": next_id(),
                    "שלב": "G2G",
                    "תרבית": src.get("תרבית"),
                    "תאריך G2G": g2g_date.strftime("%d/%m/%Y"),
                    "כמות גריין מקור": used_colonized,
                    "כמות גריין חדש": produced_new,
                }

                # העברת מטא־דאטה שימושי אם קיים
                for key in ("מספר העברה", "תאריך P2G", "תאריך בקבוקים", "תאריך צלחת"):
                    if src.get(key):
                        new_row[key] = src[key]

                add(new_row)
                st.success(f"נוצרה אצוות G2G: השתמשת ב-{used_colonized} וייצרת {produced_new} חדשים.")
                st.rerun()

    # --- טבלת G2G במלאי ---
    g2g_rows = [c for c in data if (c.get("שלב") or "").strip() == "G2G"]
    if g2g_rows:
        st.subheader("G2G במלאי")
        try:
            df = pd.DataFrame(g2g_rows).replace("", pd.NA).dropna(axis=1, how="all")
            st.dataframe(df, use_container_width=True)
        except Exception:
            for row in g2g_rows:
                st.write(
                    f"#{row.get('id','-')} | {row.get('תרבית','?')} | מקור: {row.get('כמות גריין מקור','-')} | "
                    f"חדש: {row.get('כמות גריין חדש','-')} | תאריך: {row.get('תאריך G2G','-')}"
                )

def render_underlight_generic(ctx: UIContext, data=None, **kwargs):
    st.header("העברה לשלב אנדרלייט")
    if data is None:
        data = load_data(ctx.species_en)
    ops = get_ops(ctx)
    if not ops:
        st.stop()
    update = ops["update"]

    # רק תרביות משלב אינקובציה
    incubating = [c for c in data if str(c.get("שלב", "")).strip() == "אינקובציה"]

    if incubating:
        options = {f"#{c['id']} {c.get('תרבית','-')}": c["id"] for c in incubating if "id" in c}

        with st.form("move_to_underlight", clear_on_submit=True):
            selected = st.selectbox("בחר תרבית", list(options.keys()))
            ul_date  = st.date_input("תאריך אנדרלייט", value=date.today())
            loc_sel  = st.selectbox("מיקום אנדרלייט", ["חדר 4", "חדר 5", "חדר 7", "אחר"])
            loc_txt  = st.text_input("ציין מיקום") if loc_sel == "אחר" else ""
            submit   = st.form_submit_button("סיום העברה")

        if submit:
            location = (loc_txt or loc_sel).strip()
            if loc_sel == "אחר" and not location:
                st.error("בחרת 'אחר' — אנא צייני מיקום.")
                return

            c_id = options[selected]
            # כתיבה ל־DB
            update(c_id, {
                "שלב": "אנדרלייט",
                "תאריך אנדרלייט": ul_date.strftime("%d/%m/%Y"),
                "מיקום אנדרלייט": location,
            })

            st.success(f"תרבית #{c_id} הועברה לאנדרלייט ({location}).")
            st.rerun()
    else:
        st.info("אין תרביות אינקובציה זמינות להעברה לשלב אנדרלייט.")

    # טבלת מצב נוכחי
    _show_stage_table(data, "אנדרלייט", "תרביות בשלב אנדרלייט")

def render_block_generic(ctx: UIContext, show_labels: bool = True, data=None, **kwargs):

    ops = get_ops(ctx)
    if not ops:
        return

    st.header("אינקולציה בלוקים")

    # --- טעינת נתונים ---
    from db import load_data
    if data is None:
        data = load_data(ctx.species_en)

    # --- מקורות זמינים: G2G עם "כמות גריין חדש" > 0 ---
    g2g_sources = [
        c for c in data
        if (c.get("שלב") or "").strip() == "G2G" and int(c.get("כמות גריין חדש", 0) or 0) > 0 and "id" in c
    ]

    if not g2g_sources:
        st.info("אין גריין זמין מהשלב G2G לבלוקים.")
        return

    st.subheader("יצירת בלוקים")

    # --- בחירת מצע (עם "אחר" טקסט חופשי) ---
    substrate_value = st.selectbox("סוג מצע", ["מאסטר מיקס", "סובין סויה", "עץ", "אחר"])
    if substrate_value == "אחר":
        substrate_value = st.text_input("ציין סוג מצע אחר").strip()

    # --- משך קיטור (כיתוב חופשי, כמו 'xx(yy)') ---
    sterilization_value = st.text_input("קיטור xx(yy)").strip()

    # --- משקל בלוק (עם "אחר" טקסט חופשי) ---
    block_weight_value = st.selectbox("משקל בלוק", ["2 Kg", "2.5 Kg", "אחר"])
    if block_weight_value == "אחר":
        block_weight_value = st.text_input("ציין משקל בלוק אחר").strip()

    # --- בחירת מקור G2G ---
    options = {
        f"#{c['id']} {c.get('תרבית','?')} — זמין: {int(c.get('כמות גריין חדש',0) or 0)}": c["id"]
        for c in g2g_sources
    }
    selected_label = st.selectbox("בחר מקור G2G", list(options.keys()))

    # זיכרון בחירה אחרונה למניעת שינוי תדיר ב-UI
    state_key = f"last_selected_blocks_{ctx.species_en}"
    if st.session_state.get(state_key) != selected_label:
        st.session_state[state_key] = selected_label
        st.rerun()

    src_id = options[selected_label]
    src = next((p for p in data if p["id"] == src_id), {})
    available_grain = int(src.get("כמות גריין חדש", 0) or 0)

    # --- טופס יצירת בלוקים ---
    form_key = f"add_blocks_{ctx.species_en}"
    with st.form(key=form_key, clear_on_submit=True):
        block_date = st.date_input("תאריך אכלוס", value=date.today())
        used_grain = int(st.number_input(
            "כמות גריין מקור",
            min_value=1,
            max_value=max(1, available_grain),
            value=min(available_grain, 30) if available_grain > 0 else 1,
            step=1
        ))
        block_count = int(st.number_input("כמות בלוקים", min_value=1, value=300, step=1))

        submitted = st.form_submit_button("צור בלוקים")
        if submitted:
            if used_grain > available_grain:
                st.error("אין מספיק גריין מאוכלס במקור.")
            else:
                # 1) הפחתה מן המקור G2G
                ops["update"](src_id, {"כמות גריין חדש": available_grain - used_grain})

                # 2) יצירת רשומת בלוקים חדשה
                new_row = {
                    "id": ops["next_id"](),
                    "שלב": "אינקולציה בלוקים",
                    "תרבית": src.get("תרבית"),
                    "תאריך בלוקים": block_date.strftime("%d/%m/%Y"),
                    "מצע": substrate_value or "לא צוין",
                    "משך קיטור בשעות": sterilization_value or "לא צוין",
                    "משקל בלוק": block_weight_value or "לא צוין",
                    "מספר בלוקים": block_count,
                    "גריין בשימוש": used_grain,  # למעקב
                }

                # העברת מטא-דאטה שימושי אם קיים
                for key in ("מספר העברה", "תאריך G2G", "תאריך בקבוקים", "תאריך צלחת"):
                    if src.get(key):
                        new_row[key] = src[key]

                ops["add"](new_row)
                st.success(f"נוצרו בלוקים! השתמשת ב-{used_grain} גריין והכנת {block_count} בלוקים.")
                st.rerun()

    # --- טבלת בלוקים ---
    blocks_rows = [c for c in data if (c.get("שלב") or "").strip() == "אינקולציה בלוקים"]
    if blocks_rows:
        st.subheader("בלוקים במלאי")
        try:
            df = pd.DataFrame(blocks_rows).replace("", pd.NA).dropna(axis=1, how="all")
            st.dataframe(df, use_container_width=True)
        except Exception:
            for row in blocks_rows:
                st.write(
                    f"#{row.get('id','-')} | {row.get('תרבית','?')} | משקל: {row.get('משקל בלוק','-')} | "
                    f"מספר בלוקים: {row.get('מספר בלוקים','-')} | תאריך: {row.get('תאריך בלוקים','-')} | "
                    f"מצע: {row.get('מצע','-')} | מקור G2G: {row.get('מקור G2G','-')}"
                )

    # --- (אופציונלי) מדבקות לבלוקים ---
    if show_labels:
        st.subheader("הדפסת מדבקות (בלוקים)")
        if not blocks_rows:
            st.info("אין בלוקים ליצירת מדבקות.")
        else:
            opts = {f"#{c['id']} {c.get('תרבית','?')}": c["id"] for c in blocks_rows}
            sel_keys = st.multiselect("בחר בלוקים להדפסה", list(opts.keys()))
            selected_ids = [opts[k] for k in sel_keys]
            selected_blocks = [c for c in blocks_rows if c["id"] in selected_ids]
            if selected_blocks and st.button("צור מדבקות"):
                today_str = datetime.today().strftime("%Y-%m-%d")
                filename = f"{today_str}_Blocks_Labels.pdf"
                create_labels_pdf(selected_blocks, filename)
                with open(filename, "rb") as f:
                    st.download_button("הורדה", data=f, file_name=filename, mime="application/pdf")
                os.remove(filename)

def render_sorting_generic(ctx: UIContext, data=None, **kwargs):
    import pandas as pd
    from datetime import date
    import streamlit as st
    from db import load_data

    # ========= זיהוי מין =========
    species_en = (getattr(ctx, "species_en", "") or "").strip().lower()
    is_cordy = "cordy" in species_en  # קורדיספס נשאר בדיוק כמו שהיה

    # ========= הפעלה של גרסת "כמו שהיה" לקורדיספס =========
    if is_cordy:
        # ---- גרסת מקור (ללא שום שינוי) ----
        st.header("מיון")
        if data is None:
            data = load_data(ctx.species_en)
            # לוקחים את הפעולות מה־ctx
        ops = get_ops(ctx)
        if not ops:
            st.stop()

        update = ops["update"]  # מעדכן לפי id (Persist ל-DB/Sheets)

        prev_stage = "אנדרלייט"
        ready_to_move = [c for c in data if c.get("שלב") == prev_stage]

        if ready_to_move:
            st.subheader("העברה לשלב מיון")

            # מציגים תמיד את תאריך האנדרלייט בסוגריים
            options = {
                f"#{c['id']} {c['תרבית']} ({c.get('תאריך אנדרלייט', '-')})": c["id"]
                for c in ready_to_move
            }

            with st.form("move_sorting", clear_on_submit=True):
                selected = st.selectbox("בחר תרבית", list(options.keys()))
                tdate = st.date_input("תאריך מיון", value=date.today())
                damaged = st.number_input("מספר קופסאות פגומות", min_value=0, step=1)
                partial = st.number_input("מספר קופסאות לקטיף ראשוני", min_value=0, step=1)

                if st.form_submit_button("סיום מיון"):
                    c_id = options[selected]

                    # כתיבה ל-DB/Sheets באמצעות ops.update (העטיפה שלך כבר דואגת לחתימה)
                    update(c_id, {
                        "שלב": "מיון",
                        "תאריך מיון": tdate.strftime("%d/%m/%Y"),
                        "מספר קופסאות פגומות": int(damaged),
                        "מספר קופסאות לקטיף ראשוני": int(partial),
                    })

                    st.success("בוצע מיון!")
                    st.rerun()
        else:
            st.info("אין תרביות זמינות להעברה לשלב מיון.")

        # טבלת תרביות בשלב מיון
        dfc = pd.DataFrame([c for c in data if c.get("שלב") == "מיון"])
        if not dfc.empty:
            st.subheader("תרביות בשלב מיון")
            non_empty_cols = dfc.loc[
                :, dfc.apply(lambda col: col.astype(str).str.strip().replace('nan', '').astype(bool).any())]
            st.dataframe(non_empty_cols)
        else:
            st.info("אין תרביות בשלב מיון.")
        return  # קורדיספס הסתיים כאן

    # ========= כאן מתחיל המימוש למינים שאינם קורדיספס =========

    st.header("מיון")
    if data is None:
        data = load_data(ctx.species_en)

    ops = get_ops(ctx)
    if not ops:
        st.stop()
    update = ops["update"]

    # מועמדים למיון: אינקולציה בלוקים / מיון / קטיף
    ELIGIBLE_STAGES = ("אינקולציה בלוקים", "מיון", "קטיף")
    candidates = [
        c for c in data
        if (c.get("שלב") or "").strip() in ELIGIBLE_STAGES and "id" in c
    ]

    def _sorted_status(row):
        d = (row.get("תאריך מיון") or "").strip()
        return f"מוין ב-{d}" if d else "טרם מוין"

    def _ref_date(row):
        # תאריך עזר לתצוגה
        return row.get("תאריך מיון") or row.get("תאריך בלוקים") or row.get("תאריך אנדרלייט") or "-"

    if candidates:
        st.subheader("מיון בלוקים פגומים")

        # ✨ לא מציגים את שם השלב כדי לא לבלבל, רק תרבית + סטטוס מיון + תאריך רלוונטי
        options = {
            f"#{c['id']} {c.get('תרבית','?')} | {_sorted_status(c)} ({_ref_date(c)})": c["id"]
            for c in candidates
        }

        form_key = f"sorting_unified_{ctx.species_en}"
        with st.form(form_key, clear_on_submit=True):
            selected = st.selectbox("בחר תרבית", list(options.keys()))
            tdate = st.date_input("תאריך מיון", value=date.today())

            picked_id = options[selected]
            picked = next((x for x in data if x["id"] == picked_id), {})

            # ערך פגומים נוכחי (כולל גשר לעמודות היסטוריות אם ישנן)
            legacy = 0
            legacy += int(picked.get("מספר בלוקים פגומים", 0) or 0)
            legacy += int(picked.get("מספר קופסאות פגומות", 0) or 0)
            current_damaged = int(picked.get("פגומים", 0) or 0) or legacy

            # במקום ערך כולל — מזינים תוספת (דלתא) שתיסכם ל'פגומים'
            delta_damaged = st.number_input("כמות פגומים", min_value=0, step=1, value=0)

            note = st.text_input("הערת מיון (אופציונלי)").strip()

            if st.form_submit_button("סיום מיון"):
                current_stage = (picked.get("שלב") or "").strip()
                # אם מגיעים מאינקולציה בלוקים — נעביר ל"מיון", אחרת נשאיר את השלב
                new_stage = "מיון" if current_stage == "אינקולציה בלוקים" else current_stage

                new_total_damaged = current_damaged + int(delta_damaged)

                payload = {
                    "שלב": new_stage,
                    "תאריך מיון": tdate.strftime("%d/%m/%Y"),
                    "פגומים": new_total_damaged,  # ← סכום, לא החלפה
                }
                if note:
                    payload["הערת מיון"] = note
                    payload["תאריך עדכון מיון"] = date.today().strftime("%d/%m/%Y")

                update(picked_id, payload)
                st.success(f"עודכן בהצלחה. פגומים: {current_damaged} + {int(delta_damaged)} = {new_total_damaged}")
                st.rerun()
    else:
        st.info("אין תרביות זמינות למיון (אינקולציה בלוקים / מיון / קטיף).")

    # טבלת תרביות בשלב מיון (למינים שאינם קורדיספס)
    dfc = pd.DataFrame([c for c in data if (c.get("שלב") or "").strip() == "מיון"])
    if not dfc.empty:
        # ודאי שהעמודה 'פגומים' קיימת גם לשורות ישנות
        if "פגומים" not in dfc.columns:
            dfc["פגומים"] = pd.NA
        non_empty_cols = dfc.loc[:, dfc.apply(lambda col: col.astype(str).str.strip().replace('nan', '').astype(bool).any())]
        st.subheader("תרביות בשלב מיון")
        st.dataframe(non_empty_cols, use_container_width=True)
    else:
        st.info("אין כרגע תרביות בשלב מיון.")

def render_first_harvest_generic(ctx: UIContext, data=None, **kwargs):
    st.header("קטיף ראשוני")
    st.subheader("ביצוע קטיף ראשוני")

    ops = get_ops(ctx)
    if not ops:
        st.stop()
    update = ops["update"]

    # רק תרביות בשלב "מיון"
    sorting = [c for c in data if str(c.get("שלב", "")).strip() == "מיון"]

    def _fmt_ymd(v):
        if isinstance(v, date): return v.strftime("%Y/%m/%d")
        if isinstance(v, str):
            for fmt in ("%Y-%m-%d","%Y/%m/%d","%d/%m/%Y","%d-%m-%Y"):
                try: return datetime.strptime(v, fmt).strftime("%Y/%m/%d")
                except Exception: pass
        return "-"

    if sorting:
        options = {
            f"#{c['id']} {c.get('תרבית','-')} ({_fmt_ymd(c.get('תאריך אנדרלייט'))})": c["id"]
            for c in sorting if "id" in c
        }

        with st.form("first_pick_form", clear_on_submit=True):
            selected = st.selectbox("בחר תרבית", list(options.keys()))
            first_date = st.date_input("תאריך קטיף ראשוני", value=date.today())
            first_weight = st.number_input("משקל קטיף ראשוני (גרם)", min_value=0, step=1, value=0)
            submitted = st.form_submit_button("סיום קטיף ראשוני")

        if submitted:
            c_id = options[selected]
            update(c_id, {
                "שלב": "קטיף ראשוני",
                "תאריך קטיף ראשוני": first_date.strftime("%d/%m/%Y"),
                "משקל קטיף ראשוני (גרם)": int(first_weight),
            })
            append_inventory_movement(
                ctx.species_en,
                stage="קטיף ראשוני",
                delta_fresh_g=int(first_weight or 0),
                when_ddmmyyyy=first_date.strftime("%d/%m/%Y"),
            )

            st.success(f"תרבית #{c_id} עודכנה ל'קטיף ראשוני'.")
            st.rerun()
    else:
        st.info("אין תרביות זמינות לקטיף ראשוני (שלב: מיון).")

    # טבלה – מצב נוכחי של קטיף ראשוני
    _show_stage_table(data, "קטיף ראשוני", "תרביות בשלב קטיף ראשוני")

def render_final_harvest_generic(ctx: UIContext, data=None, **kwargs):
    st.header("קטיף אחרון")
    st.subheader("ביצוע קטיף אחרון")

    if data is None:
        data = load_data(ctx.species_en)

    ops = get_ops(ctx)
    if not ops:
        st.stop()
    update = ops["update"]

    # רק תרביות בשלב "קטיף ראשוני"
    ready = [c for c in data if str(c.get("שלב", "")).strip() == "קטיף ראשוני"]

    def _fmt_ymd(v):
        if isinstance(v, date): return v.strftime("%Y/%m/%d")
        if isinstance(v, str):
            for fmt in ("%Y-%m-%d","%Y/%m/%d","%d/%m/%Y","%d-%m-%Y"):
                try: return datetime.strptime(v, fmt).strftime("%Y/%m/%d")
                except Exception: pass
        return "-"

    if ready:
        options = {
            f"#{c['id']} {c.get('תרבית','-')} ({_fmt_ymd(c.get('תאריך אנדרלייט'))})": c["id"]
            for c in ready if "id" in c
        }

        with st.form("final_harvest_form", clear_on_submit=True):
            selected = st.selectbox("בחר תרבית", list(options.keys()))
            final_date = st.date_input("תאריך קטיף אחרון", value=date.today())
            final_weight = st.number_input("משקל קטיף אחרון (גרם)", min_value=0, step=1, value=0)
            submitted = st.form_submit_button("סיום קטיף אחרון")

        if submitted:
            c_id = options[selected]
            update(c_id, {
                "שלב": "קטיף אחרון",
                "תאריך קטיף אחרון": final_date.strftime("%d/%m/%Y"),
                "משקל קטיף אחרון (גרם)": int(final_weight),
            })
            append_inventory_movement(
                ctx.species_en,
                stage="קטיף אחרון",
                delta_fresh_g=int(final_weight or 0),
                when_ddmmyyyy=final_date.strftime("%d/%m/%Y"),
            )

            st.success(f"תרבית #{c_id} עודכנה ל'קטיף אחרון'.")
            st.rerun()
    else:
        st.info("אין תרביות זמינות לקטיף אחרון (שלב: קטיף ראשוני).")

    # טבלה – מצב נוכחי של קטיף אחרון
    _show_stage_table(data, "קטיף אחרון", "תרביות בשלב קטיף אחרון")

def render_harvest_others_generic(ctx: UIContext, data=None, **kwargs):
    """
    טאב קטיף לכל המינים שאינם קורדיספס.
    - קלט: תאריך קטיף, משקל (גרם), פלאש (ראשון/שני/אחר)
    - שמירה: סכימה מצטברת לעמודות משקל לפי פלאש + "משקל קטיף (גרם)" כולל
    - רישום למלאי: append_inventory_movement(stage="קטיף", delta_fresh_g=...)
    - סגירת מחזור קטיף: 'קטיף סגור' = TRUE + 'תאריך סגירת קטיף' → חוסם קטיפים עתידיים
    """
    # טעינת נתונים ואופרציות
    if data is None:
        data = load_data(ctx.species_en)
    ops = get_ops(ctx)
    if not ops:
        st.stop()
    update = ops["update"]

    st.header("קטיף")

    # שלבים מהם מותר לקטוף
    ELIGIBLE_STAGES = ("אינקולציה בלוקים", "מיון", "קטיף")

    # רשומות מותרות לקטיף: בשלב מתאים, לא סגורות, ויש להן id
    candidates = [
        c for c in data
        if (c.get("שלב") or "").strip() in ELIGIBLE_STAGES
        and not (str(c.get("קטיף סגור", "")).strip().upper() in ("TRUE", "1", "YES"))
        and "id" in c
    ]

    def _fmt_ymd(v):
        if isinstance(v, date): return v.strftime("%Y/%m/%d")
        if isinstance(v, str):
            for fmt in ("%Y-%m-%d","%Y/%m/%d","%d/%m/%Y","%d-%m-%Y"):
                try: return datetime.strptime(v, fmt).strftime("%Y/%m/%d")
                except Exception:
                    pass
        return "-"

    def _sorted_status(row):
        d = (row.get("תאריך מיון") or "").strip()
        return f"מוין ב-{d}" if d else "טרם מוין"

    def _ref_date(row):
        return row.get("תאריך מיון") or row.get("תאריך בלוקים") or row.get("תאריך אנדרלייט") or "-"

    # ===== טופס שמירת קטיף =====
    if candidates:
        st.subheader("שמירת קטיף")

        options = {
            f"#{c['id']} {c.get('תרבית','?')} | {_sorted_status(c)} ({_ref_date(c)})": c["id"]
            for c in candidates
        }

        form_key = f"harvest_others_{ctx.species_en}"
        with st.form(form_key, clear_on_submit=True):
            selected = st.selectbox("בחר תרבית", list(options.keys()))
            harvest_date = st.date_input("תאריך קטיף", value=date.today())
            harvest_weight = st.number_input("משקל קטיף (גרם)", min_value=0, step=1, value=0)

            flash_choice = st.selectbox("פלאש", ["פלאש ראשון", "פלאש שני", "אחר"])

            # נציג מידע קיים לרפרנס
            picked_id = options[selected]
            picked = next((x for x in data if x["id"] == picked_id), {})

            total_so_far = int(picked.get("משקל קטיף (גרם)", 0) or 0)
            f1_so_far = int(picked.get("משקל פלאש ראשון (גרם)", 0) or 0)
            f2_so_far = int(picked.get("משקל פלאש שני (גרם)", 0) or 0)
            fx_so_far = int(picked.get("משקל פלאשים נוספים (גרם)", 0) or 0)

            st.caption(f"סה\"כ משקל שנקצר עד כה: {total_so_far} גרם | פלאש1: {f1_so_far} | פלאש2: {f2_so_far} | אחרים: {fx_so_far}")

            submitted = st.form_submit_button("שמור קטיף")

        if submitted:
            if str(picked.get("קטיף סגור", "")).strip().upper() in ("TRUE", "1", "YES"):
                st.error("מחזור הקטיף סגור – לא ניתן לקטוף יותר.")
                st.stop()

            w = int(harvest_weight or 0)
            if w <= 0:
                st.error("יש להזין משקל קטיף גדול מאפס.")
                st.stop()

            # סכימה מצטברת
            new_total = total_so_far + w
            f1, f2, fx = f1_so_far, f2_so_far, fx_so_far
            if flash_choice == "פלאש ראשון":
                f1 += w
            elif flash_choice == "פלאש שני":
                f2 += w
            else:
                fx += w

            # קידום שלב: אם עדיין לא ב"קטיף" – נעבור ל"קטיף"
            current_stage = (picked.get("שלב") or "").strip()
            new_stage = "קטיף" if current_stage in ("אינקולציה בלוקים", "מיון") else current_stage

            payload = {
                "שלב": new_stage,
                "תאריך קטיף אחרון": harvest_date.strftime("%d/%m/%Y"),
                "משקל קטיף (גרם)": new_total,
                "משקל פלאש ראשון (גרם)": f1,
                "משקל פלאש שני (גרם)": f2,
                "משקל פלאשים נוספים (גרם)": fx,
                "פלאש אחרון": flash_choice,
            }

            update(picked_id, payload)

            # רישום במלאי (כמו בקורדיספס, רק עם stage="קטיף")
            append_inventory_movement(
                ctx.species_en,
                stage="קטיף",
                delta_fresh_g=w,
                when_ddmmyyyy=harvest_date.strftime("%d/%m/%Y"),
            )

            st.success(f"נשמר קטיף: #{picked_id} | {flash_choice} | {w} גרם (סה\"כ: {new_total} גרם).")
            st.rerun()
    else:
        st.info("אין תרביות זמינות לקטיף (אינקולציה בלוקים / מיון / קטיף).")

    st.divider()

    # ===== כפתור נפרד: סגירת מחזור קטיף (בלתי הפיך) =====
    closable = [
        c for c in data
        if (c.get("שלב") or "").strip() in ("קטיף", "מיון", "אינקולציה בלוקים")
           and not (str(c.get("קטיף סגור", "")).strip().upper() in ("TRUE", "1", "YES"))
           and "id" in c
    ]

    st.subheader("סגירת מחזור קטיף")
    st.caption("ברגע שסוגרים – לא ניתן לבצע קטיפים נוספים לתרבית זו.")

    if closable:
        opts_close = {
            f"#{c['id']} {c.get('תרבית', '?')} (סה\"כ עד כה: {int(c.get('משקל קטיף (גרם)', 0) or 0)} גרם)": c["id"]
            for c in closable
        }

        # יישור לתחתית ולגובה אחיד
        try:
            col1, col2 = st.columns([3, 1], vertical_alignment="bottom")
        except TypeError:
            col1, col2 = st.columns([3, 1])

        with col1:
            to_close_key = st.selectbox(
                "בחר תרבית לסגירה",
                list(opts_close.keys()),
                key=f"close_sel_{ctx.species_en}",
                label_visibility="collapsed",
                placeholder="בחר תרבית לסגירה",
            )

        with col2:
            really_close = st.button(
                "סגור מחזור קטיף",
                key=f"btn_close_{ctx.species_en}",
                type="secondary",
                use_container_width=False,
            )

        if really_close and to_close_key:
            close_id = opts_close[to_close_key]
            update(close_id, {
                "קטיף סגור": True,
                "תאריך סגירת קטיף": date.today().strftime("%d/%m/%Y"),
            })
            st.success(f"מחזור הקטיף נסגר עבור תרבית #{close_id}.")
            st.rerun()
    else:
        st.info("אין תרביות פתוחות לסגירת מחזור קטיף.")

    st.divider()

    # ===== טבלאות מצב =====
    # פתוחות לקטיף (לא סגור)
    open_rows = [
        c for c in data
        if (c.get("שלב") or "").strip() in ("אינקולציה בלוקים", "מיון", "קטיף")
        and not (str(c.get("קטיף סגור", "")).strip().upper() in ("TRUE", "1", "YES"))
    ]
    if open_rows:
        st.subheader("תרביות פתוחות לקטיף")
        df_open = pd.DataFrame(open_rows).replace("", pd.NA).dropna(axis=1, how="all")
        # ודאי שהעמודות המרכזיות קיימות (גם אם רשומות ישנות)
        for col in ["משקל קטיף (גרם)", "משקל פלאש ראשון (גרם)", "משקל פלאש שני (גרם)", "משקל פלאשים נוספים (גרם)"]:
            if col not in df_open.columns:
                df_open[col] = pd.NA
        st.dataframe(df_open, use_container_width=True)
    else:
        st.info("אין כרגע תרביות פתוחות לקטיף.")

    # סגורות
    closed_rows = [
        c for c in data
        if str(c.get("קטיף סגור", "")).strip().upper() in ("TRUE", "1", "YES")
    ]
    if closed_rows:
        st.subheader("תרביות שסגרו מחזור קטיף")
        df_closed = pd.DataFrame(closed_rows).replace("", pd.NA).dropna(axis=1, how="all")
        st.dataframe(df_closed, use_container_width=True)

def render_freeze_dry_generic(ctx: UIContext, data=None, **kwargs):
    st.header("פריז דריי")
    if data is None:
        data = load_data(ctx.species_en)
    species = getattr(ctx, "species_en", "unknown")

    # עזרי-מקום קטנים, כדי שלא נהיה תלויים בשום דבר חיצוני
    norm = lambda s: str(s or "").replace("\u00a0", " ").strip().lower()
    kg_to_g = lambda x: int(round(float(x) * 1000))
    g_to_kg = lambda x: round((int(x or 0))/1000.0, 2)
    fmt = lambda d=None: (d or date.today()).strftime("%d/%m/%Y")

    # טוען שורות מלשונית ראשית או חלופית (Uppercase), מחזיר גם את שם הלשונית שממנה נקראו הנתונים

    def sheet_rows(*names: str):
        """
        מחזיר (rows, chosen_tab) עבור הטאב הראשון שקיים בפועל.
        לא יוצר טאבים חדשים. משתמש ב-load_data הקיימת שלך.
        תומך גם בקריאות ישנות: sheet_rows("Drying", "DRYING") וגם sheet_rows("Inventory")
        """
        sh = _open_spreadsheet()
        try:
            existing = {ws.title for ws in sh.worksheets()}  # בדיקת קיום בלבד (אין יצירה)
        except Exception:
            existing = set()

        for name in names:
            if name in existing:
                # הטאב קיים -> load_data לא תיצור כלום, רק תקרא נתונים
                return (load_data(name) or []), name

        # אף אחד מהשמות לא קיים: לא יוצרים טאב, רק מחזירים ריק
        return [], (names[0] if names else "")

    # ===== פתיחת ייבוש =====
    st.subheader("פתיחת ייבוש")

    inv_rows, inv_sheet = sheet_rows("Inventory")
    if not inv_rows:
        st.error("גליון Inventory/INVENTORY ריק או ללא כותרות. הוסיפי כותרות ונתונים.")
        return

    # מציאת עמודת 'מין' (תומך בשמות חלופיים)
    keymap = {norm(k): k for k in inv_rows[0].keys()}
    sp_col = keymap.get("מין") or keymap.get("species_en") or keymap.get("species")
    if not sp_col:
        st.error(f"לא נמצאה עמודת מין. כותרות קיימות: {list(inv_rows[0].keys())}")
        return

    inv_row = _pick_latest_inventory_row(inv_rows, species, sp_col)
    if inv_row is None:
        avail = sorted({str(r.get(sp_col) or "").strip() for r in inv_rows if r.get(sp_col)})
        st.error(f"לא נמצאה שורת מלאי עבור “{species}” ב־{inv_sheet}. מינים קיימים: {', '.join(avail) or '—'}")
        return

    fresh_g = int(inv_row.get("מלאי טרי (גרם)", 0) or 0)
    st.caption(f"מלאי טרי נוכחי: {g_to_kg(fresh_g):.2f} ק\"ג")

    with st.form("fd_start", clear_on_submit=True):
        d_start  = st.date_input("תאריך התחלה", value=date.today())
        fresh_kg = st.number_input("כמה ק\"ג טרי נכנס למכונה", min_value=0.00, value=27.00, step=0.25, format="%.2f")
        note     = st.text_input("הערות (אופציונלי)")
        go_start = st.form_submit_button("פתח ייבוש")

    if go_start:
        use_g = kg_to_g(fresh_kg)
        if use_g <= 0:
            st.error("כמות טרי חייבת להיות חיובית.")
        elif use_g > fresh_g:
            st.error("אין מספיק מלאי טרי.")
        else:
            # 1) תנועת מלאי: הורדת טרי (append שורה חדשה)
            append_inventory_movement(
                species_en=species,
                stage="פריז דריי – פתיחה",
                delta_fresh_g=-int(use_g),
                when_ddmmyyyy=fmt(d_start),
                note=note,
            )
            # 2) יצירת עבודה פתוחה ב־Drying/DRYING
            fd_rows, fd_sheet = sheet_rows("Drying", "DRYING")
            add_record(fd_sheet, {
                "id": next_id(fd_sheet),
                "מין": inv_row.get(sp_col, species),  # שומר בדיוק את המחרוזת שמופיעה במלאי
                "תאריך התחלה": fmt(d_start),
                "משקל טרי (גרם)": use_g,
                "סטטוס": "פתוח",
                "הערות": note,
            })
            st.success("עבודה נפתחה והמלאי עודכן.")
            st.rerun()

    # ===== סגירת ייבוש =====
    st.subheader("סגירת ייבוש")

    fd_rows, fd_sheet = sheet_rows("Drying", "DRYING")
    if not fd_rows:
        st.info("אין עבודות פתוחות למין זה.")
    else:
        keymap_fd = {norm(k): k for k in fd_rows[0].keys()} if fd_rows else {}
        fd_sp_col = keymap_fd.get("מין") or keymap_fd.get("species_en") or keymap_fd.get("species") or "מין"
        open_jobs = [r for r in fd_rows if norm(r.get("סטטוס")) == "פתוח" and norm(r.get(fd_sp_col)) == norm(species)]

        if not open_jobs:
            st.info("אין עבודות פתוחות למין זה.")
        else:
            def label(r):
                kg_in = g_to_kg(r.get("משקל טרי (גרם)", 0))
                return f"#{r.get('id','-')} | התחלה: {r.get('תאריך התחלה','-')} | טרי: {kg_in:.2f} ק\"ג"

            options = {label(r): r for r in open_jobs}
            with st.form("fd_finish", clear_on_submit=True):
                sel_key  = st.selectbox("בחר עבודה פתוחה", list(options.keys()))
                d_finish = st.date_input("תאריך סיום", value=date.today())
                dry_kg   = st.number_input("כמה ק\"ג יבש יצא", min_value=0.00, value=0.00, step=0.05, format="%.2f")
                go_fin   = st.form_submit_button("סגור ייבוש")

            if go_fin:
                job   = options[sel_key]
                dry_g = kg_to_g(dry_kg)
                in_g  = int(job.get("משקל טרי (גרם)", 0) or 0)
                yield_p = round((dry_g / in_g) * 100, 2) if in_g > 0 else 0.0

                # 1) עדכון הרשומה ב־Drying/DRYING
                update_record_by_id(fd_sheet, job["id"], {
                    "תאריך סיום": fmt(d_finish),
                    "משקל יבש (גרם)": dry_g,
                    "תשואת ייבוש (%)": yield_p,
                    "סטטוס": "נסגר",
                })

                # תנועת מלאי: הוספת יבש (append שורה חדשה)
                append_inventory_movement(
                    species_en=species,
                    stage="פריז דריי – סגירה",
                    delta_dry_g=int(dry_g),
                    when_ddmmyyyy=fmt(d_finish),
                )

                st.success(f"ייבוש נסגר. נוספו {dry_kg:.2f} ק\"ג יבש (תשואה {yield_p}%).")
                st.rerun()

    fd_rows, fd_sheet = sheet_rows("Drying", "DRYING")
    if fd_rows:
        keymap_fd = {norm(k): k for k in fd_rows[0].keys()}
        fd_sp_col = keymap_fd.get("מין") or keymap_fd.get("species_en") or keymap_fd.get("species") or "מין"
        rows = [r for r in fd_rows if norm(r.get(fd_sp_col)) == norm(species)]
        if rows:
            st.subheader("מחזורי פריז דריי")
            df = pd.DataFrame(rows).replace("", pd.NA).dropna(axis=1, how="all")
            st.dataframe(df, use_container_width=True)

def render_inventory_generic(ctx, inv_data=None, **kwargs):
    if inv_data is None:
        inv_data = load_data("Inventory") or []
    species = getattr(ctx, "species_en", "unknown")
    species_he = species_labels_he.get(species, species)  # תווית עברית, נפילה חכמה לשם המקורי

    st.header(f"מלאי {species_he}")
    def norm(s):
        return str(s or "").replace("\u00a0", " ").strip().lower()



    # אתחל sp_col מתוך הכותרות בפועל ובחרי את השורה העדכנית
    sp_col = None
    if inv_data:
        for k in inv_data[0].keys():
            if norm(k) in ("מין", "species_en", "species"):
                sp_col = k
                break
    row = _pick_latest_inventory_row(inv_data, species, sp_col) if sp_col else None
    if not row:
        append_inventory_movement(species, stage="פתיחת מלאי", when_ddmmyyyy=_today_ddmmyyyy())
        st.rerun()

    fresh_g = int(row.get("מלאי טרי (גרם)", 0) or 0)
    dry_g   = int(row.get("מלאי יבש (גרם)", 0) or 0)

    c1, c2 = st.columns(2)
    c1.metric("מלאי טרי (ק״ג)", f"{_g_to_kg(fresh_g):.2f}")
    c2.metric("מלאי יבש (ק״ג)", f"{_g_to_kg(dry_g):.2f}")

    # תנועות למין הנוכחי
    moves = []
    if inv_data and sp_col:
        moves = [r for r in inv_data
                 if str(r.get(sp_col, "")).strip() == species]

    if moves:
        st.subheader("תנועות מלאי")
        cols_order = ["תאריך", "סוג תנועה", "שינוי טרי (גרם)", "שינוי יבש (גרם)",
                      "מלאי טרי (גרם)", "מלאי יבש (גרם)", "הערה", "id"]
        df_moves = (pd.DataFrame(moves)
                    .replace("", pd.NA).dropna(axis=1, how="all"))
        # סדר עמודות נעים, אם קיימות
        df_moves = df_moves[[c for c in cols_order if c in df_moves.columns] +
                            [c for c in df_moves.columns if c not in cols_order]]
        # מיון אחרונות למעלה (לפי id אם קיים, אחרת לפי תאריך כטקסט)
        if "id" in df_moves.columns:
            df_moves = df_moves.sort_values(by="id", ascending=False)
        st.dataframe(df_moves, use_container_width=True)

def build_renderers(data_all):
    def stage(name: str):
        return [r for r in data_all if (r.get("שלב") or "").strip() == name]

    return {
        "דשבורד": lambda ctx: render_dashboard_generic(ctx, data=data_all),

        # קריאה/תצוגה בלבד – מותר להעביר slice
        "צלחות פטרי": lambda ctx: render_plate_generic(ctx, data=stage("צלחות פטרי")),
        # מסכים שצריכים גם מקור וגם יעד – MUST data_all
        "תרבית נוזלית": lambda ctx: render_liquid_generic(ctx, data=data_all),
        "P2G": lambda ctx: render_p2g_generic(ctx, data=data_all),
        "G2G": lambda ctx: render_g2g_generic(ctx, data=data_all),
        "אינקולציה בלוקים": lambda ctx: render_block_generic(ctx, data=data_all),
        "אינקובציה": lambda ctx: render_incubation_generic(ctx, data=data_all, show_labels=True),
        "אנדרלייט": lambda ctx: render_underlight_generic(ctx, data=data_all),
        "מיון": lambda ctx: render_sorting_generic(ctx, data=data_all),
        "קטיף ראשוני": lambda ctx: render_first_harvest_generic(ctx, data=data_all),
        "קטיף אחרון": lambda ctx: render_final_harvest_generic(ctx, data=data_all),
        "קטיף": lambda ctx: render_harvest_others_generic(ctx, data=data_all),

        # גיליונות נפרדים – לא להעביר data מסונן
        "ייבוש": lambda ctx: render_freeze_dry_generic(ctx),
        "מלאי": lambda ctx: render_inventory_generic(ctx),
    }

