"""Generate a Thai summary of PostGuard's front-camera RULA adaptation."""

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "reports" / "PostGuard_RULA_Adapted_Summary_2026-11-02.pdf"
FONT = Path(r"C:\Windows\Fonts\tahoma.ttf")
FONT_BOLD = Path(r"C:\Windows\Fonts\tahomabd.ttf")

NAVY = colors.HexColor("#0F172A")
BLUE = colors.HexColor("#2457D6")
BLUE_SOFT = colors.HexColor("#EEF4FF")
GREEN = colors.HexColor("#047857")
GREEN_SOFT = colors.HexColor("#ECFDF3")
AMBER = colors.HexColor("#B45309")
AMBER_SOFT = colors.HexColor("#FFF7ED")
RED_SOFT = colors.HexColor("#FEF2F2")
SLATE = colors.HexColor("#475569")
BORDER = colors.HexColor("#CBD5E1")
SURFACE = colors.HexColor("#F8FAFC")


pdfmetrics.registerFont(TTFont("Tahoma", str(FONT)))
pdfmetrics.registerFont(TTFont("Tahoma-Bold", str(FONT_BOLD)))


styles = getSampleStyleSheet()
styles.add(ParagraphStyle(
    name="ThaiTitle",
    fontName="Tahoma-Bold",
    fontSize=19,
    leading=27,
    textColor=NAVY,
    alignment=TA_CENTER,
    spaceAfter=5 * mm,
))
styles.add(ParagraphStyle(
    name="ThaiSubtitle",
    fontName="Tahoma",
    fontSize=9,
    leading=15,
    textColor=SLATE,
    alignment=TA_CENTER,
    spaceAfter=6 * mm,
))
styles.add(ParagraphStyle(
    name="ThaiHeading",
    fontName="Tahoma-Bold",
    fontSize=13,
    leading=20,
    textColor=NAVY,
    spaceBefore=3 * mm,
    spaceAfter=2.5 * mm,
))
styles.add(ParagraphStyle(
    name="ThaiBody",
    fontName="Tahoma",
    fontSize=9,
    leading=15,
    textColor=NAVY,
    spaceAfter=2.5 * mm,
))
styles.add(ParagraphStyle(
    name="ThaiSmall",
    fontName="Tahoma",
    fontSize=7.5,
    leading=12,
    textColor=SLATE,
))
styles.add(ParagraphStyle(
    name="ThaiCell",
    fontName="Tahoma",
    fontSize=7.7,
    leading=12,
    textColor=NAVY,
))
styles.add(ParagraphStyle(
    name="ThaiCellBold",
    fontName="Tahoma-Bold",
    fontSize=7.7,
    leading=12,
    textColor=NAVY,
))
styles.add(ParagraphStyle(
    name="ThaiCallout",
    fontName="Tahoma",
    fontSize=8.5,
    leading=14,
    textColor=NAVY,
    leftIndent=4 * mm,
    rightIndent=4 * mm,
    spaceBefore=2 * mm,
    spaceAfter=3 * mm,
))


def p(value, style="ThaiCell"):
    return Paragraph(str(value), styles[style])


def make_table(rows, widths, *, header=True, row_backgrounds=None):
    table = Table(rows, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
    commands = [
        ("FONTNAME", (0, 0), (-1, -1), "Tahoma"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.5, BORDER),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]
    if header:
        commands.extend([
            ("BACKGROUND", (0, 0), (-1, 0), BLUE),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Tahoma-Bold"),
        ])
    for row_index, background in row_backgrounds or []:
        commands.append(("BACKGROUND", (0, row_index), (-1, row_index), background))
    table.setStyle(TableStyle(commands))
    return table


def callout(text, background=BLUE_SOFT, border=BLUE):
    box = Table([[p(text, "ThaiCallout")]], colWidths=[174 * mm])
    box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), background),
        ("BOX", (0, 0), (-1, -1), 0.8, border),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return box


def header_footer(canvas, document):
    canvas.saveState()
    width, height = A4
    canvas.setStrokeColor(BORDER)
    canvas.line(18 * mm, height - 15 * mm, width - 18 * mm, height - 15 * mm)
    canvas.setFont("Tahoma-Bold", 8)
    canvas.setFillColor(BLUE)
    canvas.drawString(18 * mm, height - 11 * mm, "PostGuard")
    canvas.setFont("Tahoma", 7.5)
    canvas.setFillColor(SLATE)
    canvas.drawRightString(
        width - 18 * mm,
        height - 11 * mm,
        "RULA-adapted Front Camera • 2 พฤศจิกายน 2026",
    )
    canvas.line(18 * mm, 14 * mm, width - 18 * mm, 14 * mm)
    canvas.drawString(
        18 * mm,
        9 * mm,
        "เอกสารสรุปเกณฑ์ภายในโครงการ ไม่ใช่ Full RULA หรือการวินิจฉัยทางการแพทย์",
    )
    canvas.drawRightString(width - 18 * mm, 9 * mm, f"หน้า {document.page}")
    canvas.restoreState()


def build_story():
    story = [
        Spacer(1, 4 * mm),
        Paragraph("ตารางสรุป RULA ที่ประยุกต์ใช้ใน PostGuard", styles["ThaiTitle"]),
        Paragraph(
            "RULA_ADAPTED_FRONT_V1 • Contract 2.0-front-camera-adapted • กล้องด้านหน้า 1 ตัว",
            styles["ThaiSubtitle"],
        ),
        callout(
            "PostGuard นำหลักการบางส่วนของ RULA มาประยุกต์กับข้อมูลที่กล้องด้านหน้าตรวจได้ ได้แก่ "
            "การก้ม/เงยคอ การเอียงคอ ความไม่สมดุลของไหล่ และระยะเวลาที่ค้างท่า "
            "คะแนนภายในอยู่ในช่วง 1–7 และแสดงแก่ผู้ใช้เป็น 0–100% เพื่อให้อ่านง่ายขึ้น"
        ),
        Paragraph("1. สูตรคะแนนที่ระบบใช้", styles["ThaiHeading"]),
        callout(
            "คะแนน RULA-adapted = คะแนนพื้นฐานคอ + เอียงคอ + ไหล่ไม่สมดุล + ค้างท่า "
            "(ผลรวมสูงสุดไม่เกิน 7)",
            GREEN_SOFT,
            GREEN,
        ),
    ]

    component_rows = [
        [p("องค์ประกอบ", "ThaiCellBold"), p("เงื่อนไขจากระบบ", "ThaiCellBold"), p("คะแนน", "ThaiCellBold"), p("ที่มา/ความหมาย", "ThaiCellBold")],
        [p("คะแนนพื้นฐานคอ"), p("มุมคอ &lt; 0° (Extension)"), p("4", "ThaiCellBold"), p("ประยุกต์จากส่วน Neck ของ RULA")],
        [p("คะแนนพื้นฐานคอ"), p("0° ถึง 10°"), p("1", "ThaiCellBold"), p("ช่วงคอใกล้เป็นกลาง")],
        [p("คะแนนพื้นฐานคอ"), p("มากกว่า 10° ถึง 20°"), p("2", "ThaiCellBold"), p("ก้มคอระดับกลาง")],
        [p("คะแนนพื้นฐานคอ"), p("มากกว่า 20°"), p("3", "ThaiCellBold"), p("ก้มคอมาก")],
        [p("เอียงคอด้านข้าง"), p("Current Posture Assessment ระบุว่าเป็น TILT_LEFT หรือ TILT_RIGHT"), p("+1", "ThaiCellBold"), p("RULA-derived: Neck side bending")],
        [p("ไหล่ไม่สมดุล"), p("ตรวจพบ LEFT_SHOULDER_HIGH หรือ RIGHT_SHOULDER_HIGH"), p("+1", "ThaiCellBold"), p("ส่วนที่ PostGuard เพิ่มเพื่อใช้ข้อมูลกล้องหน้า")],
        [p("ค้างท่าต่อเนื่อง"), p("มีปัจจัยท่าทางใดท่าทางหนึ่งต่อเนื่องมากกว่า 60 วินาที"), p("+1", "ThaiCellBold"), p("ประยุกต์แนวคิด Static Muscle Use")],
    ]
    story.extend([
        make_table(component_rows, [34 * mm, 65 * mm, 18 * mm, 57 * mm]),
        Spacer(1, 4 * mm),
        Paragraph("2. เกณฑ์ที่ใช้จำแนกปัจจัยจากภาพ", styles["ThaiHeading"]),
    ])
    factor_rows = [
        [p("ข้อมูล", "ThaiCellBold"), p("เป็นกลาง", "ThaiCellBold"), p("เป็นปัจจัยท่าทาง", "ThaiCellBold"), p("หมายเหตุ", "ThaiCellBold")],
        [p("Shoulder tilt"), p("−2° ถึง +4°"), p("&lt; −2° = ไหล่ซ้ายสูง<br/>&gt; +4° = ไหล่ขวาสูง"), p("ใช้เส้นหัวไหล่จากภาพหลังแก้ Camera Roll")],
        [p("Relative neck lateral tilt"), p("−7° ถึง +5°"), p("&gt; +5° = เอียงซ้าย<br/>&lt; −7° = เอียงขวา"), p("คำนวณมุมแนวศีรษะเทียบกับแนวไหล่")],
        [p("Neck flexion assessment"), p("−10° ถึง +10°"), p("&gt; +10° = ก้มคอ<br/>&lt; −10° = เงยคอ"), p("การแบ่ง Factor นี้แยกจากตารางคะแนนพื้นฐานคอ")],
        [p("Temporal tracking"), p("ไม่มี Factor ต่อเนื่อง"), p("Factor เดิมต่อเนื่อง &gt; 60 วินาที"), p("Data Gap หรือ Factor เปลี่ยนจะตัดความต่อเนื่อง")],
    ]
    story.extend([
        make_table(factor_rows, [38 * mm, 39 * mm, 52 * mm, 45 * mm]),
        Spacer(1, 3 * mm),
        Paragraph(
            "หมายเหตุ: ค่าเท่ากับขอบเขตพอดีจะถือว่าเป็นกลาง เพราะตัวจำแนกใช้เงื่อนไขมากกว่า/น้อยกว่าแบบไม่รวมขอบเขต",
            styles["ThaiSmall"],
        ),
        PageBreak(),
        Paragraph("3. การแปลงคะแนน 1–7 เป็นเปอร์เซ็นต์", styles["ThaiHeading"]),
        Paragraph(
            "สูตรแสดงผล: เปอร์เซ็นต์ = (คะแนน − 1) × 100 ÷ 6 โดยหน้าจอปัดเป็นจำนวนเต็ม "
            "คะแนนดิบ 1–7 ยังคงใช้สำหรับการบันทึกและคำนวณค่าเฉลี่ย/ค่าสูงสุดใน Session Summary",
            styles["ThaiBody"],
        ),
    ])
    score_rows = [
        [p("คะแนนภายใน", "ThaiCellBold"), p("แสดงผล", "ThaiCellBold"), p("ระดับ", "ThaiCellBold"), p("ความหมายสำหรับผู้ใช้", "ThaiCellBold")],
        [p("1"), p("0%", "ThaiCellBold"), p("LOW"), p("ความเสี่ยงต่ำ")],
        [p("2"), p("17%", "ThaiCellBold"), p("LOW"), p("ความเสี่ยงต่ำ แต่ควรติดตามท่าทาง")],
        [p("3"), p("33%", "ThaiCellBold"), p("MODERATE"), p("ควรปรับท่าทางและติดตามต่อเนื่อง")],
        [p("4"), p("50%", "ThaiCellBold"), p("MODERATE"), p("ควรปรับท่าทางและติดตามต่อเนื่อง")],
        [p("5"), p("67%", "ThaiCellBold"), p("HIGH"), p("ควรปรับท่าทางโดยเร็ว")],
        [p("6"), p("83%", "ThaiCellBold"), p("HIGH"), p("ควรปรับท่าทางโดยเร็ว")],
        [p("7"), p("100%", "ThaiCellBold"), p("VERY HIGH"), p("ควรหยุดพักและปรับท่าทางทันที")],
    ]
    story.extend([
        make_table(
            score_rows,
            [27 * mm, 27 * mm, 36 * mm, 84 * mm],
            row_backgrounds=[(1, GREEN_SOFT), (2, GREEN_SOFT), (3, AMBER_SOFT), (4, AMBER_SOFT), (7, RED_SOFT)],
        ),
        Spacer(1, 5 * mm),
        Paragraph("4. ตัวอย่างการคำนวณ", styles["ThaiHeading"]),
    ])
    example_rows = [
        [p("ตัวอย่าง", "ThaiCellBold"), p("องค์ประกอบ", "ThaiCellBold"), p("ผลลัพธ์", "ThaiCellBold")],
        [p("ท่าใกล้เป็นกลาง"), p("คอ 5° = 1, ไม่เอียงคอ, ไหล่สมดุล, ไม่ค้างเกิน 60 วินาที"), p("1 = 0% (LOW)", "ThaiCellBold")],
        [p("ก้มคอและเอียงคอ"), p("คอ 15° = 2, เอียงคอ +1, ไหล่สมดุล, ยังไม่ค้างท่า"), p("3 = 33% (MODERATE)", "ThaiCellBold")],
        [p("หลายปัจจัยและค้างท่า"), p("คอ 15° = 2, เอียงคอ +1, ไหล่ไม่สมดุล +1, ค้างเกิน 60 วินาที +1"), p("5 = 67% (HIGH)", "ThaiCellBold")],
        [p("กรณีสูงสุด"), p("Extension = 4, เอียงคอ +1, ไหล่ไม่สมดุล +1, ค้างท่า +1"), p("7 = 100% (VERY HIGH)", "ThaiCellBold")],
    ]
    story.extend([
        make_table(example_rows, [38 * mm, 92 * mm, 44 * mm]),
        Spacer(1, 5 * mm),
        Paragraph("5. ความสัมพันธ์กับ Risk Event และ Alert", styles["ThaiHeading"]),
        callout(
            "เปอร์เซ็นต์ RULA-adapted ใช้สื่อสาร Risk Score แก่ผู้ใช้และบันทึกในรายงาน "
            "แต่ Risk Event/Alert ใช้หลักฐานที่ผ่าน Current Posture Assessment และ Temporal Tracking ร่วมกัน "
            "จึงไม่ควรตีความว่าเปอร์เซ็นต์ค่าเดียวเป็นเงื่อนไขแจ้งเตือนโดยตรง",
            AMBER_SOFT,
            AMBER,
        ),
    ])
    alert_rows = [
        [p("หลักฐานที่พร้อมประเมิน", "ThaiCellBold"), p("Static evidence", "ThaiCellBold"), p("ระดับสำหรับ Risk Event", "ThaiCellBold")],
        [p("ไม่มี Active evidence group"), p("ไม่มี"), p("NONE")],
        [p("1 กลุ่ม"), p("ยังไม่ถึงเวลา Static"), p("LOW")],
        [p("1 กลุ่ม"), p("มี Static evidence"), p("MODERATE")],
        [p("ตั้งแต่ 2 กลุ่มขึ้นไป"), p("ยังไม่มี Static evidence"), p("MODERATE")],
        [p("ตั้งแต่ 2 กลุ่มขึ้นไป"), p("มี Static evidence"), p("HIGH")],
    ]
    story.extend([
        make_table(alert_rows, [72 * mm, 48 * mm, 54 * mm]),
        PageBreak(),
        Paragraph("6. ลำดับการประมวลผล", styles["ThaiHeading"]),
    ])
    flow_rows = [
        [p("ขั้น", "ThaiCellBold"), p("กระบวนการ", "ThaiCellBold"), p("ผลลัพธ์", "ThaiCellBold")],
        [p("1"), p("Camera Adjustment"), p("กลับภาพและแก้ Camera Roll ก่อนตรวจจับ")],
        [p("2"), p("Pose / Face Detection"), p("จุดไหล่ จุดใบหน้า และมุมที่กล้องด้านหน้าวัดได้")],
        [p("3"), p("Current Posture Assessment"), p("จำแนก Neutral, Shoulder high, Neck tilt, Flexion/Extension")],
        [p("4"), p("Temporal Tracking"), p("วัดเวลาที่ Factor เดิมคงอยู่ต่อเนื่อง")],
        [p("5"), p("RULA-adapted Mapper"), p("คำนวณคะแนนภายใน 1–7 และระดับความเสี่ยง")],
        [p("6"), p("Presentation"), p("แปลงคะแนนเป็น 0–100% สำหรับ Monitoring, Dashboard และ Report")],
        [p("7"), p("Persistence"), p("บันทึกค่าเฉลี่ย ค่าสูงสุด และ method = RULA_ADAPTED_FRONT_V1")],
    ]
    story.extend([
        make_table(flow_rows, [15 * mm, 55 * mm, 104 * mm]),
        Spacer(1, 6 * mm),
        Paragraph("7. ข้อจำกัดที่ต้องระบุ", styles["ThaiHeading"]),
        callout(
            "ระบบใช้กล้องด้านหน้าเพียงตัวเดียว จึงไม่สามารถประเมินแขน ข้อมือ การบิดคอ แรงที่ใช้ "
            "และภาระงานได้ครบตาม Full RULA คะแนนนี้เป็นเครื่องมือคัดกรองท่าทางของ PostGuard "
            "ไม่ใช่ RULA Action Level อย่างเป็นทางการ และไม่ใช่การวินิจฉัยทางการแพทย์",
            RED_SOFT,
            colors.HexColor("#DC2626"),
        ),
        Paragraph("สิ่งที่ระบบประเมินได้", styles["ThaiHeading"]),
        Paragraph(
            "• การก้ม/เงยคอจากมุมที่กล้องด้านหน้าวัดได้<br/>"
            "• การเอียงคอด้านข้างเทียบกับแนวไหล่<br/>"
            "• ความไม่สมดุลของไหล่<br/>"
            "• ระยะเวลาที่ปัจจัยท่าทางคงอยู่ต่อเนื่อง",
            styles["ThaiBody"],
        ),
        Paragraph("สิ่งที่ระบบยังไม่ประเมินแบบ Full RULA", styles["ThaiHeading"]),
        Paragraph(
            "• ต้นแขน ปลายแขน ข้อมือ และการหมุนข้อมือครบทุกมิติ<br/>"
            "• การบิดลำตัว การบิดคอ แรง และน้ำหนักที่ยก<br/>"
            "• Muscle use และ load score ตามตาราง Full RULA ทั้งชุด",
            styles["ThaiBody"],
        ),
        Paragraph("8. แหล่งอ้างอิง", styles["ThaiHeading"]),
        Paragraph(
            "McAtamney, L. &amp; Corlett, E. N. (1993). RULA: a survey method for the investigation "
            "of work-related upper limb disorders. <i>Applied Ergonomics, 24</i>(2), 91–99. "
            "DOI: 10.1016/0003-6870(93)90080-S",
            styles["ThaiBody"],
        ),
        Paragraph(
            "แหล่งข้อมูลภายในโครงการ: desktop/app/vision/risk_evaluation/rula.py, "
            "risk_evaluator.py, current_posture_assessment.py, temporal_posture_tracker.py และ docs/RULA_MAPPING.md",
            styles["ThaiSmall"],
        ),
    ])
    return story


def main():
    document = SimpleDocTemplate(
        str(OUTPUT),
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=21 * mm,
        bottomMargin=19 * mm,
        title="PostGuard RULA-adapted Summary",
        author="PostGuard Project",
        subject="RULA-adapted front-camera scoring table and workflow",
    )
    document.build(build_story(), onFirstPage=header_footer, onLaterPages=header_footer)
    print(OUTPUT)


if __name__ == "__main__":
    main()
