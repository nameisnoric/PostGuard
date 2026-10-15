# PostGuard Desktop UI — Implementation Guide

เอกสารนี้อธิบาย UI ที่นำมาจาก `Wireframe v2` ใน Figma โครงสร้าง QSS
เทคสแตก และ flow การทำงานของโปรแกรมจริง โดยยึดหลักว่าข้อมูลที่ระบบยังคำนวณไม่ได้
ต้องแสดงเป็น `N/A` และไม่ใช้ตัวเลขตัวอย่างเป็นผลตรวจของผู้ใช้

## สิ่งที่ปรับในโค้ดจริง

- เปลี่ยน navigation จาก sidebar เป็น top navigation แบบเดียวกับ wireframe
- เพิ่ม session control bar ใต้ navigation เพื่อให้เห็น session ที่กำลังทำงานจากทุกหน้า
- Dashboard ใช้พื้นขาว การ์ด และ layout สองคอลัมน์
- Monitoring วาง camera panel ทางซ้าย และ detection/experimental metrics ทางขวา
- Camera Setup, Camera Preview และ Baseline แสดงลำดับขั้นตอน 1–3 ชัดเจน
- รวมสี typography ปุ่ม การ์ด ตาราง และ input ไว้ใน QSS กลาง
- คง signal, widget attribute และ session lifecycle เดิม เพื่อไม่ให้ flow/API/test เสีย

## Tech stack

| ส่วน | เทคโนโลยี | หน้าที่ |
|---|---|---|
| Desktop UI | Python 3.11, PySide6 / Qt Widgets | หน้าจอ desktop, signal/slot, timer และ QSS |
| Camera | OpenCV | เปิดกล้องและอ่าน frame |
| Detection | MediaPipe ผ่าน `DetectionService` | ตรวจ pose/face และคืนค่าที่วัดได้ |
| Desktop HTTP | `requests` | ติดต่อ REST API |
| Backend | FastAPI | Authentication, camera, baseline, session, summary และ alert endpoints |
| Validation | Pydantic | ตรวจ request/response model |
| ORM | SQLAlchemy | จัดการ model และ transaction |
| Database | PostgreSQL บน Supabase | เก็บ user, camera, baseline, session, summary และ alert |
| Migration | Alembic | จัดการ schema version |
| Password | Argon2, JWT, OTP, Resend | hash password, token และ reset password |

PySide6 ใช้ QSS ซึ่งมี syntax คล้าย CSS แต่ไม่ใช่ browser CSS ไม่มี DOM,
Flexbox หรือ Tailwind การจัดตำแหน่งใช้ `QVBoxLayout`, `QHBoxLayout` และ
`QGridLayout` ส่วน QSS ดูแลสี ขอบ typography และ widget state

## โครงสร้าง UI

```text
MainWindow
├── Top Navigation
│   ├── PostGuard
│   ├── Monitoring
│   ├── Dashboard
│   ├── History
│   └── Log out
├── Session Control Bar
│   ├── Running / Paused / Ending / Idle
│   ├── Pause / Resume
│   └── Stop Monitoring
└── QStackedWidget
    ├── DashboardPage
    ├── CameraSetupPage
    ├── CameraPreviewPage
    ├── BaselinePage
    ├── MonitoringPage
    ├── SessionSummaryPage
    └── HistoryPage
        └── Alert Events button
```

`MainWindow` เป็นตัวควบคุม navigation และ orchestration ส่วน page แต่ละตัวดูแล UI
และ logic เฉพาะหน้า การเปลี่ยนหน้าใช้ `QStackedWidget` จึงไม่สร้าง session ใหม่
และไม่ทำลาย `MonitoringPage` ที่กำลังทำงาน

## Flow การทำงาน

```text
Login
  → Dashboard
  → ตรวจ session เก่าที่ RUNNING/PAUSED
  → Camera Setup
  → Camera Preview
  → ลงทะเบียน/เลือก camera ใน backend
  → Baseline calibration (30 valid samples)
  → บันทึก personal baseline
  → Start session
  → Monitoring
      ├── ไป Dashboard/History ได้ และ detection ยังทำงาน
      ├── Pause → backend ยืนยัน PAUSED → หยุด local timer
      ├── Resume → backend ยืนยัน RUNNING → เริ่ม local timer
      └── Stop Monitoring
            → backend ยืนยัน COMPLETED
            → ปล่อยกล้อง
            → บันทึก measured summary
            → Session Summary
```

หากปิดโปรแกรมหรือ logout ระหว่าง session โปรแกรมจะพยายาม end session และบันทึก
summary ก่อนล้าง token หากขั้นใดล้มเหลว โปรแกรมจะเก็บ token และสถิติในหน่วยความจำ
เพื่อให้ผู้ใช้ retry ได้

เมื่อเปิดโปรแกรมใหม่ ระบบจะค้นหา session เก่าที่ `RUNNING` หรือ `PAUSED` และถามผู้ใช้
ก่อนทำเครื่องหมายเป็น `INTERRUPTED` เพราะ session อาจกำลังทำงานในอุปกรณ์อื่น
session ที่ interrupted จะไม่มี end time, duration หรือ summary ที่ระบบแต่งขึ้นเอง

## โครงสร้าง QSS และ design tokens

QSS กลางอยู่ที่ `desktop/app/ui/theme.py`

### สีหลัก

| Token | ค่า | การใช้งาน |
|---|---|---|
| `background` | `#f8fafc` | พื้นหลังแอป |
| `surface` | `#ffffff` | navigation และการ์ด |
| `surface_subtle` | `#f1f5f9` | preview placeholder / table header |
| `border` | `#e2e8f0` | ขอบการ์ดและ input |
| `text` | `#0f172a` | ข้อความหลัก |
| `muted` | `#64748b` | คำอธิบายและ metadata |
| `primary` | `#2563eb` | primary action / active navigation |
| `success` | `#059669` | Running |
| `warning` | `#b45309` | Paused |
| `danger` | `#ef4444` | Stop Monitoring |

### Selector ที่ใช้

- `QWidget[page="true"]` กำหนดพื้นหลังของหน้า
- `QFrame[card="true"]` สร้างการ์ดมาตรฐาน
- `QFrame[variant="welcome"]` สร้าง welcome banner
- `QPushButton[nav="true"]` และ `[navActive="true"]` แสดงเมนูและ active state
- `QPushButton[variant="primary"]` สำหรับ action หลัก
- `QPushButton[variant="danger"]` สำหรับ Stop Monitoring
- `QLabel[role="title|heading|metric|muted|eyebrow"]` เป็น typography scale
- `QLabel[status="running|paused|idle"]` แสดงสี session state
- `QLabel[preview="true"]` เป็นกรอบกล้องก่อนมีภาพจริง

Camera Preview, Baseline และ Monitoring กำหนด maximum size และใช้
`QSizePolicy.Ignored` เพื่อไม่ให้ `QLabel.sizeHint()` โตตาม pixmap แล้วนำขนาดใหม่
ไปขยาย pixmap ซ้ำ ภาพจึงรักษาอัตราส่วน อยู่กึ่งกลาง และไม่ทำให้หน้าต่างขยายต่อเนื่อง

เมื่อ property เปลี่ยนระหว่าง runtime จะเรียก `polish(widget)` เพื่อให้ Qt ประเมิน
property selector ใหม่ เช่น active navigation และสี Running/Paused

## การเชื่อมข้อมูลจริง

Dashboard เรียก `GET /sessions` ผ่าน background `QRunnable` เพื่อไม่ block UI thread
แล้วคำนวณข้อมูลดังนี้:

- Completed sessions: นับเฉพาะ status `COMPLETED`
- Active monitoring time: `total_duration - paused_duration`
- Interrupted sessions: นับ status `INTERRUPTED`
- Recent sessions: แสดงไม่เกิน 5 รายการล่าสุด
- duration ที่ไม่ครบหรือผิดรูปแบบ: แสดง `N/A` และไม่นับเป็นศูนย์

Risk Score History และ Blink Rate History ยังไม่เชื่อม calculation ที่สมบูรณ์ จึงแสดง
`N/A` พร้อมคำอธิบาย ไม่มีตัวเลข mock ในโปรแกรมจริง ส่วน experimental neck alert
ใน Monitoring ยังคงระบุว่าเป็น provisional/partial และไม่อ้างว่าเป็น full risk score

หน้า Session Summary ซ่อนรายละเอียดฐานข้อมูลเมื่อบันทึกสำเร็จ เพราะเป็นรายละเอียด
ภายในระบบ แต่ยังเก็บ save status ไว้ใน state และจะแสดง `Summary Save Problem` พร้อม
ปุ่ม Retry เฉพาะเมื่อบันทึก summary ไม่สำเร็จ

## ไฟล์สำคัญ

- `desktop/app/ui/theme.py` — design tokens, QSS และ dynamic repolish
- `desktop/app/ui/main_window.py` — top navigation, session bar และ page orchestration
- `desktop/app/ui/pages/dashboard_page.py` — real dashboard data และ empty/error states
- `desktop/app/ui/pages/monitoring_page.py` — camera/detection layout และ session controls
- `desktop/app/ui/pages/camera_setup_page.py` — เลือกหรือ scan กล้อง
- `desktop/app/ui/pages/camera_preview_page.py` — ตรวจภาพก่อนสร้าง baseline
- `desktop/app/ui/pages/baseline_page.py` — calibration และบันทึก baseline
- `desktop/app/ui/pages/alert_history_dialog.py` — session alert viewer with loading, error and empty states
- `desktop/app/ui/pages/profile_page.py` — Figma-aligned profile form, private photo management and persistent username/full-name edits
- `desktop/app/ui/account_recovery_window.py` — restricted 14-day account recovery screen

บัญชีที่ส่งคำขอลบจะเปลี่ยนเป็น `PENDING_DELETION` ทันที และ API ปกติจะถูกปิดกั้น
ผู้ใช้ login ได้เฉพาะหน้ากู้คืนภายใน 14 วัน Backend ตรวจบัญชีครบกำหนดตอนเริ่มระบบและทุก 6 ชั่วโมง
จากนั้นลบข้อมูลที่อ้างอิงผ่าน foreign-key cascade และรูปใน private storage คำสั่งต่อไปนี้ใช้ตรวจหรือสั่ง cleanup เพิ่มเติมด้วยตนเองได้:

```powershell
cd backend
.\.venv\Scripts\python.exe -m scripts.purge_deleted_accounts
```
- `desktop/app/ui/login_window.py` — login card and authentication entry point
- `desktop/app/ui/register_window.py` — account registration card and OTP handoff
- `desktop/app/ui/password_reset_dialog.py` — three-step password reset dialog
- `desktop/app/services/api_client.py` — REST client
- `backend/app/routers/` — API endpoints
- `backend/app/models/` — SQLAlchemy models

## วิธีรัน

เปิด backend จาก environment ของ backend แล้วเปิด desktop จากอีก terminal ตาม config
ของโครงการ โดย desktop ใช้ API URL จาก `desktop/app/core/config.py`

```powershell
cd backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8001

cd ..\desktop
.\.venv\Scripts\python.exe -m app.main
```

## การทดสอบ UI flow

ชุดทดสอบ desktop จำลอง camera, detector และ API จึงตรวจ flow ได้โดยไม่สร้างข้อมูลจริง:

```powershell
cd desktop
$env:QT_QPA_PLATFORM='offscreen'
.\.venv\Scripts\python.exe -m unittest discover `
  -s tests/unit -p "test_*.py" -v
```

`tests/hardware/test_camera_resolution.py` เป็น hardware check ที่เปิด webcam จริง จึงต้องรันบนเครื่องที่
อนุญาตให้ process เข้าถึงกล้อง และไม่ควรรวมกับ offscreen unit test

## ข้อจำกัดปัจจุบัน

- Full risk score ยังไม่พร้อม
- Blink rate และ EAR ยังไม่เชื่อมเข้ากับ dashboard
- Floating camera window ใน wireframe ยังไม่มี implementation
- UI ใช้ข้อความภาษาอังกฤษเป็นหลักตามหน้าปัจจุบัน
- QSS ของ Qt รองรับ selector และ state บางส่วน ไม่เท่ากับ browser CSS
