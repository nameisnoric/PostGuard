# การสร้างและใช้งาน PostGuard แบบ onedir

## รูปแบบการทำงาน

`PostGuard.exe` ทำงานบนเครื่องผู้ใช้เพื่อเปิดกล้องและประมวลผลภาพภายในเครื่อง
จากนั้นติดต่อ PostGuard API เพื่อใช้งานบัญชี บันทึกเซสชัน ค่าท่าทางอ้างอิง
การแจ้งเตือน ประวัติ และรายงาน โดยค่าเริ่มต้นเชื่อมต่อ API สำหรับการสอบที่
`https://postguard-api-k8oh.onrender.com`

ผู้ใช้ไม่ต้องเปิด FastAPI หรือ Python backend บนเครื่องเมื่อ API บน Render
พร้อมใช้งาน แต่ต้องเชื่อมต่ออินเทอร์เน็ตสำหรับฟังก์ชันที่อ่านหรือบันทึกข้อมูล

## สร้างโปรแกรม

เปิด PowerShell ที่โฟลเดอร์ `desktop` แล้วรัน:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\scripts\build_onedir.ps1
```

โปรแกรมที่สร้างแล้วอยู่ใน:

```text
desktop/dist/PostGuard/PostGuard.exe
```

## ทดสอบก่อนแจก

1. เปิด `https://postguard-api-k8oh.onrender.com/ready` และตรวจว่า database
   แสดง `available`
2. เปิด `desktop/dist/PostGuard/PostGuard.exe`
3. ทดสอบ Login, กล้อง, Personal Baseline และ Monitoring อย่างน้อยหนึ่งเซสชัน
4. ตรวจว่า Dashboard, History และรายงานเปิดข้อมูลของเซสชันนั้นได้
5. ทดสอบอีกครั้งบนเครื่อง Windows ที่ไม่ได้ติดตั้ง Python ถ้ามีเครื่องสำหรับทดสอบ

## วิธีแจกและใช้งาน

ZIP โฟลเดอร์ `desktop/dist/PostGuard` ทั้งโฟลเดอร์ ห้ามส่งเฉพาะ
`PostGuard.exe` เพราะไฟล์ใน `_internal` เป็นส่วนประกอบที่จำเป็น

ผู้รับแตก ZIP ไปยังโฟลเดอร์ที่ต้องการ แล้วเปิด `PostGuard.exe` ได้โดยไม่ต้อง
ติดตั้ง Python และไม่ต้องเปิด backend เอง

## ใช้กับ backend ในเครื่อง

เปิด backend ก่อน:

```powershell
cd backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8001
```

จากนั้นเปิดโปรแกรมใน PowerShell อีกหน้าต่าง:

```powershell
$env:POSTGUARD_API_BASE_URL="http://127.0.0.1:8001"
.\PostGuard.exe
```

## ข้อจำกัด

- ต้องส่งทั้งโฟลเดอร์ `PostGuard`; ย้ายเฉพาะไฟล์ EXE ไม่ได้
- ขนาดโปรแกรมค่อนข้างใหญ่ เพราะรวม PySide6, OpenCV, MediaPipe และโมเดลตรวจจับ
- Windows SmartScreen หรือ Antivirus อาจเตือน เพราะโปรแกรมยังไม่มี code-signing certificate
- Build นี้เป็น Windows 64-bit และต้องสร้างแยกใหม่สำหรับระบบปฏิบัติการอื่น
- กล้องและการตรวจจับทำงานในเครื่อง จึงขึ้นกับประสิทธิภาพ CPU คุณภาพกล้อง และแสง
- Login, History และการบันทึกข้อมูลต้องใช้อินเทอร์เน็ตเมื่อเชื่อมต่อ Render
- Render อาจใช้เวลาเริ่มระบบหลังไม่มีการใช้งาน ควรเปิด `/ready` ก่อนสาธิต
- การเปลี่ยน API ต้องตั้ง `POSTGUARD_API_BASE_URL` ก่อนเปิดโปรแกรม
- เมื่อแก้โค้ด โมเดล หรือ asset ต้อง build และแจกโฟลเดอร์ชุดใหม่
