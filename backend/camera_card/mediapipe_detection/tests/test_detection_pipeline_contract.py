import math
import sys
import time

from pathlib import Path

import cv2


# ==========================================================
# Python Path Setup
#
# File:
# camera_card/
#   mediapipe_detection/
#       tests/
#           test_detection_pipeline_contract.py
#
# parents[2] = camera_card
#
# ทำให้สามารถรันไฟล์นี้ตรง ๆ ได้:
#
# python test_detection_pipeline_contract.py
# ==========================================================

CAMERA_CARD_DIR = (
    Path(__file__)
    .resolve()
    .parents[2]
)


if str(
    CAMERA_CARD_DIR
) not in sys.path:

    sys.path.insert(
        0,
        str(
            CAMERA_CARD_DIR
        )
    )


# ==========================================================
# Detection Pipeline
# ==========================================================

from mediapipe_detection.detection_pipeline import (
    DetectionPipeline,
)


# ==========================================================
# Allowed Feature Status
# ==========================================================

VALID_STATUSES = {

    "validated_prototype",

    "candidate",

    "experimental",

    "diagnostic",
}


# ==========================================================
# Validate Single Feature Contract
# ==========================================================

def validate_feature(
    name,
    feature
):
    """
    ตรวจว่า Feature Result
    มีโครงสร้างตรงกับ Detection Contract
    """


    # ======================================================
    # Must be Dictionary
    # ======================================================

    if not isinstance(
        feature,
        dict
    ):

        raise AssertionError(

            f"{name}: "
            "feature must be dict"
        )


    # ======================================================
    # Common Required Fields
    # ======================================================

    for key in (

        "valid",

        "reason",

        "status",
    ):

        if key not in feature:

            raise AssertionError(

                f"{name}: "
                f"missing '{key}'"
            )


    # ======================================================
    # valid must be bool
    # ======================================================

    if not isinstance(
        feature[
            "valid"
        ],
        bool
    ):

        raise AssertionError(

            f"{name}: "
            "valid must be bool"
        )


    # ======================================================
    # Validate Feature Status
    # ======================================================

    if (

        feature[
            "status"
        ]

        not in

        VALID_STATUSES

    ):

        raise AssertionError(

            f"{name}: "
            "unexpected status "

            f"{feature['status']!r}"
        )


    # ======================================================
    # Shoulder Elevation
    #
    # มีค่าซ้าย/ขวา
    # ไม่ได้ใช้ value เดียว
    # ======================================================

    if (
        name
        ==
        "shoulder_elevation"
    ):

        for side in (

            "left",

            "right",
        ):

            if side not in feature:

                raise AssertionError(

                    f"{name}: "
                    f"missing '{side}'"
                )


        # --------------------------------------------------
        # Invalid Shoulder Elevation
        #
        # ต้องเป็น None
        # ห้ามแทนด้วย 0
        # --------------------------------------------------

        if not feature[
            "valid"
        ]:

            if (

                feature[
                    "left"
                ]
                is not None

                or

                feature[
                    "right"
                ]
                is not None

            ):

                raise AssertionError(

                    f"{name}: "

                    "invalid result must "
                    "have left/right=None"
                )

        else:

            # ----------------------------------------------
            # Valid left
            # ----------------------------------------------

            left = feature[
                "left"
            ]

            if (

                isinstance(
                    left,
                    bool
                )

                or

                not isinstance(
                    left,
                    (int, float)
                )

                or

                not math.isfinite(
                    float(left)
                )

            ):

                raise AssertionError(

                    f"{name}: "
                    "left is not finite"
                )


            # ----------------------------------------------
            # Valid right
            # ----------------------------------------------

            right = feature[
                "right"
            ]

            if (

                isinstance(
                    right,
                    bool
                )

                or

                not isinstance(
                    right,
                    (int, float)
                )

                or

                not math.isfinite(
                    float(right)
                )

            ):

                raise AssertionError(

                    f"{name}: "
                    "right is not finite"
                )


        return


    # ======================================================
    # Normal Single-value Feature
    # ======================================================

    if "value" not in feature:

        raise AssertionError(

            f"{name}: "
            "missing 'value'"
        )


    # ======================================================
    # Invalid Feature
    #
    # INVALID ≠ 0
    # ======================================================

    if not feature[
        "valid"
    ]:

        if (

            feature[
                "value"
            ]

            is not None

        ):

            raise AssertionError(

                f"{name}: "

                "invalid result must "
                "have value=None"
            )


        return


    # ======================================================
    # Valid Feature
    # ======================================================

    value = feature[
        "value"
    ]


    if (

        isinstance(
            value,
            bool
        )

        or

        not isinstance(
            value,
            (int, float)
        )

        or

        not math.isfinite(
            float(value)
        )

    ):

        raise AssertionError(

            f"{name}: "
            "valid value is not finite"
        )


# ==========================================================
# Validate Full Detection Contract
# ==========================================================

def validate_contract(
    result
):
    """
    ตรวจ Output ของ DetectionPipeline
    ทุก Frame
    """


    # ======================================================
    # Contract Version
    # ======================================================

    if (

        result.get(
            "contract_version"
        )

        !=

        "1.0"

    ):

        raise AssertionError(

            "contract_version "
            "must be 1.0"
        )


    # ======================================================
    # Top-level Required Keys
    # ======================================================

    required_top_level = (

        "timestamp",

        "pose_detected",

        "face_detected",

        "features",

        "eye",

        "landmarks",
    )


    for key in required_top_level:

        if key not in result:

            raise AssertionError(

                "Missing top-level key: "
                f"{key}"
            )


    # ======================================================
    # Detection Availability Type
    # ======================================================

    if not isinstance(

        result[
            "pose_detected"
        ],

        bool

    ):

        raise AssertionError(

            "pose_detected "
            "must be bool"
        )


    if not isinstance(

        result[
            "face_detected"
        ],

        bool

    ):

        raise AssertionError(

            "face_detected "
            "must be bool"
        )


    # ======================================================
    # Features
    # ======================================================

    features = result[
        "features"
    ]


    if not isinstance(
        features,
        dict
    ):

        raise AssertionError(

            "features must be dict"
        )


    required_features = (

        "shoulder_tilt",

        "shoulder_elevation",

        "neck_lateral_tilt",

        "neck_flexion",

        "head_yaw",

        "head_roll",

        "forward_head",

        "torso_orientation",

        "eye_distance",
    )


    for name in required_features:

        if name not in features:

            raise AssertionError(

                "Missing feature: "
                f"{name}"
            )


        validate_feature(

            name,

            features[
                name
            ],
        )


    # ======================================================
    # Locked Maturity Rules
    # ======================================================

    # ------------------------------------------------------
    # Shoulder Tilt
    # ------------------------------------------------------

    if (

        features[
            "shoulder_tilt"
        ][
            "status"
        ]

        !=

        "validated_prototype"

    ):

        raise AssertionError(

            "shoulder_tilt must be "
            "validated_prototype"
        )


    # ------------------------------------------------------
    # Neck Lateral Tilt
    # ------------------------------------------------------

    if (

        features[
            "neck_lateral_tilt"
        ][
            "status"
        ]

        !=

        "validated_prototype"

    ):

        raise AssertionError(

            "neck_lateral_tilt must be "
            "validated_prototype"
        )


    # ------------------------------------------------------
    # Neck Flexion
    # ------------------------------------------------------

    if (

        features[
            "neck_flexion"
        ][
            "status"
        ]

        !=

        "validated_prototype"

    ):

        raise AssertionError(

            "neck_flexion must be "
            "validated_prototype"
        )


    # ------------------------------------------------------
    # Relative Eye Distance
    # ------------------------------------------------------

    if (

        features[
            "eye_distance"
        ][
            "status"
        ]

        !=

        "validated_prototype"

    ):

        raise AssertionError(

            "eye_distance must be "
            "validated_prototype"
        )


    # ------------------------------------------------------
    # Forward Head
    #
    # ห้าม Promote ตอนนี้
    # ------------------------------------------------------

    if (

        features[
            "forward_head"
        ][
            "status"
        ]

        !=

        "experimental"

    ):

        raise AssertionError(

            "forward_head must remain "
            "experimental"
        )


    # ------------------------------------------------------
    # Torso Orientation
    #
    # ยังไม่ผ่าน Final Validation
    # ------------------------------------------------------

    if (

        features[
            "torso_orientation"
        ][
            "status"
        ]

        !=

        "experimental"

    ):

        raise AssertionError(

            "torso_orientation must remain "
            "experimental"
        )


    # ======================================================
    # Eye
    # ======================================================

    eye = result[
        "eye"
    ]


    if not isinstance(
        eye,
        dict
    ):

        raise AssertionError(

            "eye must be dict"
        )


    required_eye_keys = (

        "measurement_valid",

        "measurement",

        "state",

        "blink",

        "closure",

        "validation",
    )


    for key in required_eye_keys:

        if key not in eye:

            raise AssertionError(

                "Eye output missing: "
                f"{key}"
            )


    # ======================================================
    # Eye Measurement Valid
    # ======================================================

    if not isinstance(

        eye[
            "measurement_valid"
        ],

        bool

    ):

        raise AssertionError(

            "eye.measurement_valid "
            "must be bool"
        )


    # ======================================================
    # Eye State
    # ======================================================

    eye_state = eye[
        "state"
    ]


    if not isinstance(
        eye_state,
        dict
    ):

        raise AssertionError(

            "eye.state "
            "must be dict"
        )


    # ======================================================
    # Blink Result
    # ======================================================

    blink = eye[
        "blink"
    ]


    if not isinstance(
        blink,
        dict
    ):

        raise AssertionError(

            "eye.blink "
            "must be dict"
        )


    required_blink_keys = (

        "blink_event",

        "blink_count",

        "last_blink_time",

        "last_blink_duration",

        "detector_state",

        "reason",
    )


    for key in required_blink_keys:

        if key not in blink:

            raise AssertionError(

                "Blink output missing: "
                f"{key}"
            )


    if not isinstance(

        blink[
            "blink_event"
        ],

        bool

    ):

        raise AssertionError(

            "blink_event "
            "must be bool"
        )


    if not isinstance(

        blink[
            "blink_count"
        ],

        int

    ):

        raise AssertionError(

            "blink_count "
            "must be int"
        )


    # ======================================================
    # Long Closure Result
    # ======================================================

    closure = eye[
        "closure"
    ]


    if not isinstance(
        closure,
        dict
    ):

        raise AssertionError(

            "eye.closure "
            "must be dict"
        )


    required_closure_keys = (

        "eye_closure_active",

        "eye_closure_duration",

        "long_closure_event",

        "long_closure_count",

        "long_closure_detected",

        "detector_state",

        "reason",
    )


    for key in required_closure_keys:

        if key not in closure:

            raise AssertionError(

                "Closure output missing: "
                f"{key}"
            )


    if not isinstance(

        closure[
            "long_closure_event"
        ],

        bool

    ):

        raise AssertionError(

            "long_closure_event "
            "must be bool"
        )


    if not isinstance(

        closure[
            "long_closure_count"
        ],

        int

    ):

        raise AssertionError(

            "long_closure_count "
            "must be int"
        )


# ==========================================================
# Main
# ==========================================================

def main():

    print()

    print(
        "=============================================="
    )

    print(
        "POSTGUARD DETECTION PIPELINE CONTRACT TEST"
    )

    print(
        "=============================================="
    )

    print()

    print(
        "This test checks:"
    )

    print(
        "- DetectionPipeline output structure"
    )

    print(
        "- Feature validity contract"
    )

    print(
        "- Feature maturity status"
    )

    print(
        "- Eye State integration"
    )

    print(
        "- Blink integration"
    )

    print(
        "- Long Closure integration"
    )

    print()

    print(
        "INSTRUCTION:"
    )

    print(
        "1. Sit normally"
    )

    print(
        "2. Look directly at the camera"
    )

    print(
        "3. Keep both eyes naturally open "
        "during calibration"
    )

    print(
        "4. Blink naturally 2-3 times "
        "after calibration"
    )

    print()

    print(
        "Q / ESC = stop early"
    )


    # ======================================================
    # Open Camera
    # ======================================================

    cap = cv2.VideoCapture(
        0
    )


    if not cap.isOpened():

        raise RuntimeError(
            "Cannot open camera 0"
        )


    # ======================================================
    # Resolution
    # ======================================================

    cap.set(

        cv2.CAP_PROP_FRAME_WIDTH,

        1280
    )


    cap.set(

        cv2.CAP_PROP_FRAME_HEIGHT,

        720
    )


    # ======================================================
    # Detection Pipeline
    # ======================================================

    pipeline = (

        DetectionPipeline()
    )


    # ======================================================
    # Start Eye Calibration
    # ======================================================

    pipeline.start_eye_calibration()


    print()

    print(
        "Eye Calibration Started"
    )

    print(
        "Keep both eyes naturally open."
    )


    # ======================================================
    # Runtime Counters
    # ======================================================

    started_at = (

        time.perf_counter()
    )


    frame_count = 0

    schema_pass_count = 0


    pose_detected_count = 0

    face_detected_count = 0


    blink_event_count = 0

    long_closure_event_count = 0


    last_result = None


    # ======================================================
    # Main Loop
    # ======================================================

    try:

        while True:

            # ==============================================
            # Read Raw Frame
            # ==============================================

            success, raw_frame = (

                cap.read()
            )


            if (

                not success

                or

                raw_frame is None

            ):

                raise RuntimeError(

                    "Camera frame "
                    "read failed"
                )


            now = (

                time.perf_counter()
            )


            # ==============================================
            # Detection
            #
            # IMPORTANT:
            # raw_frame = UNMIRRORED
            # ==============================================

            result = (

                pipeline.process_frame(

                    raw_frame,

                    timestamp=now,
                )
            )


            last_result = (
                result
            )


            # ==============================================
            # Contract Validation
            # ==============================================

            validate_contract(
                result
            )


            schema_pass_count += 1

            frame_count += 1


            # ==============================================
            # Detection Counts
            # ==============================================

            if result[
                "pose_detected"
            ]:

                pose_detected_count += 1


            if result[
                "face_detected"
            ]:

                face_detected_count += 1


            # ==============================================
            # Eye Output
            # ==============================================

            eye = result[
                "eye"
            ]


            blink_result = eye[
                "blink"
            ]


            closure_result = eye[
                "closure"
            ]


            # ==============================================
            # Blink Event
            # ==============================================

            if blink_result[
                "blink_event"
            ]:

                blink_event_count += 1


                print(

                    "BLINK EVENT | "

                    "count=",

                    blink_event_count,

                    "| duration=",

                    blink_result.get(
                        "last_blink_duration"
                    ),
                )


            # ==============================================
            # Long Closure Event
            # ==============================================

            if closure_result[
                "long_closure_event"
            ]:

                long_closure_event_count += 1


                print(

                    "LONG CLOSURE EVENT | "

                    "count=",

                    long_closure_event_count,

                    "| duration=",

                    closure_result.get(
                        "eye_closure_duration"
                    ),
                )


            # ==============================================
            # Eye State
            # ==============================================

            eye_state = (

                eye[
                    "state"
                ].get(

                    "eye_state",

                    "UNKNOWN",
                )
            )


            calibrated = bool(

                eye[
                    "state"
                ].get(

                    "calibrated",

                    False,
                )
            )


            # ==============================================
            # Display
            #
            # Mirror ONLY Display
            # ==============================================

            display = (

                cv2.flip(

                    raw_frame.copy(),

                    1
                )
            )


            # ==============================================
            # UI Text
            # ==============================================

            cv2.putText(

                display,

                (
                    "PostGuard "
                    "Detection Contract 1.0"
                ),

                (20, 35),

                cv2.FONT_HERSHEY_SIMPLEX,

                0.65,

                (255, 255, 255),

                2,
            )


            cv2.putText(

                display,

                (
                    "Pose: "
                    f"{result['pose_detected']} "
                    "| "
                    "Face: "
                    f"{result['face_detected']}"
                ),

                (20, 70),

                cv2.FONT_HERSHEY_SIMPLEX,

                0.55,

                (255, 255, 255),

                1,
            )


            cv2.putText(

                display,

                (
                    "Eye Calibration: "
                    f"{calibrated}"
                ),

                (20, 105),

                cv2.FONT_HERSHEY_SIMPLEX,

                0.55,

                (255, 255, 255),

                1,
            )


            cv2.putText(

                display,

                (
                    "Eye State: "
                    f"{eye_state}"
                ),

                (20, 140),

                cv2.FONT_HERSHEY_SIMPLEX,

                0.55,

                (255, 255, 255),

                1,
            )


            cv2.putText(

                display,

                (
                    "Blink Events: "
                    f"{blink_event_count}"
                ),

                (20, 175),

                cv2.FONT_HERSHEY_SIMPLEX,

                0.55,

                (255, 255, 255),

                1,
            )


            cv2.putText(

                display,

                (
                    "Long Closure Events: "
                    f"{long_closure_event_count}"
                ),

                (20, 210),

                cv2.FONT_HERSHEY_SIMPLEX,

                0.55,

                (255, 255, 255),

                1,
            )


            cv2.putText(

                display,

                (
                    "Forward Head Status: "
                    +
                    result[
                        "features"
                    ][
                        "forward_head"
                    ][
                        "status"
                    ]
                ),

                (20, 245),

                cv2.FONT_HERSHEY_SIMPLEX,

                0.50,

                (0, 255, 255),

                1,
            )


            cv2.putText(

                display,

                (
                    "Torso Status: "
                    +
                    result[
                        "features"
                    ][
                        "torso_orientation"
                    ][
                        "status"
                    ]
                ),

                (20, 280),

                cv2.FONT_HERSHEY_SIMPLEX,

                0.50,

                (0, 255, 255),

                1,
            )


            cv2.putText(

                display,

                "Q / ESC = Quit",

                (
                    20,

                    display.shape[
                        0
                    ]
                    -
                    25
                ),

                cv2.FONT_HERSHEY_SIMPLEX,

                0.50,

                (255, 255, 255),

                1,
            )


            cv2.imshow(

                "PostGuard - Detection Contract Test",

                display
            )


            # ==============================================
            # Keyboard
            # ==============================================

            key = (

                cv2.waitKey(
                    1
                )

                &

                0xFF
            )


            if key in (

                ord("q"),

                ord("Q"),

                27,

            ):

                break


            # ==============================================
            # Automatic Finish
            #
            # 15 seconds
            # ==============================================

            elapsed = (

                now
                -
                started_at
            )


            if elapsed >= 15.0:

                break


    # ======================================================
    # Cleanup
    # ======================================================

    finally:

        pipeline.close()

        cap.release()

        cv2.destroyAllWindows()


    # ======================================================
    # Performance
    # ======================================================

    total_time = max(

        time.perf_counter()
        -
        started_at,

        1e-6,
    )


    average_fps = (

        frame_count
        /
        total_time
    )


    # ======================================================
    # Report
    # ======================================================

    print()

    print(
        "=============================================="
    )

    print(
        "FINAL RESULT"
    )

    print(
        "=============================================="
    )


    print(

        "Frames             :",

        frame_count
    )


    print(

        "Schema Pass Frames :",

        schema_pass_count
    )


    print(

        "Pose Detected      :",

        pose_detected_count
    )


    print(

        "Face Detected      :",

        face_detected_count
    )


    print(

        "Blink Events       :",

        blink_event_count
    )


    print(

        "Long Closure Events:",

        long_closure_event_count
    )


    print(

        "Average FPS        :",

        f"{average_fps:.2f}"
    )


    # ======================================================
    # Last Feature Status
    # ======================================================

    if last_result is not None:

        print()

        print(
            "FEATURE STATUS"
        )


        for (
            feature_name,
            feature
        ) in (

            last_result[
                "features"
            ].items()

        ):

            print(

                f"{feature_name:24s}",

                "valid=",
                feature.get(
                    "valid"
                ),

                "status=",
                feature.get(
                    "status"
                ),

                "reason=",
                feature.get(
                    "reason"
                ),
            )


    # ======================================================
    # PASS / FAIL
    # ======================================================

    print()

    print(
        "=============================================="
    )


    if (

        frame_count > 0

        and

        schema_pass_count
        ==
        frame_count

    ):

        print(

            "DETECTION OUTPUT CONTRACT: PASS"
        )


    else:

        print(

            "DETECTION OUTPUT CONTRACT: FAIL"
        )


        raise AssertionError(

            "Detection output "
            "contract failed"
        )


# ==========================================================
# Entry
# ==========================================================

if __name__ == "__main__":

    main()