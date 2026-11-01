import time
from collections import deque


# ==========================================================
# Prototype Parameters
# ==========================================================

DEFAULT_WINDOW_SECONDS = 60.0
DEFAULT_MIN_VALID_SECONDS = 45.0
DEFAULT_MAX_SAMPLE_GAP_SECONDS = 2.0


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
        min_valid_seconds=DEFAULT_MIN_VALID_SECONDS,
        max_sample_gap_seconds=DEFAULT_MAX_SAMPLE_GAP_SECONDS,
    ):

        self.window_seconds = float(
            window_seconds
        )

        if self.window_seconds <= 0:
            raise ValueError(
                "window_seconds must be > 0"
            )

        self.min_valid_seconds = float(min_valid_seconds)
        self.max_sample_gap_seconds = float(max_sample_gap_seconds)
        if not 0 < self.min_valid_seconds <= self.window_seconds:
            raise ValueError("min_valid_seconds must be in (0, window_seconds]")
        if self.max_sample_gap_seconds <= 0:
            raise ValueError("max_sample_gap_seconds must be > 0")

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
        self.valid_intervals = deque()
        self.last_sample_at = None
        self.last_sample_valid = False
        self.last_valid_sample_at = None
        self.continuity_broken = False


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
            and self._valid_observation_seconds(timestamp) >= self.min_valid_seconds
            and not self.continuity_broken
        )

    def _remove_expired_intervals(self, timestamp):
        cutoff = float(timestamp) - self.window_seconds
        while self.valid_intervals and self.valid_intervals[0][1] <= cutoff:
            self.valid_intervals.popleft()
        if self.valid_intervals and self.valid_intervals[0][0] < cutoff:
            _, end = self.valid_intervals[0]
            self.valid_intervals[0] = (cutoff, end)

    def _valid_observation_seconds(self, timestamp):
        self._remove_expired_intervals(timestamp)
        return sum(max(0.0, end - start) for start, end in self.valid_intervals)

    def _break_continuity(self):
        """Discard an incomplete eye window after a prolonged invalid sample gap."""
        self.started_at = None
        self.blink_timestamps.clear()
        self.valid_intervals.clear()
        self.last_valid_sample_at = None
        self.last_blink_time = None
        self.previous_blink_time = None
        self.inter_blink_interval = None
        self.continuity_broken = True


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
        observation_valid=True,
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

        if self.last_sample_at is not None and timestamp < self.last_sample_at:
            raise ValueError("timestamp cannot be earlier than the previous sample")

        observation_valid = observation_valid is True
        if not observation_valid:
            if (
                self.last_valid_sample_at is not None
                and timestamp - self.last_valid_sample_at > self.max_sample_gap_seconds
            ):
                self._break_continuity()
            self.last_sample_at = timestamp
            self.last_sample_valid = False
            return {
                "blink_count_total": self.blink_count_total,
                "blink_count_60s": len(self.blink_timestamps),
                "blink_rate": None,
                "last_blink_time": self.last_blink_time,
                "previous_blink_time": self.previous_blink_time,
                "inter_blink_interval": self.inter_blink_interval,
                "window_ready": False,
                "observation_valid": False,
                "valid_observation_seconds": self._valid_observation_seconds(timestamp),
                "continuity_broken": self.continuity_broken,
            }


        # ==================================================
        # Start Automatically
        # ==================================================

        if self.started_at is None:

            self.started_at = timestamp

        if (
            self.last_valid_sample_at is not None
            and timestamp - self.last_valid_sample_at > self.max_sample_gap_seconds
        ):
            self._break_continuity()
            self.started_at = timestamp

        if self.last_valid_sample_at is not None and self.last_sample_valid:
            self.valid_intervals.append((self.last_valid_sample_at, timestamp))
        self.last_valid_sample_at = timestamp
        self.last_sample_at = timestamp
        self.last_sample_valid = True
        self.continuity_broken = False


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
            "observation_valid": True,
            "valid_observation_seconds": self._valid_observation_seconds(timestamp),
            "continuity_broken": self.continuity_broken,
        }
