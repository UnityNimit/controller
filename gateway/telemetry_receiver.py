"""
Project Controller - Real-Time Game Engine Telemetry Ingestion Receiver
Listens on local UDP sockets (standard port 20777) and decodes native telemetry
protocols from Assetto Corsa, BeamNG, Dirt Rally, Forza, and OutSim/OutGauge.
"""

import socket
import struct
import json
import logging
import asyncio
import time
from typing import Optional, Dict, Any, Callable

logger = logging.getLogger("Controller.Telemetry")


class TelemetryPacketParser:
    """
    Decodes binary telemetry structures from major racing engines.
    """

    @staticmethod
    def parse_outsim(data: bytes) -> Optional[Dict[str, Any]]:
        """
        Parses Live for Speed / Assetto Corsa OutSim UDP packet.
        Size: 64 or 68 bytes.
        Struct: time (I), angvel (3f), heading (f), pitch (f), roll (f), accel (3f), vel (3f), pos (3i), id (i)
        """
        if len(data) not in (64, 68):
            return None
        try:
            # First 64 bytes
            unpacked = struct.unpack("<I 3f f f f 3f 3f 3i", data[:64])
            time_ms = unpacked[0]
            # Accelerometer in m/s^2 (indices 7, 8, 9)
            ax, ay, az = unpacked[7], unpacked[8], unpacked[9]
            # Velocity in m/s (indices 10, 11, 12)
            vx, vy, vz = unpacked[10], unpacked[11], unpacked[12]
            speed_ms = (vx**2 + vy**2 + vz**2) ** 0.5
            speed_kmh = speed_ms * 3.6

            g_lat = ax / 9.80665
            g_long = az / 9.80665
            total_g = (ax**2 + ay**2 + az**2) ** 0.5 / 9.80665

            return {
                "format": "outsim",
                "speed_kmh": round(speed_kmh, 1),
                "rpm": 0.0,
                "max_rpm": 8000.0,
                "gear": 1,
                "slip_ratio": 0.0,
                "g_lat": round(g_lat, 2),
                "g_long": round(g_long, 2),
                "impact_g": round(total_g, 2),
                "abs_active": False,
                "tcs_active": False,
                "timestamp": time.time()
            }
        except Exception as e:
            logger.debug(f"OutSim parse error: {e}")
            return None

    @staticmethod
    def parse_outgauge(data: bytes) -> Optional[Dict[str, Any]]:
        """
        Parses OutGauge UDP packet (BeamNG, LFS, Dirt).
        Size: 96 bytes.
        Struct: Time(I), Car(4s), Flags(H), Gear(B), PLID(B), Speed(f), RPM(f), Turbo(f),
                EngTemp(f), Fuel(f), OilPressure(f), OilTemp(f), DashLights(I), ShowLights(I),
                Throttle(f), Brake(f), Clutch(f), Display1(16s), Display2(16s), ID(i)
        """
        if len(data) < 60:
            return None
        try:
            unpacked = struct.unpack("<I 4s H B B f f f f f f f I I f f f", data[:60])
            # gear byte: 0 = reverse, 1 = neutral, 2 = 1st, 3 = 2nd...
            raw_gear = unpacked[3]
            gear = raw_gear - 1  # Standard: -1 = R, 0 = N, 1 = 1st...
            speed_ms = unpacked[5]
            rpm = unpacked[6]
            dashlights = unpacked[12]
            # Dashlight flags: bit 9 = ABS, bit 10 = TC
            abs_active = bool(dashlights & (1 << 9))
            tcs_active = bool(dashlights & (1 << 10))

            return {
                "format": "outgauge",
                "speed_kmh": round(speed_ms * 3.6, 1),
                "rpm": round(rpm, 0),
                "max_rpm": 8500.0,
                "gear": gear,
                "slip_ratio": 0.0,
                "g_lat": 0.0,
                "g_long": 0.0,
                "impact_g": 0.0,
                "abs_active": abs_active,
                "tcs_active": tcs_active,
                "timestamp": time.time()
            }
        except Exception as e:
            logger.debug(f"OutGauge parse error: {e}")
            return None

    @staticmethod
    def parse_forza(data: bytes) -> Optional[Dict[str, Any]]:
        """
        Parses Forza Motorsport / Horizon UDP Dash Telemetry packet.
        Size: 311 or 324 bytes.
        """
        if len(data) not in (311, 324):
            return None
        try:
            # Forza Dash packet fields:
            # offset 16: current_engine_rpm (f32)
            # offset 8: engine_max_rpm (f32)
            # offset 244: speed (f32, m/s)
            # offset 300: gear (u8)
            # offset 88: tire_slip_ratio_fl/fr/rl/rr (4 x f32)
            engine_max_rpm = struct.unpack_from("<f", data, 8)[0]
            current_rpm = struct.unpack_from("<f", data, 16)[0]
            speed_ms = struct.unpack_from("<f", data, 244)[0]
            gear = struct.unpack_from("<B", data, 300)[0]
            slips = struct.unpack_from("<4f", data, 88)
            avg_slip = sum(abs(s) for s in slips) / 4.0

            # G forces: accel X/Y/Z at offset 20
            ax, ay, az = struct.unpack_from("<3f", data, 20)

            return {
                "format": "forza",
                "speed_kmh": round(speed_ms * 3.6, 1),
                "rpm": round(current_rpm, 0),
                "max_rpm": round(engine_max_rpm, 0) if engine_max_rpm > 0 else 8500.0,
                "gear": int(gear),
                "slip_ratio": round(avg_slip, 3),
                "g_lat": round(ax / 9.80665, 2),
                "g_long": round(az / 9.80665, 2),
                "impact_g": round((ax**2 + ay**2 + az**2) ** 0.5 / 9.80665, 2),
                "abs_active": False,
                "tcs_active": avg_slip > 0.4,
                "timestamp": time.time()
            }
        except Exception as e:
            logger.debug(f"Forza telemetry parse error: {e}")
            return None

    @classmethod
    def parse(cls, data: bytes) -> Optional[Dict[str, Any]]:
        """Auto-detects format based on packet byte length or JSON structure."""
        length = len(data)
        if length in (64, 68):
            return cls.parse_outsim(data)
        elif length >= 92 and length <= 96:
            return cls.parse_outgauge(data)
        elif length in (311, 324):
            return cls.parse_forza(data)
        else:
            # Try parsing as JSON string
            try:
                parsed = json.loads(data.decode("utf-8"))
                if isinstance(parsed, dict) and "rpm" in parsed:
                    parsed["format"] = "json"
                    parsed["timestamp"] = time.time()
                    return parsed
            except Exception:
                pass
        return None


class UDPTelemetryReceiver:
    """
    AsyncIO UDP Listener for Game Telemetry ingestion.
    """
    def __init__(self, port: int = 20777, on_telemetry: Optional[Callable[[Dict[str, Any]], None]] = None):
        self.port = port
        self.on_telemetry = on_telemetry
        self.running = False
        self.transport: Optional[asyncio.DatagramTransport] = None
        self.last_telemetry: Dict[str, Any] = {
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

    class Protocol(asyncio.DatagramProtocol):
        def __init__(self, receiver: "UDPTelemetryReceiver"):
            self.receiver = receiver

        def datagram_received(self, data: bytes, addr: tuple) -> None:
            parsed = TelemetryPacketParser.parse(data)
            if parsed:
                self.receiver.last_telemetry = parsed
                if self.receiver.on_telemetry:
                    self.receiver.on_telemetry(parsed)

    async def start(self) -> None:
        loop = asyncio.get_running_loop()
        try:
            self.transport, _ = await loop.create_datagram_endpoint(
                lambda: self.Protocol(self),
                local_addr=("0.0.0.0", self.port)
            )
            self.running = True
            logger.info(f"UDP Telemetry listener active on port {self.port}")
        except Exception as e:
            logger.warning(f"Could not bind UDP telemetry port {self.port}: {e}")

    def stop(self) -> None:
        if self.transport:
            self.transport.close()
            self.running = False
            logger.info("UDP Telemetry listener stopped")
