"""
Project Controller - AsyncIO Gateway Server & WebSocket Protocol Router
High-Performance Cyber-Physical Teleoperation Framework
"""

import asyncio
import json
import logging
import mimetypes
import os
import socket
import secrets
import ssl
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Set, Optional, Any, Tuple, List

import struct
import websockets
from websockets.server import WebSocketServerProtocol

# ---------------------------------------------------------------------------
# Zero-Copy 24-Byte Binary Micro-Packet Wire Protocol (v2) - Pillar 4
# ---------------------------------------------------------------------------
from gateway.kernel_transport import (
    BINARY_PACKET_MAGIC,
    BINARY_PACKET_VERSION,
    BINARY_PACKET_SIZE,
    BINARY_STRUCT,
    KernelTransportTuner,
    FastBinaryDecoder
)


def decode_binary_packet(packet_bytes: bytes) -> Optional[Dict[str, Any]]:
    """
    Decodes a 24-byte packed binary micro-packet into normalized controller state.
    Achieves sub-microsecond zero-heap deserialization via FastBinaryDecoder.
    """
    return FastBinaryDecoder.decode(packet_bytes)

from config import settings
from gateway.filters import SensorFusionPipeline
from gateway.security import ChallengeResponseAuthenticator, AnomalyFirewall
from gateway.input_manager import InputManager
from gateway.telemetry_receiver import UDPTelemetryReceiver
from gateway.telemetry_simulator import TelemetrySimulatorRunner
from gateway.qos_recorder import QoSRecorder

logger = logging.getLogger("Controller.Gateway")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)


def get_local_ip_addresses() -> list[str]:
    """Retrieves all active non-loopback IPv4 addresses of the host machine."""
    ips = []
    try:
        # Standard socket connect method to determine default route
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.2)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        ips.append(ip)
        s.close()
    except Exception:
        pass

    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            addr = info[4][0]
            if addr not in ips and not addr.startswith("127."):
                ips.append(addr)
    except Exception:
        pass

    if not ips:
        ips.append("127.0.0.1")
    return ips


def generate_self_signed_cert(cert_path: Path, key_path: Path, host_ips: list[str]) -> None:
    """Generates an X.509 self-signed certificate with IP Subject Alternative Names (SAN)."""
    import ipaddress
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization

    if cert_path.exists() and key_path.exists():
        return

    logger.info("Generating self-signed SSL/TLS certificate for zero-config mobile HTTPS...")
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "IN"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Project Controller"),
        x509.NameAttribute(NameOID.COMMON_NAME, "controller.local"),
    ])

    san_list = [x509.DNSName("localhost"), x509.DNSName("controller.local")]
    for ip_str in host_ips:
        try:
            san_list.append(x509.IPAddress(ipaddress.ip_address(ip_str)))
        except ValueError:
            pass
    try:
        san_list.append(x509.IPAddress(ipaddress.ip_address("127.0.0.1")))
    except ValueError:
        pass

    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=365))
        .add_extension(x509.SubjectAlternativeName(san_list), critical=False)
        .sign(key, hashes.SHA256())
    )

    cert_path.parent.mkdir(parents=True, exist_ok=True)
    with open(key_path, "wb") as f:
        f.write(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption()
        ))

    with open(cert_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))
    
    logger.info(f"Generated TLS certificate at {cert_path}")


class ControllerGatewayServer:
    """
    Central Asynchronous Teleoperation Gateway.
    Integrates WebSockets, HTTP File Server, Cryptographic Handshake,
    Sensor Fusion Filters, ViGEm Virtual Gamepad OS Emulation, and Game Telemetry.
    """
    def __init__(
        self,
        use_ssl: bool = True,
        port: Optional[int] = None,
        enable_simulator: bool = False,
        force_mock_input: bool = False,
        bridge: Optional[Any] = None
    ):
        self.use_ssl = use_ssl
        self.port = port or (settings.network.HTTPS_PORT if use_ssl else settings.network.HTTP_PORT)
        self.enable_simulator = enable_simulator
        self.bridge = bridge
        
        # Subsystems
        self.authenticator = ChallengeResponseAuthenticator(
            shared_secret=settings.security.HMAC_SHARED_SECRET,
            timeout_sec=settings.security.HANDSHAKE_TIMEOUT_SEC
        )
        self.firewall = AnomalyFirewall(
            max_rate_hz=settings.security.MAX_PACKET_RATE_HZ,
            min_inter_arrival_sec=settings.security.MIN_INTER_ARRIVAL_SEC
        )
        self.input_manager = InputManager(force_mock=force_mock_input)
        self.qos_recorder = QoSRecorder(capacity=settings.qos.RING_BUFFER_SIZE)

        # Per-client sensor fusion pipelines {client_id: SensorFusionPipeline}
        self.pipelines: Dict[str, SensorFusionPipeline] = {}
        # Connected authenticated websockets {websocket: client_id}
        self.active_clients: Dict[WebSocketServerProtocol, str] = {}
        # Active client sockets mapped by client_id {client_id: websocket}
        self.client_sockets: Dict[str, WebSocketServerProtocol] = {}
        # Active motor rumble state per slot {slot_idx: (large, small)}
        self._active_rumble: Dict[int, Tuple[int, int]] = {}
        self._rumble_sync_counter: int = 0

        # Set up bi-directional rumble callback from OS virtual gamepads
        self.input_manager.set_rumble_callback(self._on_rumble_event)
        if self.bridge is not None:
            self.bridge.swap_slots_callback = self.swap_player_slots
            self.bridge.trigger_test_rumble_callback = self.trigger_test_rumble
            self.bridge.pulse_test_callback = self.pulse_test_slot

        # Telemetry State
        self.latest_telemetry: Dict[str, Any] = {
            "speed_kmh": 0.0,
            "rpm": 0.0,
            "max_rpm": 8500.0,
            "gear": 0,
            "slip_ratio": 0.0,
            "g_lat": 0.0,
            "g_long": 0.0,
            "impact_g": 0.0,
            "abs_active": False,
            "tcs_active": False,
            "timestamp": time.time()
        }

        # Telemetry Ingestion Receiver & Simulator
        self.telemetry_receiver = UDPTelemetryReceiver(
            port=settings.network.TELEMETRY_UDP_PORT,
            on_telemetry=self._on_game_telemetry
        )
        self.telemetry_simulator = TelemetrySimulatorRunner(
            callback=self._on_game_telemetry,
            rate_hz=settings.network.TELEMETRY_BROADCAST_RATE_HZ
        ) if self.enable_simulator else None

        self._running = False
        self._server = None
        self._downlink_task: Optional[asyncio.Task] = None
        self._last_telemetry_rx_time: float = 0.0

    def _on_game_telemetry(self, telemetry_frame: Dict[str, Any]) -> None:
        """Callback triggered when new UDP or simulated telemetry is received."""
        self.latest_telemetry = telemetry_frame
        self._last_telemetry_rx_time = time.perf_counter()

    async def _handle_http_request(self, connection, request) -> Optional[Any]:
        """Serves client static files over HTTP. Returns None to permit WebSocket upgrades."""
        headers_dict = {k.lower(): v for k, v in request.headers.items()}
        if headers_dict.get("upgrade", "").lower() == "websocket":
            return None

        from websockets.datastructures import Headers
        from websockets.http11 import Response
        path = request.path
        clean_path = path.split("?")[0].lstrip("/")

        client_dir = getattr(settings, "BUNDLE_DIR", settings.BASE_DIR) / "client"
        if not client_dir.exists():
            client_dir = settings.BASE_DIR / "client"
        if not client_dir.exists():
            client_dir = Path.cwd() / "client"
        if not clean_path or clean_path == "":
            file_path = client_dir / "index.html"
        else:
            file_path = client_dir / clean_path

        # Security check against directory traversal
        try:
            resolved = file_path.resolve()
            if not str(resolved).startswith(str(client_dir.resolve())):
                return Response(403, "Forbidden", Headers([("Content-Type", "text/plain")]), b"Forbidden")
        except Exception:
            return Response(400, "Bad Request", Headers([("Content-Type", "text/plain")]), b"Bad Request")

        if resolved.is_file():
            content_type, _ = mimetypes.guess_type(str(resolved))
            content_type = content_type or "application/octet-stream"
            with open(resolved, "rb") as f:
                body = f.read()
            return Response(
                200,
                "OK",
                Headers([
                    ("Content-Type", content_type),
                    ("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0"),
                    ("Pragma", "no-cache"),
                    ("Expires", "0"),
                    ("Access-Control-Allow-Origin", "*")
                ]),
                body
            )

        return Response(404, "Not Found", Headers([("Content-Type", "text/plain")]), b"Not Found")

    async def _handle_websocket(self, websocket, *args, **kwargs) -> None:
        """Handles full lifecycle for a connected mobile edge node."""
        client_ip = websocket.remote_address[0] if websocket.remote_address else "unknown"
        logger.info(f"Incoming connection from {client_ip}")

        # Pillar 4: Ultra-Low-Latency Kernel Socket Tuning (TCP_NODELAY + Anti-Bufferbloat)
        KernelTransportTuner.tune_websocket(websocket)

        # Phase 1: Authentication Handshake
        challenge = self.authenticator.generate_challenge(client_hint=client_ip)
        await websocket.send(json.dumps(challenge))

        client_id: Optional[str] = None
        player_slot: Optional[int] = None

        try:
            # Wait for AUTH_RESPONSE (skipping any stray binary packets or non-auth frames)
            msg = None
            start_wait = time.time()
            while time.time() - start_wait < settings.security.HANDSHAKE_TIMEOUT_SEC:
                response_raw = await asyncio.wait_for(
                    websocket.recv(),
                    timeout=max(0.1, settings.security.HANDSHAKE_TIMEOUT_SEC - (time.time() - start_wait))
                )
                if isinstance(response_raw, bytes):
                    # Client sent a binary frame before handshake completed; skip it
                    continue
                try:
                    parsed = json.loads(response_raw)
                    if isinstance(parsed, dict) and parsed.get("type") == "AUTH_RESPONSE":
                        msg = parsed
                        break
                except Exception:
                    continue

            if not msg or msg.get("type") != "AUTH_RESPONSE":
                await websocket.send(json.dumps({"type": "AUTH_ERROR", "reason": "PROTOCOL_VIOLATION"}))
                await websocket.close(1008, "Expected AUTH_RESPONSE")
                return

            nonce = msg.get("nonce", "")
            timestamp = float(msg.get("timestamp", 0.0))
            signature = msg.get("signature", "")
            client_id = msg.get("client_id", f"node_{secrets.token_hex(4)}")

            is_valid, reason = self.authenticator.verify_response(nonce, timestamp, signature)
            if not is_valid:
                logger.warning(f"Auth handshake rejected for {client_ip}: {reason}")
                await websocket.send(json.dumps({"type": "AUTH_ERROR", "reason": reason}))
                await websocket.close(1008, reason)
                return

            pref = msg.get("preferred_slot")
            preferred_idx = (int(pref) - 1) if pref is not None and str(pref).isdigit() else None

            # Phase 2: Slot Allocation (with persistent leasing and player preference)
            player_slot = self.input_manager.allocate_slot(client_id, preferred_slot=preferred_idx)
            if player_slot is None:
                await websocket.send(json.dumps({"type": "AUTH_ERROR", "reason": "SERVER_FULL"}))
                await websocket.close(1013, "Maximum players reached")
                return

            # Initialize per-client DSP filter pipeline
            self.pipelines[client_id] = SensorFusionPipeline(
                ema_alpha=settings.filters.EMA_ALPHA,
                deadband_deg=settings.filters.STEERING_DEADBAND_DEG,
                max_angle_deg=settings.filters.STEERING_MAX_ANGLE_DEG,
                curve_gamma=settings.filters.STEERING_CURVE_GAMMA,
                jerk_threshold=settings.filters.JERK_HANDBRAKE_THRESHOLD
            )
            self.firewall.reset_client(client_id)

            # Send Auth Success BEFORE adding to active_clients so downlink broadcasts never race with AUTH_SUCCESS
            player_color = settings.clients.PLAYER_COLORS[player_slot % len(settings.clients.PLAYER_COLORS)]
            await websocket.send(json.dumps({
                "type": "AUTH_SUCCESS",
                "player_slot": player_slot + 1,  # 1-indexed for display (Player 1..4)
                "player_color": player_color,
                "client_id": client_id,
                "config": {
                    "max_angle": settings.filters.STEERING_MAX_ANGLE_DEG,
                    "deadband": settings.filters.STEERING_DEADBAND_DEG
                }
            }))
            self.active_clients[websocket] = client_id
            self.client_sockets[client_id] = websocket

            logger.info(f"Client [{client_id[:8]}] authenticated successfully -> Player {player_slot + 1}")
            if self.bridge is not None:
                self.bridge.register_client(player_slot, client_id, client_ip)

            # Wake up browser gamepad testers (e.g. gamepad-tester.com) and OS XInput stack
            self.pulse_test_slot(player_slot)

            # Phase 3: Telemetry Uplink Processing Loop
            last_qos_t = 0.0
            qos_count = 0
            sync_burst_count = 0
            ws_msgs = getattr(websocket, "messages", None)
            async for message in websocket:
                sync_burst_count += 1
                if (sync_burst_count & 7) == 0:
                    await asyncio.sleep(0)
                if isinstance(message, bytes):
                    if (
                        ws_msgs
                        and len(message) == 24
                        and isinstance(ws_msgs[0], bytes)
                        and len(ws_msgs[0]) == 24
                        and ws_msgs[0][18:20] == message[18:20]
                    ):
                        continue
                    data = decode_binary_packet(message)
                    if data is None:
                        continue
                else:
                    try:
                        data = json.loads(message)
                    except Exception:
                        continue

                msg_type = data.get("type", "INPUT")
                proto_name = data.get("protocol", "JSON")

                if msg_type == "INPUT":
                    seq = int(data.get("seq", 0))
                    client_ts = float(data.get("ts", time.time()))

                    buttons = data.get("buttons", {})
                    raw_stick_x = int(data.get("stick_x", 0))
                    raw_stick_y = int(data.get("stick_y", 0))
                    raw_right_x = int(data.get("right_stick_x", 0))
                    raw_right_y = int(data.get("right_stick_y", 0))
                    raw_th = float(data.get("throttle", 0.0))
                    raw_br = float(data.get("brake", 0.0))

                    # Safety check: neutral and zero-reset transitions bypass rate-limit drops
                    is_neutral = (
                        (raw_stick_x == 0 and raw_stick_y == 0)
                        or (raw_th <= 0.001 and raw_br <= 0.001)
                        or (raw_right_x == 0 and raw_right_y == 0)
                        or not any(buttons.values())
                    )

                    # Pass through Network Anomaly Firewall
                    accepted, drop_reason = self.firewall.inspect_packet(client_id, seq, client_ts, is_neutral=is_neutral)
                    if not accepted:
                        logger.debug(f"Packet from [{client_id[:8]}] dropped by firewall: {drop_reason}")
                        continue

                    pipeline = self.pipelines[client_id]

                    # Process Steering & Thumbstick (Manual thumbstick always takes priority over gyro)
                    manual_sx = raw_stick_x
                    manual_sy = raw_stick_y
                    if data.get("gyro_enabled", False) and "angle" in data and abs(manual_sx) <= 500 and abs(manual_sy) <= 500:
                        raw_angle = float(data.get("angle", 0.0))
                        stick_x, filtered_angle, _ = pipeline.process_steering(raw_angle)
                    else:
                        raw_angle = 0.0
                        filtered_angle = 0.0
                        stick_x = manual_sx

                    stick_y = manual_sy
                    right_stick_x = raw_right_x
                    right_stick_y = raw_right_y

                    # Process Triggers (Gas & Brake)
                    th_byte, br_byte = pipeline.process_triggers(raw_th, raw_br)

                    # Dispatch to OS Virtual Gamepad
                    control_state = {
                        "stick_x": stick_x,
                        "stick_y": stick_y,
                        "right_stick_x": right_stick_x,
                        "right_stick_y": right_stick_y,
                        "throttle": th_byte,
                        "brake": br_byte,
                        "buttons": buttons
                    }
                    # Safety check: if slot was somehow lost during a reconnect race, re-acquire it
                    curr_slot = self.input_manager.get_slot(client_id)
                    if curr_slot is None:
                        curr_slot = self.input_manager.allocate_slot(client_id, preferred_slot=player_slot)

                    # Arrival timestamp using high-resolution monotonic clock (matching Virtual MCU)
                    arrival_ts = time.perf_counter()
                    client_rtt = float(data.get("rtt", 5.0))
                    self.input_manager.dispatch(client_id, control_state, timestamp=arrival_ts, rtt_ms=client_rtt)

                    # Record to QoS Flight Data Buffer (throttled after initial warmup burst to prevent CPU/GC spikes)
                    qos_count += 1
                    dt_ms = 16.6
                    if qos_count <= 250 or (arrival_ts - last_qos_t) >= 0.008:
                        last_qos_t = arrival_ts
                        qos_rec = self.qos_recorder.record_uplink(
                            client_id=client_id,
                            seq=seq,
                            client_timestamp=client_ts,
                            raw_steering=raw_angle,
                            filtered_steering=filtered_angle,
                            throttle=th_byte,
                            brake=br_byte,
                            handbrake=buttons.get("HANDBRAKE", False),
                            reception_timestamp=arrival_ts
                        )
                        dt_ms = qos_rec.get("inter_arrival_ms", 16.6)

                    if self.bridge is not None and curr_slot is not None:
                        self.bridge.record_input(
                            slot_index=curr_slot,
                            client_id=client_id,
                            control_state=control_state,
                            client_rtt=client_rtt,
                            inter_arrival_ms=dt_ms,
                            protocol=proto_name,
                            raw_angle=raw_angle,
                            filtered_angle=filtered_angle,
                            filter_mode=pipeline.filter_mode.upper()
                        )

                elif msg_type == "SWITCH_SLOT":
                    try:
                        req_slot = max(0, min(self.input_manager.max_players - 1, int(data.get("slot", 1)) - 1))
                    except Exception:
                        req_slot = 0
                    curr_slot = self.input_manager.get_slot(client_id)
                    if curr_slot is not None and curr_slot != req_slot:
                        self.swap_player_slots(curr_slot, req_slot, _from_bridge=False)
                        player_slot = req_slot
                    else:
                        actual_slot = curr_slot if curr_slot is not None else req_slot
                        color = settings.clients.PLAYER_COLORS[actual_slot % len(settings.clients.PLAYER_COLORS)]
                        await self._send_safe(websocket, json.dumps({
                            "type": "SLOT_REASSIGNED",
                            "player_slot": actual_slot + 1,
                            "player_color": color
                        }))

                elif msg_type == "CALIBRATE":
                    angle = float(data.get("angle", 0.0))
                    if client_id in self.pipelines:
                        self.pipelines[client_id].calibrate_zero(angle)
                        curr_slot = self.input_manager.get_slot(client_id)
                        slot_str = str(curr_slot + 1) if curr_slot is not None else "?"
                        logger.info(f"Calibrated zero steering offset for Player {slot_str} at {angle:.2f}°")

                elif msg_type == "PING":
                    await self._send_safe(websocket, json.dumps({"type": "PONG", "ts": data.get("ts", time.time())}))

        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception as e:
            logger.error(f"Error handling client {client_ip}: {e}")
        finally:
            if websocket in self.active_clients:
                del self.active_clients[websocket]
            if client_id:
                if self.client_sockets.get(client_id) == websocket:
                    self.client_sockets.pop(client_id, None)
                    slot = self.input_manager.release_slot(client_id)
                    if self.bridge is not None and slot is not None:
                        self.bridge.unregister_client(slot, client_id)
                    self.pipelines.pop(client_id, None)
                    self.firewall.reset_client(client_id)
                    logger.info(f"Cleaned up session for client [{client_id[:8]}]")
                else:
                    logger.info(f"Stale connection closed for client [{client_id[:8]}]; active connection preserved")

    async def _send_safe(self, ws, msg: str) -> None:
        """Helper to send a message over a websocket ignoring closed socket errors."""
        try:
            if ws is not None:
                await ws.send(msg)
        except Exception:
            pass

    def _resolve_target_ws_for_slot(self, slot_idx: int) -> Optional[Any]:
        """Resolves target WebSocket for a slot with robust fallback routing."""
        # 1. Direct slot targeting
        if 0 <= slot_idx < len(self.input_manager.slots):
            cid = self.input_manager.slots[slot_idx]
            if cid and cid in self.client_sockets and self.client_sockets[cid]:
                return self.client_sockets[cid]

        # 2. Fallback to Player 1 (Slot 0)
        if len(self.input_manager.slots) > 0:
            p1_cid = self.input_manager.slots[0]
            if p1_cid and p1_cid in self.client_sockets and self.client_sockets[p1_cid]:
                return self.client_sockets[p1_cid]

        # 3. Fallback to any active authenticated client
        for cid in self.input_manager.slots:
            if cid and cid in self.client_sockets and self.client_sockets[cid]:
                return self.client_sockets[cid]

        # 4. Fallback to any connected client socket
        for ws in self.client_sockets.values():
            if ws:
                return ws

        return None

    def _on_rumble_event(self, slot_idx: int, large_motor: int, small_motor: int) -> None:
        """Invoked by OS virtual gamepad when game engine sends XInput force-feedback."""
        # Standardize motor speed to standard 0..255 byte range
        lm = max(0, min(255, int(large_motor) if large_motor <= 255 else int(large_motor // 256)))
        sm = max(0, min(255, int(small_motor) if small_motor <= 255 else int(small_motor // 256)))

        self._active_rumble[slot_idx] = (lm, sm)

        if self.bridge is not None:
            try:
                self.bridge.record_rumble(slot_idx, lm, sm)
            except Exception as e:
                logger.debug(f"Bridge record_rumble error: {e}")

        if not self._running or getattr(self, "loop", None) is None:
            return

        msg = json.dumps({
            "type": "RUMBLE",
            "large": lm,
            "small": sm
        })

        # Collect all active target websockets for this specific player slot
        targets = set()
        if 0 <= slot_idx < len(self.input_manager.slots):
            cid = self.input_manager.slots[slot_idx]
            if cid and cid in self.client_sockets and self.client_sockets[cid]:
                targets.add(self.client_sockets[cid])

        # Only fall back to all connected clients if this slot has no direct owner AND only 1 client is connected
        if not targets and len(self.client_sockets) <= 1:
            for ws in self.client_sockets.values():
                if ws:
                    targets.add(ws)
            for ws in self.active_clients.keys():
                if ws:
                    targets.add(ws)

        if not targets:
            return

        logger.debug(f"[HAPTICS] Dispatching RUMBLE (large={lm}, small={sm}) to {len(targets)} sockets")
        for ws in targets:
            try:
                asyncio.run_coroutine_threadsafe(self._send_safe(ws, msg), self.loop)
            except Exception as e:
                logger.debug(f"Rumble websocket dispatch error: {e}")

        # Triple-redundant stop transmission: when motors stop (0, 0), re-verify delivery at +15ms and +40ms
        if lm == 0 and sm == 0:
            import threading
            def _backup_stop():
                for ws in targets:
                    try:
                        asyncio.run_coroutine_threadsafe(self._send_safe(ws, msg), self.loop)
                    except Exception:
                        pass
            threading.Timer(0.015, _backup_stop).start()
            threading.Timer(0.040, _backup_stop).start()

    def pulse_test_slot(self, slot_idx: int) -> None:
        """Pulses button A momentarily on the virtual controller to wake up browser gamepad testers."""
        import threading
        def _pulse():
            try:
                if 0 <= slot_idx < len(self.input_manager.controllers):
                    ctrl = self.input_manager.controllers[slot_idx]
                    ctrl.set_button("A", True)
                    ctrl.update()
                    time.sleep(0.12)
                    ctrl.set_button("A", False)
                    ctrl.update()
            except Exception as e:
                logger.debug(f"Pulse test slot error: {e}")
        threading.Thread(target=_pulse, daemon=True, name=f"PulseTest-Slot{slot_idx+1}").start()

    def trigger_test_rumble(self, slot_idx: int = 0, large: int = 255, small: int = 255, duration_sec: float = 1.5) -> None:
        """Sends a high-intensity force-feedback rumble pulse to the specified slot for hardware verification."""
        import threading
        def _test_pulse():
            self._on_rumble_event(slot_idx, large, small)
            if duration_sec > 0:
                time.sleep(duration_sec)
                self._on_rumble_event(slot_idx, 0, 0)
        threading.Thread(target=_test_pulse, daemon=True, name=f"TestRumble-P{slot_idx+1}").start()

    def swap_player_slots(self, slot_a: int, slot_b: int, _from_bridge: bool = False) -> bool:
        """Swaps controller assignments between slot_a and slot_b and notifies clients."""
        if not (0 <= slot_a < self.input_manager.max_players and 0 <= slot_b < self.input_manager.max_players):
            return False
        if slot_a == slot_b:
            return True

        client_a, client_b = self.input_manager.swap_slots(slot_a, slot_b)

        if self.bridge is not None and not _from_bridge:
            if hasattr(self.bridge, "_swap_slot_states_only"):
                self.bridge._swap_slot_states_only(slot_a, slot_b)

        if getattr(self, "loop", None) is not None:
            if client_a and client_a in self.client_sockets:
                ws = self.client_sockets[client_a]
                color_b = settings.clients.PLAYER_COLORS[slot_b % len(settings.clients.PLAYER_COLORS)]
                asyncio.run_coroutine_threadsafe(
                    self._send_safe(ws, json.dumps({
                        "type": "SLOT_REASSIGNED",
                        "player_slot": slot_b + 1,
                        "player_color": color_b
                    })),
                    self.loop
                )
                self.pulse_test_slot(slot_b)
            if client_b and client_b in self.client_sockets:
                ws = self.client_sockets[client_b]
                color_a = settings.clients.PLAYER_COLORS[slot_a % len(settings.clients.PLAYER_COLORS)]
                asyncio.run_coroutine_threadsafe(
                    self._send_safe(ws, json.dumps({
                        "type": "SLOT_REASSIGNED",
                        "player_slot": slot_a + 1,
                        "player_color": color_a
                    })),
                    self.loop
                )
                self.pulse_test_slot(slot_a)
        return True

    async def _downlink_telemetry_loop(self) -> None:
        """Monitors deadman's switch watchdog and broadcasts live game telemetry when active."""
        interval = 1.0 / settings.network.TELEMETRY_BROADCAST_RATE_HZ
        while self._running:
            start_t = time.perf_counter()
            # Tick deadman's switch watchdog (600ms tolerance prevents Wi-Fi micro-jitter dropouts)
            self.input_manager.tick_watchdog(0.600)

            telemetry_active = self.enable_simulator or ((start_t - self._last_telemetry_rx_time) < 1.0)
            if self.active_clients and telemetry_active:
                telem = self.latest_telemetry
                rpm = telem.get("rpm", 0.0)
                max_rpm = telem.get("max_rpm", 8500.0)
                slip = telem.get("slip_ratio", 0.0)
                impact_g = telem.get("impact_g", 0.0)

                # Closed-Loop Haptic Actuation Logic
                slip_rumble = slip > 0.30
                impact_spike = impact_g > 2.5
                redline_alert = (rpm / max_rpm) > 0.95 if max_rpm > 0 else False

                payload = json.dumps({
                    "type": "TELEMETRY",
                    "data": telem,
                    "haptics": {
                        "slip_rumble": slip_rumble,
                        "impact_spike": impact_spike,
                        "redline_alert": redline_alert
                    }
                })

                # Broadcast to all authenticated phones
                websockets_to_remove = []
                for ws in list(self.active_clients.keys()):
                    try:
                        await ws.send(payload)
                    except Exception:
                        websockets_to_remove.append(ws)

                for ws in websockets_to_remove:
                    self.active_clients.pop(ws, None)

                elapsed = time.perf_counter() - start_t
                await asyncio.sleep(max(0.001, interval - elapsed))
            else:
                await asyncio.sleep(0.050)

    def _render_ascii_banner(self, host_ips: list[str]) -> None:
        """Prints a clean, industrial terminal banner and QR code for rapid smartphone pairing."""
        proto = "https" if self.use_ssl else "http"
        primary_ip = host_ips[0]
        url = f"{proto}://{primary_ip}:{self.port}"

        print("\n" + "=" * 78)
        print("  PROJECT CONTROLLER - HIGH-PERFORMANCE CYBER-PHYSICAL TELEOPERATION HMI")
        print("  Bi-Directional Haptic Telemetry & 6-DoF Multi-Sensor Fusion Gateway")
        print("=" * 78)
        print(f"  Status        : ONLINE (Protocol: {proto.upper()})")
        print(f"  XInput Driver : {'ViGEmBus Native Virtual Xbox' if self.input_manager.controllers and hasattr(self.input_manager.controllers[0], 'gamepad') else 'SendInput Keyboard Fallback'}")
        print(f"  Telemetry     : UDP Port {settings.network.TELEMETRY_UDP_PORT} {'+ Synthetic Simulator ACTIVE' if self.enable_simulator else ''}")
        print(f"  Active Host IP: {primary_ip}")
        print(f"\n  >> CONNECT SMARTPHONE AT: {url}")
        print(f"  >> VIBRATION TEST LAB   : {url}/vibration_test.html")
        print("-" * 78)

        # Print ASCII QR Code for instant phone camera scanning
        try:
            import qrcode
            qr = qrcode.QRCode(border=1)
            qr.add_data(url)
            qr.make(fit=True)
            print("  Scan with Smartphone Camera to open cockpit instantly:\n")
            qr.print_ascii(invert=True)
        except Exception:
            pass
        print("=" * 78 + "\n")

    async def start(self) -> None:
        """Starts HTTP/WebSocket server and telemetry services."""
        self._running = True
        self.loop = asyncio.get_running_loop()
        host_ips = get_local_ip_addresses()

        # SSL Configuration
        ssl_context = None
        if self.use_ssl:
            generate_self_signed_cert(
                cert_path=settings.network.CERT_FILE,
                key_path=settings.network.KEY_FILE,
                host_ips=host_ips
            )
            ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ssl_context.load_cert_chain(
                certfile=str(settings.network.CERT_FILE),
                keyfile=str(settings.network.KEY_FILE)
            )

        # Start Telemetry Ingestion
        await self.telemetry_receiver.start()
        if self.telemetry_simulator:
            self.telemetry_simulator.start()

        # Start Downlink Broadcast Task
        self._downlink_task = asyncio.create_task(self._downlink_telemetry_loop())

        # Start Combined HTTP / WebSocket Server (max_queue=512 eliminates TCP pause_reading backpressure spikes)
        self._server = await websockets.serve(
            self._handle_websocket,
            host=settings.network.HOST,
            port=self.port,
            ssl=ssl_context,
            process_request=self._handle_http_request,
            compression=None,
            ping_interval=20,
            ping_timeout=20,
            max_size=2**20,
            max_queue=512
        )

        self._render_ascii_banner(host_ips)

        if self.bridge is not None:
            proto = "https" if self.use_ssl else "http"
            primary_ip = host_ips[0]
            url = f"{proto}://{primary_ip}:{self.port}"
            self.bridge.server_online = True
            self.bridge.server_url = url
            self.bridge.primary_ip = primary_ip
            self.bridge.port = self.port
            self.bridge.ssl_enabled = self.use_ssl
            driver_desc = "ViGEm Native X360" if (
                self.input_manager.controllers and
                hasattr(self.input_manager.controllers[0], "gamepad")
            ) else "Keyboard Fallback"
            self.bridge.driver_status = driver_desc
            self.bridge.pulse_test_callback = self.input_manager.pulse_test_button
            self.bridge.reinit_driver_callback = self.input_manager.reinit_controllers
            self.bridge.trigger_test_rumble_callback = self.trigger_test_rumble

    async def stop(self) -> None:
        """Gracefully shuts down all subsystems and hardware emulations."""
        self._running = False
        if self.bridge is not None:
            self.bridge.server_online = False
        if self._downlink_task:
            self._downlink_task.cancel()
        if self.telemetry_simulator:
            self.telemetry_simulator.stop()
        self.telemetry_receiver.stop()
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        self.input_manager.shutdown()
        logger.info("Project Controller Gateway successfully stopped.")
