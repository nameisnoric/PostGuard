# PostGuard Alert Ground Truth Studio

เครื่องมือนี้ใช้สร้าง Ground Truth สำหรับ Alert ใหม่จากวิดีโอโดยตรง แล้วรันวิดีโอ
ผ่าน Detection, Temporal Tracking, RULA-adapted Risk, Risk Event และ Alert Policy
ของ PostGuard เพื่อเปรียบเทียบเวลาที่ระบบแจ้งกับเวลาที่มนุษย์กำหนด

## เปิดโปรแกรม

จากโฟลเดอร์ `desktop`:

```powershell
.\.venv\Scripts\python.exe tools\video_validation\postguard_alert_validation.py
```

## วิธีสร้าง Ground Truth

1. กด **Open Video**
2. เล่นวิดีโอหรือเลื่อนแถบเวลาไปยังจุดที่ควรเกิด Alert
3. เลือก Event:
   - `POSTURE_RISK`
   - `LOW_BLINK_RATE`
   - `SCREEN_DISTANCE`
4. เลือก Transition:
   - `FIRST` แจ้งครั้งแรก
   - `REPEAT` แจ้งซ้ำหลัง cooldown
   - `ESCALATION` ความเสี่ยงเพิ่มระดับ
   - `RESOLVED` กลับสู่ภาวะปกติและปิดเหตุการณ์
5. กด **Add marker at current time**
6. ทำซ้ำทุกเหตุการณ์ แล้วกด **Export Ground Truth**

Ground Truth ใหม่ใช้รูปแบบ:

```csv
event_type,alert_type,timestamp_sec,note
POSTURE_RISK,FIRST,60.000000,ท่าผิดค้างครบ 60 วินาที
POSTURE_RISK,RESOLVED,75.200000,กลับสู่ท่าปกติ
LOW_BLINK_RATE,FIRST,92.000000,blink rate ต่ำต่อเนื่อง
```

## รันทดสอบ

1. กำหนด **Match tolerance** เช่น 2 วินาที
2. ถ้าทดสอบ Screen Distance ให้ใส่ค่า Baseline eye distance จากช่วงนั่งปกติ
3. กด **Run Alert Validation**
4. เลือกโฟลเดอร์ผลลัพธ์

โปรแกรมจะประมวลผลวิดีโอใหม่ทั้งหมดโดยใช้เวลาจากวิดีโอ ไม่ใช้ความเร็วในการรัน
ของเครื่องเป็นเวลา Temporal Tracking

## ผลลัพธ์

- `*_system_alerts.csv` Alert ที่ production pipeline สร้าง
- `*_alert_validation_details.csv` ผล `MATCHED`, `MISSED`, `SYSTEM_ONLY`
- `*_alert_validation_report.json` Precision, Recall, F1, latency และ false alerts/hour
- แยก metrics ตาม Event และ FIRST/REPEAT/ESCALATION/RESOLVED

## ข้อกำหนดของคลิป

- Posture FIRST: ต้องมีท่าผิดค้างต่อเนื่องอย่างน้อย 60 วินาที
- Posture REPEAT ระดับ Moderate: หลัง FIRST ต้องค้างต่ออีก 600 วินาที
- Posture REPEAT ระดับ High: หลัง FIRST ต้องค้างต่ออีก 300 วินาที
- Low Blink: ต้องมีช่วงข้อมูลตาที่ใช้ได้ครบหน้าต่าง 60 วินาทีและต่ำกว่าเกณฑ์ต่อเนื่อง
- Screen Distance: ต้องมีค่า Baseline eye distance ของคลิปนั้น
- ควรมีคลิปภาวะปกติเพื่อวัด System-only false alerts

Ground Truth ต้องกำหนดโดยผู้ตรวจจากสิ่งที่เห็นในวิดีโอ ไม่ควรคัดลอกเวลาที่ระบบ
ตรวจพบ เพราะจะทำให้ผลประเมินเอนเอียงเข้าหาระบบ
