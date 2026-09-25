"""
Project Controller - State-Space Kalman & Hermite Predictive Micro-Interpolation Engine (Pillar 2)
Provides sub-millisecond continuous analog trajectory generation and real-time network latency compensation.
Eliminates staircasing and stepping in high-refresh-rate gaming environments (144Hz, 240Hz, 360Hz).
"""

import time
import math
import threading
from typing import Dict, Any, List, Optional, Tuple


class AxisPredictor:
    """
    High-Speed 1D Analog Axis Predictor & Interpolator.
    Combines a 2nd-order State-Space Kalman filter (position, velocity, acceleration)
    with Monotonic Hermite Cubic Spline interpolation and dead-reckoning latency compensation.
    """

    def __init__(
        self,
        min_val: float = -32768.0,
        max_val: float = 32767.0,
        deadband: float = 600.0,
        q_pos: float = 5.0,
        q_vel: float = 8000.0,
        q_acc: float = 20000.0,
        r_meas: float = 8.0,
        name: str = "axis"
    ):
        self.name = name
        self.min_val = float(min_val)
        self.max_val = float(max_val)
        self.deadband = float(abs(deadband))

        # 3-State Kalman Filter: x = [pos, vel, acc]^T
        self.x: List[float] = [0.0, 0.0, 0.0]
        # Covariance Matrix (P) initialized with high velocity/accel variance for rapid adaptation
        self.p: List[List[float]] = [
            [100.0, 0.0, 0.0],
            [0.0, 1000000.0, 0.0],
            [0.0, 0.0, 1000000.0]
        ]
        self.q = [q_pos, q_vel, q_acc]
        self.r_meas = r_meas

        # History buffer for cubic spline knots: list of (timestamp, value, velocity)
        self.history: List[Tuple[float, float, float]] = []
        self.max_history = 5
        self.last_update_time: float = 0.0
        self.is_active: bool = False

    def reset(self) -> None:
        """Resets state to neutral zero."""
        self.x = [0.0, 0.0, 0.0]
        self.p = [
            [100.0, 0.0, 0.0],
            [0.0, 1000000.0, 0.0],
            [0.0, 0.0, 1000000.0]
        ]
        self.history.clear()
        self.last_update_time = 0.0
        self.is_active = False

    def feed_sample(self, raw_value: float, timestamp: Optional[float] = None) -> None:
        """
        Ingests a new raw arrival sample, updates the Kalman filter, and appends a spline knot.
        """
        t = timestamp if timestamp is not None else time.perf_counter()
        val = float(max(self.min_val, min(self.max_val, raw_value)))

        # First sample initialization
        if self.last_update_time == 0.0:
            self.x = [val, 0.0, 0.0]
            self.last_update_time = t
            self.is_active = (abs(val) > self.deadband)
            self.history = [(t, val, 0.0)]
            return

        dt = max(0.0005, min(0.1, t - self.last_update_time))
        self.last_update_time = t
        self.is_active = (abs(val) > self.deadband)

        # 1. State-Space Kalman Prediction:
        # State transition F = [[1, dt, 0.5*dt^2], [0, 1, dt], [0, 0, alpha]]
        alpha = 0.95
        dt2 = 0.5 * dt * dt
        x_pred = [
            self.x[0] + dt * self.x[1] + dt2 * self.x[2],
            self.x[1] + dt * self.x[2],
            alpha * self.x[2]
        ]

        # Covariance propagation: M = F * P
        m00 = self.p[0][0] + dt * self.p[1][0] + dt2 * self.p[2][0]
        m01 = self.p[0][1] + dt * self.p[1][1] + dt2 * self.p[2][1]
        m02 = self.p[0][2] + dt * self.p[1][2] + dt2 * self.p[2][2]

        m10 = self.p[1][0] + dt * self.p[2][0]
        m11 = self.p[1][1] + dt * self.p[2][1]
        m12 = self.p[1][2] + dt * self.p[2][2]

        m20 = alpha * self.p[2][0]
        m21 = alpha * self.p[2][1]
        m22 = alpha * self.p[2][2]

        # P_pred = M * F^T + Q*dt
        p00_pred = m00 + dt * m01 + dt2 * m02 + self.q[0] * dt
        p01_pred = m01 + dt * m02
        p02_pred = alpha * m02

        p11_pred = m11 + dt * m12 + self.q[1] * dt
        p12_pred = alpha * m12

        p22_pred = alpha * m22 + self.q[2] * dt

        # 2. Kalman Measurement Innovation (Measurement matrix H = [1, 0, 0])
        residual = val - x_pred[0]
        s = p00_pred + self.r_meas
        k0 = p00_pred / s
        k1 = p01_pred / s
        k2 = p02_pred / s

        # Updated state vector
        self.x[0] = x_pred[0] + k0 * residual
        self.x[1] = x_pred[1] + k1 * residual
        self.x[2] = x_pred[2] + k2 * residual

        # Updated covariance matrix P = (I - K*H) * P_pred
        self.p[0][0] = p00_pred - k0 * p00_pred
        self.p[0][1] = p01_pred - k0 * p01_pred
        self.p[0][2] = p02_pred - k0 * p02_pred

        self.p[1][0] = self.p[0][1]
        self.p[1][1] = p11_pred - k1 * p01_pred
        self.p[1][2] = p12_pred - k1 * p02_pred

        self.p[2][0] = self.p[0][2]
        self.p[2][1] = self.p[1][2]
        self.p[2][2] = p22_pred - k2 * p02_pred

        # 3. Store in spline knot history
        filtered_val = self.x[0]
        velocity = self.x[1]
        self.history.append((t, filtered_val, velocity))
        if len(self.history) > self.max_history:
            self.history.pop(0)

    def sample(self, query_time: float, lookahead_sec: float = 0.0) -> int:
        """
        Samples the micro-interpolated / extrapolated coordinate at high frequency (1000 Hz / 5000 Hz).
        Applies Monotonic Hermite Spline interpolation or dead-reckoning extrapolation with latency compensation.
        """
        if not self.history:
            return 0

        # Center deadband check: if raw position is in deadband and velocity is near-zero, snap to zero
        if abs(self.x[0]) <= self.deadband and abs(self.x[1]) < 800.0:
            return 0

        target_t = query_time + max(0.0, min(0.025, lookahead_sec))
        latest_t, latest_v, latest_vel = self.history[-1]

        # Case A: Query time is in the future relative to our latest packet -> Dead-Reckoning Extrapolation
        if target_t >= latest_t:
            dt = target_t - latest_t
            # Damping factor: decay velocity if packet is delayed >20ms to prevent overshoot
            decay = math.exp(-max(0.0, dt - 0.015) * 45.0)
            extrapolated = latest_v + (latest_vel * dt * decay) + (0.5 * self.x[2] * dt * dt * decay)
            result = max(self.min_val, min(self.max_val, extrapolated))
            if abs(result) <= self.deadband:
                return 0
            return int(round(result))

        # Case B: Query time is within our history window -> Monotonic Hermite Cubic Spline Interpolation
        # Find knot segment [t_k, t_k+1]
        p0, p1 = None, None
        for i in range(len(self.history) - 1):
            if self.history[i][0] <= target_t <= self.history[i + 1][0]:
                p0 = self.history[i]
                p1 = self.history[i + 1]
                break

        if p0 is None or p1 is None:
            result = latest_v
            if abs(result) <= self.deadband:
                return 0
            return int(round(result))

        t0, y0, m0 = p0
        t1, y1, m1 = p1
        span = t1 - t0
        if span <= 1e-6:
            result = y1
        else:
            s = (target_t - t0) / span
            s2 = s * s
            s3 = s2 * s

            # Hermite basis polynomials
            h00 = 2 * s3 - 3 * s2 + 1
            h10 = s3 - 2 * s2 + s
            h01 = -2 * s3 + 3 * s2
            h11 = s3 - s2

            # Fritsch-Carlson monotonicity constraint on tangents
            delta = (y1 - y0) / span
            if abs(delta) < 1e-6:
                m0_c = 0.0
                m1_c = 0.0
            else:
                alpha = m0 / delta
                beta = m1 / delta
                if alpha < 0:
                    m0_c = 0.0
                else:
                    m0_c = m0
                if beta < 0:
                    m1_c = 0.0
                else:
                    m1_c = m1
                if alpha * alpha + beta * beta > 9.0:
                    tau = 3.0 / math.sqrt(alpha * alpha + beta * beta)
                    m0_c = tau * alpha * delta
                    m1_c = tau * beta * delta

            interpolated = (h00 * y0) + (h10 * span * m0_c) + (h01 * y1) + (h11 * span * m1_c)
            result = max(self.min_val, min(self.max_val, interpolated))

        if abs(result) <= self.deadband:
            return 0
        return int(round(result))


class SlotPredictiveState:
    """Manages all 6 analog channels and digital buttons for a single player slot."""

    def __init__(self, slot_idx: int):
        self.slot_idx = slot_idx
        self.stick_x = AxisPredictor(min_val=-32768, max_val=32767, deadband=600, name="stick_x")
        self.stick_y = AxisPredictor(min_val=-32768, max_val=32767, deadband=600, name="stick_y")
        self.right_stick_x = AxisPredictor(min_val=-32768, max_val=32767, deadband=600, name="right_stick_x")
        self.right_stick_y = AxisPredictor(min_val=-32768, max_val=32767, deadband=600, name="right_stick_y")
        self.throttle = AxisPredictor(min_val=0, max_val=255, deadband=2, name="throttle")
        self.brake = AxisPredictor(min_val=0, max_val=255, deadband=2, name="brake")
        self.buttons: Dict[str, bool] = {}
        self.last_packet_time: float = 0.0
        self.rtt_sec: float = 0.005  # Default 5ms network latency estimate
        self.is_active: bool = False

    def reset(self) -> None:
        self.stick_x.reset()
        self.stick_y.reset()
        self.right_stick_x.reset()
        self.right_stick_y.reset()
        self.throttle.reset()
        self.brake.reset()
        self.buttons.clear()
        self.last_packet_time = 0.0
        self.is_active = False

    def feed_packet(self, control_state: Dict[str, Any], timestamp: float, rtt_ms: float = 5.0) -> None:
        self.is_active = True
        self.last_packet_time = timestamp
        self.rtt_sec = max(0.001, min(0.050, rtt_ms / 1000.0))

        if "stick_x" in control_state:
            self.stick_x.feed_sample(control_state["stick_x"], timestamp)
        if "stick_y" in control_state:
            self.stick_y.feed_sample(control_state["stick_y"], timestamp)
        if "right_stick_x" in control_state:
            self.right_stick_x.feed_sample(control_state["right_stick_x"], timestamp)
        if "right_stick_y" in control_state:
            self.right_stick_y.feed_sample(control_state["right_stick_y"], timestamp)
        if "throttle" in control_state:
            self.throttle.feed_sample(control_state["throttle"], timestamp)
        if "brake" in control_state:
            self.brake.feed_sample(control_state["brake"], timestamp)
        if "buttons" in control_state:
            self.buttons.update(control_state["buttons"])

    def sample(self, current_time: float, latency_comp_factor: float = 1.0) -> Dict[str, Any]:
        """Samples all 6 analog channels with dynamic one-way latency compensation."""
        # One-way network latency estimate: half of measured RTT
        lookahead = (self.rtt_sec * 0.5) * latency_comp_factor
        return {
            "stick_x": self.stick_x.sample(current_time, lookahead),
            "stick_y": self.stick_y.sample(current_time, lookahead),
            "right_stick_x": self.right_stick_x.sample(current_time, lookahead),
            "right_stick_y": self.right_stick_y.sample(current_time, lookahead),
            "throttle": self.throttle.sample(current_time, lookahead),
            "brake": self.brake.sample(current_time, lookahead),
            "buttons": dict(self.buttons),
            "is_active": self.is_active
        }


class PredictiveInterpolator:
    """
    Multi-Slot Master Orchestrator for Real-Time Predictive Micro-Interpolation.
    Thread-safe bridge between asynchronous incoming network packets and the 1000 Hz / 5000 Hz Virtual MCU loop.
    """

    def __init__(self, max_slots: int = 4, latency_comp_factor: float = 1.0):
        self.max_slots = max_slots
        self.latency_comp_factor = float(latency_comp_factor)
        self.slots: List[SlotPredictiveState] = [SlotPredictiveState(i) for i in range(max_slots)]
        self._lock = threading.Lock()

    def feed_packet(self, slot_idx: int, control_state: Dict[str, Any], timestamp: Optional[float] = None, rtt_ms: float = 5.0) -> bool:
        if not (0 <= slot_idx < self.max_slots):
            return False
        t = timestamp if timestamp is not None else time.perf_counter()
        with self._lock:
            self.slots[slot_idx].feed_packet(control_state, t, rtt_ms)
        return True

    def sample_slot(self, slot_idx: int, current_time: Optional[float] = None) -> Optional[Dict[str, Any]]:
        if not (0 <= slot_idx < self.max_slots):
            return None
        t = current_time if current_time is not None else time.perf_counter()
        with self._lock:
            slot = self.slots[slot_idx]
            if not slot.is_active:
                return None
            return slot.sample(t, self.latency_comp_factor)

    def reset_slot(self, slot_idx: int) -> None:
        if 0 <= slot_idx < self.max_slots:
            with self._lock:
                self.slots[slot_idx].reset()

    def reset_all(self) -> None:
        with self._lock:
            for s in self.slots:
                s.reset()
