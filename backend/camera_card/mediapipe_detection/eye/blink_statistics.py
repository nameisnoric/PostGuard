import time
from collections import deque


# ==========================================================
# Prototype Parameters
# ==========================================================

DEFAULT_WINDOW_SECONDS = 60.0


# ==========================================================
# Blink Statistics
# ==========================================================

class BlinkStatistics:
    """
    รับ Blink Event จาก blink_detector.py
    แล้วคำนวณสถิติการกระพริบตา

    หน้าที่ของ class นี้:

    - เก็บ timestamp ของ blink
    - ใช้ 60-second sliding window
    - นับจำนวน blink ใน window
    - คำนวณ blink rate
    - เก็บเวลาของ blink ล่าสุด
    - คำนวณระยะห่างระหว่าง blink
    - บอกว่า window ครบ 60 วินาทีหรือยัง

    ไม่ทำหน้าที่:

    - ตัดสิน Eye Fatigue
    - ตัดสิน Drowsiness
    - สร้าง Alert
    - กำหนด Risk Level
    """

    def __init__(
        self,
        window_seconds=DEFAULT_WINDOW_SECONDS,
    ):

        self.window_seconds = float(
            window_seconds
        )

        if self.window_seconds <= 0:
            raise ValueError(
                "window_seconds must be > 0"
            )

        self.reset()


    # ======================================================
    # Reset
    # ======================================================

    def reset(self):

        # --------------------------------------------------
        # Session / Window
        # --------------------------------------------------

        self.started_at = None

        self.blink_timestamps = deque()


        # --------------------------------------------------
        # Blink Information
        # --------------------------------------------------

        self.blink_count_total = 0

        self.last_blink_time = None

        self.previous_blink_time = None

        self.inter_blink_interval = None


    # ======================================================
    # Start
    # ======================================================

    def start(
        self,
        timestamp=None,
    ):
        """
        เริ่ม Statistics ใหม่

        ใช้ตอนเริ่ม Monitoring
        หรือเริ่ม Session
        """

        if timestamp is None:
            timestamp = time.perf_counter()

        timestamp = float(timestamp)

        self.reset()

        self.started_at = timestamp


    # ======================================================
    # Window Ready
    # ======================================================

    def _window_ready(
        self,
        timestamp,
    ):
        """
        ตรวจว่ามีข้อมูลครบ window หรือยัง
        """

        if self.started_at is None:
            return False

        elapsed = (
            float(timestamp)
            -
            self.started_at
        )

        return (
            elapsed >= self.window_seconds
        )


    # ======================================================
    # Remove Expired Blink
    # ======================================================

    def _remove_expired(
        self,
        timestamp,
    ):
        """
        ลบ blink ที่เก่าเกิน 60 วินาที

        Sliding Window:

        timestamp - window_seconds
            <
        blink_timestamp
            <=
        timestamp
        """

        cutoff = (
            float(timestamp)
            -
            self.window_seconds
        )

        while self.blink_timestamps:

            oldest = (
                self.blink_timestamps[0]
            )

            if oldest <= cutoff:

                self.blink_timestamps.popleft()

            else:

                break


    # ======================================================
    # Update
    # ======================================================

    def update(
        self,
        blink_event=False,
        timestamp=None,
    ):
        """
        รับ Blink Event จาก blink_detector.py

        blink_event:
            True  = เกิด blink
            False = ไม่เกิด blink

        timestamp:
            timestamp ของ frame/event
        """

        if timestamp is None:
            timestamp = time.perf_counter()

        timestamp = float(timestamp)


        # ==================================================
        # Start Automatically
        # ==================================================

        if self.started_at is None:

            self.started_at = timestamp


        # ==================================================
        # Validate Timestamp
        # ==================================================

        if timestamp < self.started_at:

            raise ValueError(
                "timestamp cannot be earlier "
                "than statistics start time"
            )


        # ==================================================
        # Remove Expired Events
        # ==================================================

        self._remove_expired(
            timestamp
        )


        # ==================================================
        # New Blink Event
        # ==================================================

        if blink_event:

            self.blink_timestamps.append(
                timestamp
            )


            self.blink_count_total += 1


            # ----------------------------------------------
            # Inter-blink interval
            # ----------------------------------------------

            if (
                self.last_blink_time
                is not None
            ):

                self.previous_blink_time = (
                    self.last_blink_time
                )

                self.inter_blink_interval = (
                    timestamp
                    -
                    self.last_blink_time
                )

            else:

                self.previous_blink_time = None

                self.inter_blink_interval = None


            # ----------------------------------------------
            # Latest blink
            # ----------------------------------------------

            self.last_blink_time = (
                timestamp
            )


        # ==================================================
        # Sliding Window
        # ==================================================

        self._remove_expired(
            timestamp
        )


        blink_count_60s = len(
            self.blink_timestamps
        )


        # ==================================================
        # Window Ready
        # ==================================================

        window_ready = (
            self._window_ready(
                timestamp
            )
        )


        # ==================================================
        # Blink Rate
        # ==================================================

        if window_ready:

            blink_rate = float(
                blink_count_60s
            )

        else:

            blink_rate = None


        # ==================================================
        # Result
        # ==================================================

        return {

            "blink_count_total": (
                self.blink_count_total
            ),

            "blink_count_60s": (
                blink_count_60s
            ),

            "blink_rate": (
                blink_rate
            ),

            "last_blink_time": (
                self.last_blink_time
            ),

            "previous_blink_time": (
                self.previous_blink_time
            ),

            "inter_blink_interval": (
                self.inter_blink_interval
            ),

            "window_ready": (
                window_ready
            ),
        }