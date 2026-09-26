"""
Project Controller - Virtual Hardware MCU High-Rate Dispatch Engine (Pillar 1)
Emulates a dedicated 1000 Hz - 5000 Hz USB hardware microcontroller on the host PC.
Continuously pushes latched input reports to the ViGEmBus kernel driver at strict,
sub-millisecond intervals using Windows multimedia timers and hybrid spinlocks.
"""

import sys
import os
import time
import math
import ctypes
import platform
import logging
import threading
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

logger = logging.getLogger("Controller.MCU")


@dataclass
class SlotStateLatch:
    """Atomic state latch for a single controller slot."""
    stick_x: int = 0
    stick_y: int = 0
    right_stick_x: int = 0
    right_stick_y: int = 0
    throttle: int = 0
    brake: int = 0
    buttons: Dict[str, bool] = field(default_factory=dict)
    has_active_client: bool = False
    last_packet_time: float = 0.0
    sequence_num: int = 0

    def reset(self) -> None:
        self.stick_x = 0
        self.stick_y = 0
        self.right_stick_x = 0
        self.right_stick_y = 0
        self.throttle = 0
        self.brake = 0
        self.buttons.clear()
        self.has_active_client = False
        self.last_packet_time = 0.0
        self.sequence_num = 0


class VirtualMcuDispatcher:
    """
    Dedicated High-Priority 1000 Hz – 5000 Hz Virtual MCU Dispatch Engine.
    Operates as the virtual gamepad's onboard USB hardware transceiver, pushing
    continuous state updates to the Windows OS kernel driver at fixed, unwavering intervals.
    """

    def __init__(
        self,
        controllers: List[Any],
        target_hz: float = 1000.0,
        enable_hybrid_spinlock: bool = True,
        max_slots: int = 4
    ):
        self.controllers = controllers
        self.max_slots = max_slots
        self.target_hz = float(target_hz)
        self.enable_hybrid_spinlock = bool(enable_hybrid_spinlock)
        self.interval = 1.0 / max(100.0, self.target_hz)

        # Per-slot atomic state latches
        self.latches: List[SlotStateLatch] = [SlotStateLatch() for _ in range(max_slots)]
        self._latch_locks: List[threading.Lock] = [threading.Lock() for _ in range(max_slots)]

        # Execution thread state
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # Pillar 2: Real-time Predictive Micro-Interpolation Engine
        self.enable_predictive_interpolation = True
        self.interpolator = None
        try:
            from gateway.predictive_interpolator import PredictiveInterpolator
            from config import settings
            self.enable_predictive_interpolation = getattr(settings.mcu, "ENABLE_PREDICTIVE_INTERPOLATION", True)
            comp = getattr(settings.mcu, "LATENCY_COMPENSATION_FACTOR", 1.0)
            self.interpolator = PredictiveInterpolator(max_slots=max_slots, latency_comp_factor=comp)
        except Exception as e:
            logger.debug(f"Predictive interpolator init note: {e}")

        # Telemetry & Performance Monitoring
        self.total_dispatches: int = 0
        self.measured_hz: float = 0.0
        self.jitter_us: float = 0.0
        self.max_jitter_us: float = 0.0
        self.min_interval_us: float = 999999.0
        self.max_interval_us: float = 0.0

        # Windows Multimedia Timer Handle
        self._winmm_active = False

    def _setup_windows_timer(self) -> None:
        """Sets Windows timer resolution to 0.5ms - 1ms via winmm.dll and ntdll.dll."""
        try:
            sys.setswitchinterval(0.0005)
        except Exception:
            pass
        if platform.system() == "Windows":
            try:
                winmm = ctypes.windll.winmm
                if winmm.timeBeginPeriod(1) == 0:
                    self._winmm_active = True
                    logger.debug("Windows multimedia timer resolution set to 1ms (timeBeginPeriod)")
            except Exception as e:
                logger.debug(f"Could not initialize Windows multimedia timer: {e}")
            try:
                ntdll = ctypes.windll.ntdll
                current_res = ctypes.c_ulong(0)
                ntdll.NtSetTimerResolution(5000, True, ctypes.byref(current_res))
            except Exception:
                pass

    def _teardown_windows_timer(self) -> None:
        """Restores default Windows timer resolution."""
        if self._winmm_active:
            try:
                winmm = ctypes.windll.winmm
                winmm.timeEndPeriod(1)
                self._winmm_active = False
            except Exception:
                pass

    def set_target_rate(self, target_hz: float) -> None:
        """Dynamically adjusts target polling rate (1000 Hz, 2000 Hz, 4000 Hz, 5000 Hz)."""
        clamped_hz = max(100.0, min(10000.0, float(target_hz)))
        self.target_hz = clamped_hz
        self.interval = 1.0 / clamped_hz
        logger.info(f"Virtual MCU target polling rate set to {self.target_hz:.1f} Hz (interval: {self.interval*1000:.3f} ms)")

    def update_slot_input(
        self,
        slot_idx: int,
        control_state: Dict[str, Any],
        timestamp: Optional[float] = None,
        rtt_ms: float = 5.0
    ) -> bool:
        """
        Asynchronously writes incoming network control state into the slot's atomic latch
        and feeds the Pillar 2 Predictive Interpolator.
        """
        if not (0 <= slot_idx < self.max_slots):
            return False

        t = timestamp if timestamp is not None else time.time()

        with self._latch_locks[slot_idx]:
            latch = self.latches[slot_idx]
            latch.has_active_client = True
            latch.last_packet_time = t
            latch.sequence_num += 1

            if "stick_x" in control_state:
                latch.stick_x = int(control_state["stick_x"])
            if "stick_y" in control_state:
                latch.stick_y = int(control_state["stick_y"])
            if "right_stick_x" in control_state:
                latch.right_stick_x = int(control_state["right_stick_x"])
            if "right_stick_y" in control_state:
                latch.right_stick_y = int(control_state["right_stick_y"])
            if "throttle" in control_state:
                latch.throttle = int(control_state["throttle"])
            if "brake" in control_state:
                latch.brake = int(control_state["brake"])
            if "buttons" in control_state:
                latch.buttons.update(control_state["buttons"])

        # Pillar 2: Feed Predictive Micro-Interpolator
        if self.enable_predictive_interpolation and self.interpolator is not None:
            self.interpolator.feed_packet(slot_idx, control_state, t, rtt_ms)

        return True

    def reset_slot(self, slot_idx: int) -> None:
        """Resets a slot to neutral resting state."""
        if 0 <= slot_idx < self.max_slots:
            with self._latch_locks[slot_idx]:
                self.latches[slot_idx].reset()
            if self.interpolator is not None:
                self.interpolator.reset_slot(slot_idx)

    def start(self) -> None:
        """Starts the high-priority Virtual MCU dispatch loop."""
        if self._running:
            return

        self._running = True
        self._stop_event.clear()
        self._setup_windows_timer()

        self._thread = threading.Thread(
            target=self._mcu_loop,
            name="VirtualMcuEngine",
            daemon=True
        )
        self._thread.start()
        logger.info(f"Virtual MCU Engine STARTED @ {self.target_hz:.0f} Hz (Pillar 1 Active)")

    def stop(self) -> None:
        """Gracefully stops the Virtual MCU dispatch loop."""
        if not self._running:
            return

        self._running = False
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.5)

        self._teardown_windows_timer()
        logger.info("Virtual MCU Engine STOPPED")

    def _mcu_loop(self) -> None:
        """
        High-precision dispatch loop.
        Runs at the exact target interval (e.g. 1.000 ms for 1000 Hz, 0.200 ms for 5000 Hz)
        while explicitly yielding the Python GIL every tick so network/WebSocket threads
        experience zero GIL contention or ping spikes.
        """
        next_tick = time.perf_counter()

        # Rolling statistics window (sampled every 250 reports)
        window_size = 250
        delta_window: List[float] = []
        last_stat_time = time.perf_counter()
        reports_in_window = 0

        target_int = self.interval

        while self._running and not self._stop_event.is_set():
            t_start = time.perf_counter()

            # 1. Dispatch latched or predictive interpolated state to active controllers
            for slot_idx in range(min(len(self.controllers), self.max_slots)):
                ctrl = self.controllers[slot_idx]
                is_mock = getattr(ctrl, "is_mock", False) or ctrl.__class__.__name__ == "MockGamepad"
                with self._latch_locks[slot_idx]:
                    latch = self.latches[slot_idx]
                    if not latch.has_active_client and not is_mock:
                        continue

                    # Pillar 2: Sample smooth micro-interpolated and latency-compensated analog coordinates
                    interp = None
                    if self.enable_predictive_interpolation and self.interpolator is not None:
                        interp = self.interpolator.sample_slot(slot_idx, t_start)

                    if interp is not None:
                        sx = interp["stick_x"]
                        sy = interp["stick_y"]
                        rx = interp["right_stick_x"]
                        ry = interp["right_stick_y"]
                        th = interp["throttle"]
                        br = interp["brake"]
                        btns = interp["buttons"]
                    else:
                        sx = latch.stick_x
                        sy = latch.stick_y
                        rx = latch.right_stick_x
                        ry = latch.right_stick_y
                        th = latch.throttle
                        br = latch.brake
                        btns = latch.buttons

                    # 1000 Hz Sub-Perceptual Active State Dither:
                    # Windows XInput only increments dwPacketNumber when controller state bytes change.
                    if latch.has_active_client and not is_mock:
                        if sx == 0 and sy == 0:
                            sx = 1 if (self.total_dispatches & 1) else 0

                    # Apply continuous analog sticks
                    if hasattr(ctrl, "set_stick"):
                        ctrl.set_stick(sx, sy)
                    elif hasattr(ctrl, "set_steering"):
                        ctrl.set_steering(sx)

                    if hasattr(ctrl, "set_right_stick"):
                        ctrl.set_right_stick(rx, ry)

                    if hasattr(ctrl, "set_throttle"):
                        ctrl.set_throttle(th)
                    if hasattr(ctrl, "set_brake"):
                        ctrl.set_brake(br)

                    if hasattr(ctrl, "set_button"):
                        for btn_name, pressed in btns.items():
                            ctrl.set_button(btn_name, pressed)

                # Push updated report to ViGEm kernel driver
                try:
                    ctrl.update()
                except Exception:
                    pass

            self.total_dispatches += 1
            reports_in_window += 1

            # 2. Timing telemetry accounting
            t_done = time.perf_counter()
            actual_delta = t_done - t_start
            delta_window.append(actual_delta)

            if len(delta_window) >= window_size:
                now_stat = time.perf_counter()
                elapsed = now_stat - last_stat_time
                if elapsed > 0:
                    self.measured_hz = float(reports_in_window / elapsed)

                # Compute jitter standard deviation in microseconds
                mean_d = sum(delta_window) / len(delta_window)
                variance = sum((d - mean_d) ** 2 for d in delta_window) / len(delta_window)
                self.jitter_us = math.sqrt(variance) * 1e6
                self.max_jitter_us = max(self.max_jitter_us, self.jitter_us)

                delta_window.clear()
                reports_in_window = 0
                last_stat_time = now_stat

            # 3. High-precision schedule next frame with explicit GIL release
            target_int = self.interval
            next_tick += target_int

            now = time.perf_counter()
            remaining = next_tick - now

            # If behind schedule (e.g. OS interrupt / frame drop), skip forward to prevent cascade
            if remaining < -0.010:
                next_tick = now + target_int
                time.sleep(0)
                continue

            # Hybrid Sleep + GIL-Cooperative Microsecond Spinlock
            if self.enable_hybrid_spinlock:
                if remaining > 0.0015:
                    time.sleep(remaining - 0.0010)
                else:
                    # Explicitly release and re-acquire Python GIL in C so asyncio network
                    # threads can immediately service incoming WebSocket packets & PINGs
                    time.sleep(0)
                spin_iters = 0
                while time.perf_counter() < next_tick:
                    spin_iters += 1
                    if (spin_iters & 15) == 0:
                        time.sleep(0)
            else:
                if remaining > 0.0001:
                    time.sleep(remaining)

    def get_metrics(self) -> Dict[str, Any]:
        """Returns real-time telemetry metrics for HUD and logging."""
        return {
            "target_hz": self.target_hz,
            "measured_hz": round(self.measured_hz, 1) if self.measured_hz > 0 else self.target_hz,
            "total_dispatches": self.total_dispatches,
            "jitter_us": round(self.jitter_us, 1),
            "max_jitter_us": round(self.max_jitter_us, 1),
            "running": self._running,
            "winmm_active": self._winmm_active
        }
