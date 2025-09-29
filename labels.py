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
    רושם את NotoSansHebrew ל-ReportLab פעם אחת לכל תהליך.
    לקרוא לפונקציה הזו בתחילת כל יצירת PDF.
    """
    global _FONTS_READY
    if _FONTS_READY:
        return

    # דיוק מיקום הקובץ: תקייה מקומית בשם Noto_Sans_Hebrew לצד labels.py
    base_dir = os.path.dirname(__file__)
    font_path = os.path.join(base_dir, "Noto_Sans_Hebrew", "NotoSansHebrew-Regular.ttf")

    if not os.path.exists(font_path):
        # אם תרצי – אפשר להחליף ל-st.warning במקום Exception
        raise FileNotFoundError(f"Font not found at: {font_path}")

    pdfmetrics.registerFont(TTFont("NotoSansHebrew", font_path))
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

    def _fit_text_size(text, font_name, max_width_pt, start_size=10, min_size=6):
        size = start_size
        while size >= min_size:
            if stringWidth(text, font_name, size) <= max_width_pt:
                return size
            size -= 1
        return min_size  # ניפול למינימום

    def _truncate_middle(text, max_width_pt, font_name, font_size):
        # אם גם במינימום לא נכנס – נקצר במרכז עם …
        if stringWidth(text, font_name, font_size) <= max_width_pt:
            return text
        left, right = 0, 0
        ell = "…"
        while left + right < len(text):
            candidate = text[: len(text) // 2 - left] + ell + text[len(text) // 2 + right:]
            if stringWidth(candidate, font_name, font_size) <= max_width_pt or len(candidate) <= 3:
                return candidate
            # נגדל את החיתוך משני הצדדים
            if (left + right) % 2 == 0:
                left += 1
            else:
                right += 1
        return ell

    # ---------- הגדרות עמוד (מדבקה גדולה 4x4 אינץ') ----------
    page_w, page_h = (4 * 25.4 * mm, 4 * 25.4 * mm)
    c = canvas.Canvas(filename, pagesize=(page_w, page_h))

    # --- כותרת לכל דף מדבקות קטנות ---
    def start_small_labels_page(title_he):
        c.setFont("NotoSansHebrew", 12)
        c.drawCentredString(page_w / 2, page_h - 6 * mm, reverse_hebrew_text(title_he))

    def new_small_labels_page(title_he):
        c.showPage()
        start_small_labels_page(title_he)

    # ---------- עזרי טקסט/מספר ----------
    def as_int(x, default=0):
        try:
            s = str(x or "").strip().replace(",", "")
            return int(float(s))
        except Exception:
            return default

    def increment_transfer_code(code):
        s = (code or "").strip()
        m = re.match(r'^([A-Za-z]?)(\d+)$', s)
        if not m:
            return "P2"
        prefix, num = m.group(1), int(m.group(2))
        if not prefix:
            prefix = "P"
        return f"{prefix}{num+1}"

    def build_inoculation_url(species_en: str, culture_id: str):
        # <<< החליפי ל-URL האמיתי של האפליקציה שלך אם צריך >>>
        base = "https://mycospring.com/app/inoculation"
        return f"{base}/{species_en.lower()}?id={culture_id}"

    # ---------- ציור מדבקות קטנות (2 שורות ממורכז) ----------
    small_label_w = 28 * mm
    small_label_h = 12 * mm
    small_gap = 2 * mm
    cols = 3  # 3 עמודות למדבקות קטנות
    left_margin = (page_w - (cols * small_label_w + (cols - 1) * small_gap)) / 2.0
    top_margin = page_h - 8 * mm

    def draw_small_2line_label(cx, cy, line1, line2, base_size=10, pad_mm=2):
        font = "NotoSansHebrew"
        max_w = (small_label_w - pad_mm * mm * 2)  # רוחב פנימי זמין

        # קבעי גודל פונט שמתאים לשתי השורות
        s1 = _fit_text_size(line1, font, max_w, start_size=base_size, min_size=6)
        s2 = _fit_text_size(line2, font, max_w, start_size=base_size, min_size=6)
        size = min(s1, s2)

        # ואם גם במינימום לא נכנס – נקצר עם …
        l1 = _truncate_middle(line1, max_w, font, size)
        l2 = _truncate_middle(line2, max_w, font, size)

        c.setFont(font, size)
        c.drawCentredString(cx, cy + 3, l1)
        c.drawCentredString(cx, cy - 9, l2)

    def grid_positions_for_small(n_items, title_he=None):
        # ציור כותרת לדף הראשון (רק אם ביקשו)
        if title_he:
            start_small_labels_page(title_he)

        per_row = cols
        rows_can_fit = int((top_margin - 10 * mm) // (small_label_h + small_gap))
        per_page = per_row * rows_can_fit if rows_can_fit > 0 else 1

        count = 0
        while count < n_items:
            items_this_page = min(per_page, n_items - count)
            idx_in_page = 0
            while idx_in_page < items_this_page:
                row = idx_in_page // per_row
                col = idx_in_page % per_row
                x = left_margin + col * (small_label_w + small_gap) + small_label_w / 2.0
                y = top_margin - row * (small_label_h + small_gap) - small_label_h / 2.0
                yield (x, y)
                idx_in_page += 1
            count += items_this_page
            if count < n_items:
                if title_he:
                    new_small_labels_page(title_he)
                else:
                    c.showPage()

    # ---------- ציור גריד 3x3 לבקבוקים ----------
    cell_cols = 3
    cell_rows = 3
    cell_gap = 2 * mm
    # מסגרת פנימית עם שוליים קטנים
    inner_margin = 6 * mm
    grid_w = page_w - inner_margin * 2
    grid_h = page_h - inner_margin * 2
    cell_w = (grid_w - cell_gap * (cell_cols - 1)) / cell_cols
    cell_h = (grid_h - cell_gap * (cell_rows - 1)) / cell_rows

    def draw_qr_at_center(x, y, size_mm, url):
        # x,y = מרכז הריבוע; נגדיל/נמקם QR
        qr_widget = qr.QrCodeWidget(url)
        b = qr_widget.getBounds()
        w = b[2] - b[0]
        h = b[3] - b[1]
        size_pt = size_mm * mm
        scale = min(size_pt / w, size_pt / h)
        d = Drawing(size_pt, size_pt, transform=[scale,0,0,scale,0,0])
        d.add(qr_widget)
        renderPDF.draw(d, c, x - size_pt/2.0, y - size_pt/2.0)

    def draw_bottle_cell(ix, iy, id_text, name_he, date_text, url):
        # ix, iy = אינדקסים בגריד (0..2)
        x0 = inner_margin + ix * (cell_w + cell_gap)
        y0 = page_h - inner_margin - (iy + 1) * cell_h - iy * cell_gap

        # מסגרת דקה לעזרה בחיתוך (אפשר לבטל)
        c.setStrokeColor(colors.black)
        c.setLineWidth(0.5)
        c.rect(x0, y0, cell_w, cell_h, stroke=1, fill=0)

        # טקסט עליון: ID + שם תרבית (בלי כותרת)
        c.setFont("NotoSansHebrew", 8)
        # טקסט עליון: ID + שם תרבית (בלי כותרת שדה נוספת)
        top_y = y0 + cell_h - 10
        top_text = f"ID: {id_text}   {reverse_hebrew_text(name_he)}"

        font = "NotoSansHebrew"
        pad = 2 * mm
        max_w = cell_w - pad * 2
        size = _fit_text_size(top_text, font, max_w, start_size=8, min_size=6)
        top_text = _truncate_middle(top_text, max_w, font, size)

        c.setFont(font, size)
        c.drawCentredString(x0 + cell_w / 2.0, top_y, top_text)

        # QR במרכז
        qr_center_x = x0 + cell_w/2.0
        qr_center_y = y0 + cell_h/2.0
        draw_qr_at_center(qr_center_x, qr_center_y, size_mm=16, url=url)

        # טקסט תחתון: תאריך (בלי כותרת)
        c.setFont("NotoSansHebrew", 8)
        bottom_y = y0 + 6
        c.drawCentredString(x0 + cell_w/2.0, bottom_y, str(date_text))

    # ============ יצירה ============
    for culture in selected_cultures:
        species_en = "cordyceps"  # פה זה ספציפית קורדיספס
        mother_id = str(culture.get("id", "-"))
        mother_name = culture.get("תרבית", "-")
        bottle_date = culture.get("תאריך בקבוקים", "-")
        mother_transfer = str(culture.get("מספר העברה", "") or "").strip()
        daughters_transfer = increment_transfer_code(mother_transfer)

        daughters_count = as_int(culture.get("מספר העברות לצלחת פטרי", 1), default=1)
        if daughters_count < 1:
            daughters_count = 1

        total_bottles = as_int(culture.get("מספר בקבוקים", 1), default=1)
        if total_bottles < 1:
            total_bottles = 1

        # בנות
        positions = list(grid_positions_for_small(daughters_count, title_he="צלחות בנות"))
        for i, (cx, cy) in enumerate(positions, start=1):
            daughter_name = f"{mother_name}-{i}"
            line1 = f"ID: {mother_id}  {reverse_hebrew_text(daughter_name)}"
            line2 = f"{bottle_date}  {daughters_transfer}"
            draw_small_2line_label(cx, cy, line1=line1, line2=line2)
        if daughters_count > 0:
            c.showPage()

        # ריוטיפים (תמיד 2)
        positions = list(grid_positions_for_small(2, title_he="ריוטיפים"))
        for (cx, cy) in positions:
            line1 = f"ID: {mother_id}  {reverse_hebrew_text(mother_name)}"
            line2 = f"{bottle_date}  {mother_transfer or '-'}"
            draw_small_2line_label(cx, cy, line1=line1, line2=line2)
        c.showPage()

        # ---------- (C) בקבוקים – גריד 3x3 בכל עמוד ----------
        pages_needed = math.ceil(total_bottles / 9)
        url_tmpl = build_inoculation_url(species_en, mother_id)

        counter = 0
        for _ in range(pages_needed):
            # ציור 9 תאים או עד שנגמרים הבקבוקים
            for iy in range(cell_rows):
                for ix in range(cell_cols):
                    if counter >= total_bottles:
                        # למלא מסגרת ריקה לעקביות חיתוך
                        x0 = inner_margin + ix * (cell_w + cell_gap)
                        y0 = page_h - inner_margin - (iy + 1) * cell_h - iy * cell_gap
                        c.setStrokeColor(colors.black)
                        c.setLineWidth(0.5)
                        c.rect(x0, y0, cell_w, cell_h, stroke=1, fill=0)
                        continue
                    draw_bottle_cell(
                        ix, iy,
                        id_text=mother_id,
                        name_he=mother_name,
                        date_text=bottle_date,
                        url=url_tmpl,
                    )
                    counter += 1
            c.showPage()

    c.save()
