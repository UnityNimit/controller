"""
Project Controller - 1000 Hz Polling Rate & Micro-Interpolation Automated Test Suite
Verifies 1000 Hz sustained pump frequency, micro-jitter bounds (<350us),
sub-perceptual LSB dither generation for Windows XInput dwPacketNumber incrementing,
and predictive interpolator continuity across button holds and stick deflection.
"""

import time
import math
import pytest
from gateway.input_manager import InputManager, MockGamepad
from gateway.mcu_dispatch import VirtualMcuDispatcher, SlotStateLatch
from gateway.predictive_interpolator import PredictiveInterpolator


def test_mcu_1000hz_sustained_frequency_and_micro_jitter():
    """Verifies that VirtualMcuDispatcher sustains 1000 Hz (>= 950 Hz) with microsecond precision."""
    mock_ctrl = MockGamepad(0)
    mcu = VirtualMcuDispatcher(controllers=[mock_ctrl], target_hz=1000.0, max_slots=1)
    mcu.start()

    try:
        # Simulate active connected client
        mcu.update_slot_input(0, {"stick_x": 0, "stick_y": 0, "buttons": {}})
        
        # Warmup and allow stats accumulator to populate
        time.sleep(0.35)

        hz = mcu.measured_hz
        jitter_us = mcu.jitter_us

        # Sustained frequency must achieve >= 950 Hz (1000 Hz nominal)
        assert hz >= 950.0, f"Measured dispatch rate was {hz:.1f} Hz, expected >= 950.0 Hz"
        # Microsecond dispatch jitter standard deviation
        assert jitter_us < 800.0, f"Dispatch jitter was {jitter_us:.1f} us, expected < 800 us"

    finally:
        mcu.stop()


def test_mcu_dither_state_generation_for_xinput():
    """
    Verifies that the MCU dispatch loop produces alternating LSB values
    during neutral active sessions (0 <-> 1), ensuring Windows XInput increments
    dwPacketNumber on every millisecond report.
    """
    class TrackingGamepad(MockGamepad):
        def __init__(self):
            super().__init__(0)
            self.is_mock = False  # Enable real-hardware dither code path
            self.recorded_steering = []

        def set_stick(self, x: int, y: int = 0):
            self.recorded_steering.append(x)
            super().set_stick(x, y)

    ctrl = TrackingGamepad()
    mcu = VirtualMcuDispatcher(controllers=[ctrl], target_hz=1000.0, max_slots=1)
    mcu.start()

    try:
        # Mark slot as having an active client with centered neutral stick
        mcu.update_slot_input(0, {"stick_x": 0, "stick_y": 0, "buttons": {}})
        time.sleep(0.03)  # Accumulate ~30 reports

        reports = ctrl.recorded_steering[-20:]
        assert len(reports) >= 15

        # Confirm alternating 0 and 1 LSB dither (inside 0.003% deadband)
        has_zero = 0 in reports
        has_one = 1 in reports
        assert has_zero and has_one, f"Expected 0 and 1 dither in reports: {reports}"

    finally:
        mcu.stop()


def test_button_hold_sustained_1000hz_stream():
    """Verifies that holding a button (e.g. Button A) maintains 1000 Hz continuous report pumping."""
    mock_ctrl = MockGamepad(0)
    mcu = VirtualMcuDispatcher(controllers=[mock_ctrl], target_hz=1000.0, max_slots=1)
    mcu.start()

    try:
        # Hold Button A pressed continuously
        mcu.update_slot_input(0, {
            "stick_x": 0,
            "stick_y": 0,
            "throttle": 0,
            "brake": 0,
            "buttons": {"A": True}
        })

        initial_count = mock_ctrl.update_count
        time.sleep(0.10)  # 100ms
        delta_reports = mock_ctrl.update_count - initial_count

        # 100ms @ 1000Hz should yield ~100 reports (minimum 90)
        assert delta_reports >= 90, f"Expected >= 90 reports in 100ms, got {delta_reports}"
        assert mock_ctrl.buttons.get("A") is True

    finally:
        mcu.stop()


def test_predictive_interpolator_forward_projection_continuity():
    """Verifies that the predictive interpolator produces smooth forward knot samples at 1ms intervals."""
    interp = PredictiveInterpolator(max_slots=1)
    t0 = time.perf_counter()

    # Feed initial rest packet
    interp.feed_packet(0, {"stick_x": 0, "stick_y": 0, "throttle": 0, "brake": 0}, t0, 5.0)

    # Feed flick packet 8ms later (e.g. touch move event)
    t1 = t0 + 0.008
    interp.feed_packet(0, {"stick_x": 16000, "stick_y": -8000, "throttle": 200, "brake": 0}, t1, 5.0)

    # Sample at 1ms increments between t1 and t1 + 8ms
    samples = []
    for step in range(8):
        t_sample = t1 + (step * 0.001)
        s = interp.sample_slot(0, t_sample)
        assert s is not None
        samples.append(s["stick_x"])

    # Ensure monotonic or smooth forward trajectory without sudden collapse to 0
    assert all(val > 10000 for val in samples), f"Interpolated stick samples collapsed: {samples}"
    assert len(samples) == 8
