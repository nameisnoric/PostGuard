import cv2
import numpy as np

class PostGuardCameraSetup:
    def __init__(self, frame_width=1280, frame_height=720):
        # 1. ข้อกำหนดทางกายภาพของ PostGuard Reference Card (ISO 7810 ID-1)
        self.W_REAL_MM = 85.60
        self.H_REAL_MM = 53.98
        self.CARD_ASPECT_RATIO = self.W_REAL_MM / self.H_REAL_MM # ~1.585
        
        # 2. ตั้งค่าขนาดกรอบนำสายตา (ROI) ให้อยู่กึ่งกลางหน้าจออัตโนมัติ
        self.roi_w = 400
        self.roi_h = 250
        self.roi_x = (frame_width - self.roi_w) // 2
        self.roi_y = (frame_height - self.roi_h) // 2
        
        # 3. ตัวแปรเก็บผลลัพธ์การคาลิเบรต
        self.perspective_matrix = None
        self.reference_pixel_scale = None # หน่วย: mm/pixel
        self.is_camera_ready = False
        
        # 4. ระบบตรวจสอบความนิ่งคงที่ (Stability Auto-Lock)
        self.stable_frames_required = 15 # ต้องเจอบัตรนิ่งๆ ติดกัน 15 เฟรม (~0.5 วินาที)
        self.stable_frame_count = 0
        self.last_pixel_width = 0

    def order_points_relative(self, pts):
        """ จัดระเบียบพิกัด 4 มุมของการ์ดให้อยู่ในลำดับ: [บนซ้าย, บนขวา, ล่างขวา, ล่างซ้าย] """
        pts = pts.reshape(4, 2)
        rect = np.zeros((4, 2), dtype="float32")
        
        s = pts.sum(axis=1)
        rect[0] = pts[np.argmin(s)] # บนซ้าย
        rect[2] = pts[np.argmax(s)] # ล่างขวา
        
        diff = np.diff(pts, axis=1)
        rect[1] = pts[np.argmin(diff)] # บนขวา
        rect[3] = pts[np.argmax(diff)] # ล่างซ้าย
        return rect

    def process_setup(self, frame):
        """ ท่อประมวลผลกล้องต้นทาง บีบพื้นที่ตรวจจับเฉพาะในกรอบ ROI """
        display_frame = frame.copy()
        
        # 1. ตัดภาพเฉพาะพื้นที่ในกรอบนำสายตา (Region of Interest - ROI) เพื่อส่งให้ OpenCV สแกน
        roi_img = frame[self.roi_y:self.roi_y+self.roi_h, self.roi_x:self.roi_x+self.roi_w]
        
        # 2. ทำ Image Pre-processing ภายใน ROI
        gray = cv2.cvtColor(roi_img, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edged = cv2.Canny(blurred, 40, 130)
        
        # 3. ค้นหาเค้าโครงสี่เหลี่ยมผืนผ้า (Contours)
        contours, _ = cv2.findContours(edged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours = sorted(contours, key=cv2.contourArea, reverse=True)[:3]
        
        card_detected = False
        card_contour_global = None
        
        for c in contours:
            peri = cv2.arcLength(c, True)
            approx = cv2.approxPolyDP(c, 0.02 * peri, True)
            
            # ตรวจสอบเบื้องต้นภายในกรอบ (พื้นที่ต้องใหญ่พอสมควรเมื่อเทียบกับขนาดกรอบ)
            if len(approx) == 4 and cv2.contourArea(c) > 15000:
                pts_local = self.order_points_relative(approx)
                (tl, tr, br, bl) = pts_local
                
                # คำนวณขนาดความกว้างความสูงพิกเซลของการ์ดภายใน ROI
                w_pixel = (np.linalg.norm(tr - tl) + np.linalg.norm(br - bl)) / 2
                h_pixel = (np.linalg.norm(tl - bl) + np.linalg.norm(tr - br)) / 2
                
                # ตรวจสอบสัดส่วนสี่เหลี่ยมผืนผ้า (Aspect Ratio) เพื่อยืนยันตัวตนของ Card
                detected_ratio = w_pixel / h_pixel
                if 1.4 < detected_ratio < 1.75: # ขอบเขตยอมรับรอบค่าสากล 1.585
                    card_detected = True
                    
                    # แปลงพิกัดสี่เหลี่ยมจาก Local (ในกรอบ ROI) ให้กลับเป็น Global (พิกัดหน้าจอหลัก) เพื่อใช้วาด UI
                    card_contour_global = approx.copy()
                    card_contour_global[:, 0, 0] += self.roi_x
                    card_contour_global[:, 0, 1] += self.roi_y
                    
                    # หากระบบยังไม่ได้ทำการล็อกค่าคงที่สำเร็จ
                    if not self.is_camera_ready:
                        current_scale = self.W_REAL_MM / w_pixel
                        
                        # ตรวจสอบเงื่อนไขความนิ่ง: บัตรต้องไม่ขยับสั่นเกิน 3 พิกเซลหน้าจอ
                        if abs(w_pixel - self.last_pixel_width) < 3:
                            self.stable_frame_count += 1
                        else:
                            self.stable_frame_count = 0
                            
                        self.last_pixel_width = w_pixel
                        
                        # บัตรนิ่งผ่านเงื่อนไข -> ทำการล็อกค่าคาลิเบรตทันที
                        if self.stable_frame_count >= self.stable_frames_required:
                            # แปลงจุดมุมของการ์ดเป็นพิกัด Global ก่อนทำ Perspective Transform
                            pts_global = pts_local.copy()
                            pts_global[:, 0] += self.roi_x
                            pts_global[:, 1] += self.roi_y
                            
                            # กำหนดเป้าหมายปลายทางสำหรับสร้างแผ่นระนาบอ้างอิงหน้าตรง
                            dst_pts = np.array([
                                [w_pixel - 1, 0],
                                [w_pixel - 1, h_pixel - 1],
                                [0, h_pixel - 1]
                            ], dtype="float32")
                            
                            # คำนวณและบันทึกข้อมูลสำคัญลงระบบ PostGuard
                            self.perspective_matrix = cv2.getPerspectiveTransform(pts_global, dst_pts)
                            self.reference_pixel_scale = current_scale
                            self.is_camera_ready = True
                    break
                    
        # 4. วาดเส้นบอกสถานะและไกด์ไลน์ UI บนหน้าจอหลัก
        self.draw_postguard_ui(display_frame, card_detected, card_contour_global)
        return display_frame

    def draw_postguard_ui(self, frame, card_detected, card_contour_global):
        """ จัดการการวาดเส้นกรอบนำสายตาและแผงควบคุม Dashboard ด้านบน """
        # เลือกสีตามสถานะความพร้อมของระบบ
        if self.is_camera_ready:
            status_text = "Status: CAMERA READY"
            status_color = (0, 255, 0)       # สีเขียว
            roi_color = (0, 255, 0)          # กรอบนำสายตาสีเขียวทึบ
            instruction = "Action: Setup Complete! You can remove the card."
            scale_text = f"Reference Scale: {self.reference_pixel_scale:.4f} mm/px"
        elif card_detected:
            status_text = "Status: CALCULATING..."
            status_color = (0, 165, 255)     # สีส้ม
            roi_color = (0, 165, 255)        # กรอบสี่เหลี่ยมสีส้มกระพริบตามบัตร
            instruction = "Action: Hold the card steady inside the box."
            scale_text = "Reference Scale: Analyzing constraints..."
        else:
            status_text = "Status: ADJUST CAMERA"
            status_color = (0, 0, 255)       # สีแดง
            roi_color = (255, 255, 255)      # กรอบไกด์ไลน์สีขาวนิ่ง
            instruction = "Action: Align your PostGuard Card with the box."
            scale_text = "Reference Scale: Waiting for reference plane..."

        # วาดกรอบสี่เหลี่ยมนำสายตา (ROI Box Guide) ตรงกลางจอให้ผู้ใช้วางการ์ดทาบ
        cv2.rectangle(frame, (self.roi_x, self.roi_y), (self.roi_x + self.roi_w, self.roi_y + self.roi_h), roi_color, 2)
        
        # วาดเส้นขอบเรืองแสงรอบตัวการ์ดจริงหากตรวจจับเจอ
        if card_detected and card_contour_global is not None:
            cv2.drawContours(frame, [card_contour_global], -1, status_color, 3)

        # วาดแถบ Dashboard พื้นหลังโปร่งแสงบริเวณมุมซ้ายบน
        overlay = frame.copy()
        cv2.rectangle(overlay, (20, 20), (500, 165), (30, 30, 30), -1)
        cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)
        
        # พิมพ์ข้อความแสดงรายละเอียดทั้งหมดของสถานะระบบ
        cv2.putText(frame, "--- PostGuard Camera Setup Workflow ---", (35, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)
        cv2.putText(frame, status_text, (35, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.6, status_color, 2)
        cv2.putText(frame, scale_text, (35, 115), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (230, 230, 230), 1)
        cv2.putText(frame, instruction, (35, 145), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (190, 190, 190), 1)

# --- ส่วนของการเปิดกล้องวิดีโอเพื่อทดสอบโมดูลสแกนการ์ด ---
if __name__ == "__main__":
    # เปิดสตรีมกล้องเว็บแคมโน้ตบุ๊กที่ความละเอียดมาตรฐาน 1280x720
    WIDTH, HEIGHT = 1280, 720
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)
    
    # เริ่มต้นระบบกล้องและกรอบ ROI
    setup_system = PostGuardCameraSetup(frame_width=WIDTH, frame_height=HEIGHT)
    
    # แก้ไขบรรทัดที่ 103 จากเดิมที่เป็นภาษาไทย ให้เป็นภาษาอังกฤษ
    print("PostGuard: Camera setup system started. Press 'q' to quit.")

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret: 
            break
        
        # ปรับการแสดงผลภาพให้กลับด้านซ้ายขวาเพื่อให้ผู้ใช้ส่องใช้งานได้เป็นธรรมชาติเหมือนกระจกเงา
        frame = cv2.flip(frame, 1)
        
        # ประมวลผลภาพในลูปวิดีโอ
        output_frame = setup_system.process_setup(frame)
        
        # แสดงผลหน้าต่างโปรแกรม
        cv2.imshow("PostGuard - Seamless Camera Setup Workflow", output_frame)
        
        # หากระบบเซ็ตอัปเรียบร้อย (Ready) และผู้ใช้ต้องการกดผ่านเพื่อไปเก็บสเต็ป Baseline ต่อ
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
            
    cap.release()
    cv2.destroyAllWindows()
