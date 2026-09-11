"""
Unit tests for Game Telemetry Parsers and Synthetic Racing Physics Simulator
"""

import struct
import json
import pytest
from gateway.telemetry_receiver import TelemetryPacketParser
from gateway.telemetry_simulator import RacingLapSimulator


def test_parse_outsim():
    # Construct synthetic 64-byte OutSim packet
    # struct: <I 3f f f f 3f 3f 3i
    data = struct.pack(
        "<I 3f f f f 3f 3f 3i",
        1000,                # time ms
        0.0, 0.0, 0.0,       # angvel
        0.0, 0.0, 0.0,       # heading, pitch, roll
        9.8, 0.0, 0.0,       # accel m/s^2 (lateral ~1G)
        0.0, 0.0, 27.78,     # vel m/s (27.78 m/s = 100 km/h)
        0, 0, 0              # pos
    )
    parsed = TelemetryPacketParser.parse(data)
    assert parsed is not None
    assert parsed["format"] == "outsim"
    assert abs(parsed["speed_kmh"] - 100.0) < 1.0
    assert abs(parsed["g_lat"] - 1.0) < 0.1


def test_parse_outgauge():
    # Construct synthetic 96-byte OutGauge packet
    # struct: <I 4s H B B f f f f f f f I I f f f
    prefix = struct.pack(
        "<I 4s H B B f f f f f f f I I f f f",
        500,
        b"CAR1",
        0,
        4,                   # gear byte (4 -> gear 3)
        0,
        30.0,                # speed m/s (108 km/h)
        6500.0,              # rpm
        0.0, 90.0, 50.0, 4.0, 95.0,
        (1 << 9),            # Dashlights bit 9 = ABS active
        0,
        1.0, 0.0, 0.0
    )
    # Pad to 96 bytes
    data = prefix + b"\x00" * (96 - len(prefix))
    parsed = TelemetryPacketParser.parse(data)
    assert parsed is not None
    assert parsed["format"] == "outgauge"
    assert parsed["gear"] == 3
    assert parsed["rpm"] == 6500.0
    assert parsed["abs_active"] is True


def test_parse_json_telemetry():
    json_data = json.dumps({"rpm": 7200, "speed_kmh": 145.5, "gear": 4}).encode("utf-8")
    parsed = TelemetryPacketParser.parse(json_data)
    assert parsed is not None
    assert parsed["format"] == "json"
    assert parsed["rpm"] == 7200
    assert parsed["gear"] == 4


def test_racing_lap_simulator():
    sim = RacingLapSimulator(update_rate_hz=60.0)
    
    # Check initial step
    frame0 = sim.step()
    assert frame0["format"] == "simulated"
    assert frame0["rpm"] >= 1000.0
    assert frame0["gear"] >= 1

    # Advance through acceleration straight
    for _ in range(300):
        frame = sim.step()
    assert frame["speed_kmh"] > 50.0
    assert frame["gear"] > 1

    # Advance into braking / cornering phase
    for _ in range(400):
        frame = sim.step()
    assert "slip_ratio" in frame
    assert "g_lat" in frame
