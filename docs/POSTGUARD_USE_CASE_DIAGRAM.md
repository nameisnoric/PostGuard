# PostGuard Use Case Diagram

เอกสารนี้แสดง Use Case หลักของ PostGuard Desktop Application ตามขอบเขตระบบปัจจุบันและข้อกำหนด ToR

```mermaid
flowchart LR
    user([ผู้ใช้งาน])
    camera([กล้อง Webcam])
    email([Resend Email Service])
    database[(Backend / Supabase)]

    subgraph postguard[PostGuard Desktop Application]
        direction TB

        subgraph account[Account และ Privacy]
            register([สมัครสมาชิก])
            verifyOtp([ยืนยัน OTP])
            login([เข้าสู่ระบบ])
            resetPassword([ลืมและตั้งรหัสผ่านใหม่])
            changePassword([เปลี่ยนรหัสผ่าน])
            manageProfile([จัดการ Profile และรูปส่วนตัว])
            manageConsent([ให้หรือถอน Privacy Consent])
            manageSettings([ตั้งค่า Popup เสียง และช่วงแจ้งเตือน])
            deleteAccount([ขอลบบัญชีหรือกู้คืนบัญชี])
        end

        subgraph setup[Camera Setup และ Personal Baseline]
            scanCamera([ค้นหาและเลือกกล้อง])
            prepareCamera([เตรียมและปรับความเอียงกล้อง])
            previewCamera([ตรวจสอบภาพหลังปรับกล้อง])
            createBaseline([สร้าง Personal Baseline])
        end

        subgraph session[Monitoring Session]
            startSession([เริ่ม Monitoring Session])
            detectPosture([ตรวจจับท่าทางและการกะพริบตา])
            evaluateRisk([ประเมิน RULA-adapted Risk Score])
            checkDistance([ประเมินระยะห่างจากหน้าจอ])
            trackDuration([ติดตามระยะเวลาต่อเนื่อง])
            receiveAlert([รับ Popup และเสียงแจ้งเตือน])
            pauseSession([Pause หรือ Resume Session])
            miniControl([ควบคุม Session จากหน้าต่างเล็ก])
            stopSession([Stop และบันทึก Session])
            recoverSession([กู้สถานะ Session ที่จบไม่สมบูรณ์])
        end

        subgraph reports[Dashboard, History และ Report]
            dashboard([ดู Dashboard และแนวโน้ม Risk Score])
            history([ดูประวัติ Session])
            alertHistory([ดู Alert History])
            sessionReport([ดู Session Summary และ Report])
        end
    end

    user --> register
    user --> login
    user --> resetPassword
    user --> changePassword
    user --> manageProfile
    user --> manageConsent
    user --> manageSettings
    user --> deleteAccount

    register -. include .-> verifyOtp
    resetPassword -. include .-> verifyOtp
    verifyOtp --> email

    user --> scanCamera
    scanCamera -. include .-> prepareCamera
    prepareCamera -. include .-> previewCamera
    previewCamera -. include .-> createBaseline
    camera --> scanCamera
    camera --> prepareCamera
    camera --> previewCamera
    camera --> createBaseline

    user --> startSession
    startSession -. requires .-> manageConsent
    startSession -. include .-> detectPosture
    detectPosture -. include .-> evaluateRisk
    detectPosture -. include .-> checkDistance
    detectPosture -. include .-> trackDuration
    evaluateRisk -. extend .-> receiveAlert
    checkDistance -. extend .-> receiveAlert
    trackDuration -. extend .-> receiveAlert
    camera --> detectPosture

    user --> pauseSession
    user --> miniControl
    miniControl -. include .-> pauseSession
    miniControl -. include .-> stopSession
    user --> stopSession
    user --> recoverSession

    stopSession -. include .-> sessionReport
    user --> dashboard
    user --> history
    user --> alertHistory
    user --> sessionReport

    register --> database
    login --> database
    resetPassword --> database
    changePassword --> database
    manageProfile --> database
    manageConsent --> database
    manageSettings --> database
    deleteAccount --> database
    startSession --> database
    pauseSession --> database
    stopSession --> database
    recoverSession --> database
    receiveAlert --> database
    dashboard --> database
    history --> database
    alertHistory --> database
    sessionReport --> database

    classDef actor fill:#ffffff,stroke:#334155,stroke-width:2px,color:#0f172a;
    classDef usecase fill:#eef4ff,stroke:#2457d6,stroke-width:1.5px,color:#0f172a;
    classDef external fill:#f8fafc,stroke:#64748b,stroke-width:1.5px,color:#0f172a;
    class user actor;
    class camera,email,database external;
    class register,verifyOtp,login,resetPassword,changePassword,manageProfile,manageConsent,manageSettings,deleteAccount usecase;
    class scanCamera,prepareCamera,previewCamera,createBaseline usecase;
    class startSession,detectPosture,evaluateRisk,checkDistance,trackDuration,receiveAlert,pauseSession,miniControl,stopSession,recoverSession usecase;
    class dashboard,history,alertHistory,sessionReport usecase;
```

## Actor

| Actor | หน้าที่ |
| --- | --- |
| ผู้ใช้งาน | จัดการบัญชี ตั้งค่าระบบ เตรียมกล้อง สร้าง Baseline เริ่มและควบคุม Session รับการแจ้งเตือน และดูรายงาน |
| กล้อง Webcam | ส่งภาพให้ขั้นตอน Camera Setup, Personal Baseline และ Monitoring โดยประมวลผลภาพภายในเครื่อง |
| Resend Email Service | ส่ง OTP สำหรับการสมัครสมาชิกและการตั้งรหัสผ่านใหม่ |
| Backend / Supabase | ตรวจสอบสิทธิ์และเก็บข้อมูลผู้ใช้ Consent, Settings, Baseline, Session, Alert และ Report |

## ความสัมพันธ์สำคัญ

- การเริ่ม Monitoring ต้องมี Privacy Consent ที่ยังใช้งานอยู่
- Camera Setup, Camera Preparation, Adjusted Preview และ Personal Baseline เป็นขั้นตอนก่อนเริ่ม Session
- การตรวจจับท่าทางประกอบด้วยการประเมิน RULA-adapted, ระยะหน้าจอ และระยะเวลาที่ค้างท่า
- Popup และเสียงเป็นส่วนขยายที่เกิดเมื่อ Alert Policy ยืนยันว่าควรแจ้งเตือน
- เมื่อย่อหน้าต่าง ผู้ใช้ควบคุม Pause, Resume และ Stop ได้จากหน้าต่างขนาดเล็ก โดยยังใช้ Session เดิม
- เมื่อ Stop ระบบจบ Session บันทึกข้อมูล และสร้าง Session Summary
- Dashboard, History, Alert History และ Report อ่านเฉพาะข้อมูลของผู้ใช้ที่เข้าสู่ระบบ

