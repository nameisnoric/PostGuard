import cv2, math, statistics

from PySide6.QtCore import (
    Qt,
    QTimer,
    Signal
)

from PySide6.QtGui import (
    QImage,
    QPixmap
)

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QGroupBox,
    QMessageBox
)

from app.services.detection_service import DetectionService
from app.services.api_client import APIClient


class BaselinePage(QWidget):

    # ส่งข้อมูลกล้องกลับไป MainWindow
    back_requested = Signal(dict)
    
    monitoring_requested = Signal(dict, int)

    def __init__(self):
        super().__init__()

        # -------------------------
        # Variables
        # -------------------------

        self.selected_camera = None
        self.capture = None
        self.detector = None
        self.frame_count = 0
        
        #Calibrate State
        
        self.is_calibrating = False
        self.calibration_samples = []
        self.baseline_result = None
        self.required_samples = 30
        #ความนิ่งของผู้ใช้
        self.stability_threshold = 2.0

        self.saved_baseline_id = None   
        # -------------------------
        # Camera Timer
        # -------------------------

        self.timer = QTimer(self)
        self.timer.setInterval(30)

        self.timer.timeout.connect(
            self.update_frame
        )

        # -------------------------
        # Main Layout
        # -------------------------

        layout = QVBoxLayout(self)

        # -------------------------
        # Title
        # -------------------------

        self.title_label = QLabel(
            "Personal Baseline"
        )

        self.description_label = QLabel(
            "Prepare your sitting posture "
            "before starting calibration."
        )

        # -------------------------
        # Camera Information
        # -------------------------

        camera_group = QGroupBox(
            "Selected Camera"
        )

        camera_layout = QVBoxLayout(
            camera_group
        )

        self.camera_name_label = QLabel(
            "Camera: Not selected"
        )

        self.device_label = QLabel(
            "Device: -"
        )

        self.camera_id_label = QLabel(
            "Camera ID: -"
        )

        self.resolution_label = QLabel(
            "Resolution: -"
        )

        camera_layout.addWidget(
            self.camera_name_label
        )

        camera_layout.addWidget(
            self.device_label
        )

        camera_layout.addWidget(
            self.camera_id_label
        )

        camera_layout.addWidget(
            self.resolution_label
        )

        # -------------------------
        # Camera Preview
        # -------------------------

        self.preview_label = QLabel(
            "Camera preview will appear here."
        )

        self.preview_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.preview_label.setMinimumSize(
            640,
            360
        )

        self.preview_label.setStyleSheet(
            """
            QLabel {
                background-color: #111111;
                border: 1px solid #444444;
                border-radius: 8px;
            }
            """
        )

        # -------------------------
        # Calibration Information
        # -------------------------

        calibration_group = QGroupBox(
            "Calibration"
        )

        calibration_layout = QVBoxLayout(
            calibration_group
        )

        self.instruction_label = QLabel(
            "1. Sit in your normal working position.\n"
            "2. Keep your head and shoulders relaxed.\n"
            "3. Face the camera directly.\n"
            "4. Keep your posture steady during calibration."
        )

        self.status_label = QLabel(
            "Status: Waiting for camera"
        )

        # -------------------------
        # Detection Information
        # -------------------------

        self.detection_label = QLabel(
            "Pose: Waiting | Face: Waiting"
        )

        self.shoulder_tilt_label = QLabel(
            "Shoulder Tilt: --"
        )

        self.neck_tilt_label = QLabel(
            "Neck Lateral Tilt: --"
        )

        calibration_layout.addWidget(
            self.instruction_label
        )

        calibration_layout.addWidget(
            self.status_label
        )

        calibration_layout.addWidget(
            self.detection_label
        )

        calibration_layout.addWidget(
            self.shoulder_tilt_label
        )

        calibration_layout.addWidget(
            self.neck_tilt_label
        )

        # -------------------------
        # Buttons
        # -------------------------

        button_layout = QHBoxLayout()

        self.back_button = QPushButton(
            "Back to Camera Preview"
        )

        self.calibrate_button = QPushButton(
            "Start Calibration"
        )
        
        self.save_button = QPushButton(
            "Save Personal Baseline"
        )
        #Save ไม่ได้จนกว่า calibrate จะเสร็จ
        self.save_button.setEnabled(False)
        
        self.monitor_button = QPushButton(
            "Start Monitoring"  
        )
        self.monitor_button.setEnabled(False)
        # ยังไม่เปิดจนกว่าจะทำ Calibration Logic
        self.calibrate_button.setEnabled(False)
        
        button_layout.addWidget(
            self.back_button
        )

        button_layout.addWidget(
            self.calibrate_button
        )
        
        button_layout.addWidget(
            self.save_button
        )
        
        button_layout.addWidget(
            self.monitor_button
        )

        # -------------------------
        # Add Widgets
        # -------------------------

        layout.addWidget(
            self.title_label
        )

        layout.addWidget(
            self.description_label
        )

        layout.addWidget(
            camera_group
        )

        layout.addWidget(
            self.preview_label,
            1
        )

        layout.addWidget(
            calibration_group
        )

        layout.addLayout(
            button_layout
        )

        # -------------------------
        # Events
        # -------------------------

        self.back_button.clicked.connect(
            self.handle_back
        )
        
        self.calibrate_button.clicked.connect(
            self.start_calibration
        )
        
        self.save_button.clicked.connect(
            self.save_baseline
        )
        
        self.monitor_button.clicked.connect(
            self.handle_start_monitoring
        )

    # =========================================================
    # Receive Camera
    # =========================================================

    def set_camera(
        self,
        camera: dict
    ) -> None:

        self.selected_camera = camera.copy()

        camera_id = camera.get(
            "camera_id"
        )

        camera_name = camera.get(
            "camera_name",
            "Unknown Camera"
        )

        device_index = camera.get(
            "device_index"
        )

        width = camera.get(
            "resolution_width"
        )

        height = camera.get(
            "resolution_height"
        )

        self.camera_id_label.setText(
            f"Camera ID: {camera_id}"
        )

        self.camera_name_label.setText(
            f"Camera: {camera_name}"
        )

        self.device_label.setText(
            f"Device: {device_index}"
        )

        self.resolution_label.setText(
            f"Resolution: {width}x{height}"
        )

        print(
            "BASELINE CAMERA:",
            self.selected_camera
        )

        # เปิด Webcam และ Detection
        self.start_camera_preview()

    # =========================================================
    # Start Camera Preview
    # =========================================================

    def start_camera_preview(self) -> None:

        # ปิดทรัพยากรเดิมก่อนเปิดใหม่
        self.stop_camera_preview()

        if self.selected_camera is None:
            return

        device_index = self.selected_camera.get(
            "device_index"
        )

        if device_index is None:

            self.status_label.setText(
                "Status: Camera not selected"
            )

            return

        # -------------------------
        # Open Webcam
        # -------------------------

        try:
            self.capture = cv2.VideoCapture(
                int(device_index)
            )

            if not self.capture.isOpened():
                raise RuntimeError(
                    "Unable to open the selected camera."
                )

        except Exception as error:

            self.stop_camera_preview()

            self.status_label.setText(
                "Status: Camera unavailable"
            )

            QMessageBox.warning(
                self,
                "Camera Error",
                str(error)
            )

            return

        # -------------------------
        # Initialize Detection
        # -------------------------

        try:
            self.detector = DetectionService()

        except Exception as error:

            self.stop_camera_preview()

            self.status_label.setText(
                "Status: Detection unavailable"
            )

            QMessageBox.critical(
                self,
                "Detection Error",
                str(error)
            )

            return

        # -------------------------
        # Start Timer
        # -------------------------

        self.frame_count = 0

        self.status_label.setText(
            "Status: Camera and detection ready"
        )

       # เปิดปุ่มเมื่อกล้องและ Detection พร้อมแล้ว  
        self.calibrate_button.setEnabled(True)

        self.calibrate_button.setText(
            "Start Calibration"
        )

        self.timer.start()

    #Start Calibration

    def start_calibration(self) -> None:

        if (
            self.capture is None
            or self.detector is None
        ):
            QMessageBox.warning(
                self,
                "Calibration",
                "Camera or detection is not ready."
            )
            return

        # เริ่มเก็บข้อมูลใหม่
        self.is_calibrating = True

        self.calibration_samples = []

        self.baseline_result = None
        
        self.saved_baseline_id = None
        self.save_button.setEnabled(False)
        self.monitor_button.setEnabled(False)

        self.calibrate_button.setEnabled(False)

        self.status_label.setText(
            "Status: Calibrating 0/30"
        )
        
    def collect_calibration_sample(
        self,
        result: dict
    ) -> None:

        if not self.is_calibrating:
            return

        shoulder = result.get("shoulder_tilt")
        neck_result = result.get("neck_lateral_tilt")

        # ต้องพบ Pose และ Face
        if (
            result.get("pose_points") is None
            or not result.get("face_detected")
            or shoulder is None
            or neck_result is None
        ):
            self.calibration_samples.clear()

            self.status_label.setText(
                "Status: Face and shoulders must be visible"
            )
            return

        neck = neck_result.get("neck_tilt")

        if neck is None:
            self.calibration_samples.clear()
            return

        # ตรวจสอบว่าค่าเป็นตัวเลขที่ใช้คำนวณได้
        if not (
            math.isfinite(shoulder)
            and math.isfinite(neck)
        ):
            self.calibration_samples.clear()
            return

        self.calibration_samples.append({
            "shoulder_tilt": shoulder,
            "neck_tilt": neck
        })

        count = len(self.calibration_samples)

        self.status_label.setText(
            f"Status: Calibrating {count}/{self.required_samples}"
        )

        if count < self.required_samples:
            return

        # แยกชุดข้อมูลสองประเภท
        shoulder_values = [
            sample["shoulder_tilt"]
            for sample in self.calibration_samples
        ]

        neck_values = [
            sample["neck_tilt"]
            for sample in self.calibration_samples
        ]

        # ตรวจสอบความกระจายของข้อมูล
        shoulder_std = statistics.pstdev(
            shoulder_values
        )

        neck_std = statistics.pstdev(
            neck_values
        )

        if (
            shoulder_std > self.stability_threshold
            or neck_std > self.stability_threshold
        ):
            self.calibration_samples.clear()

            self.status_label.setText(
                "Status: Movement detected. "
                "Collecting again..."
            )
            return

        # คำนวณค่าเฉลี่ยพื้นฐาน
        self.baseline_result = {
            "shoulder_tilt": statistics.mean(
                shoulder_values
            ),
            "neck_lateral_tilt": statistics.mean(
                neck_values
            ),
            "shoulder_std": shoulder_std,
            "neck_std": neck_std,
            "sample_count": count
        }   

        self.is_calibrating = False
        self.save_button.setEnabled(True)
        self.calibrate_button.setEnabled(True)
        self.calibrate_button.setText(
            "Recalibrate"
        )

        self.status_label.setText(
            "Status: Calibration completed"
        )

        QMessageBox.information(
            self,
            "Calibration Completed",
            (
                "Personal Baseline calculated.\n\n"
                f"Shoulder Tilt: "
                f"{self.baseline_result['shoulder_tilt']:+.2f}°\n"
                f"Neck Lateral Tilt: "
                f"{self.baseline_result['neck_lateral_tilt']:+.2f}°\n\n"
                f"Samples: {count}\n"
                "Not saved to database yet."
            )   
        )

        print(
            "PERSONAL BASELINE:",
            self.baseline_result
        )
    
    # =========================================================
    # Save Personal Baseline
    # =========================================================

    def save_baseline(self) -> None:

        # -------------------------
        # Validate Calibration
        # -------------------------

        if self.baseline_result is None:

            QMessageBox.warning(
                self,
                "Save Baseline",
                "Please complete calibration first."
            )

            return

        if self.selected_camera is None:

            QMessageBox.warning(
                self,
                "Save Baseline",
                "No camera selected."
            )

            return

        # ป้องกันการบันทึกซ้ำ
        if self.saved_baseline_id is not None:
            return

        camera_id = self.selected_camera.get(
            "camera_id"
        )

        if (
            not isinstance(camera_id, int)
            or camera_id <= 0
        ):

            QMessageBox.warning(
                self,
                "Save Baseline",
                "Invalid Camera ID."
            )

            return

        # -------------------------
        # Prepare Measurements
        # -------------------------

        measurements = {
            "shoulder_angle": (
                self.baseline_result["shoulder_tilt"]
            ),
            "lateral_tilt_baseline": (
                self.baseline_result["neck_lateral_tilt"]
            )
        }

        # -------------------------
        # Send to Backend
        # -------------------------

        self.save_button.setEnabled(False)

        self.status_label.setText(
            "Status: Saving baseline..."
        )

        try:

            response = APIClient.create_personal_baseline(
                camera_id=camera_id,
                measurements=measurements
            )

            # -------------------------
            # Check API Response
            # -------------------------

            if response.status_code != 201:

                try:
                    detail = response.json().get(
                        "detail",
                        response.text
                    )
                except ValueError:
                    detail = response.text

                raise RuntimeError(
                    f"HTTP {response.status_code}: {detail}"
                )

            saved_data = response.json()

            baseline_id = saved_data.get(
                "baseline_id"
            )

            if baseline_id is None:
                raise RuntimeError(
                    "Server did not return a Baseline ID."
                )

            # -------------------------
            # Save Successful
            # -------------------------

            self.saved_baseline_id = baseline_id
            
            self.monitor_button.setEnabled(True)

            self.status_label.setText(
                "Status: Baseline saved successfully"
            )

            print(
                "SAVED PERSONAL BASELINE:",
                saved_data
            )

            QMessageBox.information(
                self,
                "Baseline Saved",
                (
                    "Personal Baseline saved successfully!\n\n"
                    f"Baseline ID: {baseline_id}\n"
                    f"Camera ID: {camera_id}\n\n"
                    f"Shoulder Tilt: "
                    f"{self.baseline_result['shoulder_tilt']:+.2f}°\n"
                    f"Neck Lateral Tilt: "
                    f"{self.baseline_result['neck_lateral_tilt']:+.2f}°"
                )
            )

        except Exception as error:

            self.status_label.setText(
                "Status: Failed to save baseline"
            )

            QMessageBox.warning(
                self,
                "Save Baseline Error",
                str(error)
            )

        finally:

            # ถ้าบันทึกไม่สำเร็จ ให้ลองใหม่ได้
            # ถ้าสำเร็จแล้ว ป้องกันการบันทึกซ้ำ
            self.save_button.setEnabled(
                self.baseline_result is not None
                and self.saved_baseline_id is None
            )

    # =========================================================
    # Update Frame
    # =========================================================

    def update_frame(self) -> None:

        if self.capture is None:
            return

        # -------------------------
        # Read Webcam Frame 
        # -------------------------

        success, frame = self.capture.read()

        if not success or frame is None:

            self.stop_camera_preview()

            self.status_label.setText(
                "Status: Camera read failed"
            )

            QMessageBox.warning(
                self,
                "Camera Error",
                "Unable to read a camera frame."
            )

            return

        # -------------------------
        # Count Frames
        # -------------------------

        self.frame_count += 1

        # -------------------------
        # Detection Every 5 Frames
        # -------------------------

        if (
            self.detector is not None
            and self.frame_count % 5 == 0
        ):

            try:
                result = self.detector.process_frame(
                    frame
                )
                
                self.collect_calibration_sample(
                    result
                )

                # -------------------------
                # Pose / Face Status
                # -------------------------

                pose_detected = (
                    result["pose_points"] is not None
                )

                face_detected = result[
                    "face_detected"
                ]

                pose_text = (
                    "Detected"
                    if pose_detected
                    else "Not Found"
                )

                face_text = (
                    "Detected"
                    if face_detected
                    else "Not Found"
                )

                self.detection_label.setText(
                    f"Pose: {pose_text} | "
                    f"Face: {face_text}"
                )

                # -------------------------
                # Shoulder Tilt
                # -------------------------

                shoulder_tilt = result[
                    "shoulder_tilt"
                ]

                if shoulder_tilt is not None:

                    self.shoulder_tilt_label.setText(
                        f"Shoulder Tilt: "
                        f"{shoulder_tilt:+.2f}°"
                    )

                else:

                    self.shoulder_tilt_label.setText(
                        "Shoulder Tilt: --"
                    )

                # -------------------------
                # Neck Lateral Tilt
                # -------------------------

                neck_result = result[
                    "neck_lateral_tilt"
                ]

                if neck_result is not None:

                    neck_angle = neck_result[
                        "neck_tilt"
                    ]

                    self.neck_tilt_label.setText(
                        f"Neck Lateral Tilt: "
                        f"{neck_angle:+.2f}°"
                    )

                else:

                    self.neck_tilt_label.setText(
                        "Neck Lateral Tilt: --"
                    )

            except Exception as error:

                self.stop_camera_preview()

                self.status_label.setText(
                    "Status: Detection error"
                )

                QMessageBox.warning(
                    self,
                    "Detection Error",
                    str(error)
                )

                return

        # -------------------------
        # Convert Frame to RGB
        # -------------------------

        frame_rgb = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2RGB
        )

        height, width, channels = (
            frame_rgb.shape
        )

        bytes_per_line = (
            channels * width
        )

        # -------------------------
        # Convert to QImage
        # -------------------------

        image = QImage(
            frame_rgb.data,
            width,
            height,
            bytes_per_line,
            QImage.Format.Format_RGB888
        ).copy()

        # -------------------------
        # Display Frame
        # -------------------------

        pixmap = QPixmap.fromImage(
            image
        )

        pixmap = pixmap.scaled(
            self.preview_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )

        self.preview_label.setPixmap(
            pixmap
        )

    # =========================================================
    # Stop Camera Preview
    # =========================================================

    def stop_camera_preview(self) -> None:

        # -------------------------
        # Stop Timer
        # -------------------------

        if self.timer.isActive():
            self.timer.stop()

        # -------------------------
        # Close Detection
        # -------------------------

        if self.detector is not None:

            try:
                self.detector.close()

            finally:
                self.detector = None

        # -------------------------
        # Release Webcam
        # -------------------------

        if self.capture is not None:

            if self.capture.isOpened():
                self.capture.release()

            self.capture = None

        # -------------------------
        # Reset Detection Values
        # -------------------------

        self.frame_count = 0
        
        # -------------------------
        # Reset Calibration State
        # -------------------------
        self.monitor_button.setEnabled(False)
        self.is_calibrating = False

        self.calibration_samples.clear()

        self.baseline_result = None

        self.calibrate_button.setEnabled(False)

        self.calibrate_button.setText(
            "Start Calibration"
        )


        self.detection_label.setText(
            "Pose: Waiting | Face: Waiting"
        )

        self.shoulder_tilt_label.setText(
            "Shoulder Tilt: --"
        )

        self.neck_tilt_label.setText(
            "Neck Lateral Tilt: --"
        )

        # -------------------------
        # Reset Preview
        # -------------------------

        self.preview_label.clear()

        self.preview_label.setText(
            "Camera preview will appear here."
        )

        print(
            "BASELINE CAMERA STOPPED"
        )

    # =========================================================
    # Back to Camera Preview
    # =========================================================

    def handle_back(self) -> None:

        if self.selected_camera is None:

            QMessageBox.warning(
                self,
                "PostGuard",
                "No camera selected."
            )

            return

        camera = self.selected_camera.copy()

        self.stop_camera_preview()

        self.back_requested.emit(
            camera
        )
        


    # =========================================================
    # Stop Camera When Page Is Hidden
    # =========================================================

    def hideEvent(self, event) -> None:

        self.stop_camera_preview()

        super().hideEvent(event)
         
    def handle_start_monitoring(self) -> None:

        if (
            self.selected_camera is None
            or self.saved_baseline_id is None
        ):
            QMessageBox.warning(
                self,
                "Monitoring",
                "Please save your Personal Baseline first."
            )
            return

        camera = self.selected_camera.copy()
        baseline_id = self.saved_baseline_id

        # ปิดกล้องหน้า Baseline ก่อน
        # เพื่อไม่ให้เปิด Webcam ซ้อนกัน
        self.stop_camera_preview()

        self.monitoring_requested.emit(
            camera,
            baseline_id
        )

