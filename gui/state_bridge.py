"""
Project Controller - Thread-Safe Telemetry & State Bridge
Transfers high-frequency input frames, latency metrics, controller slot states,
and logging records from the AsyncIO Gateway to the CustomTkinter GUI thread.
"""

import time
import queue
import logging
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class ControllerSlotState:
    slot_index: int
    connected: bool = False
    client_id: str = ""
    client_ip: str = ""
    player_color: str = "#00f5ff"
    last_seen: float = 0.0
    rtt_ms: float = 0.0
    jitter_ms: float = 0.0
    packet_rate_hz: float = 0.0
    total_packets: int = 0
    stick_x: int = 0
    stick_y: int = 0
    right_stick_x: int = 0
    right_stick_y: int = 0
    throttle: int = 0
    brake: int = 0
    buttons: Dict[str, bool] = field(default_factory=dict)
    # Dedicated per-slot time-series ring buffers
    latency_history: deque = field(default_factory=lambda: deque(maxlen=80))
    stick_x_history: deque = field(default_factory=lambda: deque(maxlen=80))
    stick_y_history: deque = field(default_factory=lambda: deque(maxlen=80))
    right_stick_x_history: deque = field(default_factory=lambda: deque(maxlen=80))
    right_stick_y_history: deque = field(default_factory=lambda: deque(maxlen=80))
    throttle_history: deque = field(default_factory=lambda: deque(maxlen=80))
    brake_history: deque = field(default_factory=lambda: deque(maxlen=80))


class QueueLogHandler(logging.Handler):
    """Captures Python logging events and routes them to a thread-safe GUI log queue."""
    def __init__(self, log_queue: queue.Queue, max_records: int = 500):
        super().__init__()
        self.log_queue = log_queue
        self.max_records = max_records

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            entry = {
                "timestamp": time.strftime("%H:%M:%S", time.localtime(record.created)),
                "level": record.levelname,
                "name": record.name,
                "message": msg
            }
            if self.log_queue.qsize() > self.max_records:
                try:
                    self.log_queue.get_nowait()
                except queue.Empty:
                    pass
            self.log_queue.put_nowait(entry)
        except Exception:
            self.handleError(record)


class TelemetryBridge:
    """
    High-Frequency Thread-Safe Telemetry Bridge.
    Maintains ring-buffers for real-time oscilloscope rendering and multi-controller state.
    """
    def __init__(self, history_len: int = 150):
        self.history_len = history_len

        # Server metadata
        self.server_online: bool = False
        self.server_url: str = ""
        self.primary_ip: str = "127.0.0.1"
        self.port: int = 8443
        self.ssl_enabled: bool = True
        self.driver_status: str = "Detecting..."
        self.start_time: float = time.time()
        self.total_gateway_packets: int = 0

        # Player slots (0 to 3 for Players 1 to 4)
        player_colors = ["#00f5ff", "#00f59b", "#ffb830", "#ff2a8d"]
        self.slots: List[ControllerSlotState] = [
            ControllerSlotState(slot_index=i, player_color=player_colors[i % 4])
            for i in range(4)
        ]

        # Time-series ring buffers for oscilloscope graphs: [(timestamp, value)]
        self.latency_history: deque = deque(maxlen=history_len)
        self.jitter_history: deque = deque(maxlen=history_len)
        self.rate_history: deque = deque(maxlen=history_len)
        self.stick_x_history: deque = deque(maxlen=history_len)
        self.stick_y_history: deque = deque(maxlen=history_len)
        self.right_stick_x_history: deque = deque(maxlen=history_len)
        self.right_stick_y_history: deque = deque(maxlen=history_len)
        self.throttle_history: deque = deque(maxlen=history_len)
        self.brake_history: deque = deque(maxlen=history_len)

        # Logging stream queue
        self.log_queue: queue.Queue = queue.Queue(maxsize=1000)

        # External callbacks
        self.pulse_test_callback: Optional[Any] = None
        self.reinit_driver_callback: Optional[Any] = None
        self.swap_slots_callback: Optional[Any] = None

        # Internal tracking for rate estimation
        self._last_packet_times: Dict[int, deque] = {i: deque(maxlen=30) for i in range(4)}
        self._global_packet_times: deque = deque(maxlen=60)

        # Global aggregate metrics
        self.avg_rtt_ms: float = 0.0
        self.min_rtt_ms: float = 0.0
        self.max_rtt_ms: float = 0.0
        self.effective_hz: float = 0.0

    def pulse_test(self, slot_index: int) -> None:
        """Triggers a momentary button pulse on slot_index to wake up online controller testers."""
        if self.pulse_test_callback is not None:
            try:
                self.pulse_test_callback(slot_index)
            except Exception as e:
                logging.getLogger("Controller.Bridge").debug(f"Pulse test error: {e}")

    def swap_slots(self, slot_a: int, slot_b: int) -> bool:
        """Atomically swaps two player slots in GUI and notifies gateway server."""
        if not (0 <= slot_a < 4 and 0 <= slot_b < 4) or slot_a == slot_b:
            return False

        if self.swap_slots_callback is not None:
            try:
                self.swap_slots_callback(slot_a, slot_b)
            except Exception as e:
                logging.getLogger("Controller.Bridge").error(f"Error in swap_slots_callback: {e}")

        s_a = self.slots[slot_a]
        s_b = self.slots[slot_b]

        s_a.connected, s_b.connected = s_b.connected, s_a.connected
        s_a.client_id, s_b.client_id = s_b.client_id, s_a.client_id
        s_a.client_ip, s_b.client_ip = s_b.client_ip, s_a.client_ip
        s_a.rtt_ms, s_b.rtt_ms = s_b.rtt_ms, s_a.rtt_ms
        s_a.packet_rate_hz, s_b.packet_rate_hz = s_b.packet_rate_hz, s_a.packet_rate_hz
        s_a.total_packets, s_b.total_packets = s_b.total_packets, s_a.total_packets
        s_a.stick_x, s_b.stick_x = 0, 0
        s_a.stick_y, s_b.stick_y = 0, 0
        s_a.right_stick_x, s_b.right_stick_x = 0, 0
        s_a.right_stick_y, s_b.right_stick_y = 0, 0
        s_a.throttle, s_b.throttle = 0, 0
        s_a.brake, s_b.brake = 0, 0
        s_a.buttons, s_b.buttons = {}, {}
        return True

    def reinit_driver(self) -> bool:
        """Attempts to dynamically hot-reload ViGEmBus driver once installed."""
        if self.reinit_driver_callback is not None:
            try:
                success = self.reinit_driver_callback()
                if success:
                    self.driver_status = "ViGEmBus X360"
                return success
            except Exception as e:
                logging.getLogger("Controller.Bridge").debug(f"Reinit driver error: {e}")
        return False

    def register_client(self, slot_index: int, client_id: str, client_ip: str) -> None:
        """Called when a client completes handshake and obtains a controller slot."""
        if 0 <= slot_index < 4:
            slot = self.slots[slot_index]
            slot.connected = True
            slot.client_id = client_id
            slot.client_ip = client_ip
            slot.last_seen = time.time()
            slot.total_packets = 0
            slot.stick_x = 0
            slot.stick_y = 0
            slot.right_stick_x = 0
            slot.right_stick_y = 0
            slot.throttle = 0
            slot.brake = 0
            slot.buttons = {}
            self._last_packet_times[slot_index].clear()

    def unregister_client(self, slot_index: int, client_id: str) -> None:
        """Called when a client disconnects."""
        if 0 <= slot_index < 4:
            slot = self.slots[slot_index]
            if slot.client_id == client_id:
                slot.connected = False
                slot.client_id = ""
                slot.client_ip = ""
                slot.stick_x = 0
                slot.stick_y = 0
                slot.right_stick_x = 0
                slot.right_stick_y = 0
                slot.throttle = 0
                slot.brake = 0
                slot.buttons = {}
                self._last_packet_times[slot_index].clear()

    def record_input(
        self,
        slot_index: int,
        client_id: str,
        control_state: Dict[str, Any],
        client_rtt: float = 0.0,
        inter_arrival_ms: float = 16.6
    ) -> None:
        """High-frequency input frame ingestion from gateway WebSocket."""
        now = time.perf_counter()
        self.total_gateway_packets += 1

        # Global Hz computation
        self._global_packet_times.append(now)
        if len(self._global_packet_times) >= 2:
            dt_span = self._global_packet_times[-1] - self._global_packet_times[0]
            if dt_span > 0:
                self.effective_hz = round((len(self._global_packet_times) - 1) / dt_span, 1)

        # Update slot state
        if 0 <= slot_index < 4:
            slot = self.slots[slot_index]
            slot.last_seen = now
            slot.total_packets += 1
            slot.rtt_ms = client_rtt
            slot.stick_x = control_state.get("stick_x", 0)
            slot.stick_y = control_state.get("stick_y", 0)
            slot.right_stick_x = control_state.get("right_stick_x", 0)
            slot.right_stick_y = control_state.get("right_stick_y", 0)
            slot.throttle = control_state.get("throttle", 0)
            slot.brake = control_state.get("brake", 0)
            slot.buttons = dict(control_state.get("buttons", {}))

            # Per-slot rate
            dq = self._last_packet_times[slot_index]
            dq.append(now)
            if len(dq) >= 2:
                span = dq[-1] - dq[0]
                if span > 0:
                    slot.packet_rate_hz = round((len(dq) - 1) / span, 1)

            # Update live stats for primary slot
            primary_slot = self._get_primary_active_slot()
            if slot_index == primary_slot and client_rtt > 0:
                if self.min_rtt_ms == 0.0 or client_rtt < self.min_rtt_ms:
                    self.min_rtt_ms = client_rtt
                if client_rtt > self.max_rtt_ms:
                    self.max_rtt_ms = client_rtt
                self.avg_rtt_ms = round((self.avg_rtt_ms * 0.9) + (client_rtt * 0.1), 1)

    def _get_primary_active_slot(self) -> int:
        for idx, s in enumerate(self.slots):
            if s.connected:
                return idx
        return 0

    def sample_tick(self) -> None:
        """Called on every GUI render frame to roll continuous waveforms for ALL 4 player slots."""
        now = time.perf_counter()
        for s in self.slots:
            curr_rtt = s.rtt_ms if s.connected else 0.0
            curr_x = s.stick_x if s.connected else 0
            curr_y = s.stick_y if s.connected else 0
            curr_rx = s.right_stick_x if s.connected else 0
            curr_ry = s.right_stick_y if s.connected else 0
            curr_th = s.throttle if s.connected else 0
            curr_br = s.brake if s.connected else 0

            s.latency_history.append((now, curr_rtt))
            s.stick_x_history.append((now, curr_x))
            s.stick_y_history.append((now, curr_y))
            s.right_stick_x_history.append((now, curr_rx))
            s.right_stick_y_history.append((now, curr_ry))
            s.throttle_history.append((now, curr_th))
            s.brake_history.append((now, curr_br))

        # Global aggregate history
        primary_slot = self._get_primary_active_slot()
        prim = self.slots[primary_slot]
        self.latency_history.append((now, prim.rtt_ms if prim.connected else 0.0))
        self.stick_x_history.append((now, prim.stick_x if prim.connected else 0))
        self.stick_y_history.append((now, prim.stick_y if prim.connected else 0))
        self.right_stick_x_history.append((now, prim.right_stick_x if prim.connected else 0))
        self.right_stick_y_history.append((now, prim.right_stick_y if prim.connected else 0))
        self.throttle_history.append((now, prim.throttle if prim.connected else 0))
        self.brake_history.append((now, prim.brake if prim.connected else 0))
        self.rate_history.append((now, self.effective_hz if prim.connected else 0.0))

    def get_snapshot(self) -> Dict[str, Any]:
        """Provides an atomic, non-blocking state snapshot with live sampled tick for all 4 players."""
        self.sample_tick()
        return {
            "server_online": self.server_online,
            "server_url": self.server_url,
            "primary_ip": self.primary_ip,
            "port": self.port,
            "ssl_enabled": self.ssl_enabled,
            "driver_status": self.driver_status,
            "uptime_sec": int(time.time() - self.start_time),
            "total_packets": self.total_gateway_packets,
            "effective_hz": self.effective_hz,
            "avg_rtt_ms": self.avg_rtt_ms,
            "min_rtt_ms": self.min_rtt_ms,
            "max_rtt_ms": self.max_rtt_ms,
            "slots": [
                {
                    "slot_index": s.slot_index,
                    "connected": s.connected,
                    "client_id": s.client_id,
                    "client_ip": s.client_ip,
                    "player_color": s.player_color,
                    "rtt_ms": s.rtt_ms,
                    "hz": s.packet_rate_hz,
                    "packets": s.total_packets,
                    "stick_x": s.stick_x,
                    "stick_y": s.stick_y,
                    "right_stick_x": s.right_stick_x,
                    "right_stick_y": s.right_stick_y,
                    "throttle": s.throttle,
                    "brake": s.brake,
                    "buttons": dict(s.buttons),
                    "latency_wave": list(s.latency_history),
                    "stick_x_wave": list(s.stick_x_history),
                    "stick_y_wave": list(s.stick_y_history),
                    "right_stick_x_wave": list(s.right_stick_x_history),
                    "right_stick_y_wave": list(s.right_stick_y_history),
                    "throttle_wave": list(s.throttle_history),
                    "brake_wave": list(s.brake_history)
                }
                for s in self.slots
            ],
            "latency_wave": list(self.latency_history),
            "stick_x_wave": list(self.stick_x_history),
            "stick_y_wave": list(self.stick_y_history),
            "right_stick_x_wave": list(self.right_stick_x_history),
            "right_stick_y_wave": list(self.right_stick_y_history),
            "throttle_wave": list(self.throttle_history),
            "brake_wave": list(self.brake_history),
            "rate_wave": list(self.rate_history)
        }
