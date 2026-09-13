"""
Unit tests for Project Controller Mathematical Filters and Signal Processing
"""

import pytest
import math
from gateway.filters import (
    EMAFilter,
    DeadbandFilter,
    ExponentialSteeringCurve,
    JerkDetector,
    SensorFusionPipeline
)


def test_ema_filter():
    # Alpha = 0.5 for easy verification
    ema = EMAFilter(alpha=0.5)
    
    # First sample: should initialize state
    assert ema.filter(10.0) == 10.0
    
    # Second sample: 0.5 * 20.0 + 0.5 * 10.0 = 15.0
    assert ema.filter(20.0) == 15.0
    
    # Third sample: 0.5 * 20.0 + 0.5 * 15.0 = 17.5
    assert ema.filter(20.0) == 17.5

    # Invalid alpha
    with pytest.raises(ValueError):
        EMAFilter(alpha=0.0)
    with pytest.raises(ValueError):
        EMAFilter(alpha=1.5)


def test_deadband_filter():
    # Deadband = 2.0 deg, Max = 35.0 deg
    db = DeadbandFilter(deadband=2.0, max_val=35.0)
    
    # Inside deadband -> exactly 0.0
    assert db.apply(0.0) == 0.0
    assert db.apply(1.5) == 0.0
    assert db.apply(-1.8) == 0.0
    
    # At deadband threshold
    assert db.apply(2.0) == 0.0
    
    # Above deadband: smooth progressive scaling
    pos_val = db.apply(20.0)
    assert 0.0 < pos_val < 1.0
    
    neg_val = db.apply(-20.0)
    assert -1.0 < neg_val < 0.0
    assert abs(pos_val - abs(neg_val)) < 1e-6
    
    # At or above max_val -> clamped to 1.0
    assert db.apply(35.0) == 1.0
    assert db.apply(45.0) == 1.0
    assert db.apply(-45.0) == -1.0


def test_exponential_steering_curve():
    curve = ExponentialSteeringCurve(gamma=1.5)
    
    # Center neutral
    assert curve.compute(0.0) == 0
    
    # Full lock positive / negative
    assert curve.compute(1.0) == 32767
    assert curve.compute(-1.0) == -32768
    
    # Mid-range: exponential curve provides precision around center
    linear_val = 0.3 * 32767
    curved_val = curve.compute(0.3)
    # With gamma > 1.0, curved_val must be softer (smaller) than linear
    assert curved_val < linear_val


def test_jerk_detector():
    jerk = JerkDetector(jerk_threshold_g_s=2.5, debounce_sec=0.2)
    
    # Initial resting state: 1G static gravity
    assert jerk.update(0.0, 0.0, 9.81, timestamp=0.0) is False
    
    # Gentle change: dt = 0.05s, accel changes slightly
    assert jerk.update(0.0, 0.0, 9.85, timestamp=0.05) is False
    
    # Sudden violent spike (jerk > 2.5 G/s)
    # magnitude jump from ~9.81 to ~20.0 in 0.02s
    spike = jerk.update(0.0, 0.0, 20.0, timestamp=0.07)
    assert spike is True
    
    # Immediate subsequent spike within debounce window (0.2s) should be suppressed
    assert jerk.update(0.0, 0.0, 25.0, timestamp=0.10) is False


def test_sensor_fusion_pipeline():
    pipeline = SensorFusionPipeline(
        ema_alpha=0.35,
        deadband_deg=1.0,
        max_angle_deg=30.0,
        curve_gamma=1.4
    )
    
    # Neutral input -> neutral stick
    stick_x, filtered, norm = pipeline.process_steering(0.0)
    assert stick_x == 0
    assert filtered == 0.0
    assert norm == 0.0

    # Calibration zero testing: calibrate at +5.0 deg
    pipeline.calibrate_zero(5.0)
    stick_x, filtered, norm = pipeline.process_steering(5.0)
    assert stick_x == 0
    assert filtered == 0.0

    # Triggers processing: full press, partial press, and clean release to zero
    th_byte, br_byte = pipeline.process_triggers(1.0, 0.0)
    assert th_byte == 255
    assert br_byte == 0

    th_byte, br_byte = pipeline.process_triggers(0.0, 1.0)
    assert th_byte == 0
    assert br_byte == 255

    # Critical: releasing to 0.0 must immediately output (0, 0) with ZERO lag/ghosting
    th_byte, br_byte = pipeline.process_triggers(0.0, 0.0)
    assert th_byte == 0
    assert br_byte == 0


def test_state_space_kalman_filter():
    from gateway.filters import StateSpaceKalmanFilter1D
    kf = StateSpaceKalmanFilter1D(q_pos=0.1, q_vel=2.0, r_meas=1.5, initial_val=0.0)

    # Initial update
    angle, vel = kf.update(0.0, timestamp=0.0)
    assert angle == 0.0
    assert vel == 0.0

    # Step response with noisy measurements
    # Over 20 iterations at 60Hz (dt = 0.0166s), angle moves toward 15.0 deg
    t = 0.0
    for i in range(1, 21):
        t += 0.0166
        # Simulate noisy sensor measurement: true 15.0 + alternating noise
        noise = 1.0 if (i % 2 == 0) else -1.0
        angle, vel = kf.update(15.0 + noise, timestamp=t)

    # Kalman filter should converge near 15.0 and reject high frequency alternating noise
    assert 13.5 < angle < 16.5
    # Covariance matrix P should be strictly positive definite
    assert kf.p[0][0] > 0.0
    assert kf.p[1][1] > 0.0


def test_dead_reckoning_extrapolation():
    from gateway.filters import StateSpaceKalmanFilter1D
    kf = StateSpaceKalmanFilter1D(q_pos=0.1, q_vel=2.0, r_meas=1.5, initial_val=0.0)

    # Establish steady angular velocity
    kf.update(0.0, timestamp=0.0)
    kf.update(1.0, timestamp=0.02)
    kf.update(2.0, timestamp=0.04)

    # Extrapolate forward by 16ms (simulated delayed packet)
    current_angle = kf.x[0]
    extrapolated = kf.predict_extrapolate(0.0166)
    # Extrapolated angle must be ahead of current filtered estimate in direction of velocity
    assert extrapolated > current_angle
    assert kf.x[1] > 0.0
