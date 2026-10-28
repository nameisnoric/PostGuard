# PostGuard Detection Validation Studio v4

เครื่องมือนี้ใช้วิดีโอและ Human Ground Truth เพื่อวัดผล Detection ของ
PostGuard โดยไม่รวมคะแนนความเสี่ยง RULA, Risk Event หรือ Alert Policy
เข้ามาเป็นตัวตัดสินความถูกต้อง

## เปิดโปรแกรม

จากโฟลเดอร์ `desktop`:

```powershell
.\.venv\Scripts\python.exe tools\video_validation\postguard_detection_validation_v4.py
```

## วิธีทดสอบ

1. เปิดไฟล์วิดีโอที่ต้องการทดสอบ
2. เลื่อนไปยังเวลาเริ่ม posture แล้วกด `S`
3. เลื่อนไปยังเวลาสิ้นสุดแล้วกด `E`
4. เลือก label ของ posture แล้วเพิ่ม Human Ground Truth
5. สำหรับการกะพริบตา เลื่อนไปยังเวลาที่กะพริบแล้วกด `B`
6. Export Ground Truth เก็บไว้ใช้ซ้ำได้
7. กด Run Validation และเลือกโฟลเดอร์ผลลัพธ์

Label ที่รองรับ:

- `NEUTRAL`
- `LEFT_SHOULDER_HIGH`
- `RIGHT_SHOULDER_HIGH`
- `TILT_LEFT`
- `TILT_RIGHT`
- `FLEXION`
- `EXTENSION`
- `BLINK`
- `IGNORE`

## ผลลัพธ์

- `*_ground_truth.csv`
- `*_frame_results.csv`
- `*_posture_event_summary.csv`
- `*_posture_event_details.csv`
- `*_blink_summary.csv`
- `*_blink_details.csv`
- `*_validation_report.json`

Posture summary รายงาน Human Events, Detected, Missed และ Detection Rate
แยกตามท่า ส่วน Blink รายงาน Precision, Recall และ F1 Score โดยจับคู่เหตุการณ์
ภายในช่วงคลาดเคลื่อน ±0.25 วินาที

Detection Rate ของ posture เป็น event recall และยังไม่ใช่ accuracy แบบครบถ้วน
เพราะยังไม่ลงโทษ system-only false positive ควรอ่านร่วมกับ frame results และ
event details ก่อนสรุปความแม่นยำของระบบ
