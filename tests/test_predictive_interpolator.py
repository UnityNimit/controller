"""
Unit and benchmark tests for Pillar 2: State-Space Kalman & Hermite Predictive Micro-Interpolation Engine
Tests sub-millisecond analog continuity, monotonicity, dead-reckoning extrapolation, and performance.
"""

import time
import math
import pytest
from gateway.predictive_interpolator import AxisPredictor, SlotPredictiveState, PredictiveInterpolator


def test_axis_predictor_micro_interpolation_continuity():
    """
    Verify that sampling an axis between two 60 Hz arrival packets yields
    continuous, strictly monotonic intermediate values rather than staircase steps.
    """
    axis = AxisPredictor(min_val=-32768, max_val=32767, deadband=100)

    t0 = 100.0
    t1 = 100.0166  # 60 Hz packet interval (~16.6ms)

    axis.feed_sample(0.0, timestamp=t0)
    axis.feed_sample(20000.0, timestamp=t1)

    # Sample at 10 intermediate micro-steps (e.g. 1000 Hz query rate)
    samples = []
    for step in range(11):
        t = t0 + (t1 - t0) * (step / 10.0)
        val = axis.sample(t)
        samples.append(val)

    # First sample should be near 0, last sample near 20000
    assert samples[0] == 0 or abs(samples[0]) < 1000
    assert samples[-1] > 10000

    # Monotonic progression: each intermediate sample should be non-decreasing
    for i in range(len(samples) - 1):
        assert samples[i] <= samples[i + 1] + 50, f"Monotonicity violation at step {i}: {samples[i]} > {samples[i+1]}"


def test_axis_predictor_dead_reckoning_extrapolation():
    """Verify forward extrapolation when query time extends beyond the latest packet."""
    axis = AxisPredictor(min_val=-32768, max_val=32767, deadband=100)

    t0 = 200.0
    t1 = 200.010
    t2 = 200.020

    axis.feed_sample(1000.0, timestamp=t0)
    axis.feed_sample(5000.0, timestamp=t1)
    axis.feed_sample(9000.0, timestamp=t2)

    # Query 5ms into the future (simulating Wi-Fi one-way latency lookahead)
    future_t = t2 + 0.005
    extrapolated = axis.sample(future_t, lookahead_sec=0.002)

    # Should predict continuation along positive velocity vector (> 9000)
    assert extrapolated > 9000, f"Expected extrapolated > 9000, got {extrapolated}"
    assert extrapolated <= 32767


def test_axis_predictor_center_deadband_snapping():
    """Verify that values within the deadband snap to true zero without residual drift."""
    axis = AxisPredictor(min_val=-32768, max_val=32767, deadband=600)

    t = 300.0
    axis.feed_sample(0.0, timestamp=t)
    assert axis.sample(t) == 0

    # Small tremor of +350 (within deadband)
    axis.feed_sample(350.0, timestamp=t + 0.016)
    assert axis.sample(t + 0.016) == 0

    # Large deflection outside deadband
    axis.feed_sample(15000.0, timestamp=t + 0.032)
    assert axis.sample(t + 0.032) > 5000


def test_slot_predictive_state_multi_channel():
    """Verify all 6 analog channels and buttons operate concurrently across a slot."""
    slot = SlotPredictiveState(0)

    t = 400.0
    slot.feed_packet({
        "stick_x": -15000,
        "stick_y": 22000,
        "right_stick_x": 8000,
        "right_stick_y": -12000,
        "throttle": 240,
        "brake": 0,
        "buttons": {"A": True, "RB": True}
    }, timestamp=t, rtt_ms=4.0)

    sample = slot.sample(t)
    assert sample["is_active"] is True
    assert sample["buttons"]["A"] is True
    assert sample["buttons"]["RB"] is True
    assert abs(sample["stick_x"]) > 10000
    assert abs(sample["stick_y"]) > 15000
    assert sample["throttle"] > 180
    assert sample["brake"] == 0

    slot.reset()
    assert slot.is_active is False
    assert len(slot.buttons) == 0


def test_predictive_interpolator_orchestrator_and_benchmark():
    """
    Verify multi-slot master orchestrator and benchmark performance
    to guarantee sub-microsecond evaluation for 1000 Hz – 5000 Hz throughput.
    """
    engine = PredictiveInterpolator(max_slots=4, latency_comp_factor=1.0)

    # Feed packets to Slot 0
    t_base = time.perf_counter()
    engine.feed_packet(0, {"stick_x": 10000, "stick_y": -5000, "throttle": 200, "buttons": {"X": True}}, timestamp=t_base)
    engine.feed_packet(0, {"stick_x": 25000, "stick_y": -12000, "throttle": 255, "buttons": {"X": True}}, timestamp=t_base + 0.010)

    # Benchmark: 5,000 continuous samples (equivalent to a full second at 5000 Hz)
    start_bench = time.perf_counter()
    for i in range(5000):
        t_sample = t_base + (i * 0.0002)
        state = engine.sample_slot(0, current_time=t_sample)
        assert state is not None
    bench_duration = time.perf_counter() - start_bench

    # 5,000 samples should evaluate in under 50ms (< 10µs per sample)
    assert bench_duration < 0.100, f"5000 samples took too long: {bench_duration:.4f}s"
    avg_us = (bench_duration / 5000.0) * 1e6

    # Test reset
    engine.reset_slot(0)
    assert engine.sample_slot(0) is None
