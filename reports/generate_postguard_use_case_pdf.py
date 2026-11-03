"""Generate the Thai PostGuard use-case PDF with vector diagrams."""

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "reports" / "PostGuard_Use_Case_Diagram_2026-11-02.pdf"
FONT = Path(r"C:\Windows\Fonts\tahoma.ttf")
FONT_BOLD = Path(r"C:\Windows\Fonts\tahomabd.ttf")

PAGE_W, PAGE_H = landscape(A4)
NAVY = colors.HexColor("#0F172A")
BLUE = colors.HexColor("#2457D6")
BLUE_SOFT = colors.HexColor("#EEF4FF")
GREEN = colors.HexColor("#047857")
GREEN_SOFT = colors.HexColor("#ECFDF3")
AMBER = colors.HexColor("#B45309")
AMBER_SOFT = colors.HexColor("#FFF7ED")
SLATE = colors.HexColor("#64748B")
BORDER = colors.HexColor("#CBD5E1")
SURFACE = colors.HexColor("#F8FAFC")


pdfmetrics.registerFont(TTFont("Tahoma", str(FONT)))
pdfmetrics.registerFont(TTFont("Tahoma-Bold", str(FONT_BOLD)))


def text(c, value, x, y, size=9, bold=False, color=NAVY, align="left"):
    c.setFillColor(color)
    c.setFont("Tahoma-Bold" if bold else "Tahoma", size)
    if align == "center":
        c.drawCentredString(x, y, value)
    elif align == "right":
        c.drawRightString(x, y, value)
    else:
        c.drawString(x, y, value)


def title(c, heading, subtitle, page_number):
    text(c, "PostGuard", 18 * mm, PAGE_H - 15 * mm, 10, True, BLUE)
    text(c, heading, PAGE_W / 2, PAGE_H - 16 * mm, 17, True, NAVY, "center")
    text(c, subtitle, PAGE_W / 2, PAGE_H - 23 * mm, 8.5, False, SLATE, "center")
    text(c, f"หน้า {page_number}", PAGE_W - 18 * mm, PAGE_H - 15 * mm, 8, False, SLATE, "right")
    c.setStrokeColor(BORDER)
    c.line(15 * mm, PAGE_H - 27 * mm, PAGE_W - 15 * mm, PAGE_H - 27 * mm)


def actor(c, x, y, label):
    c.setStrokeColor(NAVY)
    c.setLineWidth(1.3)
    c.circle(x, y + 21, 7, fill=0)
    c.line(x, y + 14, x, y - 8)
    c.line(x - 11, y + 5, x + 11, y + 5)
    c.line(x, y - 8, x - 9, y - 22)
    c.line(x, y - 8, x + 9, y - 22)
    text(c, label, x, y - 35, 8.5, True, NAVY, "center")


def use_case(c, x, y, w, h, label, fill=BLUE_SOFT, stroke=BLUE, font_size=7.7):
    c.setFillColor(fill)
    c.setStrokeColor(stroke)
    c.setLineWidth(1)
    c.roundRect(x - w / 2, y - h / 2, w, h, h / 2, fill=1, stroke=1)
    lines = label.split("\n")
    start = y + (len(lines) - 1) * 4 - 3
    for index, line in enumerate(lines):
        text(c, line, x, start - index * 9, font_size, False, NAVY, "center")


def external(c, x, y, w, h, label):
    c.setFillColor(SURFACE)
    c.setStrokeColor(SLATE)
    c.setLineWidth(1)
    c.roundRect(x - w / 2, y - h / 2, w, h, 6, fill=1, stroke=1)
    lines = label.split("\n")
    start = y + (len(lines) - 1) * 4 - 3
    for index, line in enumerate(lines):
        text(c, line, x, start - index * 9, 7.5, True, NAVY, "center")


def connector(c, x1, y1, x2, y2, dashed=False, label=None, color=SLATE):
    c.setStrokeColor(color)
    c.setLineWidth(0.8)
    c.setDash(4, 3) if dashed else c.setDash()
    c.line(x1, y1, x2, y2)
    c.setDash()
    if label:
        box_x = (x1 + x2) / 2
        box_y = (y1 + y2) / 2 + 3
        c.setFillColor(colors.white)
        width = pdfmetrics.stringWidth(label, "Tahoma", 6.8) + 6
        c.rect(box_x - width / 2, box_y - 3, width, 9, fill=1, stroke=0)
        text(c, label, box_x, box_y, 6.8, False, color, "center")


def group(c, x, y, w, h, label, color=BLUE):
    c.setFillColor(colors.white)
    c.setStrokeColor(BORDER)
    c.setLineWidth(0.8)
    c.roundRect(x, y, w, h, 8, fill=1, stroke=1)
    text(c, label, x + 9, y + h - 14, 8, True, color)


def footer(c):
    text(
        c,
        "PostGuard ใช้ RULA-adapted สำหรับกล้องด้านหน้า ไม่ใช่ Full RULA หรือการวินิจฉัยทางการแพทย์",
        PAGE_W / 2,
        8 * mm,
        7.5,
        False,
        SLATE,
        "center",
    )


def draw_overview(c):
    title(
        c,
        "Use Case Diagram — ภาพรวมระบบ",
        "ขอบเขต Account, Camera Setup, Monitoring, Alert และ Report",
        1,
    )

    boundary_x, boundary_y = 82, 45
    boundary_w, boundary_h = 650, 485
    c.setStrokeColor(NAVY)
    c.setLineWidth(1.2)
    c.roundRect(boundary_x, boundary_y, boundary_w, boundary_h, 10, fill=0, stroke=1)
    text(c, "PostGuard Desktop Application", boundary_x + 12, boundary_y + boundary_h - 17, 9, True)

    actor(c, 41, 300, "ผู้ใช้งาน")
    external(c, 785, 415, 82, 38, "กล้อง\nWebcam")
    external(c, 785, 290, 82, 38, "Backend /\nSupabase")
    external(c, 785, 165, 82, 38, "Resend\nEmail Service")

    group(c, 100, 335, 285, 165, "Account และ Privacy", BLUE)
    group(c, 405, 335, 305, 165, "Camera Setup", GREEN)
    group(c, 100, 80, 390, 235, "Monitoring Session", AMBER)
    group(c, 510, 80, 200, 235, "Dashboard และ Report", BLUE)

    account_cases = [
        (175, 455, "สมัคร / ยืนยัน OTP"),
        (310, 455, "Login / Reset Password"),
        (175, 405, "Profile / Settings"),
        (310, 405, "Privacy Consent"),
        (242, 355, "เปลี่ยนรหัส / ลบบัญชี"),
    ]
    for x, y, label in account_cases:
        use_case(c, x, y, 118, 30, label)

    camera_cases = [
        (485, 455, "ค้นหาและเลือกกล้อง"),
        (625, 455, "เตรียมและปรับกล้อง"),
        (485, 395, "ตรวจภาพหลังปรับเอียง"),
        (625, 395, "สร้าง Personal Baseline"),
        (555, 350, "เริ่ม Monitoring Session"),
    ]
    for x, y, label in camera_cases:
        use_case(c, x, y, 126, 30, label, GREEN_SOFT, GREEN)

    monitor_cases = [
        (185, 270, "ตรวจจับท่าทาง\nและการกะพริบตา"),
        (330, 270, "ประเมิน RULA-adapted\nและระยะหน้าจอ"),
        (185, 205, "ติดตามเวลาค้างท่า"),
        (330, 205, "รับ Popup และเสียง"),
        (185, 140, "Pause / Resume"),
        (330, 140, "หน้าต่างเล็กเมื่อ Minimize"),
        (257, 95, "Stop และบันทึก Session"),
    ]
    for x, y, label in monitor_cases:
        use_case(c, x, y, 130, 34, label, AMBER_SOFT, AMBER)

    report_cases = [
        (610, 270, "ดู Dashboard และ\nRisk Score Trend"),
        (610, 210, "ดู Session History"),
        (610, 150, "ดู Alert History"),
        (610, 95, "ดู Summary / Report"),
    ]
    for x, y, label in report_cases:
        use_case(c, x, y, 145, 34, label)

    # User associations to the four functional areas.
    connector(c, 56, 315, 100, 425)
    connector(c, 56, 300, 100, 245)
    connector(c, 56, 285, 100, 135)
    connector(c, 56, 270, 510, 200)

    # External system associations.
    connector(c, 710, 420, 744, 415)
    connector(c, 710, 235, 744, 290)
    connector(c, 385, 455, 744, 165)

    # Main include/extend relations.
    connector(c, 548, 350, 485, 395, True, "<<include>>")
    connector(c, 555, 335, 330, 287, True, "<<include>>")
    connector(c, 330, 252, 330, 222, True, "<<extend>>")
    connector(c, 330, 188, 330, 157, True, "<<extend>>")
    connector(c, 257, 123, 257, 112, True, "<<include>>")
    connector(c, 322, 95, 537, 95, True, "<<include>>")
    footer(c)
    c.showPage()


def draw_monitoring_detail(c):
    title(
        c,
        "Use Case Diagram — Monitoring และ Alert Lifecycle",
        "รายละเอียดขั้นตอนตั้งแต่เริ่ม Session จนถึงบันทึก Summary",
        2,
    )

    actor(c, 45, 300, "ผู้ใช้งาน")
    external(c, 792, 410, 74, 36, "กล้อง")
    external(c, 792, 285, 74, 36, "Backend")
    external(c, 792, 160, 74, 36, "Supabase")

    c.setStrokeColor(NAVY)
    c.roundRect(85, 52, 650, 470, 10, fill=0, stroke=1)
    text(c, "PostGuard Monitoring", 97, 504, 9, True)

    cases = {
        "start": (175, 445, "เริ่ม Session"),
        "consent": (320, 445, "ตรวจ Privacy Consent"),
        "camera": (465, 445, "เปิดกล้องและใช้\nCamera Adjustment"),
        "detect": (610, 445, "ตรวจ Pose, Face, Eye"),
        "baseline": (175, 360, "เปรียบเทียบ\nPersonal Baseline"),
        "temporal": (320, 360, "ติดตามเวลาต่อเนื่อง"),
        "risk": (465, 360, "คำนวณ Risk Score"),
        "policy": (610, 360, "ประเมิน Alert Policy"),
        "first": (175, 270, "FIRST Alert"),
        "repeat": (320, 270, "REPEAT Alert"),
        "resolved": (465, 270, "RESOLVED Event"),
        "popup": (610, 270, "Popup และเสียง"),
        "pause": (175, 180, "Pause / Resume\nSession เดิม"),
        "mini": (320, 180, "ควบคุมเมื่อ Minimize"),
        "gap": (465, 180, "จัดการ Camera /\nNetwork Data Gap"),
        "stop": (610, 180, "Stop Session"),
        "persist": (320, 95, "บันทึก Risk Event\nและ Notification"),
        "summary": (535, 95, "สร้าง Session Summary"),
    }
    for key, (x, y, label) in cases.items():
        fill, stroke = (AMBER_SOFT, AMBER) if key in {
            "first", "repeat", "resolved", "popup"
        } else (BLUE_SOFT, BLUE)
        use_case(c, x, y, 120, 36, label, fill, stroke)

    # Primary session flow.
    connector(c, 235, 445, 260, 445, True, "<<include>>")
    connector(c, 380, 445, 405, 445, True, "<<include>>")
    connector(c, 525, 445, 550, 445, True, "<<include>>")
    connector(c, 610, 427, 175, 378, True, "<<include>>")
    connector(c, 235, 360, 260, 360, True, "<<include>>")
    connector(c, 380, 360, 405, 360, True, "<<include>>")
    connector(c, 525, 360, 550, 360, True, "<<include>>")

    # Alert decisions.
    connector(c, 570, 345, 175, 288, True, "<<extend>>")
    connector(c, 590, 342, 320, 288, True, "<<extend>>")
    connector(c, 620, 342, 465, 288, True, "<<extend>>")
    connector(c, 235, 270, 550, 270, True, "<<include>>")
    connector(c, 380, 270, 550, 270, True, "<<include>>")

    # Session controls and persistence.
    connector(c, 380, 180, 550, 180, True, "<<include Stop>>")
    connector(c, 610, 162, 535, 113, True, "<<include>>")
    connector(c, 475, 95, 380, 95, True, "<<include>>")
    connector(c, 175, 252, 320, 113, True, "<<persist>>")
    connector(c, 320, 252, 320, 113, True, "<<persist>>")

    # User and external associations.
    connector(c, 60, 315, 115, 445)
    connector(c, 60, 300, 115, 180)
    connector(c, 60, 285, 550, 180)
    connector(c, 670, 445, 755, 410)
    connector(c, 670, 180, 755, 285)
    connector(c, 380, 95, 755, 160)

    footer(c)
    c.showPage()


def draw_reference_page(c):
    title(
        c,
        "คำอธิบาย Actor และ Use Case",
        "ขอบเขตการทำงานและเงื่อนไขสำคัญของระบบ",
        3,
    )

    styles = getSampleStyleSheet()
    normal = ParagraphStyle(
        "ThaiNormal",
        parent=styles["BodyText"],
        fontName="Tahoma",
        fontSize=8,
        leading=11,
        textColor=NAVY,
        alignment=TA_LEFT,
    )
    header = ParagraphStyle(
        "ThaiHeader",
        parent=normal,
        fontName="Tahoma-Bold",
        textColor=colors.white,
        alignment=TA_CENTER,
    )
    section = ParagraphStyle(
        "ThaiSection",
        parent=normal,
        fontName="Tahoma-Bold",
        fontSize=11,
        leading=14,
        textColor=BLUE,
    )

    story = []
    story.append(Paragraph("Actor", section))
    story.append(Spacer(1, 3 * mm))
    actor_rows = [
        [Paragraph("Actor", header), Paragraph("หน้าที่", header)],
        [Paragraph("ผู้ใช้งาน", normal), Paragraph("จัดการบัญชีและความเป็นส่วนตัว เตรียมกล้อง สร้าง Baseline ควบคุม Session รับ Alert และตรวจสอบรายงาน", normal)],
        [Paragraph("กล้อง Webcam", normal), Paragraph("ส่งภาพให้ Camera Setup, Baseline และ Monitoring โดยภาพถูกประมวลผลภายในเครื่อง", normal)],
        [Paragraph("Resend Email Service", normal), Paragraph("ส่ง OTP สำหรับการสมัครสมาชิกและการตั้งรหัสผ่านใหม่", normal)],
        [Paragraph("Backend / Supabase", normal), Paragraph("ตรวจสิทธิ์และจัดเก็บ Consent, Settings, Baseline, Session, Risk Event, Notification และ Summary", normal)],
    ]
    actor_table = Table(actor_rows, colWidths=[48 * mm, 214 * mm], repeatRows=1)
    actor_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BLUE),
        ("GRID", (0, 0), (-1, -1), 0.5, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BACKGROUND", (0, 1), (-1, -1), colors.white),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(actor_table)
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph("เงื่อนไขและความสัมพันธ์สำคัญ", section))
    story.append(Spacer(1, 2 * mm))

    notes = [
        "การเริ่ม Monitoring ต้องมี Privacy Consent ที่ยังใช้งานอยู่",
        "Camera Setup → Camera Preparation → Adjusted Preview → Personal Baseline เป็นลำดับก่อนเริ่ม Session",
        "การตรวจจับประกอบด้วย Current Posture Assessment, Temporal Tracking, RULA-adapted, Blink Rate และ Screen Distance",
        "FIRST เกิดเมื่อ Policy ยืนยันเหตุการณ์, REPEAT เกิดหลัง Cooldown และ RESOLVED เกิดเมื่อค่ากลับสู่ปกติ",
        "Popup แสดงเมื่อเปิด Notifications ส่วนเสียงเป็นทางเลือกตาม Settings ของผู้ใช้",
        "เมื่อ Minimize ระบบยังตรวจจับต่อและมีหน้าต่างเล็กสำหรับ Pause, Resume และ Stop",
        "Stop ต้องจบ Session, ปิดกล้อง, บันทึก Event และสร้าง Session Summary",
        "Dashboard, History และ Report ต้องแสดงเฉพาะข้อมูลของผู้ใช้ที่เข้าสู่ระบบ",
        "ภาพและวิดีโอจากกล้องไม่ถูกบันทึกหรืออัปโหลด ระบบเก็บเฉพาะข้อมูลที่จำเป็นต่อ Session และ Report",
    ]
    note_rows = []
    for index, note in enumerate(notes, start=1):
        note_rows.append([
            Paragraph(str(index), ParagraphStyle("Number", parent=normal, alignment=TA_CENTER, fontName="Tahoma-Bold")),
            Paragraph(note, normal),
        ])
    note_table = Table(note_rows, colWidths=[12 * mm, 250 * mm])
    note_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, BORDER),
        ("BACKGROUND", (0, 0), (0, -1), BLUE_SOFT),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(note_table)

    frame_x = 17 * mm
    frame_y = 14 * mm
    frame_w = PAGE_W - 34 * mm
    frame_h = PAGE_H - 46 * mm
    from reportlab.platypus import Frame

    frame = Frame(frame_x, frame_y, frame_w, frame_h, showBoundary=0)
    frame.addFromList(story, c)
    footer(c)
    c.showPage()


def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(OUTPUT), pagesize=landscape(A4))
    c.setTitle("PostGuard Use Case Diagram")
    c.setAuthor("PostGuard Project")
    c.setSubject("PostGuard Desktop Application Use Cases")
    draw_overview(c)
    draw_monitoring_detail(c)
    draw_reference_page(c)
    c.save()
    print(OUTPUT)


if __name__ == "__main__":
    main()
