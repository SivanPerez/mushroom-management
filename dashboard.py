import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from datetime import datetime

def create_dashboard(data):
    # --- חישוב תפוסה באנדרלייט (כולל שלבים שממשיכים לתפוס מקום) ---
    valid_data = [c for c in data if isinstance(c, dict)]

    # איסוף כל התרביות שתופסות מקום
    underlight_data = []
    for c in valid_data:
        stage = c.get("שלב")
        boxes = int(c.get("מספר קופסאות", 0) or 0)

        # תרביות באנדרלייט – כל הקופסאות
        if stage == "אנדרלייט":
            underlight_data.append({"חדר": c.get("מיקום אנדרלייט", "לא צוין"), "קופסאות": boxes})

        # תרביות במיון – פחות פגומות
        elif stage == "מיון":
            damaged = int(c.get("מספר קופסאות פגומות", 0) or 0)
            underlight_data.append({"חדר": c.get("מיקום אנדרלייט", "לא צוין"), "קופסאות": max(boxes - damaged, 0)})

        # תרביות בקטיף ראשוני – פחות פגומות ופחות אלו שנכנסלו לקטיף מוקדם
        elif stage == "קטיף ראשוני":
            damaged = int(c.get("מספר קופסאות פגומות", 0) or 0)
            early = int(c.get("מספר קופסאות לקטיף ראשוני", 0) or 0)
            underlight_data.append(
                {"חדר": c.get("מיקום אנדרלייט", "לא צוין"), "קופסאות": max(boxes - damaged - early, 0)})

    # חישוב סטטיסטיקות לחדרים
    room_caps = {"חדר 4": 6900, "חדר 5": 2700, "חדר 7": 2700}
    room_stats = {r: 0 for r in room_caps}

    for item in underlight_data:
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
    st.subheader("קטיף חודשי (בקילוגרמים)")

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

    st.subheader("תרביות מובילות לפי סוג קופסה")

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
