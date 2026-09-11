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

import websockets
from websockets.server import WebSocketServerProtocol

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
        force_mock_input: bool = False
    ):
        self.use_ssl = use_ssl
        self.port = port or (settings.network.HTTPS_PORT if use_ssl else settings.network.HTTP_PORT)
        self.enable_simulator = enable_simulator
        
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

    def _on_game_telemetry(self, telemetry_frame: Dict[str, Any]) -> None:
        """Callback triggered when new UDP or simulated telemetry is received."""
        self.latest_telemetry = telemetry_frame

    async def _handle_http_request(self, connection, request) -> Optional[Any]:
        """Serves client static files over HTTP. Returns None to permit WebSocket upgrades."""
        headers_dict = {k.lower(): v for k, v in request.headers.items()}
        if headers_dict.get("upgrade", "").lower() == "websocket":
            return None

        from websockets.datastructures import Headers
        from websockets.http11 import Response

        path = request.path
        client_dir = settings.BASE_DIR / "client"
        clean_path = path.split("?")[0].lstrip("/")
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
                    ("Cache-Control", "no-cache"),
                    ("Access-Control-Allow-Origin", "*")
                ]),
                body
            )

        return Response(404, "Not Found", Headers([("Content-Type", "text/plain")]), b"Not Found")

    async def _handle_websocket(self, websocket, *args, **kwargs) -> None:
        """Handles full lifecycle for a connected mobile edge node."""
        client_ip = websocket.remote_address[0] if websocket.remote_address else "unknown"
        logger.info(f"Incoming connection from {client_ip}")

        # Phase 1: Authentication Handshake
        challenge = self.authenticator.generate_challenge(client_hint=client_ip)
        await websocket.send(json.dumps(challenge))

        client_id: Optional[str] = None
        player_slot: Optional[int] = None

        try:
            # Wait for AUTH_RESPONSE
            response_raw = await asyncio.wait_for(websocket.recv(), timeout=settings.security.HANDSHAKE_TIMEOUT_SEC)
            msg = json.loads(response_raw)
            
            if msg.get("type") != "AUTH_RESPONSE":
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

            # Phase 2: Slot Allocation
            player_slot = self.input_manager.allocate_slot(client_id)
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
            self.active_clients[websocket] = client_id

            # Send Auth Success with Player Slot & Theme Color
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
            logger.info(f"Client [{client_id[:8]}] authenticated successfully -> Player {player_slot + 1}")

            # Phase 3: Telemetry Uplink Processing Loop
            async for message in websocket:
                data = json.loads(message)
                msg_type = data.get("type", "INPUT")

                if msg_type == "INPUT":
                    seq = int(data.get("seq", 0))
                    client_ts = float(data.get("ts", time.time()))

                    # Pass through Network Anomaly Firewall
                    accepted, drop_reason = self.firewall.inspect_packet(client_id, seq, client_ts)
                    if not accepted:
                        logger.debug(f"Packet from [{client_id[:8]}] dropped by firewall: {drop_reason}")
                        continue

                    pipeline = self.pipelines[client_id]

                    # Process Steering & Thumbstick
                    if data.get("gyro_enabled", True) and "angle" in data:
                        raw_angle = float(data.get("angle", 0.0))
                        stick_x, filtered_angle, _ = pipeline.process_steering(raw_angle)
                    else:
                        raw_angle = 0.0
                        filtered_angle = 0.0
                        stick_x = int(data.get("stick_x", 0))

                    stick_y = int(data.get("stick_y", 0))

                    # Process Triggers (Gas & Brake)
                    raw_th = float(data.get("throttle", 0.0))
                    raw_br = float(data.get("brake", 0.0))
                    th_byte, br_byte = pipeline.process_triggers(raw_th, raw_br)

                    # Digital Buttons strictly from client input (no ghost triggers)
                    buttons = data.get("buttons", {})

                    # Dispatch to OS Virtual Gamepad
                    control_state = {
                        "stick_x": stick_x,
                        "stick_y": stick_y,
                        "throttle": th_byte,
                        "brake": br_byte,
                        "buttons": buttons
                    }
                    self.input_manager.dispatch(client_id, control_state)

                    # Record to QoS Flight Data Buffer
                    self.qos_recorder.record_uplink(
                        client_id=client_id,
                        seq=seq,
                        client_timestamp=client_ts,
                        raw_steering=raw_angle,
                        filtered_steering=filtered_angle,
                        throttle=th_byte,
                        brake=br_byte,
                        handbrake=buttons.get("HANDBRAKE", False)
                    )

                elif msg_type == "CALIBRATE":
                    angle = float(data.get("angle", 0.0))
                    if client_id in self.pipelines:
                        self.pipelines[client_id].calibrate_zero(angle)
                        logger.info(f"Calibrated zero steering offset for Player {player_slot + 1} at {angle:.2f}°")

                elif msg_type == "PING":
                    await websocket.send(json.dumps({"type": "PONG", "ts": data.get("ts", time.time())}))

        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception as e:
            logger.error(f"Error handling client {client_ip}: {e}")
        finally:
            if websocket in self.active_clients:
                del self.active_clients[websocket]
            if client_id:
                self.input_manager.release_slot(client_id)
                self.pipelines.pop(client_id, None)
                self.firewall.reset_client(client_id)
                logger.info(f"Cleaned up session for client [{client_id[:8]}]")

    async def _downlink_telemetry_loop(self) -> None:
        """Broadcasts live game telemetry and dynamic haptic triggers to connected phones at 60 Hz."""
        interval = 1.0 / settings.network.TELEMETRY_BROADCAST_RATE_HZ
        while self._running:
            start_t = time.perf_counter()
            if self.active_clients:
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

        # Start Combined HTTP / WebSocket Server
        self._server = await websockets.serve(
            self._handle_websocket,
            host=settings.network.HOST,
            port=self.port,
            ssl=ssl_context,
            process_request=self._handle_http_request,
            ping_interval=10,
            ping_timeout=5,
            max_size=2**20
        )

        self._render_ascii_banner(host_ips)

    async def stop(self) -> None:
        """Gracefully shuts down all subsystems and hardware emulations."""
        self._running = False
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
