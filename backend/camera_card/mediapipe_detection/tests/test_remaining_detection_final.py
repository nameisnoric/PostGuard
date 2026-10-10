from pathlib import Path
import csv
import json
import math
import statistics
import sys
import time
from datetime import datetime

import cv2

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parents[2]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from mediapipe_detection.detection_pipeline import DetectionPipeline

TOTAL_ROUNDS = 3
SAMPLE_DURATION_SECONDS = 2.0
MIN_VALID_SAMPLES = 15
INITIAL_WARMUP_VALID_SECONDS = 3.0
STATE_SETTLE_SECONDS = 0.75
MAX_ATTEMPTS = 5
MAX_CONTIGUOUS_INVALID_SECONDS = 0.35
MAX_CAPTURE_WINDOW_SECONDS = 3.5
MAX_HEAD_ONLY_TO_BODY_RATIO = 0.50
MIN_BODY_SIGNAL_TO_NORMAL = 3.0
MAX_BODY_TO_HEAD_RELATIVE_RATIO = 0.50
MIN_HEAD_SIGNAL_TO_NORMAL = 3.0
EPSILON = 1e-9
WINDOW_NAME = "PostGuard - Remaining Detection Final Test"

STATE_ORDER = (
    "NORMAL_1", "HEAD_LEFT", "NORMAL_2", "BODY_LEFT", "NORMAL_3",
    "HEAD_RIGHT", "NORMAL_4", "BODY_RIGHT", "NORMAL_5",
)

STATE_INSTRUCTIONS = {
    "NORMAL_1": "Sit naturally, face forward, shoulders relaxed.",
    "HEAD_LEFT": "Turn HEAD LEFT only. Keep shoulders facing forward.",
    "NORMAL_2": "Return to normal and face forward.",
    "BODY_LEFT": "Turn HEAD + UPPER TORSO LEFT together.",
    "NORMAL_3": "Return to normal and face forward.",
    "HEAD_RIGHT": "Turn HEAD RIGHT only. Keep shoulders facing forward.",
    "NORMAL_4": "Return to normal and face forward.",
    "BODY_RIGHT": "Turn HEAD + UPPER TORSO RIGHT together.",
    "NORMAL_5": "Return to normal and face forward.",
}

EXPECTED_FEATURES = (
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


def is_num(v):
    try:
        return v is not None and math.isfinite(float(v))
    except (TypeError, ValueError):
        return False


def ratio(a, b):
    b = abs(float(b))
    if b <= EPSILON:
        return math.inf
    return abs(float(a)) / b


def median(values):
    values = [float(v) for v in values if is_num(v)]
    return float(statistics.median(values)) if values else None


def summary(values):
    values = [float(v) for v in values if is_num(v)]
    if not values:
        return None
    return {
        "median": float(statistics.median(values)),
        "mean": float(statistics.mean(values)),
        "std": float(statistics.pstdev(values)) if len(values) >= 2 else 0.0,
        "min": float(min(values)),
        "max": float(max(values)),
    }


def feature_value(result, name):
    if not isinstance(result, dict):
        return None
    features = result.get("features")
    if not isinstance(features, dict):
        return None
    block = features.get(name)
    if not isinstance(block, dict) or block.get("valid") is False:
        return None
    value = block.get("value")
    return float(value) if is_num(value) else None


def context_of(result):
    if not isinstance(result, dict):
        return {"state": "UNKNOWN", "reason": "invalid_result", "allow_posture_evaluation": False, "stable_seconds": 0.0}
    context = result.get("context")
    if not isinstance(context, dict):
        return {"state": "UNKNOWN", "reason": "context_missing", "allow_posture_evaluation": False, "stable_seconds": 0.0}
    return context


def context_valid(context):
    return (
        isinstance(context, dict)
        and context.get("state") == "VALID"
        and context.get("allow_posture_evaluation") is True
    )


def validate_contract(result):
    errors = []
    if not isinstance(result, dict):
        return ["result_not_dict"]
    if result.get("contract_version") != "1.0":
        errors.append("contract_version")
    if not is_num(result.get("timestamp")):
        errors.append("timestamp")
    if not isinstance(result.get("pose_detected"), bool):
        errors.append("pose_detected")
    if not isinstance(result.get("face_detected"), bool):
        errors.append("face_detected")

    context = result.get("context")
    if not isinstance(context, dict):
        errors.append("context")
    else:
        if context.get("state") not in {"VALID", "TRANSITION", "UNKNOWN"}:
            errors.append("context.state")
        if not isinstance(context.get("allow_posture_evaluation"), bool):
            errors.append("context.allow")

    features = result.get("features")
    if not isinstance(features, dict):
        errors.append("features")
    else:
        for name in EXPECTED_FEATURES:
            if not isinstance(features.get(name), dict):
                errors.append(f"features.{name}")

    eye = result.get("eye")
    if not isinstance(eye, dict):
        errors.append("eye")
    else:
        for key in ("measurement_valid", "state", "blink", "closure", "validation"):
            if key not in eye:
                errors.append(f"eye.{key}")

    landmarks = result.get("landmarks")
    if not isinstance(landmarks, dict):
        errors.append("landmarks")
    else:
        if "pose" not in landmarks:
            errors.append("landmarks.pose")
        if "face" not in landmarks:
            errors.append("landmarks.face")
    return errors


def draw(frame, text, y, scale=0.60, thickness=2):
    cv2.putText(frame, str(text), (20, y), cv2.FONT_HERSHEY_SIMPLEX,
                scale, (255, 255, 255), thickness, cv2.LINE_AA)


def preview(frame):
    return cv2.flip(frame, 1)


def process(pipeline, frame, contract_stats):
    result = pipeline.process_frame(frame, time.perf_counter())
    contract_stats["frames"] += 1
    errors = validate_contract(result)
    if errors:
        contract_stats["violation_frames"] += 1
        for error in errors:
            contract_stats["errors"][error] = contract_stats["errors"].get(error, 0) + 1
    return result


def warmup(pipeline, capture, contract_stats):
    print("\n" + "=" * 72)
    print("INITIAL WARM-UP")
    print("=" * 72)
    valid_since = None
    while True:
        ok, frame = capture.read()
        if not ok or frame is None:
            time.sleep(0.01)
            continue
        result = process(pipeline, frame, contract_stats)
        context = context_of(result)
        if context_valid(context):
            if valid_since is None:
                valid_since = time.perf_counter()
            elapsed = time.perf_counter() - valid_since
        else:
            valid_since = None
            elapsed = 0.0

        d = preview(frame)
        draw(d, "INITIAL WARM-UP - NORMAL", 35, 0.75)
        draw(d, f"Context: {context.get('state')} | {context.get('reason')}", 75, 0.55)
        draw(d, f"Continuous VALID: {elapsed:.1f}/{INITIAL_WARMUP_VALID_SECONDS:.1f}s", 110)
        draw(d, "ESC = abort", 145, 0.52, 1)
        cv2.imshow(WINDOW_NAME, d)
        key = cv2.waitKey(1) & 0xFF
        if key == 27:
            raise KeyboardInterrupt
        if elapsed >= INITIAL_WARMUP_VALID_SECONDS:
            print("[OK] Warm-up completed.")
            return


def wait_ready(pipeline, capture, phase, round_no, state, contract_stats):
    while True:
        ok, frame = capture.read()
        if not ok or frame is None:
            time.sleep(0.01)
            continue
        result = process(pipeline, frame, contract_stats)
        context = context_of(result)
        stable = context.get("stable_seconds", 0.0)
        stable = float(stable) if is_num(stable) else 0.0
        torso = feature_value(result, "torso_orientation")
        head = feature_value(result, "head_yaw")
        ready = (
            context_valid(context)
            and stable >= STATE_SETTLE_SECONDS
            and is_num(torso)
            and is_num(head)
        )

        d = preview(frame)
        draw(d, f"{phase} | Round {round_no}/{TOTAL_ROUNDS} | {state}", 35, 0.68)
        draw(d, STATE_INSTRUCTIONS[state], 72, 0.46)
        draw(d, f"Context: {context.get('state')} | {context.get('reason')}", 110, 0.52)
        draw(d, f"Stable: {stable:.2f}s", 145)
        draw(d, f"Torso: {torso:+.2f} deg" if is_num(torso) else "Torso: INVALID", 180)
        draw(d, f"Head yaw: {head:+.2f} deg" if is_num(head) else "Head yaw: INVALID", 215)
        draw(d, "READY - SPACE = record" if ready else "WAIT - hold posture still", 255, 0.65)
        draw(d, "ESC = abort", 290, 0.52, 1)
        cv2.imshow(WINDOW_NAME, d)
        key = cv2.waitKey(1) & 0xFF
        if key == 27:
            raise KeyboardInterrupt
        if key == 32 and ready:
            return


def record_state(pipeline, capture, phase, round_no, state, raw_rows, contract_stats):
    """
    Record one posture state.

    Important:
    - A single bad MediaPipe frame does NOT invalidate the whole attempt.
    - Only frames with VALID context + valid torso + valid head yaw are scored.
    - A continuous tracking dropout longer than
      MAX_CONTIGUOUS_INVALID_SECONDS discards the attempt.
    - The capture window may extend beyond 2 seconds, up to
      MAX_CAPTURE_WINDOW_SECONDS, to obtain enough valid samples.

    This separates transient tracking/data-quality loss from metric failure.
    """

    for attempt in range(1, MAX_ATTEMPTS + 1):
        wait_ready(
            pipeline,
            capture,
            phase,
            round_no,
            state,
            contract_stats,
        )

        samples = []
        started = time.perf_counter()
        invalid_since = None
        failed_reason = None

        while True:
            now = time.perf_counter()
            elapsed = now - started

            if (
                elapsed >= SAMPLE_DURATION_SECONDS
                and len(samples) >= MIN_VALID_SAMPLES
            ):
                print(
                    f"[{phase}][R{round_no}] {state}: "
                    f"{len(samples)} VALID samples"
                )
                return samples

            if elapsed >= MAX_CAPTURE_WINDOW_SECONDS:
                failed_reason = (
                    "insufficient_valid_samples:"
                    f"{len(samples)}/{MIN_VALID_SAMPLES}"
                )
                break

            ok, frame = capture.read()

            if not ok or frame is None:
                failed_reason = "camera_frame_failed"
                break

            result = process(
                pipeline,
                frame,
                contract_stats,
            )

            context = context_of(
                result
            )

            torso = feature_value(
                result,
                "torso_orientation",
            )

            head = feature_value(
                result,
                "head_yaw",
            )

            good = (
                context_valid(context)
                and is_num(torso)
                and is_num(head)
            )

            raw_rows.append({
                "timestamp": datetime.now().isoformat(
                    timespec="milliseconds"
                ),
                "phase": phase,
                "round": round_no,
                "state": state,
                "attempt": attempt,
                "elapsed_seconds": elapsed,
                "context_state": context.get("state"),
                "context_reason": context.get("reason"),
                "valid": good,
                "torso_angle": (
                    float(torso)
                    if is_num(torso)
                    else ""
                ),
                "head_yaw": (
                    float(head)
                    if is_num(head)
                    else ""
                ),
            })

            if good:
                samples.append({
                    "torso": float(torso),
                    "head_yaw": float(head),
                })

                # Tracking recovered.
                invalid_since = None

            else:
                if invalid_since is None:
                    invalid_since = now

                invalid_duration = (
                    now
                    -
                    invalid_since
                )

                if (
                    invalid_duration
                    >=
                    MAX_CONTIGUOUS_INVALID_SECONDS
                ):
                    failed_reason = (
                        "tracking_dropout_too_long:"
                        f"{context.get('state')}/"
                        f"{context.get('reason')}"
                    )
                    break

            d = preview(
                frame
            )

            draw(
                d,
                f"{phase} | R{round_no} | {state}",
                35,
                0.72,
            )

            draw(
                d,
                (
                    "RECORDING "
                    f"{min(elapsed, SAMPLE_DURATION_SECONDS):.1f}/"
                    f"{SAMPLE_DURATION_SECONDS:.1f}s"
                ),
                75,
                0.70,
            )

            if is_num(torso) and is_num(head):
                draw(
                    d,
                    (
                        f"Torso={float(torso):+.2f} | "
                        f"Head={float(head):+.2f}"
                    ),
                    115,
                )
            else:
                draw(
                    d,
                    "Torso/Head: temporary INVALID frame",
                    115,
                )

            draw(
                d,
                (
                    f"Valid samples={len(samples)} "
                    f"(need >= {MIN_VALID_SAMPLES})"
                ),
                150,
            )

            draw(
                d,
                (
                    "Context="
                    f"{context.get('state')} | "
                    f"{context.get('reason')}"
                ),
                185,
                0.52,
            )

            draw(
                d,
                "Hold the SAME posture",
                220,
            )

            draw(
                d,
                "ESC = abort",
                255,
                0.52,
                1,
            )

            cv2.imshow(
                WINDOW_NAME,
                d,
            )

            key = cv2.waitKey(1) & 0xFF

            if key == 27:
                raise KeyboardInterrupt

        print(
            f"[RETRY] {phase} R{round_no} {state} "
            f"attempt {attempt}: {failed_reason}"
        )

        if hasattr(
            pipeline,
            "reset_context",
        ):
            pipeline.reset_context()

    print(
        f"[INSUFFICIENT_DATA] {phase} R{round_no} {state}: "
        f"could not obtain >= {MIN_VALID_SAMPLES} valid samples "
        f"after {MAX_ATTEMPTS} attempts."
    )

    # Do not crash the entire test.
    # The analysis layer will mark this round as INSUFFICIENT_DATA.
    return []


def capture_phase(pipeline, capture, phase, raw_rows, contract_stats):
    summaries = []
    for round_no in range(1, TOTAL_ROUNDS + 1):
        for state in STATE_ORDER:
            print("\n" + "=" * 72)
            print(f"{phase} | ROUND {round_no}/{TOTAL_ROUNDS} | {state}")
            print(STATE_INSTRUCTIONS[state])
            print("=" * 72)
            samples = record_state(pipeline, capture, phase, round_no, state, raw_rows, contract_stats)
            s = {
                "phase": phase,
                "round": round_no,
                "state": state,
                "valid_samples": len(samples),
                "torso": summary(
                    [x["torso"] for x in samples]
                ),
                "head_yaw": summary(
                    [x["head_yaw"] for x in samples]
                ),
            }

            summaries.append(
                s
            )

            if (
                s["torso"] is not None
                and s["head_yaw"] is not None
            ):
                print(
                    "  torso median  : "
                    f"{s['torso']['median']:+.4f} deg"
                )
                print(
                    "  head yaw med. : "
                    f"{s['head_yaw']['median']:+.4f} deg"
                )
            else:
                print(
                    "  summary       : INSUFFICIENT_DATA"
                )
    return summaries


def state_map_for(summaries, round_no):
    return {x["state"]: x for x in summaries if x["round"] == round_no}


def med(m, state, key):
    return m[state][key]["median"]


def analyze_torso_round(summaries, round_no):
    m = state_map_for(summaries, round_no)
    for state in STATE_ORDER:
        if state not in m or m[state]["valid_samples"] < MIN_VALID_SAMPLES:
            return {"round": round_no, "status": "INSUFFICIENT_DATA"}

    def side(which):
        if which == "LEFT":
            hs, bs = "HEAD_LEFT", "BODY_LEFT"
            hn, bn, nw = ("NORMAL_1", "NORMAL_2"), ("NORMAL_2", "NORMAL_3"), ("NORMAL_1", "NORMAL_2", "NORMAL_3")
        else:
            hs, bs = "HEAD_RIGHT", "BODY_RIGHT"
            hn, bn, nw = ("NORMAL_3", "NORMAL_4"), ("NORMAL_4", "NORMAL_5"), ("NORMAL_3", "NORMAL_4", "NORMAL_5")

        head_base = median([med(m, x, "torso") for x in hn])
        body_base = median([med(m, x, "torso") for x in bn])
        body_head_base = median([med(m, x, "head_yaw") for x in bn])
        head_delta = med(m, hs, "torso") - head_base
        body_delta = med(m, bs, "torso") - body_base
        body_head_delta = med(m, bs, "head_yaw") - body_head_base
        normal_vals = [med(m, x, "torso") for x in nw]
        normal_var = max(normal_vals) - min(normal_vals)
        crosstalk = ratio(head_delta, body_delta)
        signal = ratio(body_delta, normal_var)
        k = body_head_delta / body_delta if abs(body_delta) > EPSILON else None
        passed = abs(body_delta) > EPSILON and crosstalk <= MAX_HEAD_ONLY_TO_BODY_RATIO and signal >= MIN_BODY_SIGNAL_TO_NORMAL
        return {
            "head_only_delta": head_delta,
            "body_torso_delta": body_delta,
            "body_head_yaw_delta": body_head_delta,
            "normal_variability": normal_var,
            "head_only_to_body_ratio": crosstalk,
            "body_signal_to_normal": signal,
            "mapping_k": k,
            "passed": passed,
        }

    left, right = side("LEFT"), side("RIGHT")
    opposite = left["body_torso_delta"] * right["body_torso_delta"] < 0
    passed = left["passed"] and right["passed"] and opposite
    return {"round": round_no, "status": "PASS" if passed else "FAIL", "left": left, "right": right, "body_opposite_direction": opposite}


def analyze_torso(summaries):
    rounds = [analyze_torso_round(summaries, r) for r in range(1, TOTAL_ROUNDS + 1)]
    if any(r.get("left") is None for r in rounds):
        return rounds, {"status": "INSUFFICIENT_DATA"}

    k_values = []
    for r in rounds:
        for side in ("left", "right"):
            k = r[side].get("mapping_k")
            if is_num(k):
                k_values.append(float(k))

    signs = [1 if k > 0 else -1 for k in k_values if abs(k) > EPSILON]
    k_consistent = len(signs) == TOTAL_ROUNDS * 2 and len(set(signs)) == 1
    all_rounds = all(r["status"] == "PASS" for r in rounds)
    status = "PASS" if all_rounds and k_consistent else "FAIL"
    return rounds, {
        "status": status,
        "recommended_k": float(statistics.median(k_values)) if k_values else None,
        "k_values": k_values,
        "k_direction_consistent": k_consistent,
    }


def combined_signal(m, state, k):
    return med(m, state, "head_yaw") - k * med(m, state, "torso")


def analyze_relative_round(summaries, round_no, k):
    m = state_map_for(summaries, round_no)
    for state in STATE_ORDER:
        if state not in m or m[state]["valid_samples"] < MIN_VALID_SAMPLES:
            return {"round": round_no, "status": "INSUFFICIENT_DATA"}

    S = {state: combined_signal(m, state, k) for state in STATE_ORDER}

    def side(which):
        if which == "LEFT":
            hs, bs = "HEAD_LEFT", "BODY_LEFT"
            hn, bn, nw = ("NORMAL_1", "NORMAL_2"), ("NORMAL_2", "NORMAL_3"), ("NORMAL_1", "NORMAL_2", "NORMAL_3")
        else:
            hs, bs = "HEAD_RIGHT", "BODY_RIGHT"
            hn, bn, nw = ("NORMAL_3", "NORMAL_4"), ("NORMAL_4", "NORMAL_5"), ("NORMAL_3", "NORMAL_4", "NORMAL_5")

        head_base = median([S[x] for x in hn])
        body_base = median([S[x] for x in bn])
        head_response = S[hs] - head_base
        body_response = S[bs] - body_base
        normal_vals = [S[x] for x in nw]
        normal_var = max(normal_vals) - min(normal_vals)
        suppression = ratio(body_response, head_response)
        signal = ratio(head_response, normal_var)
        passed = abs(head_response) > EPSILON and suppression <= MAX_BODY_TO_HEAD_RELATIVE_RATIO and signal >= MIN_HEAD_SIGNAL_TO_NORMAL
        return {
            "head_response": head_response,
            "body_response": body_response,
            "normal_variability": normal_var,
            "body_to_head_ratio": suppression,
            "head_signal_to_normal": signal,
            "passed": passed,
        }

    left, right = side("LEFT"), side("RIGHT")
    opposite = left["head_response"] * right["head_response"] < 0
    passed = left["passed"] and right["passed"] and opposite
    return {"round": round_no, "status": "PASS" if passed else "FAIL", "left": left, "right": right, "head_opposite_direction": opposite}


def analyze_relative(summaries, k):
    rounds = [analyze_relative_round(summaries, r, k) for r in range(1, TOTAL_ROUNDS + 1)]
    if any(r.get("left") is None for r in rounds):
        return rounds, {"status": "INSUFFICIENT_DATA"}
    status = "PASS" if all(r["status"] == "PASS" for r in rounds) else "FAIL"
    return rounds, {"status": status, "mapping_k": k}


def print_torso(rounds, overall):
    print("\n" + "#" * 72)
    print("TORSO ORIENTATION CALIBRATION RESULT")
    print("#" * 72)
    for r in rounds:
        print(f"\nROUND {r['round']}: {r['status']}")
        if r.get("left"):
            for key, label in (("left", "LEFT"), ("right", "RIGHT")):
                x = r[key]
                print(f"  {label}: head-only={x['head_only_delta']:+.3f} body={x['body_torso_delta']:+.3f} ratio={x['head_only_to_body_ratio']:.3f} signal/normal={x['body_signal_to_normal']:.3f} K={x['mapping_k']:+.6f}")
            print(f"  Body opposite direction: {r['body_opposite_direction']}")
    print(f"\nTORSO OVERALL: {overall['status']}")
    if overall.get("recommended_k") is not None:
        print(f"Recommended TORSO_MAPPING_K: {overall['recommended_k']:+.6f}")
    print(f"K direction consistent: {overall.get('k_direction_consistent')}")
    print(f"Criteria: head-only/body <= {MAX_HEAD_ONLY_TO_BODY_RATIO:.2f}, body signal/normal >= {MIN_BODY_SIGNAL_TO_NORMAL:.1f}")


def print_relative(rounds, overall):
    print("\n" + "#" * 72)
    print("RELATIVE NECK ROTATION FINAL RESULT")
    print("#" * 72)
    for r in rounds:
        print(f"\nROUND {r['round']}: {r['status']}")
        if r.get("left"):
            for key, label in (("left", "LEFT"), ("right", "RIGHT")):
                x = r[key]
                print(f"  {label}: HEAD={x['head_response']:+.3f} BODY={x['body_response']:+.3f} body/head={x['body_to_head_ratio']:.3f} signal/normal={x['head_signal_to_normal']:.3f}")
            print(f"  Head L/R opposite direction: {r['head_opposite_direction']}")
    print(f"\nRELATIVE NECK OVERALL: {overall['status']}")
    print(f"K used: {overall.get('mapping_k'):+.6f}" if overall.get("mapping_k") is not None else "K used: INVALID")
    print(f"Criteria: body/head <= {MAX_BODY_TO_HEAD_RELATIVE_RATIO:.2f}, head signal/normal >= {MIN_HEAD_SIGNAL_TO_NORMAL:.1f}")


def save_raw(path, rows):
    fields = ["timestamp", "phase", "round", "state", "attempt", "elapsed_seconds", "context_state", "context_reason", "valid", "torso_angle", "head_yaw"]
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def main():
    capture = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not capture.isOpened():
        capture.release()
        capture = cv2.VideoCapture(0)
    if not capture.isOpened():
        raise RuntimeError("Cannot open camera index 0.")

    pipeline = DetectionPipeline()
    raw_rows = []
    contract_stats = {"frames": 0, "violation_frames": 0, "errors": {}}

    try:
        print("[OK] Camera opened.")
        print("\n" + "=" * 72)
        print("POSTGUARD - REMAINING DETECTION FINAL TEST")
        print("=" * 72)
        print("Phase A: Torso Orientation + K Calibration")
        print("Phase B: Independent Relative Neck Rotation Validation")
        print("Phase C: Detection Output Contract / E2E Summary")
        print("Shoulder Elevation and Forward Head are NOT blocking final status.")
        print("They remain experimental outside final risk calculation.")

        if hasattr(pipeline, "reset_context"):
            pipeline.reset_context()
        warmup(pipeline, capture, contract_stats)

        calibration = capture_phase(pipeline, capture, "CALIBRATION", raw_rows, contract_stats)
        torso_rounds, torso_overall = analyze_torso(calibration)
        print_torso(torso_rounds, torso_overall)

        if torso_overall["status"] != "PASS" or not is_num(torso_overall.get("recommended_k")):
            print("\nSTOP: Torso Orientation did not pass. Relative Neck Rotation will remain experimental.")
            relative_rounds = []
            relative_overall = {"status": "NOT_RUN", "mapping_k": torso_overall.get("recommended_k")}
        else:
            k = float(torso_overall["recommended_k"])
            print("\n" + "=" * 72)
            print("PHASE B - INDEPENDENT VALIDATION")
            print("=" * 72)
            print(f"Using calibrated K = {k:+.6f}")
            print("This phase records NEW data; calibration data is not reused.")

            if hasattr(pipeline, "reset_context"):
                pipeline.reset_context()
            warmup(pipeline, capture, contract_stats)
            validation = capture_phase(pipeline, capture, "VALIDATION", raw_rows, contract_stats)
            relative_rounds, relative_overall = analyze_relative(validation, k)
            print_relative(relative_rounds, relative_overall)

        e2e_status = "PASS" if contract_stats["violation_frames"] == 0 else "FAIL"

        print("\n" + "#" * 72)
        print("DETECTION E2E / OUTPUT CONTRACT")
        print("#" * 72)
        print(f"Frames checked    : {contract_stats['frames']}")
        print(f"Violation frames  : {contract_stats['violation_frames']}")
        print(f"E2E CONTRACT      : {e2e_status}")
        if contract_stats["errors"]:
            print("Errors:")
            for key, count in sorted(contract_stats["errors"].items()):
                print(f"  {key}: {count}")

        remaining_status = (
            "PASS"
            if torso_overall["status"] == "PASS"
            and relative_overall["status"] == "PASS"
            and e2e_status == "PASS"
            else "FAIL"
        )

        print("\n" + "#" * 72)
        print("FINAL REMAINING DETECTION STATUS")
        print("#" * 72)
        print(f"Torso Orientation      : {torso_overall['status']}")
        print(f"Relative Neck Rotation : {relative_overall['status']}")
        print(f"Detection E2E Contract : {e2e_status}")
        print(f"OVERALL                : {remaining_status}")
        print("Experimental/non-blocking: Shoulder Elevation, Forward Head")
        print("This is engineering prototype validation, not clinical validation.")

        output_dir = Path(__file__).resolve().parent / "results"
        output_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        raw_path = output_dir / f"remaining_detection_{stamp}_raw.csv"
        summary_path = output_dir / f"remaining_detection_{stamp}_summary.json"
        save_raw(raw_path, raw_rows)
        summary_obj = {
            "overall": remaining_status,
            "torso": {"overall": torso_overall, "rounds": torso_rounds},
            "relative_neck_rotation": {"overall": relative_overall, "rounds": relative_rounds},
            "e2e_contract": {"status": e2e_status, **contract_stats},
            "experimental_non_blocking": ["shoulder_elevation", "forward_head"],
            "note": "Engineering prototype validation; not clinical validation.",
        }
        summary_path.write_text(json.dumps(summary_obj, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nRaw CSV : {raw_path}")
        print(f"Summary : {summary_path}")
        return 0 if remaining_status == "PASS" else 1

    except KeyboardInterrupt:
        print("\nTest aborted by user.")
        return 130
    finally:
        try:
            if hasattr(pipeline, "close"):
                pipeline.close()
        finally:
            capture.release()
            cv2.destroyAllWindows()


if __name__ == "__main__":
    raise SystemExit(main())
