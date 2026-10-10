from pathlib import Path
import sys


# ==========================================================
# Add backend to Python path
# ==========================================================

BASE_DIR = (
    Path(__file__)
    .resolve()
    .parents[1]
)

if str(BASE_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(BASE_DIR)
    )


from eye.blink_statistics import (
    BlinkStatistics
)


# ==========================================================
# Helper
# ==========================================================

def check(
    condition,
    message,
):
    if not condition:
        raise AssertionError(
            message
        )


# ==========================================================
# Test 1
# NO BLINK
# ==========================================================

def test_no_blink():

    stats = BlinkStatistics()

    stats.start(0.0)

    result = stats.update(
        blink_event=False,
        timestamp=10.0,
    )

    check(
        result["blink_count_60s"] == 0,
        "NO_BLINK count should be 0",
    )

    check(
        result["blink_rate"] is None,
        "Blink rate should be None "
        "before 60 seconds",
    )

    check(
        result["window_ready"] is False,
        "Window should not be ready",
    )


# ==========================================================
# Test 2
# ONE BLINK
# ==========================================================

def test_one_blink():

    stats = BlinkStatistics()

    stats.start(0.0)

    result = stats.update(
        blink_event=True,
        timestamp=10.0,
    )

    check(
        result["blink_count_total"] == 1,
        "Total blink count should be 1",
    )

    check(
        result["blink_count_60s"] == 1,
        "60s blink count should be 1",
    )

    check(
        result["last_blink_time"] == 10.0,
        "Last blink time should be 10.0",
    )

    check(
        result["inter_blink_interval"] is None,
        "First blink interval should be None",
    )


# ==========================================================
# Test 3
# MULTIPLE BLINKS
# ==========================================================

def test_multiple_blinks():

    stats = BlinkStatistics()

    stats.start(0.0)

    stats.update(
        blink_event=True,
        timestamp=5.0,
    )

    stats.update(
        blink_event=True,
        timestamp=15.0,
    )

    result = stats.update(
        blink_event=True,
        timestamp=30.0,
    )

    check(
        result["blink_count_total"] == 3,
        "Total blink count should be 3",
    )

    check(
        result["blink_count_60s"] == 3,
        "60s blink count should be 3",
    )

    check(
        result["last_blink_time"] == 30.0,
        "Last blink time should be 30.0",
    )

    check(
        result["inter_blink_interval"] == 15.0,
        "Last interval should be 15 seconds",
    )


# ==========================================================
# Test 4
# FIRST 60 SECONDS
# ==========================================================

def test_first_60_seconds():

    stats = BlinkStatistics()

    stats.start(0.0)

    stats.update(
        blink_event=True,
        timestamp=10.0,
    )

    result = stats.update(
        blink_event=False,
        timestamp=59.9,
    )

    check(
        result["window_ready"] is False,
        "Window must not be ready before 60s",
    )

    check(
        result["blink_rate"] is None,
        "Blink rate must be None before 60s",
    )


# ==========================================================
# Test 5
# WINDOW BECOMES READY
# ==========================================================

def test_window_ready():

    stats = BlinkStatistics()

    stats.start(0.0)

    stats.update(
        blink_event=True,
        timestamp=10.0,
    )

    stats.update(
        blink_event=True,
        timestamp=30.0,
    )

    result = stats.update(
        blink_event=False,
        timestamp=60.0,
    )

    check(
        result["window_ready"] is True,
        "Window should be ready at 60s",
    )

    check(
        result["blink_rate"] == 2.0,
        "Blink rate should be 2",
    )


# ==========================================================
# Test 6
# SLIDING WINDOW EXPIRATION
# ==========================================================

def test_sliding_window_expiration():

    stats = BlinkStatistics()

    stats.start(0.0)

    # Blink at 5s
    stats.update(
        blink_event=True,
        timestamp=5.0,
    )

    # Blink at 30s
    stats.update(
        blink_event=True,
        timestamp=30.0,
    )

    # At 60s both are still inside
    result = stats.update(
        blink_event=False,
        timestamp=60.0,
    )

    check(
        result["blink_count_60s"] == 2,
        "Both blinks should still be in window",
    )

    # At 65s:
    # 5s blink expires
    result = stats.update(
        blink_event=False,
        timestamp=65.0,
    )

    check(
        result["blink_count_60s"] == 1,
        "5s blink should expire",
    )

    check(
        result["blink_rate"] == 1.0,
        "Blink rate should be 1",
    )


# ==========================================================
# Test 7
# RESET
# ==========================================================

def test_reset():

    stats = BlinkStatistics()

    stats.start(0.0)

    stats.update(
        blink_event=True,
        timestamp=10.0,
    )

    stats.reset()

    result = stats.update(
        blink_event=False,
        timestamp=20.0,
    )

    check(
        result["blink_count_total"] == 0,
        "Total count should reset",
    )

    check(
        result["blink_count_60s"] == 0,
        "Window count should reset",
    )

    check(
        result["last_blink_time"] is None,
        "Last blink should reset",
    )

    check(
        result["inter_blink_interval"] is None,
        "Interval should reset",
    )


# ==========================================================
# Main
# ==========================================================

def main():

    print()
    print("=" * 56)
    print("POSTGUARD BLINK STATISTICS LOGIC TEST")
    print("=" * 56)


    tests = [
        (
            "NO_BLINK",
            test_no_blink,
        ),

        (
            "ONE_BLINK",
            test_one_blink,
        ),

        (
            "MULTIPLE_BLINKS",
            test_multiple_blinks,
        ),

        (
            "FIRST_60_SECONDS",
            test_first_60_seconds,
        ),

        (
            "WINDOW_READY",
            test_window_ready,
        ),

        (
            "SLIDING_WINDOW_EXPIRATION",
            test_sliding_window_expiration,
        ),

        (
            "RESET",
            test_reset,
        ),
    ]


    passed = 0


    for name, test_function in tests:

        try:

            test_function()

            print(
                f"{name}: PASS"
            )

            passed += 1

        except Exception as error:

            print(
                f"{name}: FAIL"
            )

            print(
                f"  {error}"
            )


    print("-" * 56)

    print(
        f"Logic Tests: "
        f"{passed}/{len(tests)}"
    )


    if passed == len(tests):

        print(
            "BLINK STATISTICS LOGIC TEST: PASS"
        )

    else:

        print(
            "BLINK STATISTICS LOGIC TEST: FAIL"
        )

    print("=" * 56)


if __name__ == "__main__":
    main()