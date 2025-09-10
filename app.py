import os
from datetime import datetime, timedelta, date
import streamlit as st
import json
import pandas as pd
import plotly.graph_objects as go
import gspread

from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.units import mm
from oauth2client.service_account import ServiceAccountCredentials
from datetime import date
from io import StringIO

DB_FILE = "cordyceps-db"  # שם הגיליון

# התחברות ל־Google Sheets
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]
service_account_info = json.loads(st.secrets["GOOGLE_SERVICE_ACCOUNT"])
creds = ServiceAccountCredentials.from_json_keyfile_dict(service_account_info, scope)
client = gspread.authorize(creds)
worksheet = client.open("cordyceps-db").sheet1
data = worksheet.get_all_records()

def update_record_by_id(record_id: int, updates: dict):
    """מחפש שורה לפי id ומעדכן את השדות שנשלחו בעדכון."""
    headers = worksheet.row_values(1)
    records = worksheet.get_all_records()
    for idx, row in enumerate(records):
        if row.get("id") == record_id:
            # השורה ב־gspread מתחילה משורה 2 כי שורת הכותרת היא 1
            sheet_row_index = idx + 2
            for key, value in updates.items():
                if key in headers:
                    col_index = headers.index(key) + 1  # עמודות הן 1-based
                    worksheet.update_cell(sheet_row_index, col_index, value)
            return True
    return False  # לא נמצא

def load_data():
    """טוען את כל הנתונים מהגיליון כ־dictים (כמו JSON)."""
    records = worksheet.get_all_records()
    return records

def get_next_id(data):
    """מחשב את ה-id הבא לפי הנתונים הקיימים."""
    return max([c.get('id', 0) for c in data], default=0) + 1

def add_record(record: dict):
    """מוסיף רשומה חדשה לשורה האחרונה בגיליון"""
    headers = worksheet.row_values(1)
    row = [record.get(col, "") for col in headers]
    worksheet.append_row(row)
def get_next_id(data):
    """מקבל את הרשומות ומחזיר את ה-id הבא הפנוי"""
    return max([c.get('id', 0) for c in data], default=0) + 1
# רישום פונט Arial (כדי לתמוך בעברית)
font_path = os.path.join(os.path.dirname(__file__), "Noto_Sans_Hebrew", "NotoSansHebrew-Regular.ttf")

# בדיקה שהפונט באמת קיים
if not os.path.exists(font_path):
    raise FileNotFoundError(f"Font not found at: {font_path}")

# רישום הפונט
pdfmetrics.registerFont(TTFont('NotoSansHebrew', font_path))
def create_labels_pdf(selected_cultures, filename):
    """יוצר PDF עם מדבקה נפרדת לכל תרבית שנבחרה (עמוד 4x4 אינץ' לכל אחת)."""
    page_size = (4 * 25.4 * mm, 4 * 25.4 * mm)
    c = canvas.Canvas(filename, pagesize=page_size)

    for culture in selected_cultures:
        # כל מדבקה היא עמוד נפרד
        create_single_label_page(c, culture, page_size)
        c.showPage()  # מסיים עמוד לפני הבא

    c.save()

def create_single_label_page(c, culture, page_size):
    """מייצר עמוד בודד של מדבקה (בשימוש בפונקציה הראשית)."""
    c.setStrokeColor(colors.black)
    c.setLineWidth(2)
    c.rect(0, 0, page_size[0], page_size[1])

    incubation_date = culture.get("תאריך אינקובציה", "")
    try:
        underlight_date = (datetime.strptime(incubation_date, "%d/%m/%Y") + timedelta(days=7)).strftime("%Y-%m-%d")
    except:
        underlight_date = ""

    rows = [
        ("ID", str(culture.get("id", "")), False, False),
        ("תאריך אינקובציה", incubation_date, True, False),
        ("תאריך אנדרלייט צפוי", underlight_date, True, False),
        ("תרבית", culture.get("תרבית", ""), True, True),
        ("מצע", culture.get("מצע", ""), True, True),
        ("משך קיטור בשעות", culture.get("משך קיטור בשעות", ""), True, False),
        ("בקבוקים", str(culture.get("מספר בקבוקים", "")), True, False),
        ("קופסאות", str(culture.get("מספר קופסאות", "")), True, False),
    ]

    c.setFont("NotoSansHebrew", 24)
    c.drawCentredString(page_size[0]/2, page_size[1]-40, f"ID: {rows[0][1]}")

    c.setFont("NotoSansHebrew", 18)
    y_text = page_size[1] - 90
    for title, value, flip_title, flip_value in rows[1:]:
        title_fixed = reverse_hebrew_text(title, flip_title)
        value_fixed = reverse_hebrew_text(value, flip_value)
        line = f"{value_fixed}: {title_fixed}"
        c.drawCentredString(page_size[0]/2, y_text, line)
        y_text -= 30

def reverse_hebrew_text(text, flip=True):
    """
    הופך את סדר האותיות אם יש טקסט עברי, אבל לא מפרק למילים.
    אם זה מספר או תאריך – משאיר כמו שהוא.
    """
    if not flip:
        return text
    # אם אין בכלל אותיות עבריות – לא הופכים
    if not any('\u0590' <= ch <= '\u05EA' for ch in text):
        return text
    return text[::-1]  # הופך את כל הטקסט (רק אם יש עברית)

def create_dashboard(data):
    # --- חישוב תפוסה באנדרלייט (כולל שלבים שממשיכים לתפוס מקום) ---
    valid_data = [c for c in data if isinstance(c, dict)]

    # איסוף כל התרביות שתופסות מקום
    underlay_data = []
    for c in valid_data:
        stage = c.get("שלב")
        boxes = int(c.get("מספר קופסאות", 0) or 0)

        # תרביות באנדרלייט – כל הקופסאות
        if stage == "אנדרלייט":
            underlay_data.append({"חדר": c.get("מיקום אנדרלייט", "לא צוין"), "קופסאות": boxes})

        # תרביות במיון – פחות פגומות
        elif stage == "מיון":
            damaged = int(c.get("מספר קופסאות פגומות", 0) or 0)
            underlay_data.append({"חדר": c.get("מיקום אנדרלייט", "לא צוין"), "קופסאות": max(boxes - damaged, 0)})

        # תרביות בקטיף ראשוני – פחות פגומות ופחות אלו שנכנסלו לקטיף מוקדם
        elif stage == "קטיף ראשוני":
            damaged = int(c.get("מספר קופסאות פגומות", 0) or 0)
            early = int(c.get("מספר קופסאות לקטיף ראשוני", 0) or 0)
            underlay_data.append(
                {"חדר": c.get("מיקום אנדרלייט", "לא צוין"), "קופסאות": max(boxes - damaged - early, 0)})

    # חישוב סטטיסטיקות לחדרים
    room_caps = {"חדר 4": 6900, "חדר 5": 2700, "חדר 7": 2700}
    room_stats = {r: 0 for r in room_caps}

    for item in underlay_data:
        room = item["חדר"]
        count = item["קופסאות"]
        if room in room_stats:
            room_stats[room] += count

    total_boxes = sum(room_stats.values())
    total_capacity = sum(room_caps.values())
    occupancy_pct = (total_boxes / total_capacity * 100) if total_capacity > 0 else 0

    if occupancy_pct < 50:
        bar_color = "#E74C3C"
        status_text = "🔴 תפוסה נמוכה"
    elif occupancy_pct < 80:
        bar_color = "#F39C12"
        status_text = "🟡 תפוסה בינונית"
    else:
        bar_color = "#2ECC71"
        status_text = "🟢 תפוסה מלאה"

    st.markdown(f"""
    <div style="background: #F8F9FA; padding: 20px; border-radius: 10px;
                border-left: 6px solid {bar_color}; margin-bottom: 20px;">
        <h3>תפוסה כוללת באנדרלייט</h3>
        <p>סה"כ קופסאות: <b>{total_boxes}</b> מתוך <b>{total_capacity}</b></p>
        <div style="background: #E9ECEF; border-radius: 8px; height: 25px; overflow: hidden;">
            <div style="background: {bar_color}; height: 100%; width: {occupancy_pct:.1f}%;"></div>
        </div>
        <p style="margin-top: 10px;">רמת תפוסה: {status_text} ({occupancy_pct:.1f}%)</p>
    </div>
    """, unsafe_allow_html=True)

    def draw_room_donut(room_name, occupancy_pct, color, total, capacity):
        # חישוב הערכים לתצוגה ולטול־טיפ
        display_pct = min(occupancy_pct, 100)
        remaining = 100 - display_pct

        # ערכים לטול־טיפ (מציגים את המספרים האמיתיים)
        full_boxes = total if total <= capacity else total
        free_boxes = max(capacity - total, 0)

        fig = go.Figure(data=[go.Pie(
            labels=['תפוס', 'פנוי'],
            values=[display_pct, remaining],
            hole=0.6,
            marker=dict(colors=[color, '#BDC3C7']),
            textinfo='none',
            hoverinfo='label+text',
            text=[f"תפוס: {full_boxes} קופסאות", f"פנוי: {free_boxes} קופסאות"]
        )])

        center_text = f"<b>{room_name}</b><br>{occupancy_pct:.1f}%"
        fig.update_layout(
            showlegend=False,
            margin=dict(t=0, b=0, l=0, r=0),
            annotations=[dict(
                text=center_text,
                x=0.5, y=0.5,
                font_size=16,
                showarrow=False,
                align="center"
            )],
            height=220, width=220
        )

        return fig


    # --- דונאטים לכל חדר באנדרלייט ---
    st.subheader("תפוסה לפי חדר (אנדרלייט)")
    cols = st.columns(len(room_stats))

    for idx, (room, count) in enumerate(room_stats.items()):
        capacity = room_caps.get(room, 0)
        occupancy_pct = (count / capacity * 100) if capacity > 0 else 0

        # בוחרים צבע לפי אחוזי תפוסה (מלא = ירוק, בינוני = כתום, נמוך = אדום)
        if occupancy_pct >= 80:
            color = "#2ECC71"  # ירוק
        elif occupancy_pct >= 50:
            color = "#F39C12"  # כתום
        else:
            color = "#E74C3C"  # אדום

        with cols[idx]:
            fig = draw_room_donut(room, occupancy_pct, color, count, capacity)
            import uuid
            unique_id = str(uuid.uuid4())
            st.plotly_chart(fig, use_container_width=False, key=f"donut-{unique_id}")


    # --- גרף קטיף חודשי בק"ג ---
    st.subheader("📈 קטיף חודשי (בקילוגרמים)")

    # שליפת נתוני קטיף (חודש מלא)
    harvest_data = []
    for culture in valid_data:
        for harvest_type in ["קטיף ראשוני", "קטיף אחרון"]:
            date_key = f"תאריך {harvest_type}"
            weight_key = f"משקל {harvest_type} (גרם)"
            if date_key in culture and weight_key in culture:
                try:
                    date_obj = datetime.strptime(culture[date_key], "%d/%m/%Y")
                    start_of_month = date_obj.replace(day=1)  # עיגול ל-1 בחודש
                    kg = float(culture.get(weight_key, 0)) / 1000
                    harvest_data.append({
                        "חודש": start_of_month.strftime("%Y-%m"),  # נשאר מחרוזת
                        "קילוגרמים": kg
                    })
                except:
                    continue

    if harvest_data:
        df_harvest = pd.DataFrame(harvest_data)
        monthly = df_harvest.groupby("חודש", as_index=False)["קילוגרמים"].sum()

        # הפיכת הציר לקטגוריות (ולא תאריך)
        monthly["חודש"] = monthly["חודש"].astype(str)

        # גרף
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=monthly["חודש"],
            y=monthly["קילוגרמים"],
            name="סה\"כ ק\"ג",
            text=monthly["קילוגרמים"].round(1),
            textposition="outside",
            marker_color="royalblue"
        ))

        fig.update_layout(
            title="קטיף חודשי (סה\"כ ק\"ג)",
            xaxis_title="חודש",
            yaxis_title="סה\"כ ק\"ג",
            xaxis=dict(type="category"),  # ציר X קטגוריאלי
            height=500,
            bargap=0.3,
            margin=dict(t=80, b=40),
            yaxis=dict(automargin=True, rangemode="tozero")
        )

        st.plotly_chart(fig, use_container_width=True, key="harvest-monthly")
    else:
        st.info("אין עדיין נתוני קטיף להצגה בגרף.")

        # יצירת גרף ריק עם צירים בלבד
        fig = go.Figure()
        fig.update_layout(
            title="קטיף חודשי (אין נתונים)",
            xaxis_title="חודש",
            yaxis_title="סה\"כ ק\"ג",
            xaxis=dict(type="category"),
            height=500,
            bargap=0.3,
            margin=dict(t=80, b=40),
            yaxis=dict(automargin=True, rangemode="tozero")
        )
        st.plotly_chart(fig, use_container_width=True, key="harvest-monthly-empty")

    st.subheader("🏆 תרביות מובילות לפי סוג קופסה")

    culture_avgs = []
    for culture in valid_data:
        if culture.get("שלב") != "קטיף אחרון":
            continue
        box_type = culture.get("סוג קופסא")
        if box_type not in ["קופסא שחורה עגולה", "קופסא מלבנית 4.5 ליטר"]:
            continue
        total_boxes = int(culture.get("מספר קופסאות", 0))
        total_weight_g = (
                float(culture.get("משקל קטיף ראשוני (גרם)", 0)) +
                float(culture.get("משקל קטיף אחרון (גרם)", 0))
        )
        if total_boxes > 0:
            avg_per_box = total_weight_g / total_boxes
            culture_avgs.append({
                "תרבית": culture.get("תרבית", "לא ידוע"),
                "ממוצע גרם לקופסא": avg_per_box,
                "סוג קופסא": box_type
            })

    df_cultures = pd.DataFrame(culture_avgs)

    col1, col2 = st.columns(2)
    for col, (box_type, color) in zip([col1, col2],
                                      [("קופסא שחורה עגולה", "#1F77B4"), ("קופסא מלבנית 4.5 ליטר", "#E67E22")]):
        df_filtered = df_cultures[df_cultures["סוג קופסא"] == box_type]
        if df_filtered.empty:
            with col:
                st.info(f"אין נתונים עבור {box_type}")
            continue

        top_20 = df_filtered.sort_values("ממוצע גרם לקופסא", ascending=True).tail(20)
        top_20 = top_20.sort_values("ממוצע גרם לקופסא", ascending=False).head(20)
        min_val, max_val = top_20["ממוצע גרם לקופסא"].min(), top_20["ממוצע גרם לקופסא"].max()

        def get_gradient_color(value, vmin, vmax):
            ratio = (value - vmin) / (vmax - vmin + 1e-6)
            if ratio < 0.5:
                r = int(231 + (241 - 231) * (ratio / 0.5))
                g = int(76 + (196 - 76) * (ratio / 0.5))
                b = int(60 + (15 - 60) * (ratio / 0.5))
            else:
                r = int(241 + (46 - 241) * ((ratio - 0.5) / 0.5))
                g = int(196 + (204 - 196) * ((ratio - 0.5) / 0.5))
                b = int(15 + (113 - 15) * ((ratio - 0.5) / 0.5))
            return f"rgb({r},{g},{b})"

        bar_colors = [get_gradient_color(v, min_val, max_val) for v in top_20["ממוצע גרם לקופסא"]]

        with col:
            st.markdown(f"#### {box_type}")
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=top_20["ממוצע גרם לקופסא"],
                y=top_20["תרבית"],
                orientation="h",
                marker_color=bar_colors,
                text=top_20["ממוצע גרם לקופסא"].round(1),
                textposition="outside"
            ))
            fig.update_layout(
                title="תרביות עם ממוצע משקל גבוה",
                xaxis_title="גרם לקופסא",
                yaxis_title="תרבית",
                height=500,
                margin=dict(t=60, b=40, l=100),
                bargap=0.4,
                yaxis=dict(
                    categoryorder="array",
                    categoryarray=top_20.sort_values("ממוצע גרם לקופסא", ascending=True)["תרבית"].tolist()
                )
            )
            st.plotly_chart(fig, use_container_width=True, key=f"top-cultures-{box_type}")

    # --- ממוצע משקל חודשי לקופסה (עמודות) לפי תאריך קטיף אחרון ---
    st.subheader("ממוצע משקל חודשי לקופסה")

    box_data = []
    for culture in valid_data:
        if culture.get("שלב") != "קטיף אחרון":  # רק אחרי סיום קטיף
            continue
        box_type = culture.get("סוג קופסא", "לא צוין")
        if box_type not in ["קופסא שחורה עגולה", "קופסא מלבנית 4.5 ליטר"]:
            continue
        total_boxes = int(culture.get("מספר קופסאות", 0))
        total_weight_g = (
                float(culture.get("משקל קטיף ראשוני (גרם)", 0)) +
                float(culture.get("משקל קטיף אחרון (גרם)", 0))
        )
        if total_boxes > 0:
            try:
                date_obj = datetime.strptime(culture["תאריך קטיף אחרון"], "%d/%m/%Y")
                avg_per_box = total_weight_g / total_boxes
                box_data.append({
                    "חודש": date_obj.strftime("%Y-%m"),
                    "סוג קופסא": box_type,
                    "ממוצע גרם לקופסא": avg_per_box
                })
            except:
                continue

    if box_data:
        df_box = pd.DataFrame(box_data)

        # ממירים תאריכים כדי לסדר לפי זמן
        df_box["תאריך"] = pd.to_datetime(df_box["חודש"], format="%Y-%m")
        # מילון שמות חודשים בעברית
        months_map_he = {
            1: "ינואר", 2: "פברואר", 3: "מרץ", 4: "אפריל", 5: "מאי", 6: "יוני",
            7: "יולי", 8: "אוגוסט", 9: "ספטמבר", 10: "אוקטובר", 11: "נובמבר", 12: "דצמבר"
        }

        # מייצרים תווית עברית - חודש + שנה
        df_box["חודש"] = df_box["תאריך"].apply(lambda d: f"{months_map_he[d.month]} {d.year}")

        # ממיינים לפי התאריך כך שהחודש האחרון יופיע מימין
        df_box = df_box.sort_values("תאריך")
        months_sorted = df_box.sort_values("תאריך")["חודש"].unique()

        # סיכום לפי חודש וסוג קופסא
        summary = df_box.groupby(["חודש", "סוג קופסא", "תאריך"], as_index=False)["ממוצע גרם לקופסא"].mean()
        # שני גרפים זה לצד זה
        col1, col2 = st.columns(2)
        for col, (box_type, color) in zip([col1, col2],
                                          [("קופסא שחורה עגולה", "#1F77B4"), ("קופסא מלבנית 4.5 ליטר", "#E67E22")]):
            box_df = summary[summary["סוג קופסא"] == box_type]
            box_df = box_df.sort_values("תאריך")
            if box_df.empty:
                with col:
                    st.info(f"אין נתונים עבור {box_type}")
                continue

            with col:
                st.markdown(f"#### {box_type}")
                fig = go.Figure()
                fig.add_trace(go.Bar(
                    x=box_df["חודש"],
                    y=box_df["ממוצע גרם לקופסא"],
                    marker_color=color,
                    text=box_df["ממוצע גרם לקופסא"].round(1),
                    textposition="inside",  # כדי שהטקסט לא יצא החוצה
                    insidetextanchor="start"
                ))

                fig.update_xaxes(categoryorder="array", categoryarray=months_sorted)

                fig.update_layout(
                    xaxis_title="חודש",
                    yaxis_title="גרם לקופסא",
                    height=400,
                    bargap=0.3,
                    margin=dict(t=60, b=40),
                    uniformtext_minsize=10,
                    uniformtext_mode="hide"
                )
                st.plotly_chart(fig, use_container_width=True, key=f"box-type-{box_type}")


                # חיווי על הממוצע של החודש האחרון (עם st.metric)
                if len(box_df) >= 1:
                    # דואגים שהחודשים יהיו ממוקמים בסדר כרונולוגי לפני החיווי
                    box_df = box_df.sort_values("תאריך")
                    current = box_df.iloc[-1]["ממוצע גרם לקופסא"]
                    if len(box_df) >= 2:
                        previous = box_df.iloc[-2]["ממוצע גרם לקופסא"]

                        change_pct = ((current - previous) / previous) * 100 if previous != 0 else 0
                        st.metric(
                            label="ממוצע החודש האחרון",
                            value=f"{current:.1f}",
                            delta=f"{change_pct:.1f}%"
                        )
                    else:
                        st.metric(
                            label="ממוצע החודש האחרון",
                            value=f"{current:.1f}"
                        )

    else:
        st.info("אין נתונים להצגה עבור ממוצע משקל לקופסא.")
    st.markdown("""
    <div style="
        text-align: center;
        color: #B0B0B0;
        font-size: 10px;
        margin-top: 100px;
    ">
        © Sivan the Queen Of Cordyceps
    </div>
    """, unsafe_allow_html=True)



def simple_login():
    if 'authentication_status' not in st.session_state:
        st.session_state.authentication_status = None

    if st.session_state.authentication_status is None:
        st.title("🍄 התחברות למערכת ניהול קורדיספס")

        with st.form("login_form"):
            username = st.text_input("שם משתמש")
            password = st.text_input("סיסמא", type="password")
            submit_button = st.form_submit_button("התחבר")

            if submit_button:
                # רשימת משתמשים מורשים
                valid_users = {
                    "sivan": "mycospring",
                    "ido": "mycospring",
                    "rea": "mycospring",
                    "pavel": "mycospring",
                    "niv": "mycospring",
                    "tania": "mycospring",
                    "asia": "mycospring",
                    "ron": "mycospring",
                    "matan": "mycospring",
                    "eyal": "mycospring"
                }

                if username in valid_users and password == valid_users[username]:
                    st.session_state.authentication_status = True
                    st.session_state.username = username
                    st.success(f"ברוך הבא {username}!")
                    st.rerun()
                else:
                    st.error("שם משתמש או סיסמא שגויים")
        return False

    else:
        # כפתור יציאה
        if st.sidebar.button("התנתק"):
            st.session_state.authentication_status = None
            st.session_state.username = None
            st.rerun()

        st.sidebar.write(f"משתמש מחובר: {st.session_state.get('username', 'לא ידוע')}")
        return True



# בדיקת התחברות
if not simple_login():
    st.stop()

def get_next_id(data):
    return max([c['id'] for c in data], default=0) + 1
def show_backups_page():
    st.header("ניהול גיבויים יומיים")
    if not os.path.exists(BACKUP_DIR):
        st.write("עדיין לא נוצרו גיבויים.")
        return

    backups = sorted(os.listdir(BACKUP_DIR))
    if not backups:
        st.write("אין גיבויים זמינים.")
        return

    for bfile in backups:
        bpath = os.path.join(BACKUP_DIR, bfile)
        with open(bpath, "rb") as f:
            st.download_button(
                label=f"הורד {bfile}",
                data=f,
                file_name=bfile,
                mime="application/json"
            )

    # מחיקת גיבויים ישנים (אופציונלי)
    if st.button("מחק גיבויים ישנים (מעל 30 יום)"):
        cutoff = datetime.datetime.now() - datetime.timedelta(days=30)
        for bfile in backups:
            date_str = bfile.replace("cordyceps_", "").replace(".json", "")
            try:
                file_date = datetime.datetime.fromisoformat(date_str)
                if file_date < cutoff:
                    os.remove(os.path.join(BACKUP_DIR, bfile))
            except ValueError:
                pass
        st.success("גיבויים ישנים נמחקו.")


data = load_data()

# --- עיצוב כללי ---
st.set_page_config(page_title="ניהול גידול קורדיספס", layout="wide")
st.markdown("""
    <style>
    .main > div {
        direction: rtl;
        text-align: right;
        font-family: NotoSansHebrew, sans-serif;
    }
    </style>
""", unsafe_allow_html=True)

st.markdown("<h1 style='text-align:center;'>🍄 נתוני גידול קורדיספס</h1>", unsafe_allow_html=True)

stages = [
    "צלחות פטרי",
    "תרבית נוזלית",
    "אינקובציה",
    "מדבקות",
    "אנדרלייט",
    "מיון",
    "קטיף ראשוני",
    "קטיף אחרון"
]

tabs = st.tabs(["דשבורד", *stages])
with tabs[0]:
    create_dashboard(data)

# --- טאב 1: צלחות פטרי ---
with tabs[1]:
    st.header("🧫 צלחות פטרי")
    plates = [c for c in data if c.get("שלב") == "צלחות פטרי"]
    st.subheader("➕ הוספת צלחת חדשה")
    with st.form("add_plate", clear_on_submit=True):
        strain = st.text_input("שם התרבית")
        plate_date = st.date_input("תאריך צלחת", value=date.today())
        submitted = st.form_submit_button("הוסף")
        if submitted:
            new_entry = {
                "id": get_next_id(data),
                "שלב": "צלחות פטרי",
                "תרבית": strain,
                "תאריך צלחת": plate_date.strftime("%d/%m/%Y")
            }
            add_record(new_entry)
            data = load_data()
            st.success("הצלחת נוספה בהצלחה!")
            st.rerun()
    if plates:
        st.subheader("צלחות קיימות")
        df_plates = pd.DataFrame(plates)
        df_plates = df_plates.replace("", pd.NA)
        df_plates = df_plates.dropna(axis=1, how="all")

        st.dataframe(df_plates)

# --- טאב 2: תרבית נוזלית ---
with tabs[2]:
    st.header("🧪 תרבית נוזלית")
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
                    "מספר בקבוקים": bottle_count
                })
                next_id = get_next_id(data)  # חישוב פעם אחת לפני הלולאה

                for j in range(1, transfers + 1):
                    daughter = {
                        "id": next_id,
                        "שלב": "צלחות פטרי",
                        "תרבית": f"{plate['תרבית']}-{j}",
                        "תאריך צלחת": date.today().strftime("%d/%m/%Y"),
                    }
                    add_record(daughter)
                    data.append(daughter)   # חשוב לעדכן את הרשימה המקומית
                    next_id += 1            # מגדילים ידנית ל-ID הבא

                data = load_data()

                st.success(f"נוספו {transfers} צלחות בנות!")
                st.rerun()
    else:
        st.info("אין צלחות זמינות ליצירת בקבוקים.")

# --- טאב 3: אינקובציה ---
with tabs[3]:
    st.header("📦 אינקובציה")

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
        all_data = load_data()
        fresh_bottles = [c for c in all_data if c.get("שלב") == "בקבוקי תרבית נוזלית" and c.get("מספר בקבוקים", 0) > 0]
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
                        "id": get_next_id(data),
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

                    data = load_data()

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

# --- טאב מדבקות ---
with tabs[4]:
    st.header("🖨️ הדפסת מדבקות")

    # רשימת כל התרביות עם אינקובציה
    cultures_for_labels = [c for c in data if c.get("שלב") == "אינקובציה"]

    if not cultures_for_labels:
        st.info("אין תרביות בשלב אינקובציה ליצירת מדבקות.")
    else:
        # מאפשר לבחור כמה ID-ים
        options = {f"#{c['id']} {c['תרבית']} ({c.get('תאריך אינקובציה', '-')})": c["id"] for c in cultures_for_labels}
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


# --- טאב אנדרלייט ---
with tabs[5]:
    st.header("🔄 אנדרלייט")
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
                data = load_data()
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


# --- טאב מיון ---
with tabs[6]:
    st.header("🔄 מיון")
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
                data = load_data()

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

# --- טאב קטיף ראשוני ---
with tabs[7]:
    st.header("🔄 קטיף ראשוני")
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
                data = load_data()

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

# --- טאב קטיף אחרון ---
with tabs[8]:
    st.header("🔄 קטיף אחרון")
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
                data = load_data()

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

