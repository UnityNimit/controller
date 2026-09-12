"""
Project Controller - Mathematical Signal Processing & Sensor Fusion Pipeline
Implements Exponential Moving Average (EMA), Deadband Thresholding,
Non-Linear Dynamic Sensitivity Curves, and Jerk Detection.
"""

import math
import time
from typing import Optional, Tuple, Dict, Any


class EMAFilter:
    """
    Single-pole Exponential Moving Average (EMA) Low-Pass Filter.
    Formulation:
        y[t] = alpha * x[t] + (1 - alpha) * y[t - 1]
    Eliminates high-frequency hand tremors and thermal IMU sensor noise.
    """
    def __init__(self, alpha: float = 0.35, initial_value: Optional[float] = None):
        if not (0.0 < alpha <= 1.0):
            raise ValueError(f"EMA alpha must be in (0.0, 1.0], got {alpha}")
        self.alpha = float(alpha)
        self.state: Optional[float] = initial_value

    def filter(self, raw_value: float) -> float:
        if self.state is None:
            self.state = float(raw_value)
            return self.state
        self.state = (self.alpha * float(raw_value)) + ((1.0 - self.alpha) * self.state)
        return self.state

    def reset(self, initial_value: Optional[float] = None) -> None:
        self.state = initial_value


class DeadbandFilter:
    """
    Linear Deadband Window with Smooth Continuous Rescaling.
    Prevents step-discontinuity when exiting the deadband region:
        f(x) = 0, if |x| <= deadband
        f(x) = sign(x) * (|x| - deadband) / (max_val - deadband), otherwise
    """
    def __init__(self, deadband: float = 1.2, max_val: float = 35.0):
        self.deadband = float(abs(deadband))
        self.max_val = float(abs(max_val))
        if self.deadband >= self.max_val:
            raise ValueError(f"Deadband ({self.deadband}) must be strictly less than max_val ({self.max_val})")

    def apply(self, value: float) -> float:
        val = float(value)
        abs_val = abs(val)
        if abs_val <= self.deadband:
            return 0.0
        
        sign = 1.0 if val > 0 else -1.0
        scaled = (abs_val - self.deadband) / (self.max_val - self.deadband)
        clamped = min(1.0, max(0.0, scaled))
        return sign * clamped


class ExponentialSteeringCurve:
    """
    Non-Linear Dynamic Sensitivity Response Curve.
    Formulation:
        S(norm_x) = sign(norm_x) * (|norm_x| ** gamma)
    Scales normalized [-1.0, 1.0] steering domain into native 16-bit
    signed XInput thumbstick range [-32768, 32767].
    """
    def __init__(self, gamma: float = 1.45):
        self.gamma = float(gamma)

    def compute(self, normalized_steering: float) -> int:
        norm = max(-1.0, min(1.0, float(normalized_steering)))
        sign = 1.0 if norm >= 0 else -1.0
        curved = sign * (abs(norm) ** self.gamma)
        
        # Map to signed 16-bit XInput thumbstick integer range
        if curved >= 0:
            return int(curved * 32767)
        else:
            return int(curved * 32768)


class JerkDetector:
    """
    Eulerian Jerk (da/dt) & Sudden Spike Detector.
    Monitors high-rate 3-axis accelerometer vector:
        j = | ||a(t)|| - ||a(t - dt)|| | / dt
    Used for gesture trigger (e.g. sharp upward snap -> mechanical handbrake).
    """
    def __init__(self, jerk_threshold_g_s: float = 2.6, debounce_sec: float = 0.4):
        self.jerk_threshold = float(jerk_threshold_g_s)
        self.debounce_sec = float(debounce_sec)
        self.last_magnitude: Optional[float] = None
        self.last_timestamp: Optional[float] = None
        self.last_trigger_time: float = -1e9

    def update(self, ax: float, ay: float, az: float, timestamp: Optional[float] = None) -> bool:
        t = timestamp if timestamp is not None else time.perf_counter()
        magnitude = math.sqrt(ax * ax + ay * ay + az * az)

        if self.last_magnitude is None or self.last_timestamp is None:
            self.last_magnitude = magnitude
            self.last_timestamp = t
            return False

        dt = t - self.last_timestamp
        self.last_timestamp = t

        if dt <= 1e-4:
            return False

        jerk = abs(magnitude - self.last_magnitude) / dt
        self.last_magnitude = magnitude

        # Check threshold and debounce
        if jerk >= self.jerk_threshold and (t - self.last_trigger_time) >= self.debounce_sec:
            self.last_trigger_time = t
            return True

        return False


class SensorFusionPipeline:
    """
    Unified 6-DoF Sensor Fusion & Signal Conditioning Pipeline for an Edge Node.
    Chains Zero-Offset Calibration -> Deadband Filter -> EMA Smoother -> Dynamic Curve.
    """
    def __init__(
        self,
        ema_alpha: float = 0.35,
        deadband_deg: float = 1.2,
        max_angle_deg: float = 35.0,
        curve_gamma: float = 1.45,
        jerk_threshold: float = 2.6
    ):
        self.zero_offset_deg: float = 0.0
        self.deadband_filter = DeadbandFilter(deadband=deadband_deg, max_val=max_angle_deg)
        self.ema_filter = EMAFilter(alpha=ema_alpha)
        self.steering_curve = ExponentialSteeringCurve(gamma=curve_gamma)
        self.jerk_detector = JerkDetector(jerk_threshold_g_s=jerk_threshold)

    def calibrate_zero(self, current_angle_deg: float) -> None:
        """Sets current physical orientation as the neutral center (0 deg)."""
        self.zero_offset_deg = float(current_angle_deg)
        self.ema_filter.reset(0.0)

    def process_steering(self, raw_angle_deg: float) -> Tuple[int, float, float]:
        """
        Processes raw gyro/orientation angle.
        Returns:
            (xinput_stick_val [-32768, 32767], smoothed_angle_deg, normalized_factor [-1.0, 1.0])
        """
        # Step 1: Calibration zero correction
        zeroed_angle = float(raw_angle_deg) - self.zero_offset_deg
        
        # Step 2: Exponential Moving Average Filter
        filtered_angle = self.ema_filter.filter(zeroed_angle)
        
        # Step 3: Deadband window & linear normalization [-1.0, 1.0]
        normalized = self.deadband_filter.apply(filtered_angle)
        
        # Step 4: Non-linear dynamic sensitivity curve -> 16-bit XInput
        xinput_val = self.steering_curve.compute(normalized)
        
        return xinput_val, filtered_angle, normalized

    def process_triggers(self, raw_throttle: float, raw_brake: float) -> Tuple[int, int]:
        """
        Processes normalized throttle and brake inputs [0.0, 1.0].
        Direct 1:1 mapping with 0ms latency and guaranteed zero cutoff upon release.
        Returns 8-bit XInput trigger bytes [0, 255].
        """
        th = max(0.0, min(1.0, float(raw_throttle)))
        br = max(0.0, min(1.0, float(raw_brake)))

        th_byte = int(round(th * 255.0)) if th > 0.001 else 0
        br_byte = int(round(br * 255.0)) if br > 0.001 else 0

        return th_byte, br_byte

    def process_acceleration(self, ax: float, ay: float, az: float, timestamp: Optional[float] = None) -> bool:
        """Evaluates linear acceleration jerk. Returns True if sudden handbrake jerk is detected."""
        return self.jerk_detector.update(ax, ay, az, timestamp)
