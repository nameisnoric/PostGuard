# รายงานการประเมินเกณฑ์การแจ้งเตือนของระบบ PostGuard

**วันที่จัดทำ:** 2 พฤศจิกายน 2569  
**โครงการ:** PostGuard Desktop Application  
**ขอบเขต:** การแจ้งเตือนท่าทาง ความเสี่ยงจากท่าทาง อัตราการกะพริบตา ระยะห่างจากหน้าจอ และการแจ้งเตือนซ้ำ

## 1. วัตถุประสงค์

รายงานฉบับนี้จัดทำขึ้นเพื่อตรวจสอบว่าเกณฑ์การแจ้งเตือนที่ PostGuard ใช้อยู่ในปัจจุบันมีส่วนใดอ้างอิงจากงานวิจัย ส่วนใดเป็นค่าที่ได้จากการทดลองของระบบ และส่วนใดยังต้องผ่านการทดสอบเพิ่มเติมก่อนนำไปกล่าวอ้างว่าเป็นเกณฑ์ที่มีหลักฐานรองรับ

PostGuard ใช้กล้องด้านหน้าเพียงตัวเดียว ระบบจึงประเมินได้เฉพาะข้อมูลที่มองเห็นจากด้านหน้า ได้แก่ การก้มและเงยคอ การเอียงคอ ความไม่สมดุลของไหล่ ระยะเวลาที่ค้างท่า การกะพริบตา และการเปลี่ยนแปลงของขนาดใบหน้าในภาพ ระบบไม่สามารถประเมินองค์ประกอบทั้งหมดของ Full RULA และไม่ควรใช้เพื่อวินิจฉัยโรค

## 2. วิธีการตรวจสอบ

การตรวจสอบใช้ข้อมูลจากแหล่งต่อไปนี้

1. เกณฑ์ที่กำหนดอยู่ในโค้ดของ PostGuard
2. เอกสาร RULA Mapping และเอกสารวงจรการตรวจจับของโครงการ
3. ผลการทำ Prototype Validation ที่บันทึกไว้ในไฟล์ค่าความเปลี่ยนแปลงจาก Personal Baseline
4. งานวิจัยต้นฉบับเกี่ยวกับ RULA ระยะการมองหน้าจอ อัตราการกะพริบตา และการแจ้งเตือนให้พักจากการนั่งต่อเนื่อง

## 3. สรุปเกณฑ์ที่ระบบใช้อยู่

| ประเภท | เกณฑ์ปัจจุบัน | วิธีทำงาน | สถานะหลักฐาน |
| --- | --- | --- | --- |
| RULA-adapted Risk Score | คะแนนภายใน 1–7 และแสดงผลแก่ผู้ใช้เป็นร้อยละ | ใช้การก้มเงยคอ การเอียงคอ ความไม่สมดุลของไหล่ และการค้างท่า | อ้างอิงหลักการจาก RULA แต่เป็นการประยุกต์สำหรับกล้องด้านหน้า |
| ท่าทางค้างต่อเนื่อง | มากกว่า 60 วินาที | เพิ่มองค์ประกอบ Sustained Posture และใช้สร้าง Risk Event | สอดคล้องกับแนวคิด Static Muscle Use ของ RULA |
| Shoulder Tilt | เปลี่ยนจาก Personal Baseline มากกว่า 1.153° | ใช้เป็น Measurement Change Gate | Prototype Validation ไม่ใช่เกณฑ์ทางคลินิก |
| Neck Lateral Tilt | เปลี่ยนจาก Personal Baseline มากกว่า 2.276° | ใช้เป็น Measurement Change Gate | Prototype Validation ไม่ใช่เกณฑ์ทางคลินิก |
| Neck Flexion | เปลี่ยนจาก Personal Baseline มากกว่า 3.542° | ใช้เป็น Measurement Change Gate | Prototype Validation ไม่ใช่เกณฑ์ทางคลินิก |
| Low Blink Rate | น้อยกว่าหรือเท่ากับ 8 ครั้งต่อนาที | รอข้อมูลครบหน้าต่าง 60 วินาที และยืนยันค่าต่ำต่อเนื่อง 15 วินาที | Prototype Engineering Policy |
| Blink Recovery | ตั้งแต่ 10 ครั้งต่อนาทีขึ้นไป | ปิดเหตุการณ์ Low Blink Rate | Prototype Engineering Policy |
| Screen Distance | Eye-distance ratio ตั้งแต่ 1.25 ขึ้นไป | ต้องเกิดต่อเนื่อง 3 วินาทีก่อนยืนยันว่าอยู่ใกล้เกินไป | Prototype Engineering Policy |
| Screen Distance Recovery | Eye-distance ratio ไม่เกิน 1.15 | ใช้ Hysteresis เพื่อป้องกันสถานะสลับไปมา | Prototype Engineering Policy |
| Moderate Repeat Alert | ทุก 600 วินาที | แจ้งเตือนซ้ำเมื่อเหตุการณ์เดิมยังไม่หาย | ค่าที่ระบบกำหนด ยังไม่มีผลทดสอบผู้ใช้รองรับ |
| High Repeat Alert | ทุก 300 วินาที | แจ้งเตือนระดับสูงถี่กว่าระดับปานกลาง | ค่าที่ระบบกำหนด ยังไม่มีผลทดสอบผู้ใช้รองรับ |
| Resolution Notification | ปิดอยู่ | ปิด Event เมื่อท่าทางกลับเป็นปกติ แต่ไม่แสดง Popup ตอนหาย | เป็นการตัดสินใจด้าน UX |

## 4. การประเมินตามหลักฐานวิจัย

### 4.1 RULA-adapted Risk Score

ระบบอ้างอิงงานของ McAtamney และ Corlett ซึ่งพัฒนา Rapid Upper Limb Assessment หรือ RULA เพื่อคัดกรองความเสี่ยงด้านการยศาสตร์จากท่าทาง แรง และการใช้กล้ามเนื้อ คะแนน 1–7 ของ PostGuard จึงมีฐานแนวคิดจากงานวิจัยดังกล่าว

อย่างไรก็ตาม PostGuard มีกล้องด้านหน้าเพียงตัวเดียว จึงไม่สามารถตรวจตำแหน่งแขน ข้อมือ การบิดคอ แรง และภาระงานได้ครบ ระบบจึงใช้ชื่อ `RULA_ADAPTED_FRONT_V1` และต้องแสดงข้อจำกัดว่าไม่ใช่ Full RULA

องค์ประกอบ Shoulder Asymmetry เป็นการประยุกต์ของ PostGuard เพื่อใช้ข้อมูลที่กล้องด้านหน้าตรวจได้ ไม่ใช่รายการให้คะแนนไหล่อย่างเป็นทางการจาก RULA

**ผลการประเมิน:** มีงานวิจัยรองรับหลักการ แต่ต้องใช้คำว่า RULA-adapted และห้ามกล่าวอ้างเป็นผลวินิจฉัยหรือ Full RULA

### 4.2 เกณฑ์การเปลี่ยนแปลงจาก Personal Baseline

ค่า Shoulder Tilt 1.153°, Neck Lateral Tilt 2.276° และ Neck Flexion 3.542° มาจากผล Prototype Validation ของระบบ เกณฑ์เหล่านี้ทำหน้าที่ตรวจว่าค่าปัจจุบันเปลี่ยนจากท่านั่งอ้างอิงของผู้ใช้มากพอที่จะนำไปประเมินต่อหรือไม่

ค่าดังกล่าวไม่ใช่องศาความเสี่ยงตามหลักการแพทย์หรือการยศาสตร์โดยตรง การตั้งค่าไว้ค่อนข้างต่ำอาจช่วยให้ระบบไวต่อการเปลี่ยนท่า แต่มีความเสี่ยงต่อ False Positive จาก noise ของ landmark การเคลื่อนไหวตามธรรมชาติ และการเปลี่ยนตำแหน่งกล้อง

**ผลการประเมิน:** ผ่านในระดับ Prototype แต่ยังต้องทดสอบกับผู้ใช้และวิดีโอหลายสภาพแวดล้อม

### 4.3 Low Blink Rate

ระบบปัจจุบันใช้หน้าต่างเวลา 60 วินาที แจ้งเตือนเมื่อ Blink Rate ไม่เกิน 8 ครั้งต่อนาที และต้องมีค่าต่ำต่อเนื่องอีก 15 วินาที โดยจะปิดเหตุการณ์เมื่อ Blink Rate กลับมาตั้งแต่ 10 ครั้งต่อนาทีขึ้นไป

งานวิจัยพบว่าอัตราการกะพริบตาเปลี่ยนแปลงได้ตามชนิดของงาน สภาพแวดล้อม ความสนใจ ความล้าของดวงตา และความแตกต่างระหว่างบุคคล จึงไม่ควรนำค่าตัดเพียงค่าเดียวไปใช้เป็นการวินิจฉัยอาการตาล้า

ค่า 8 ครั้งต่อนาทีของ PostGuard มีลักษณะเป็นเกณฑ์คัดกรองแบบระมัดระวัง การใช้หน้าต่าง 60 วินาทีและช่วงยืนยัน 15 วินาทีช่วยลดการแจ้งเตือนจากความผันผวนระยะสั้น แต่ยังต้องวัด Precision, Recall และ False Alert Rate กับ Ground Truth

เอกสารวงจรการตรวจจับฉบับเดิมระบุเกณฑ์ `<10 ครั้งต่อนาที` ขณะที่โค้ดปัจจุบันใช้ `≤8 ครั้งต่อนาที` และ recovery ที่ `≥10 ครั้งต่อนาที` จึงต้องปรับเอกสารให้ตรงกับระบบ

**ผลการประเมิน:** ยังเป็น Prototype Engineering Policy ไม่ควรกล่าวว่าเป็นเกณฑ์ทางการแพทย์

### 4.4 Screen Distance

PostGuard ไม่สามารถวัดระยะจากใบหน้าถึงหน้าจอเป็นเซนติเมตรได้โดยตรง ระบบจึงเปรียบเทียบระยะระหว่างดวงตาในภาพปัจจุบันกับค่าที่เก็บจาก Personal Baseline

สูตรที่ใช้คือ

```text
distance_ratio = current_eye_distance_px / baseline_eye_distance_px
```

เมื่อใบหน้าเคลื่อนเข้าใกล้กล้อง ระยะระหว่างดวงตาในภาพจะเพิ่มขึ้น ระบบเริ่มพิจารณาว่าใกล้เกินไปเมื่อ ratio ตั้งแต่ 1.25 ขึ้นไปต่อเนื่อง 3 วินาที และกลับเป็นปกติเมื่อ ratio ไม่เกิน 1.15

งานวิจัยเกี่ยวกับระยะมองจอพบว่าระยะที่เหมาะสมขึ้นอยู่กับขนาดตัวอักษร ความสามารถในการมองเห็น และความชอบของแต่ละบุคคล โดยมีรายงานช่วงประมาณ 52–73 เซนติเมตร และช่วงที่ผู้ใช้เลือกเองประมาณ 60–100 เซนติเมตร การใช้ Personal Baseline จึงเหมาะกับข้อจำกัดของกล้องมากกว่าการสมมติระยะเซนติเมตร แต่ค่า 1.25 และ 1.15 ยังไม่มีผล validation ที่เพียงพอ

**ผลการประเมิน:** วิธีเปรียบเทียบกับ Personal Baseline มีเหตุผลรองรับ แต่ค่า ratio ยังเป็น Prototype Engineering Policy

### 4.5 ระยะเวลาการแจ้งเตือนซ้ำ

ระบบแจ้งเตือนครั้งแรกเมื่อ Alert Policy ยืนยันเหตุการณ์ จากนั้นแจ้งเตือนซ้ำระดับ Moderate ทุก 10 นาที และระดับ High ทุก 5 นาที การกำหนดระดับสูงให้แจ้งถี่กว่าระดับปานกลางเป็นหลักการออกแบบที่เข้าใจได้ แต่ยังไม่มีผลการทดสอบว่าความถี่ดังกล่าวช่วยให้ผู้ใช้แก้ท่าทางโดยไม่สร้าง Alert Fatigue

**ผลการประเมิน:** เป็นค่าที่กำหนดจากการออกแบบระบบ ต้องผ่าน User Acceptance Test

### 4.6 การเตือนให้พักจากการนั่งต่อเนื่อง

งานทดลองกับพนักงานสำนักงานพบว่าการแจ้งเตือนให้ลุกทุก 30 นาทีสามารถลดจำนวนและระยะเวลาของช่วงนั่งต่อเนื่องได้ และงานทดลองอื่นพบว่าการพักสั้นและถี่สามารถลดเวลานั่งระหว่างวันทำงานได้

ปัจจุบัน PostGuard มี `reminder_interval_minutes` แต่ทำหน้าที่ควบคุมช่วงแจ้งเตือนหรือเสียงซ้ำ ไม่ได้เป็น Sitting Break Policy ที่ติดตามเวลานั่งต่อเนื่องแยกต่างหาก หากต้องการให้ตรงกับหลักฐานด้านการพักจากการนั่ง ควรแยก Break Reminder ออกจาก Posture Alert อย่างชัดเจน

**ผลการประเมิน:** ยังไม่มี Sitting Break Policy ที่อ้างอิงงานวิจัยโดยตรง

## 5. งานที่ยังไม่เสร็จ

### 5.1 งานด้านเกณฑ์และการวิจัย

1. จัดทำ Alert Policy ฉบับสุดท้ายพร้อมหมายเลขเวอร์ชันและแหล่งอ้างอิง
2. แก้เอกสาร Blink Rate จาก `<10` ให้ตรงกับโค้ด `≤8` และ recovery `≥10`
3. ระบุให้ชัดว่าค่า Measurement Change เป็นค่าตรวจการเปลี่ยนแปลง ไม่ใช่องศาความเสี่ยงทางคลินิก
4. ทดสอบค่า Blink Rate, Screen Distance ratio และระยะ Repeat Alert กับผู้ใช้จริง
5. ตัดสินใจว่าจะเพิ่ม Sitting Break Reminder ทุก 30 นาทีเป็น policy แยกหรือไม่

### 5.2 งานทดสอบความแม่นยำ

1. จัดทำคลิปทดสอบใหม่พร้อม Ground Truth
2. กำหนดช่วงเวลา `FIRST`, `REPEAT` และ `RESOLVED` ใน Ground Truth
3. วัด Precision, Recall, F1 Score และ False Alerts ต่อชั่วโมง
4. วัด Alert Latency ตั้งแต่เริ่มท่าทางจนถึง Popup
5. ทดสอบในสภาพแสง ระยะกล้อง มุมกล้อง และผู้ใช้หลายคน
6. ทดสอบ Blink Rate ให้ครบหน้าต่าง 60 วินาที
7. ทดสอบระยะใบหน้าอย่างน้อยสามระดับ ได้แก่ ปกติ ใกล้ และใกล้เกินไป
8. ปรับ threshold จากผล validation และบันทึก config version ใหม่

### 5.3 งานระบบและข้อมูล

1. บันทึก Repeat Notification ทุกครั้งใน Backend เพื่อให้จำนวนในรายงานตรงกับ Popup ที่ผู้ใช้เห็น
2. ตรวจสอบ Alert History, Session Summary และ Dashboard กับข้อมูล Supabase จริง
3. ทดสอบ Popup และเสียงตาม Settings ของผู้ใช้
4. ทดสอบ Data Gap, กล้องหลุด, Internet loss และการกลับมาทำงานต่อ
5. ทดสอบ Long Session พร้อม Minimize, Pause, Resume และ Stop
6. ทดสอบการปิดโปรแกรมและ Session Recovery
7. สร้างและทดสอบ Windows executable/installer

## 6. แผนการปรับเกณฑ์ที่แนะนำ

### ระยะที่ 1: คงค่าปัจจุบันและแก้คำอธิบาย

- คง RULA-adapted และคำเตือนว่าไม่ใช่ Full RULA
- คง Blink Rate `≤8` ชั่วคราว แต่แสดงว่าเป็น Wellness Screening
- คง Screen Distance ratio 1.25/1.15 ชั่วคราว
- แก้เอกสารทุกไฟล์ให้ตรงกับค่าที่โค้ดใช้จริง
- แสดงสถานะ `prototype_engineering_policy` ในข้อมูลภายในต่อไป

### ระยะที่ 2: Ground Truth Validation

- เก็บวิดีโอจากผู้ใช้หลายคน
- ให้ผู้ประเมินระบุช่วงท่าทางจริงและช่วงที่ควรแจ้งเตือน
- รันเครื่องมือ Alert Validation
- สร้าง Confusion Matrix และคำนวณ Precision, Recall และ F1
- เปรียบเทียบ threshold หลายชุดโดยไม่ปรับค่าจากคลิปเพียงชุดเดียว

### ระยะที่ 3: User Acceptance Test

- ทดสอบความถี่ Popup และเสียง
- เก็บข้อมูลว่าผู้ใช้ตอบสนองต่อ Alert หรือปิดทิ้ง
- ตรวจ Alert Fatigue จาก Repeat Alert 5 และ 10 นาที
- ทดลอง Break Reminder ทุก 30 นาทีแยกจาก Posture Alert

### ระยะที่ 4: Freeze Policy

- เลือกค่าที่ผ่านเกณฑ์ความแม่นยำ
- กำหนด Policy Version
- บันทึก threshold, แหล่งที่มา และข้อจำกัด
- Freeze เกณฑ์ก่อนทำ Regression และ Packaging

## 7. เกณฑ์ยอมรับก่อนปิดงาน

ระบบควรผ่านเงื่อนไขต่อไปนี้ก่อนถือว่าเกณฑ์แจ้งเตือนพร้อมใช้งาน

1. ไม่มีค่า threshold ในเอกสารที่ขัดกับโค้ด
2. RULA-adapted แสดงข้อจำกัดครบทุกหน้าที่เกี่ยวข้อง
3. Ground Truth แยกข้อมูล train/tuning ออกจากข้อมูลทดสอบสุดท้าย
4. มี Precision, Recall, F1 และ False Alerts ต่อชั่วโมงของแต่ละประเภท Alert
5. มีผลทดสอบ Alert Latency และ Resolved Latency
6. Blink Alert ไม่ประเมินก่อนข้อมูลครบ 60 วินาที
7. Data Gap ไม่ถูกตีความว่าเป็นท่าทางปกติหรือไม่กะพริบตา
8. Popup, เสียง, Persistence, History และ Summary ให้ผลตรงกัน
9. Repeat Alert ไม่สร้างรายการซ้ำจากการ retry ของเครือข่าย
10. ผ่านการทดสอบกับกล้องจริงและ Supabase จริงแบบ End-to-End

## 8. ข้อสรุป

PostGuard มีโครงสร้าง Alert Lifecycle ที่ค่อนข้างครบ ได้แก่ `FIRST`, `REPEAT`, `RESOLVED`, Data Gap, Popup, เสียง, Persistence และ Session Summary ส่วน RULA-adapted มีงานวิจัยรองรับแนวคิดหลักแล้ว แต่ยังมีข้อจำกัดจากกล้องด้านหน้าและองค์ประกอบ Shoulder Asymmetry ที่เป็นการประยุกต์ของระบบ

เกณฑ์ Blink Rate, Screen Distance และ Repeat Cooldown ยังเป็น Prototype Engineering Policy แม้วิธีลด False Alert เช่น Sliding Window, Confirmation Time และ Hysteresis จะออกแบบไว้อย่างเหมาะสมแล้วก็ตาม งานสำคัญที่เหลือคือการทำ Ground Truth Validation การวัดความแม่นยำ การทดลองกับผู้ใช้ และการจัดทำ Policy Version ก่อน Freeze ระบบ

## 9. เอกสารอ้างอิง

1. McAtamney, L. and Corlett, E. N. (1993). *RULA: a survey method for the investigation of work-related upper limb disorders*. Applied Ergonomics, 24(2), 91–99. DOI: [10.1016/0003-6870(93)90080-S](https://doi.org/10.1016/0003-6870(93)90080-S)
2. Jaschinski, W. et al. Preferred position of visual displays relative to the eyes: a field study of visual strain and individual differences. [PubMed PMID 9674376](https://pubmed.ncbi.nlm.nih.gov/9674376/)
3. The effects of visual display distance on eye accommodation, head posture, and vision and neck symptoms. [PubMed PMID 17915601](https://pubmed.ncbi.nlm.nih.gov/17915601/)
4. Comparative study on visual fatigue and blink frequency during display viewing. [PubMed PMID 31422638](https://pubmed.ncbi.nlm.nih.gov/31422638/)
5. Point-of-choice prompts to reduce sitting time at work: a randomized trial. [PubMed PMID 22898122](https://pubmed.ncbi.nlm.nih.gov/22898122/)
6. Comparing two break strategies on occupational sedentary behavior: a randomized trial. [PubMed PMID 27583200](https://pubmed.ncbi.nlm.nih.gov/27583200/)
7. เอกสารภายในโครงการ: `docs/RULA_MAPPING.md`
8. เอกสารภายในโครงการ: `docs/DETECTION_LIFECYCLE_IMPLEMENTATION_SUMMARY.md`
9. เกณฑ์ Measurement Change: `desktop/app/vision/session_monitoring/measurement_change_thresholds.json`

