import os
from datetime import datetime, timedelta
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import math, re
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.graphics.shapes import Drawing
from reportlab.graphics import renderPDF
from reportlab.graphics.barcode import qr
from reportlab.pdfbase.pdfmetrics import stringWidth

_FONTS_READY = False

def ensure_fonts():
    """
    רושם את NotoSansHebrew (Regular + Bold) ל-ReportLab פעם אחת לכל תהליך.
    """
    global _FONTS_READY
    if _FONTS_READY:
        return

    base_dir = os.path.dirname(__file__)
    fonts_dir = os.path.join(base_dir, "Noto_Sans_Hebrew")

    reg_path  = os.path.join(fonts_dir, "NotoSansHebrew-Regular.ttf")
    bold_path = os.path.join(fonts_dir, "NotoSansHebrew-Bold.ttf")  # ← חדש

    if not os.path.exists(reg_path):
        raise FileNotFoundError(f"Font not found at: {reg_path}")
    if not os.path.exists(bold_path):
        raise FileNotFoundError(f"Font not found at: {bold_path}")  # ← חדש

    pdfmetrics.registerFont(TTFont("NotoSansHebrew", reg_path))
    pdfmetrics.registerFont(TTFont("NotoSansHebrew-Bold", bold_path))  # ← חדש

    _FONTS_READY = True


def create_labels_pdf(selected_cultures, filename):
    ensure_fonts()
    """יוצר PDF עם מדבקה נפרדת לכל תרבית שנבחרה (עמוד 4x4 אינץ' לכל אחת)."""
    page_size = (4 * 25.4 * mm, 4 * 25.4 * mm)
    c = canvas.Canvas(filename, pagesize=page_size)

    for culture in selected_cultures:
        # כל מדבקה היא עמוד נפרד
        create_single_label_page(c, culture, page_size)
        c.showPage()  # מסיים עמוד לפני הבא

    c.save()
def create_single_label_page(c, culture, page_size):
    ensure_fonts()
    # מסגרת
    c.setStrokeColor(colors.black)
    c.setLineWidth(2)
    c.rect(0, 0, page_size[0], page_size[1])

    # זיהוי מדבקת בלוקים
    stage = str(culture.get("שלב", "")).strip()
    is_blocks = (
        stage == "אינקובציה בלוקים"
        or ("תאריך בלוקים" in culture)
        or ("מספר בלוקים" in culture)
    )

    if is_blocks:
        # ----- תבנית בלוקים (מה שביקשת) -----
        inoc_date = culture.get("תאריך אינקובציה") or culture.get("תאריך בלוקים") or ""
        rows = [
            ("ID", str(culture.get("id", "")), False, False),
            ("תרבית", culture.get("תרבית", ""), True, False),
            ("תאריך אינקולציה", inoc_date, True, False),
            ("כמות בלוקים", str(culture.get("מספר בלוקים", "")), True, False),
            ("תאריך הפרחה", "__________", True, False),
            ("תאריך פלאש ראשון", "__________", True, False),
        ]
    else:
        # ----- התבנית הקיימת (לשימושים אחרים כפי שהיה) -----
        incubation_date = culture.get("תאריך אינקובציה", "")
        try:
            base = datetime.strptime(incubation_date, "%d/%m/%Y")
            underlight_date = (base + timedelta(days=8)).strftime("%d/%m/%Y")
        except Exception:
            underlight_date = ""
        rows = [
            ("ID", str(culture.get("id", "")), False, False),
            ("תאריך אינקובציה", incubation_date, True, False),
            ("תאריך אנדרלייט צפוי", underlight_date, True, False),
            ("תרבית", culture.get("תרבית", ""), True, True),
            ("מצע", culture.get("מצע", ""), True, True),
            ("משך קיטור בשעות", culture.get("קיטור xx(yy)", ""), True, False),
            ("בקבוקים", str(culture.get("מספר בקבוקים", "")), True, False),
            ("קופסאות", str(culture.get("מספר קופסאות", "")), True, False),
        ]

    # כותרת ID גדולה
    c.setFont("NotoSansHebrew", 24)
    c.drawCentredString(page_size[0]/2, page_size[1]-40, f"ID: {rows[0][1]}")

    # גוף המדבקה
    c.setFont("NotoSansHebrew", 18)
    y_text = page_size[1] - 90
    for title, value, flip_title, flip_value in rows[1:]:
        title_fixed = reverse_hebrew_text(str(title), flip_title)
        value_fixed = reverse_hebrew_text(str(value), flip_value)
        c.drawCentredString(page_size[0]/2, y_text, f"{value_fixed}: {title_fixed}")
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
def increment_transfer_code(code):
    """
    'P1' -> 'P2', 'p3' -> 'p4', '1' -> '2', ''/None -> 'P2'
    אם אין אות – נוסיף 'P' כברירת מחדל.
    """
    s = (code or "").strip()
    m = re.match(r'^([A-Za-z]?)(\d+)$', s)
    if not m:
        return "P2"
    prefix, num = m.group(1), int(m.group(2))
    if not prefix:
        prefix = "P"
    return f"{prefix}{num+1}"
def extract_int(s, default=0):
    """מחזיר מספר שלם מתוך ערך טקסטואלי/מספרי (למשל '15', 'P12', 7)."""
    if s is None or s == "":
        return default
    if isinstance(s, (int, float)):
        try:
            return int(s)
        except:
            return default
    m = re.search(r'(\d+)', str(s))
    return int(m.group(1)) if m else default

def create_liquid_labels_pdf(selected_cultures, filename):
    ensure_fonts()

    # --- קבועים / מידות ---
    page_w, page_h = (4 * 25.4 * mm, 4 * 25.4 * mm)
    c = canvas.Canvas(filename, pagesize=(page_w, page_h))

    # ----- מדבקות קטנות: חישוב דינמי שימלא את רוחב הדף -----
    cols = 2  # שני טורים
    gap = 2 * mm  # רווח בין מדבקות
    side_margin = 3 * mm  # שוליים צדדיים קטנים וקבועים
    small_h = 12 * mm  # גובה מדבקה (אין שינוי)
    small_w = (page_w - 2 * side_margin - (cols - 1) * gap) / cols  # ממלא כמעט את כל הרוחב
    left_margin = side_margin
    top_margin = page_h - 8 * mm

    cell_cols, cell_rows, cell_gap = 3, 3, 0*mm
    inner_margin = 6*mm
    grid_w = page_w - inner_margin*2
    grid_h = page_h - inner_margin*2
    cell_w = (grid_w - cell_gap*(cell_cols-1)) / cell_cols
    cell_h = (grid_h - cell_gap*(cell_rows-1)) / cell_rows

    # --- עזרי טקסט קטנים ---
    def _fit(text, font, max_w, start=10, min_=6):
        s = start
        while s >= min_:
            if stringWidth(text, font, s) <= max_w: return s
            s -= 1
        return min_

    def _ellips(text, max_w, font, size):
        if stringWidth(text, font, size) <= max_w: return text
        mid = len(text)//2
        for k in range(len(text)):
            cand = text[:max(0,mid-k)] + "…" + text[min(len(text),mid+k):]
            if stringWidth(cand, font, size) <= max_w or len(cand) <= 3:
                return cand
        return "…"

    def draw_small_label(cx, cy, line1, line2):
        font = "NotoSansHebrew-Bold"
        max_w = small_w - 4*mm
        s = min(_fit(line1, font, max_w), _fit(line2, font, max_w))
        c.setFont(font, s)
        c.drawCentredString(cx, cy+3,  _ellips(line1, max_w, font, s))
        c.drawCentredString(cx, cy-9, _ellips(line2, max_w, font, s))

    def rows_can_fit():
        return max(1, int((top_margin - 10*mm) // (small_h + gap)))

    def start_page(title):
        c.setFont("NotoSansHebrew-Bold", 12)
        c.drawCentredString(page_w/2, page_h-6*mm, reverse_hebrew_text(title))

    def draw_bottle_grid_lines():
        """קווי גריד דקים על פני כל ה-3×3 (בלי רווחים בין מדבקות)."""
        c.saveState()
        c.setStrokeColor(colors.black)
        c.setLineWidth(0.1)
        c.setDash(1, 2)

        # קואורדינטות שוליים
        x_left = inner_margin
        x_right = inner_margin + grid_w
        y_top = page_h - inner_margin
        y_bot = page_h - inner_margin - grid_h

        # אנכיים: אחרי עמודה 1 ואחרי עמודה 2
        for i in (1, 2):
            x = inner_margin + i * cell_w + (i - 1) * cell_gap
            c.line(x, y_top, x, y_bot)

        # אופקיים: אחרי שורה 1 ואחרי שורה 2
        for j in (1, 2):
            y = y_top - j * cell_h - (j - 1) * cell_gap
            c.line(x_left, y, x_right, y)

        c.restoreState()

    def draw_block(labels, add_title=None, row_index=0, title_blank_row=False):
        """
        labels: [(line1,line2), ...]
        אם אין מקום ל(כותרת+שורות) – פותח עמוד חדש.
        מחזיר row_index מעודכן.
        """
        need_rows = (len(labels)+cols-1)//cols
        avail = rows_can_fit() - row_index
        title_cost = 1 if (add_title and title_blank_row) else 0
        need = need_rows + title_cost
        if avail < need:
            c.showPage()
            if add_title: start_page(add_title)
            row_index = 0
        elif add_title:
            # מציבים את הכותרת ממש מעל שורת המדבקות הראשונה,
            # בלי "לבזבז" שורת גריד שלמה
            c.setFont("NotoSansHebrew-Bold", 12)
            y_title = top_margin - row_index * (small_h + gap) - 12 * mm
            c.drawCentredString(page_w / 2, y_title, reverse_hebrew_text(add_title))
            # לא מעלים row_index — כדי שהמדבקות יתחילו באותה שורה
            if title_blank_row:
                row_index += 1
        # ציור המדבקות
        i = 0
        while i < len(labels):
            if row_index >= rows_can_fit():
                c.showPage()
                if add_title: start_page(add_title)  # כותרת בעמוד חדש
                row_index = 0
            for col in range(cols):
                if i >= len(labels): break
                x = left_margin + col*(small_w+gap) + small_w/2.0
                y = top_margin - row_index*(small_h+gap) - small_h/2.0
                l1, l2 = labels[i]
                draw_small_label(x, y, l1, l2)
                i += 1
            row_index += 1
        return row_index

    def draw_qr_center(x, y, size_mm, url):
        w = qr.QrCodeWidget(url)
        b = w.getBounds(); W, H = (b[2]-b[0]), (b[3]-b[1])
        S = min(size_mm*mm/W, size_mm*mm/H)
        d = Drawing(size_mm*mm, size_mm*mm, transform=[S,0,0,S,0,0]); d.add(w)
        renderPDF.draw(d, c, x-size_mm*mm/2, y-size_mm*mm/2)

    def draw_bottle_cell(ix, iy, id_text, name_he, date_text, url):
        x0 = inner_margin + ix * (cell_w + cell_gap)
        y0 = page_h - inner_margin - (iy + 1) * cell_h - iy * cell_gap

        # לא מציירים מסגרת (יש קווי גריד חיצוניים)
        font = "NotoSansHebrew-Bold"
        pad = 2 * mm
        max_w = cell_w - pad * 2

        # --- שורה 1: ID ---
        line_id = f"ID: {id_text}"
        s_id = _fit(line_id, font, max_w, start=8, min_=6)
        c.setFont(font, s_id)
        c.drawCentredString(x0 + cell_w / 2, y0 + cell_h - 8, line_id)

        # --- שורה 2: שם התרבית ---
        line_name = reverse_hebrew_text(name_he)
        s_name = _fit(line_name, font, max_w, start=8, min_=6)
        c.setFont(font, s_name)
        c.drawCentredString(x0 + cell_w / 2, y0 + cell_h - 18, line_name)

        # --- QR במרכז ---
        draw_qr_center(x0 + cell_w / 2, y0-3 + cell_h / 2, 20, url)

        # --- תאריך בתחתית ---
        c.setFont(font, 8)
        c.drawCentredString(x0 + cell_w / 2, y0 + 6, str(date_text))

    # --- יצירה ---
    for culture in selected_cultures:
        species_en = "cordyceps"
        mother_id   = str(culture.get("id","-"))
        mother_name = culture.get("תרבית","-")
        bottle_date = culture.get("תאריך בקבוקים","-")
        mother_transfer = str(culture.get("מספר העברה","") or "").strip()
        daughters_transfer = increment_transfer_code(mother_transfer)
        daughters_count = int((str(culture.get("מספר העברות לצלחת פטרי",1)) or "1").split()[0])
        daughters_count = max(1, daughters_count)
        total_bottles = max(1, int((str(culture.get("מספר בקבוקים",1)) or "1").split()[0]))

        # --- צלחות בנות ---
        start_page("צלחות בנות")
        d_labels = []
        for i in range(1, daughters_count+1):
            name = f"{mother_name}-{i}"
            l1 = f"ID: {mother_id}  {reverse_hebrew_text(name)}"
            l2 = f"{bottle_date}  {daughters_transfer}"
            d_labels.append((l1, l2))
        row_idx = draw_block(d_labels, add_title=None, row_index=0)

        # --- ריוטיפים (2) – באותו עמוד אם יש מקום, אחרת חדש ---
        cryo_labels = []
        for _ in range(2):
            l1 = f"ID: {mother_id}  {reverse_hebrew_text(mother_name)}"
            l2 = f"{bottle_date}  {mother_transfer or '-'}"
            cryo_labels.append((l1, l2))
        row_idx = draw_block(cryo_labels, add_title="ריוטיפים", row_index=row_idx, title_blank_row=True)

        # --- מעבר עמוד לפני הבקבוקים ---
        c.showPage()

        # --- בקבוקים 3×3 עם QR (כמו שהיה) ---
        pages_needed = math.ceil(total_bottles / 9)
        url_tmpl = "https://mushroom-manage.streamlit.app/"
        counter = 0
        for _ in range(pages_needed):
            draw_bottle_grid_lines()
            for iy in range(cell_rows):
                for ix in range(cell_cols):
                    if counter >= total_bottles:
                        x0 = inner_margin + ix*(cell_w+cell_gap)
                        y0 = page_h - inner_margin - (iy+1)*cell_h - iy*cell_gap
                        continue
                    draw_bottle_cell(ix, iy, mother_id, mother_name, bottle_date, url_tmpl)
                    counter += 1
            c.showPage()

    c.save()
