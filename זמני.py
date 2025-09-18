def render_cordyceps(species_en: str, data: list[dict]):
    st.markdown("<h1 style='text-align:center;'>נתוני גידול קורדיספס</h1>", unsafe_allow_html=True)

    stages = [
        "צלחות פטרי", "תרבית נוזלית", "אינקובציה",
        "אנדרלייט", "מיון", "קטיף ראשוני", "קטיף אחרון"
    ]

    tabs = st.tabs(["דשבורד", *stages])

    # טאב דשבורד
    with tabs[0]:
        create_dashboard(data)

    # --- טאב 1: צלחות פטרי ---
    with tabs[1]:
        create_petri(data)

    # --- טאב 2: תרבית נוזלית ---
    with tabs[2]:
        st.header("תרבית נוזלית")
        liquid_stage = [c for c in data if c.get("שלב") == "בקבוקי תרבית נוזלית"]
        if liquid_stage:
            st.subheader("בקבוקים במלאי")
            df1_disp = pd.DataFrame(liquid_stage)
            df1_disp = df1_disp.replace("", pd.NA)
            df1_disp = df1_disp.dropna(axis=1, how="all")
            st.dataframe(df1_disp)

        plates = [c for c in data if c.get("שלב") == "צלחות פטרי"]
        if plates:
            st.subheader("הוספת בקבוקים מצלחת")
            options = {f"#{c['id']} {c['תרבית']} ({c['תאריך צלחת']})": c["id"] for c in plates}
            with st.form(f"add_liquid_{0}", clear_on_submit=True):  # ייחודי לכל טופס
                selected = st.selectbox("בחר צלחת", list(options.keys()))
                bottle_date = st.date_input("תאריך הכנת בקבוקים", value=date.today())
                bottle_count = st.number_input("מספר בקבוקים", min_value=1, value=15)
                transfers = st.number_input("מספר העברות לצלחת פטרי", min_value=0, value=2)
                if st.form_submit_button("צור בקבוקים"):
                    plate_id = options[selected]
                    plate = next(p for p in data if p["id"] == plate_id)
                    update_record_by_id(plate["id"], {
                        "שלב": "בקבוקי תרבית נוזלית",
                        "תאריך בקבוקים": bottle_date.strftime("%d/%m/%Y"),
                        "מספר בקבוקים": bottle_count,
                        "מספר העברות לצלחת פטרי": transfers
                    })

                    # מספר ההעברה של האם, ברירת מחדל 0 אם לא קיים
                    raw_parent = str(plate.get("מספר העברה", "")).strip()
                    if raw_parent.startswith("P"):
                        parent_passage = int(raw_parent[1:])  # מוריד את ה־P
                    elif raw_parent.isdigit():
                        parent_passage = int(raw_parent)  # אם זה מספר נקי
                    else:
                        parent_passage = 0  # אם חסר ערך

                    daughters_date = bottle_date.strftime("%d/%m/%Y")

                    for j in range(1, transfers + 1):
                        daughter = {
                            "id": get_next_id(species_en),
                            "שלב": "צלחות פטרי",
                            "תרבית": f"{plate['תרבית']}-{j}",
                            "תאריך צלחת": date.today().strftime("%d/%m/%Y"),
                            "מספר העברה": f"P{parent_passage + 1}",  # ← נשמר כטקסט "P1"
                        }
                        add_record(daughter)

                    data = load_data(species_en)

                    st.success(f"נוספו {transfers} צלחות בנות!")
                    st.rerun()
        else:
            st.info("אין צלחות זמינות ליצירת בקבוקים.")
        st.header("הדפסת מדבקות – תרבית נוזלית")

        # סינון התרביות בשלב בקבוקי תרבית נוזלית
        liquid_cultures = [c for c in data if c.get("שלב") == "בקבוקי תרבית נוזלית"]

        if not liquid_cultures:
            st.info("אין תרביות בשלב תרבית נוזלית ליצירת מדבקות.")
        else:
            options = {
                f"#{c['id']} {c.get('תרבית', '?')} ({c.get('תאריך בקבוקים', '-')})": c["id"]
                for c in liquid_cultures
            }
            selected_keys = st.multiselect("בחר תרביות (אצוות) לייצור מדבקות", list(options.keys()))

            selected_cultures = [c for c in liquid_cultures if c["id"] in [options[k] for k in selected_keys]]

            if selected_cultures and st.button("צור מדבקות (PDF)"):
                today_str = datetime.today().strftime("%Y-%m-%d")
                filename = f"{today_str}_Liquid_Labels.pdf"

                create_liquid_labels_pdf(selected_cultures, filename)

                with open(filename, "rb") as f:
                    st.download_button(
                        label="הורדה",
                        data=f,
                        file_name=filename,
                        mime="application/pdf"
                    )
                os.remove(filename)
        pass

    # --- טאב 3: אינקובציה ---
    with tabs[3]:
        st.header("אינקובציה")

        # סינון תרביות עם בקבוקים זמינים בלבד
        bottles = [c for c in data if c.get("שלב") == "בקבוקי תרבית נוזלית" and c.get("מספר בקבוקים", 0) > 0]

        if bottles:
            st.subheader("ביצוע אינקובציה")

            # בחירות כלליות
            substrate_value = st.selectbox("סוג מצע", ["כוסמין אורגני + נוזל חדש", "רותה + נוזל חדש", "אחר"])
            if substrate_value == "אחר":
                substrate_value = st.text_input("ציין סוג מצע אחר")

            sterilization_value = st.selectbox("משך קיטור בשעות", ["25", "30", "35", "אחר"])
            if sterilization_value == "אחר":
                sterilization_value = st.text_input("פרט שיטת חיטוי")

            box_type_value = st.selectbox("סוג קופסא", ["קופסא שחורה עגולה", "קופסא מלבנית 4.5 ליטר", "אחר"])
            if box_type_value == "אחר":
                box_type_value = st.text_input("פרט סוג קופסא")

            # רשימת התרביות לבחירה
            all_data = load_data(species_en)
            fresh_bottles = [c for c in all_data if
                             c.get("שלב") == "בקבוקי תרבית נוזלית" and c.get("מספר בקבוקים", 0) > 0]
            options = {
                f"#{c['id']} {c['תרבית']} ({c.get('תאריך בקבוקים', '-')}) - {c.get('מספר בקבוקים', 0)} בקבוקים": c["id"]
                for c in fresh_bottles
            }

            # שדה בחירת התרבית
            selected = st.selectbox("בחר תרבית מתאימה", list(options.keys()))

            # שמירת הבחירה ב-Session כדי לרנדר מחדש
            if "last_selected" not in st.session_state or st.session_state.last_selected != selected:
                st.session_state.last_selected = selected
                st.rerun()

            bottle_id = options[selected]
            bottle = next((p for p in all_data if p["id"] == bottle_id), {})
            total_bottles = bottle.get("מספר בקבוקים", 0)

            # מציג כמה בקבוקים יש במלאי
            st.markdown(f"**נשארו במלאי: {total_bottles} בקבוקים**")

            # טופס העברה לאינקובציה
            with st.form("add_inoc", clear_on_submit=True):
                box_date = st.date_input("תאריך אינקובציה", value=date.today())

                # כאן ה-Number Input מתעדכן לפי הבחירה הנוכחית
                inoc_bottles = st.number_input(
                    "כמה בקבוקים להעביר לאינקובציה",
                    min_value=1,
                    max_value=total_bottles,
                    value=total_bottles
                )
                box_count = st.number_input("כמה קופסאות להכין מהבקבוקים האלו", min_value=1)

                if st.form_submit_button("בצע אינקובציה"):
                    if inoc_bottles > total_bottles:
                        st.error("אין מספיק בקבוקים!")
                    else:
                        # עדכון מלאי בקבוקים
                        # 1. עדכון מספר בקבוקים בתרבית המקור
                        update_record_by_id(bottle_id, {
                            "מספר בקבוקים": total_bottles - inoc_bottles
                        })

                        # 2. יצירת תרבית חדשה בשלב אינקובציה
                        new_culture = {
                            "id": get_next_id(species_en),
                            "שלב": "אינקובציה",
                            "תרבית": bottle["תרבית"],
                            "תאריך אינקובציה": box_date.strftime("%d/%m/%Y"),
                            "מצע": substrate_value or "לא צוין",
                            "משך קיטור בשעות": sterilization_value or "לא צוין",
                            "סוג קופסא": box_type_value or "לא צוין",
                            "מספר בקבוקים": inoc_bottles,
                            "מספר קופסאות": box_count
                        }
                        add_record(new_culture)

                        data = load_data(species_en)

                        st.success(f"אינקובציה בוצעה! {inoc_bottles} בקבוקים → {box_count} קופסאות")
                        st.rerun()

        else:
            st.info("אין בקבוקים זמינים לאינקובציה.")

        # הצגת תרביות שכבר בשלב אינקובציה
        # הצגת תרביות שכבר בשלב אינקובציה
        incubations = [c for c in data if c.get("שלב") == "אינקובציה"]
        if incubations:
            st.subheader("תרביות בשלב אינקובציה")
            df_incubations = pd.DataFrame(incubations)
            df_incubations = df_incubations.replace("", pd.NA)
            df_incubations = df_incubations.dropna(axis=1, how="all")

            st.dataframe(df_incubations)

        # מדבקות
        st.header("הדפסת מדבקות")

        # רשימת כל התרביות עם אינקובציה
        cultures_for_labels = [c for c in data if c.get("שלב") == "אינקובציה"]

        if not cultures_for_labels:
            st.info("אין תרביות בשלב אינקובציה ליצירת מדבקות.")
        else:
            # מאפשר לבחור כמה ID-ים
            options = {f"#{c['id']} {c['תרבית']} ({c.get('תאריך אינקובציה', '-')})": c["id"] for c in
                       cultures_for_labels}
            selected_keys = st.multiselect("בחר תרביות להדפסה", list(options.keys()))

            # מאתרים את האובייקטים שנבחרו
            selected_cultures = [c for c in cultures_for_labels if c["id"] in [options[k] for k in selected_keys]]

            if selected_cultures and st.button("צור מדבקות"):
                today_str = datetime.today().strftime("%Y-%m-%d")
                filename = f"{today_str}_Labels.pdf"

                create_labels_pdf(selected_cultures, filename)

                with open(filename, "rb") as f:
                    st.download_button(
                        label="הורדה",
                        data=f,
                        file_name=filename,
                        mime="application/pdf"
                    )
                os.remove(filename)

        pass

    # --- טאב אנדרלייט ---
    with tabs[4]:
        st.header("אנדרלייט")
        prev_stage = "אינקובציה"
        ready_to_move = [c for c in data if c.get("שלב") == prev_stage]

        if ready_to_move:
            st.subheader("העברה לשלב אנדרלייט")
            options = {f"#{c['id']} {c['תרבית']} ({c.get('תאריך אינקובציה', '-')})": c["id"] for c in ready_to_move}
            with st.form("move_underlight", clear_on_submit=True):
                selected = st.selectbox("בחר תרבית", list(options.keys()))
                tdate = st.date_input("תאריך אנדרלייט", value=date.today())
                room = st.selectbox("מיקום אנדרלייט", ["חדר 4", "חדר 5", "חדר 7"])
                if st.form_submit_button("סיום העברה"):
                    c_id = options[selected]
                    update_record_by_id(c_id, {
                        "שלב": "אנדרלייט",
                        "תאריך אנדרלייט": tdate.strftime("%d/%m/%Y"),
                        "מיקום אנדרלייט": room
                    })
                    data = load_data(species_en)
                    st.success("בוצעה העברה לאנדרלייט!")
                    st.rerun()

        else:
            st.info("אין תרביות זמינות להעברה לשלב אנדרלייט.")

        dfc = pd.DataFrame([c for c in data if c.get("שלב") == "אנדרלייט"])
        if not dfc.empty:
            st.subheader("תרביות בשלב אנדרלייט")

            # החלפה של ערכים ריקים ל־Na כדי לסנן עמודות ריקות
            dfc = dfc.replace("", pd.NA)
            dfc = dfc.dropna(axis=1, how="all")

            st.dataframe(dfc)

        else:
            st.info("אין תרביות בשלב אנדרלייט.")

        pass

    # --- טאב מיון ---
    with tabs[5]:
        st.header("מיון")
        prev_stage = "אנדרלייט"
        ready_to_move = [c for c in data if c.get("שלב") == prev_stage]

        if ready_to_move:
            st.subheader("העברה לשלב מיון")
            options = {f"#{c['id']} {c['תרבית']} ({c.get('תאריך אנדרלייט', '-')})": c["id"] for c in ready_to_move}
            with st.form("move_sorting", clear_on_submit=True):
                selected = st.selectbox("בחר תרבית", list(options.keys()))
                tdate = st.date_input("תאריך מיון", value=date.today())
                damaged = st.number_input("מספר קופסאות פגומות", min_value=0)
                partial = st.number_input("מספר קופסאות לקטיף ראשוני", min_value=0)
                if st.form_submit_button("סיום מיון"):
                    c_id = options[selected]
                    update_record_by_id(c_id, {
                        "שלב": "מיון",
                        "תאריך מיון": tdate.strftime("%d/%m/%Y"),
                        "מספר קופסאות פגומות": damaged,
                        "מספר קופסאות לקטיף ראשוני": partial
                    })
                    data = load_data(species_en)

                    st.success("בוצע מיון!")
                    st.rerun()
        else:
            st.info("אין תרביות זמינות להעברה לשלב מיון.")

        dfc = pd.DataFrame([c for c in data if c.get("שלב") == "מיון"])
        if not dfc.empty:
            st.subheader("תרביות בשלב מיון")
            non_empty_cols = dfc.loc[:,
                             dfc.apply(lambda col: col.astype(str).str.strip().replace('nan', '').astype(bool).any())]
            st.dataframe(non_empty_cols)
        else:
            st.info("אין תרביות בשלב מיון.")
        pass

    # --- טאב קטיף ראשוני ---
    with tabs[6]:
        st.header("קטיף ראשוני")
        prev_stage = "מיון"
        ready_to_move = [c for c in data if c.get("שלב") == prev_stage]

        if ready_to_move:
            st.subheader("ביצוע קטיף ראשוני")
            options = {f"#{c['id']} {c['תרבית']} ({c.get('תאריך מיון', '-')})": c["id"] for c in ready_to_move}
            with st.form("move_first_harvest", clear_on_submit=True):
                selected = st.selectbox("בחר תרבית", list(options.keys()))
                tdate = st.date_input("תאריך קטיף ראשוני", value=date.today())
                weight = st.number_input("משקל קטיף ראשוני (גרם)", min_value=0)
                if st.form_submit_button("סיום קטיף ראשוני"):
                    c_id = options[selected]
                    update_record_by_id(c_id, {
                        "שלב": "קטיף ראשוני",
                        "תאריך קטיף ראשוני": tdate.strftime("%d/%m/%Y"),
                        "משקל קטיף ראשוני (גרם)": weight
                    })
                    data = load_data(species_en)

                    st.success("בוצע קטיף ראשוני!")
                    st.rerun()
        else:
            st.info("אין תרביות זמינות לקטיף ראשוני.")

        dfc = pd.DataFrame([c for c in data if c.get("שלב") == "קטיף ראשוני"])
        if not dfc.empty:
            st.subheader("תרביות בשלב קטיף ראשוני")
            non_empty_cols = dfc.loc[:,
                             dfc.apply(lambda col: col.astype(str).str.strip().replace('nan', '').astype(bool).any())]
            st.dataframe(non_empty_cols)
        else:
            st.info("אין תרביות בשלב קטיף ראשוני.")

        pass

    # --- טאב קטיף אחרון ---
    with tabs[7]:
        st.header("קטיף אחרון")
        prev_stage = "קטיף ראשוני"
        ready_to_move = [c for c in data if c.get("שלב") == prev_stage]

        if ready_to_move:
            st.subheader("ביצוע קטיף אחרון")
            options = {f"#{c['id']} {c['תרבית']} ({c.get('תאריך קטיף ראשוני', '-')})": c["id"] for c in ready_to_move}
            with st.form("move_final_harvest", clear_on_submit=True):
                selected = st.selectbox("בחר תרבית", list(options.keys()))
                tdate = st.date_input("תאריך קטיף אחרון", value=date.today())
                weight = st.number_input("משקל קטיף אחרון (גרם)", min_value=0)
                if st.form_submit_button("סיום קטיף אחרון"):
                    c_id = options[selected]
                    culture = next(c for c in data if c["id"] == c_id)
                    update_record_by_id(c_id, {
                        "שלב": "קטיף אחרון",
                        "סטטוס": "נקטף במלואו",
                        "תאריך קטיף אחרון": tdate.strftime("%d/%m/%Y"),
                        "משקל קטיף אחרון (גרם)": weight,
                        "סה\"כ קטיף (ק\"ג)": round((weight + culture.get("משקל קטיף ראשוני (גרם)", 0)) / 1000, 2),
                        "ממוצע משקל לקופסא (גרם)": round(
                            (weight + culture.get("משקל קטיף ראשוני (גרם)", 0)) / culture.get("מספר קופסאות", 1), 2)
                    })
                    data = load_data(species_en)

                    st.success("בוצע קטיף אחרון!")
                    st.rerun()
        else:
            st.info("אין תרביות זמינות לקטיף אחרון.")

        dfc = pd.DataFrame([c for c in data if c.get("שלב") == "קטיף אחרון"])
        if not dfc.empty:
            # חישובי משקל וממוצע כמו קודם
            # המרה מספרית לשדות דרושים
            dfc["משקל קטיף אחרון (גרם)"] = pd.to_numeric(
                dfc.get("משקל קטיף אחרון (גרם)", pd.Series([0] * len(dfc))),
                errors="coerce"
            ).fillna(0)

            dfc["משקל קטיף ראשוני (גרם)"] = pd.to_numeric(
                dfc.get("משקל קטיף ראשוני (גרם)", pd.Series([0] * len(dfc))),
                errors="coerce"
            ).fillna(0)

            dfc["מספר קופסאות"] = pd.to_numeric(
                dfc.get("מספר קופסאות", pd.Series([0] * len(dfc))),
                errors="coerce"
            ).fillna(0)

            dfc["מספר קופסאות לקטיף ראשוני"] = pd.to_numeric(
                dfc.get("מספר קופסאות לקטיף ראשוני", pd.Series([0] * len(dfc))),
                errors="coerce"
            ).fillna(0)

            dfc["מספר קופסאות פגומות"] = pd.to_numeric(
                dfc.get("מספר קופסאות פגומות", pd.Series([0] * len(dfc))),
                errors="coerce"
            ).fillna(0)

            # חישובים
            total_g = dfc["משקל קטיף אחרון (גרם)"] + dfc["משקל קטיף ראשוני (גרם)"]
            dfc["סה\"כ קטיף (ק\"ג)"] = (total_g / 1000).round(2)

            dfc["ממוצע משקל לקופסא (גרם)"] = dfc.apply(
                lambda row: round(total_g.loc[row.name] / row["מספר קופסאות"], 2)
                if row["מספר קופסאות"] > 0 else 0,
                axis=1
            )

            dfc["% אובדן לפני קטיף אחרון"] = dfc.apply(
                lambda row: round(
                    (row["מספר קופסאות לקטיף ראשוני"] + row["מספר קופסאות פגומות"]) / row["מספר קופסאות"] * 100
                    if row["מספר קופסאות"] > 0 else 0,
                    1
                ),
                axis=1
            )

            st.subheader("תרביות בשלב קטיף אחרון")
            non_empty_cols = dfc.loc[:,
                             dfc.apply(lambda col: col.astype(str).str.strip().replace('nan', '').astype(bool).any())]
            st.dataframe(non_empty_cols)
        else:
            st.info("אין תרביות בשלב קטיף אחרון.")

        pass

st.set_page_config(page_title="...", layout="wide")

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

/* ===== תיבות Alert (info/success/warning/error) ===== */
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
  background-color: var(--brand-main) !important; /* פס בצד */
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

# ===================== מינים נתמכים =====================
species_order = [
    "Cordyceps",
    "Hericium",
    "Reishi",
    "Shiitake",
    "Maitake",
    "Turkey Tail",
]

species_labels_he = {
    "Cordyceps": "קורדיספס",
    "Hericium": "רעמת אריה",
    "Reishi": "ריישי",
    "Shiitake": "שיטאקה",
    "Maitake": "מייטאקה",
    "Turkey Tail": "טרקי טייל",
}

# ===================== שמות שלבים =====================
STAGES = [
    "צלחות פטרי",
    "תרבית נוזלית",
    "P2G",              # מצלחת לגרעינים
    "G2G",              # גרעין לגרעין
    "אינקובציה",
    "אנדרלייט",
    "מיון",
    "קטיף ראשוני",
    "קטיף אחרון",
    "קטיף",             # פלאש יחיד
]

# ===================== רנדרים בסיסיים לכל שלב =====================
def stage_plate(data, species_he):          _show_stage_table(data, "צלחות פטרי", "צלחות פטרי")
def stage_lc(data, species_he):             _show_stage_table(data, "תרבית נוזלית", "תרבית נוזלית")
def stage_p2g(data, species_he):            _show_stage_table(data, "P2G", "P2G (מצלחת לגרעינים)")
def stage_g2g(data, species_he):            _show_stage_table(data, "G2G", "G2G (גרעין־לגרעין)")
def stage_inoc(data, species_he):           _show_stage_table(data, "אינקובציה", "אינקובציה")
def stage_underlight(data, species_he):     _show_stage_table(data, "אנדרלייט", "אנדרלייט")
def stage_sorting(data, species_he):        _show_stage_table(data, "מיון", "מיון")
def stage_harvest_single(data, species_he): _show_stage_table(data, "קטיף", "קטיף (פלאש יחיד)")
def stage_harvest_first(data, species_he):  _show_stage_table(data, "קטיף ראשוני", "קטיף ראשוני")
def stage_harvest_final(data, species_he):  _show_stage_table(data, "קטיף אחרון", "קטיף אחרון")

# ===================== מיפוי שלב → פונקציה =====================
RENDERERS = {
    "צלחות פטרי":    create_petri,
    "תרבית נוזלית": stage_lc,
    "P2G":          stage_p2g,
    "G2G":          stage_g2g,
    "אינקובציה":   stage_inoc,
    "אנדרלייט":    stage_underlight,
    "מיון":        stage_sorting,
    "קטיף":        stage_harvest_single,
    "קטיף ראשוני": stage_harvest_first,
    "קטיף אחרון":  stage_harvest_final,
}

# ===================== וורקפלו לכל מין =====================
# ===================== WORKFLOW לכל מין =====================
WORKFLOW = {
    # לקורדיספס – כולל דשבורד
    "קורדיספס": [
        "דשבורד",
        "צלחות פטרי",
        "תרבית נוזלית",
        "אינקובציה",
        "אנדרלייט",
        "מיון",
        "קטיף ראשוני",
        "קטיף אחרון",
    ],

    # לשאר המינים – בלי דשבורד
    "ריישי": [
        "צלחות פטרי",
        "P2G",
        "G2G",
        "אינקובציה",
        "אנדרלייט",
        "מיון",
        "קטיף ראשוני",
        "קטיף אחרון",
    ],
    "שיטאקה": [
        "צלחות פטרי",
        "P2G",
        "G2G",
        "אינקובציה",
        "אנדרלייט",
        "מיון",
        "קטיף ראשוני",
        "קטיף אחרון",
    ],
    "רעמת אריה": [
        "צלחות פטרי",
        "P2G",
        "G2G",
        "אינקובציה",
        "אנדרלייט",
        "מיון",
        "קטיף",   # פלאש יחיד
    ],
    "מייטאקה": [
        "צלחות פטרי",
        "P2G",
        "G2G",
        "אינקובציה",
        "אנדרלייט",
        "מיון",
        "קטיף",
    ],
    "טרקי טייל": [
        "צלחות פטרי",
        "P2G",
        "G2G",
        "אינקובציה",
        "אנדרלייט",
        "מיון",
        "קטיף",
    ],
}

if "species" not in st.session_state:
    st.session_state.species = st.query_params.get("species", [species_order[0]])[0]
if st.session_state.species not in species_order:
    st.session_state.species = species_order[0]

with st.sidebar:
    st.header("בחרי מין פטרייה")
    for sp in species_order:
        is_selected = (st.session_state.species == sp)
        label = species_labels_he.get(sp, sp)
        if st.button(label, key=f"sp_{sp}", use_container_width=True,
                     type=("primary" if is_selected else "secondary")):
            st.session_state.species = sp
            st.query_params["species"] = sp
            st.rerun()

# ===================== קבלת workflow_key בעברית מהמפתח בסשן =====================
def get_workflow_key_from_session():
    current_key = st.session_state.species                       # למשל "Cordyceps"
    workflow_key = species_labels_he.get(current_key, current_key)  # למשל "קורדיספס"
    return workflow_key, current_key

def render_species(species_en: str, data: list[dict]):
    data_local = data

    # מפתח עברי ל-WORKFLOW + המפתח האנגלי מהסיידבר
    workflow_key, current_key = get_workflow_key_from_session()
    current_he = species_labels_he.get(current_key, workflow_key)

    # אם זה קורדיספס – משתמשים ברנדר המקורי (שכולל דשבורד)
    if current_key == "Cordyceps":
        render_cordyceps(species_en, data_local)
        return

    # לשאר המינים – בלי דשבורד
    stages = WORKFLOW.get(workflow_key, [])
    # נוודא שלא במקרה נשאר "דשבורד" בתוך הרשימה
    stages_no_dashboard = [s for s in stages if s != "דשבורד"]

    st.markdown(
        f"<h1 style='text-align:center;'>נתוני גידול {current_he}</h1>",
        unsafe_allow_html=True
    )

    tabs = st.tabs(stages_no_dashboard)

    for i, stage_name in enumerate(stages_no_dashboard):
        with tabs[i]:
            fn = RENDERERS.get(stage_name)
            if fn:
                fn(data_local, current_he)
            else:
                st.subheader(stage_name)
                st.info("שלב זה עוד לא חובר לפונקציה.")

# ========= קריאה מרוכזת לרנדר לפי המין שנבחר =========
species_en = st.session_state.species  # לדוגמה: "Cordyceps"
data = load_data(species_en)
render_species(species_en, data)




def create_petri(data_local, current_he):
    st.header("צלחות פטרי")
    plates = [c for c in data_local if c.get("שלב") == "צלחות פטרי"]
    st.subheader("הוספת צלחת חדשה")
    with st.form("add_plate", clear_on_submit=True):
        strain = st.text_input("שם התרבית")
        passage_num = st.number_input("מספר העברה (P)", min_value=0, value=0, step=1)
        plate_date = st.date_input("תאריך צלחת", value=date.today())
        submitted = st.form_submit_button("הוסף")
        if submitted:
            new_entry = {
                "id": get_next_id(species_en),
                "שלב": "צלחות פטרי",
                "תרבית": strain,
                "תאריך צלחת": plate_date.strftime("%d/%m/%Y"),
                "מספר העברה": f"P{int(passage_num)}"
            }
            add_record(new_entry)
            data_local = load_data(species_en)
            st.success("הצלחת נוספה בהצלחה!")
            st.rerun()
    if plates:
        st.subheader("צלחות קיימות במלאי")
        df_plates = pd.DataFrame(plates)
        df_plates = df_plates.replace("", pd.NA)
        df_plates = df_plates.dropna(axis=1, how="all")

            # ודא שהעמודה קיימת ותמיד מספרית
            # אם אין עמודה בכלל – נוסיף אותה ריקה
        if "מספר העברה" not in df_plates.columns:
            df_plates["מספר העברה"] = ""

        def _to_P(v):
                # אם חסר/NaN/None → ריק
            if pd.isna(v):
                return ""
            s = str(v).strip()
            if not s or s in ("None", "nan", "NaN"):
                return ""
            if s.upper().startswith("P"):
                return "P" + s[1:]  # מבטיחים P גדול
            if s.isdigit():
                return f"P{int(s)}"
            return s  # משאיר כמו שהוא אם חריג

        df_plates["מספר העברה"] = df_plates["מספר העברה"].apply(_to_P)

            # סדר עמודות: id, מספר העברה, ואז השאר
        ordered_cols = ["id", "מספר העברה"] + [
            c for c in df_plates.columns if c not in ("id", "מספר העברה")
        ]
        st.dataframe(df_plates[ordered_cols])

    pass
