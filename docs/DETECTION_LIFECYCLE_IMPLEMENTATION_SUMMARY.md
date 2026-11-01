# สรุปงาน Detection และ Session Lifecycle ที่เพิ่มใน PostGuard

เอกสารนี้สรุปงานที่เพิ่มบน branch `feature/detection` ในรอบล่าสุด ตั้งแต่การรับมือกล้องและเครือข่ายขัดข้อง การตรวจระยะหน้าจอและอัตราการกะพริบตา การบันทึก Alert และ Session Summary จนถึงการเตรียมโปรแกรมสำหรับสร้าง Windows executable

## 1. ภาพรวมงานที่เพิ่ม

| งาน | สิ่งที่เพิ่ม | ผลลัพธ์สำหรับผู้ใช้ |
| --- | --- | --- |
| Camera loss lifecycle | ตรวจพบกล้องหลุด พยายามเชื่อมใหม่ และเก็บเวลาที่ไม่มีข้อมูล | Session เดิมไม่ถูกปิดทันทีเมื่อกล้องหลุด |
| Data Gap | แยกช่วงที่ไม่มีภาพออกจากท่าปกติ | ระบบไม่ตีความภาพที่หายว่าเป็นท่าปลอดภัย |
| Internet retry | เก็บคำสั่งบันทึก Risk Event ที่ล้มเหลวไว้ retry | ลดโอกาสข้อมูลหายเมื่ออินเทอร์เน็ตสะดุดชั่วคราว |
| Screen Distance | เปรียบเทียบระยะดวงตาปัจจุบันกับ Personal Baseline | แจ้งเตือนเมื่อผู้ใช้เข้าใกล้หน้าจอต่อเนื่อง |
| Low Blink Rate | คำนวณจำนวนครั้งที่กะพริบในหน้าต่างเวลา 60 วินาที | แจ้งเตือนเมื่ออัตราการกะพริบต่ำกว่าเกณฑ์ |
| Wellness Alert | เพิ่ม First/Repeat/Resolved lifecycle | Popup และเสียงทำงานตามช่วงเหตุการณ์ |
| Alert History | รวม RULA Alert และ Wellness Alert | ดูเหตุการณ์ทั้งหมดได้จากหน้าประวัติเดียวกัน |
| Session Summary | เพิ่ม Camera Loss และ Data Gap | รายงานสะท้อนคุณภาพข้อมูลของ Session |
| Password visibility | เพิ่มปุ่มดูและซ่อนรหัสผ่าน | ใช้ได้ในทุกหน้าที่กรอกรหัสผ่าน |
| Build readiness | เพิ่ม API configuration, dependencies และ PyInstaller spec | เตรียมโครงสร้างสำหรับสร้างโปรแกรม Windows |

## 2. Camera Loss และ Data Gap

### หลักการทำงาน

เดิมเมื่ออ่านภาพจากกล้องไม่สำเร็จ โปรแกรมจะจบ Session ทันที พฤติกรรมใหม่จะรักษา Session เดิมไว้และทำงานตามลำดับต่อไปนี้

1. `MonitoringPage` อ่านภาพจากกล้องตามรอบของ `QTimer`
2. หากอ่านภาพไม่สำเร็จ จะปล่อยเฉพาะอุปกรณ์กล้อง แต่ยังเก็บ Detector, Session ID, Risk Event และสถิติของ Session ไว้
3. `CameraLossTracker` เริ่มจับเวลาช่วงที่กล้องไม่มีข้อมูลและเพิ่มจำนวน Camera Loss หนึ่งครั้ง
4. `DetectionService.process_data_gap()` ส่งสถานะ `NOT_EVALUATED` เข้าสู่ Risk Event lifecycle
5. Risk Event ที่กำลังทำงานจะถูกเก็บไว้ในสถานะ Data Gap และไม่ถูกปิดเป็นท่าปกติ
6. โปรแกรมลองเปิดกล้องใหม่ทุก 1 วินาที
7. เมื่อกล้องกลับมา โปรแกรมใช้ Session เดิมและเริ่มตรวจจับต่อ

ค่าที่เก็บเพิ่มในรายงานคือ

- `camera_loss_count`: จำนวนช่วงที่กล้องขาดการเชื่อมต่อ
- `data_gap_duration`: เวลารวมที่ไม่มีภาพจากกล้อง หน่วยเป็นวินาที

### การทำงานร่วมกับ Pause

Pause เป็นช่วงที่ผู้ใช้ตั้งใจหยุดตรวจ จึงไม่ถือเป็น Data Gap หากกล้องหลุดอยู่ก่อนกด Pause ระบบจะปิดช่วง Data Gap ณ เวลาที่ Backend ยืนยันสถานะ `PAUSED` และจะไม่นับเวลาที่ Pause รวมเข้าไป

เมื่อ Resume แล้วกล้องยังไม่กลับมา ระบบจะเปิดช่วง Data Gap ต่อโดยไม่เพิ่มจำนวน Camera Loss ซ้ำจากเหตุการณ์เดิม

### การป้องกันผลตรวจผิดหลังกล้องกลับมา

เมื่อเกิด Data Gap ระบบจะทำดังนี้

- Reset Temporal Posture window เพราะยืนยันไม่ได้ว่าผู้ใช้ค้างท่าเดิมตลอดช่วงที่ไม่มีภาพ
- ยกเลิก Screen Distance candidate ที่ยังยืนยันไม่ครบเวลา
- รักษา Screen Distance episode ที่ยืนยันแล้วไว้เป็น Data Gap จนกว่าจะมีภาพใหม่มายืนยันว่า recovered
- เริ่ม Blink Statistics window ใหม่เมื่อกล้องกลับมา เพื่อไม่ให้ช่วงที่ไม่มีภาพถูกตีความว่าเป็นการไม่กะพริบตา

ไฟล์หลัก:

- `desktop/app/services/camera_loss_tracker.py`
- `desktop/app/services/detection_service.py`
- `desktop/app/ui/pages/monitoring_page.py`

## 3. การรับมืออินเทอร์เน็ตขาด

`RiskPersistenceService` ใช้ worker thread ส่ง Risk Event และ Notification ไป Backend โดยไม่ให้การเรียก API ขวาง UI thread

เมื่อคำสั่งบันทึกล้มเหลว:

1. ระบบ retry ตามจำนวนครั้งที่กำหนด
2. หากยังไม่สำเร็จ จะเก็บ operation batch ไว้ในหน่วยความจำ
3. การประมวลผลรอบถัดไปหรือการเรียก `flush()` จะนำ batch เดิมกลับมาส่งใหม่
4. Runtime Event ID และ Notification idempotency key เดิมถูกนำกลับมาใช้ เพื่อป้องกันข้อมูลซ้ำ
5. ก่อน Pause, Stop หรือจบ Session โปรแกรมต้อง `flush()` งานค้างให้สำเร็จก่อน

ข้อจำกัดปัจจุบันคือ queue อยู่ในหน่วยความจำ หากผู้ใช้ force close โปรแกรมขณะออฟไลน์ operation ที่ยังไม่ส่งจะไม่สามารถกู้คืนหลังเปิดโปรแกรมใหม่ได้

ไฟล์หลัก:

- `desktop/app/services/risk_persistence_service.py`

## 4. Screen Distance

Screen Distance เป็น Wellness policy แยกจากคะแนน RULA เพราะกล้องด้านหน้าไม่สามารถคำนวณระยะจริงเป็นเซนติเมตรได้อย่างน่าเชื่อถือ

### วิธีคำนวณ

Personal Baseline เก็บระยะระหว่างดวงตาในภาพเป็น `ipd_baseline` จากนั้น Monitoring คำนวณ

```text
distance_ratio = current_eye_distance_px / baseline_eye_distance_px
```

เมื่อใบหน้าขยับเข้าใกล้กล้อง ระยะดวงตาในหน่วยพิกเซลจะเพิ่มขึ้น

เกณฑ์ปัจจุบัน:

| เงื่อนไข | ค่า |
| --- | ---: |
| เริ่ม candidate ว่าใกล้เกินไป | ratio ≥ 1.25 |
| ยืนยัน TOO_CLOSE | ต่อเนื่อง 3 วินาที |
| กลับสู่ NORMAL | ratio ≤ 1.15 |

ใช้ค่าเข้าและออกต่างกันแบบ hysteresis เพื่อลดการสลับสถานะเมื่อค่าอยู่ใกล้เส้นเกณฑ์ ค่าเหล่านี้เป็น engineering candidate policy และยังต้องทดสอบกับผู้ใช้และตำแหน่งกล้องหลายรูปแบบ

ไฟล์หลัก:

- `desktop/app/vision/mediapipe_detection/posture/screen_distance_policy.py`
- `desktop/app/services/detection_service.py`

## 5. Low Blink Rate

ระบบใช้ `BlinkStatistics` เก็บ Blink Event ใน sliding window 60 วินาที หลังข้อมูลครบหน้าต่างเวลาแล้วจึงคำนวณจำนวนครั้งที่กะพริบต่อนาที

Wellness policy ปัจจุบันแจ้งเตือนเมื่อ

```text
blink_rate < 10 ครั้งต่อนาที
```

ระบบจะไม่ตัดสิน Low Blink Rate ก่อนครบ 60 วินาที และจะเริ่มหน้าต่างเวลาใหม่หลังกล้องขาดการเชื่อมต่อ เพื่อป้องกัน False Alert

ค่า 10 ครั้งต่อนาทีเป็น candidate policy สำหรับระบบต้นแบบ ไม่ใช่การวินิจฉัยทางการแพทย์

ไฟล์หลัก:

- `desktop/app/vision/mediapipe_detection/eye/blink_statistics.py`
- `desktop/app/services/wellness_alert_policy.py`

## 6. Wellness Alert lifecycle

Wellness Alert รองรับสองประเภท

- `SCREEN_DISTANCE`
- `LOW_BLINK_RATE`

แต่ละประเภทมีสถานะดังนี้

| Action | ความหมาย |
| --- | --- |
| `STARTED` | เริ่มพบเหตุการณ์ต่อเนื่อง |
| `UPDATED` | เหตุการณ์เดิมยังทำงานอยู่ |
| `DATA_GAP` | ไม่มีข้อมูลเพียงพอและยังสรุปว่า recovered ไม่ได้ |
| `RESOLVED` | ค่ากลับเข้าสู่ช่วงปกติ |

Policy สร้าง `FIRST` notification เมื่อเริ่มเหตุการณ์ และสร้าง `REPEAT` หลัง cooldown 300 วินาทีหากเหตุการณ์ยังคงอยู่

`WellnessAlertPersistence` ใช้ Alert Event API เดิมเพื่อบันทึกช่วงเวลาเริ่มและสิ้นสุดของ episode หาก request สร้างเหตุการณ์ timeout ระบบจะค้นหา active event จาก Backend เพื่อกู้ ID ก่อนสร้างซ้ำ

ปัจจุบัน Backend บันทึก Wellness episode แต่ยังไม่ได้เก็บ Repeat popup ทุกครั้งเป็น notification record แยก ดังนั้นจำนวนในรายงานหมายถึงจำนวน episode รวมกับ RULA notifications ไม่ใช่จำนวนครั้งที่ popup แสดงทั้งหมด

ไฟล์หลัก:

- `desktop/app/services/wellness_alert_policy.py`
- `desktop/app/services/wellness_alert_persistence.py`
- `desktop/app/ui/dialogs/posture_alert_dialog.py`

## 7. Alert History และ Session Summary

หน้าประวัติรวมข้อมูลสองชุด

1. Integrated RULA Risk Events และ Alert Notifications
2. Wellness episodes จาก Alert Event API

Legacy posture alerts จะไม่ถูกนำมานับซ้ำเมื่อ Session มี integrated risk records แล้ว

ค่า `most_frequent_alert_event` เปลี่ยนให้ใช้สาเหตุที่ผู้ใช้เข้าใจได้ เช่น

- `TILT_LEFT`
- `FLEXION`
- `LEFT_SHOULDER_HIGH`
- `SCREEN_DISTANCE`
- `LOW_BLINK_RATE`

จึงไม่แสดง `FIRST`, `REPEAT` หรือ `ESCALATION` เป็นสาเหตุหลักของรายงานอีกต่อไป เพราะค่าเหล่านั้นบอกลำดับการแจ้งเตือน ไม่ได้บอกท่าหรือปัญหาที่ตรวจพบ

Session Summary เก็บข้อมูลเพิ่มดังนี้

```text
data_gap_duration: float >= 0
camera_loss_count: integer >= 0
```

Migration ที่เพิ่มคอลัมน์คือ `7c9e2a4b1d60_add_session_data_gap_metrics.py` และ Supabase อยู่ที่ revision `7c9e2a4b1d60 (head)`

ไฟล์หลัก:

- `backend/app/routers/session_summaries.py`
- `backend/app/models/session_summary.py`
- `backend/app/schemas/session_summary.py`
- `backend/alembic/versions/7c9e2a4b1d60_add_session_data_gap_metrics.py`
- `desktop/app/services/alert_history_service.py`
- `desktop/app/ui/dialogs/alert_history_dialog.py`
- `desktop/app/ui/pages/session_summary_page.py`

## 8. ปุ่มดูและซ่อนรหัสผ่าน

เพิ่ม helper กลางสำหรับสร้าง trailing icon บน `QLineEdit` และสลับ Echo Mode ระหว่าง Password กับ Normal

นำไปใช้กับ

- Login
- Register Password
- Register Confirm Password
- Reset Password
- Confirm Reset Password
- Current Password ใน Change Password
- New Password และ Confirm New Password

ไฟล์หลัก:

- `desktop/app/ui/utils/password_visibility.py`
- `desktop/app/assets/icons/eye.svg`
- `desktop/app/assets/icons/eye-off.svg`

## 9. การเตรียม Windows build

Desktop API URL ไม่ถูกล็อกไว้เฉพาะ `127.0.0.1` อีกต่อไป สามารถตั้งค่าด้วย

```env
POSTGUARD_API_BASE_URL=http://127.0.0.1:8001
```

สำหรับ Backend ที่ host ภายนอกให้เปลี่ยนเป็น HTTPS URL โดยไม่ใส่ Database, JWT, Resend หรือ Supabase service-role secret ลงใน Desktop `.env`

เพิ่มไฟล์สำหรับ build:

- `desktop/.env.example`
- `desktop/requirements-build.txt`
- `desktop/PostGuard.spec`

PyInstaller spec เตรียมรวม resource ต่อไปนี้

- MediaPipe package data และ binaries
- `pose_landmarker_lite.task`
- `face_landmarker.task`
- `measurement_change_thresholds.json`
- เสียงแจ้งเตือน
- ไอคอนดูและซ่อนรหัสผ่าน

`desktop/requirements.txt` ถูกแปลงจาก UTF-16 เป็น UTF-8 และเพิ่ม MediaPipe กับ OpenCV Contrib เพื่อให้ติดตั้งบนเครื่องใหม่ได้

ยังไม่ได้สร้าง executable เพราะ PyInstaller ยังไม่ได้ติดตั้งใน environment ปัจจุบัน และยังไม่มีการ deploy หรืออัปโหลดไฟล์ build

## 10. Automated tests

เพิ่มหรือปรับการทดสอบสำหรับ

- Camera loss count และ duration
- Camera gap ก่อนและหลัง Pause
- Data Gap ที่ไม่ถูกตีความเป็น safe posture
- Blink window restart หลังกล้องกลับมา
- Screen Distance threshold, confirmation และ hysteresis
- Wellness First, Repeat, Data Gap และ Resolution
- Wellness persistence create, recover, retry และ close
- Risk persistence retry ด้วย ID เดิม
- Session Summary validation
- Combined RULA และ Wellness Alert History
- Password visibility
- Desktop API URL configuration
- Desktop workflow ตั้งแต่กล้องจนถึง Session Summary

ผลล่าสุด:

| ชุดทดสอบ | ผลลัพธ์ |
| --- | --- |
| Desktop unit/regression | 269 tests ผ่านทั้งหมด |
| Backend unit/regression | 48 tests ผ่านทั้งหมด |
| Python compile check | ผ่าน |
| Git diff whitespace check | ผ่าน |

Backend test มี Starlette deprecation warning จาก dependency ของ TestClient และมี log จำลองกรณีส่งอีเมลแจ้งเปลี่ยนรหัสผ่านไม่สำเร็จ แต่ test suite ยังผ่านและไม่ได้เป็น runtime failure ของงานรอบนี้

## 11. งานที่ยังเหลือ

1. ทดสอบถอดและเสียบกล้องจริงระหว่าง Monitoring
2. ทดสอบ Camera Loss ร่วมกับ Pause, Resume และ Stop
3. ทดสอบตัดอินเทอร์เน็ตและเชื่อมใหม่ระหว่างมี Risk Event
4. ทดสอบ Screen Distance และ Low Blink Rate ครบ 60 วินาที
5. ตรวจ Popup, เสียง, Summary, Dashboard, History และ Alert History กับข้อมูลจริง
6. พิจารณาเพิ่ม disk-backed persistence queue สำหรับกรณี force close ขณะออฟไลน์
7. พิจารณาเก็บ Wellness Repeat popup เป็น notification record แยก หากรายงานต้องแสดงจำนวน popup จริง
8. สร้างและ smoke test Windows executable
9. จัด PySide6 packages ใน build environment ให้เป็น version เดียวกัน
10. ทำ Core Freeze หลัง Hardware/Network E2E ผ่าน

## 12. สถานะ Git และการเผยแพร่

- ทำงานบน branch `feature/detection`
- ยังไม่ได้ commit งานชุดนี้
- ยังไม่ได้ push งานชุดนี้
- ยังไม่ได้ deploy Backend หรือ Desktop build
- ไม่มีการแก้ไข source branch อื่น
