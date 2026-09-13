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

    update = filter

    def reset(self, initial_value: Optional[float] = None) -> None:
        self.state = initial_value


# Alias for academic and benchmark compatibility
ExponentialMovingAverage = EMAFilter


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


class StateSpaceKalmanFilter1D:
    """
    2-State Discrete-Time Linear Kalman Filter with Dead-Reckoning Extrapolator.
    Formulation:
        State Vector: x = [theta (deg), omega (deg/s)]^T
        State Transition: F = [[1, dt], [0, 1]]
        Measurement Matrix: H = [1, 0]
        Riccati Covariance: P_pred = F * P * F^T + Q
        Kalman Gain: K = P_pred * H^T * (H * P_pred * H^T + R)^-1
        State Update: x = x_pred + K * (z - H * x_pred)
    """
    def __init__(
        self,
        q_pos: float = 2.0,
        q_vel: float = 3000.0,
        r_meas: float = 2.5,
        initial_val: float = 0.0,
        dt: float = 0.005,
        process_var: Optional[float] = None,
        measurement_var: Optional[float] = None,
        **kwargs
    ):
        if process_var is not None:
            q_pos = process_var
        if measurement_var is not None:
            r_meas = measurement_var
        self.dt = float(dt)
        self.q_pos = float(q_pos)
        self.q_vel = float(q_vel)
        self.r_meas = float(r_meas)
        self.x = [float(initial_val), 0.0]
        self.p = [[1.0, 0.0], [0.0, 1.0]]
        self.last_timestamp: Optional[float] = None

    @property
    def P(self):
        """Covariance matrix alias for academic uppercase notation."""
        return self.p

    def predict(self, dt: Optional[float] = None) -> Tuple[float, float]:
        """A priori state propagation across discrete time step dt."""
        step = dt if dt is not None else self.dt
        dt_c = max(1e-4, min(0.2, float(step)))
        x_pred = self.x[0] + dt_c * self.x[1]
        v_pred = self.x[1]

        fp00 = self.p[0][0] + dt_c * self.p[1][0]
        fp01 = self.p[0][1] + dt_c * self.p[1][1]
        fp10 = self.p[1][0]
        fp11 = self.p[1][1]

        p00_pred = fp00 + dt_c * fp01 + (self.q_pos * dt_c)
        p01_pred = fp01
        p10_pred = fp10 + dt_c * fp11
        p11_pred = fp11 + (self.q_vel * dt_c)

        self.x[0] = x_pred
        self.x[1] = v_pred
        self.p = [[p00_pred, p01_pred], [p10_pred, p11_pred]]
        return self.x[0], self.x[1]

    def update(self, measurement: float, timestamp: Optional[float] = None) -> Tuple[float, float]:
        """A posteriori measurement correction with dynamic Kalman Gain calculation."""
        t = timestamp if timestamp is not None else time.perf_counter()
        if self.last_timestamp is None:
            self.last_timestamp = t
            self.x[0] = float(measurement)
            self.x[1] = 0.0
            return self.x[0], self.x[1]

        dt = t - self.last_timestamp
        self.last_timestamp = t

        # Prediction step
        self.predict(dt)

        # Innovation
        z = float(measurement)
        residual = z - self.x[0]
        s = self.p[0][0] + self.r_meas

        k0 = self.p[0][0] / s
        k1 = self.p[1][0] / s

        # State update
        self.x[0] += k0 * residual
        self.x[1] += k1 * residual

        # Covariance update
        p00_new = (1.0 - k0) * self.p[0][0]
        p01_new = (1.0 - k0) * self.p[0][1]
        p10_new = self.p[1][0] - k1 * self.p[0][0]
        p11_new = self.p[1][1] - k1 * self.p[0][1]
        self.p = [[p00_new, p01_new], [p10_new, p11_new]]

        return self.x[0], self.x[1]

    def predict_extrapolate(self, dt: float = 0.005, steps_ahead: int = 1) -> float:
        """Dead-reckoning extrapolation for dropped/delayed packets without measurement."""
        step = dt * max(1, steps_ahead)
        dt_c = max(0.0, min(1.0, float(step)))
        return self.x[0] + dt_c * self.x[1]

    extrapolate = predict_extrapolate

    def reset(self, initial_val: float = 0.0) -> None:
        self.x = [float(initial_val), 0.0]
        self.p = [[1.0, 0.0], [0.0, 1.0]]
        self.last_timestamp = None


class SensorFusionPipeline:
    """
    Unified 6-DoF Sensor Fusion & Signal Conditioning Pipeline for an Edge Node.
    Chains Zero-Offset Calibration -> Discrete State-Space Kalman Filter / EMA Smoother
    -> Deadband Filter -> Dynamic Non-Linear Exponential Steering Curve.
    """
    def __init__(
        self,
        ema_alpha: float = 0.35,
        deadband_deg: float = 1.2,
        max_angle_deg: float = 35.0,
        curve_gamma: float = 1.45,
        jerk_threshold: float = 2.6,
        filter_mode: str = "kalman"
    ):
        self.zero_offset_deg: float = 0.0
        self.filter_mode = filter_mode.lower()  # "kalman" or "ema"
        self.deadband_filter = DeadbandFilter(deadband=deadband_deg, max_val=max_angle_deg)
        self.ema_filter = EMAFilter(alpha=ema_alpha)
        self.kalman_filter = StateSpaceKalmanFilter1D()
        self.steering_curve = ExponentialSteeringCurve(gamma=curve_gamma)
        self.jerk_detector = JerkDetector(jerk_threshold_g_s=jerk_threshold)

        # Telemetry Cache
        self.latest_raw_angle: float = 0.0
        self.latest_kalman_angle: float = 0.0
        self.latest_ema_angle: float = 0.0
        self.latest_velocity_deg_s: float = 0.0

    def calibrate_zero(self, current_angle_deg: float) -> None:
        """Sets current physical orientation as the neutral center (0 deg)."""
        self.zero_offset_deg = float(current_angle_deg)
        self.ema_filter.reset(0.0)
        self.kalman_filter.reset(0.0)

    def process_steering(
        self,
        raw_angle_deg: float,
        timestamp: Optional[float] = None
    ) -> Tuple[int, float, float]:
        """
        Processes raw gyro/orientation angle through the active mathematical filter.
        Returns:
            (xinput_stick_val [-32768, 32767], smoothed_angle_deg, normalized_factor [-1.0, 1.0])
        """
        self.latest_raw_angle = float(raw_angle_deg)
        zeroed_angle = self.latest_raw_angle - self.zero_offset_deg

        # Update both filters concurrently for live comparison
        self.latest_ema_angle = self.ema_filter.filter(zeroed_angle)
        kalman_angle, vel = self.kalman_filter.update(zeroed_angle, timestamp)
        self.latest_kalman_angle = kalman_angle
        self.latest_velocity_deg_s = vel

        filtered_angle = self.latest_kalman_angle if self.filter_mode == "kalman" else self.latest_ema_angle

        # Deadband window & linear normalization [-1.0, 1.0]
        normalized = self.deadband_filter.apply(filtered_angle)

        # Non-linear dynamic sensitivity curve -> 16-bit XInput
        xinput_val = self.steering_curve.compute(normalized)

        return xinput_val, filtered_angle, normalized

    def extrapolate_steering(self, dt: float) -> Tuple[int, float, float]:
        """Dead-reckoning extrapolation during Wi-Fi jitter pauses."""
        extrapolated_angle = self.kalman_filter.predict_extrapolate(dt)
        normalized = self.deadband_filter.apply(extrapolated_angle)
        xinput_val = self.steering_curve.compute(normalized)
        return xinput_val, extrapolated_angle, normalized

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
