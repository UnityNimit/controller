"""
Unit and integration tests for the Zero-Copy 24-Byte Binary Micro-Packet Wire Protocol (v2)
"""

import struct
import asyncio
import hmac
import hashlib
import json
import websockets
from config import settings
from gateway.server import (
    decode_binary_packet,
    BINARY_STRUCT,
    BINARY_PACKET_MAGIC,
    BINARY_PACKET_VERSION,
    ControllerGatewayServer
)


def test_binary_packet_decode_structure():
    # Construct a sample 24-byte packet
    # magic=0x43, version=0x02, seq=100, ts_ms=54321
    # stick_x=16000, stick_y=-8000, right_x=-4000, right_y=12000
    # throttle=255, brake=128, btn_mask=0b0000000000000101 (A and X pressed)
    # angle_x100=-1450 (-14.50 deg), flags=0x01 (gyro_enabled), rtt=12
    packet = BINARY_STRUCT.pack(
        BINARY_PACKET_MAGIC,
        BINARY_PACKET_VERSION,
        100,
        54321,
        16000,
        -8000,
        -4000,
        12000,
        255,
        128,
        (1 << 0) | (1 << 2),  # A and X
        -1450,
        0x01,  # gyro_enabled
        12     # rtt_ms
    )
    assert len(packet) == 24

    decoded = decode_binary_packet(packet)
    assert decoded is not None
    assert decoded["type"] == "INPUT"
    assert decoded["seq"] == 100
    assert abs(decoded["ts"] - 54.321) < 1e-4
    assert decoded["stick_x"] == 16000
    assert decoded["stick_y"] == -8000
    assert decoded["right_stick_x"] == -4000
    assert decoded["right_stick_y"] == 12000
    assert abs(decoded["throttle"] - 1.0) < 1e-3
    assert abs(decoded["brake"] - (128 / 255.0)) < 1e-3
    assert decoded["buttons"]["A"] is True
    assert decoded["buttons"]["X"] is True
    assert decoded["buttons"]["B"] is False
    assert decoded["buttons"]["Y"] is False
    assert decoded["gyro_enabled"] is True
    assert abs(decoded["angle"] - (-14.50)) < 1e-3
    assert decoded["rtt"] == 12.0
    assert decoded["protocol"] == "BINARY v2"


def test_binary_packet_rejection():
    # Corrupt magic byte
    bad_magic = BINARY_STRUCT.pack(0x99, BINARY_PACKET_VERSION, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
    assert decode_binary_packet(bad_magic) is None

    # Too short
    assert decode_binary_packet(b"\x43\x02\x01") is None


def test_binary_websocket_live_transmission():
    async def _async_test():
        test_port = 8109
        server = ControllerGatewayServer(
            use_ssl=False,
            port=test_port,
            enable_simulator=False,
            force_mock_input=True
        )
        await server.start()

        try:
            url = f"ws://127.0.0.1:{test_port}/ws"
            async with websockets.connect(url) as ws:
                # 1. Challenge-Response Authentication
                challenge_raw = await ws.recv()
                challenge = json.loads(challenge_raw)
                nonce = challenge["nonce"]
                ts = challenge["timestamp"]

                payload = f"{nonce}:{ts}".encode("utf-8")
                sig = hmac.new(settings.security.HMAC_SHARED_SECRET, payload, hashlib.sha256).hexdigest()

                await ws.send(json.dumps({
                    "type": "AUTH_RESPONSE",
                    "client_id": "test_binary_node",
                    "nonce": nonce,
                    "timestamp": ts,
                    "signature": sig
                }))

                auth_raw = await ws.recv()
                auth = json.loads(auth_raw)
                assert auth["type"] == "AUTH_SUCCESS"

                # 2. Transmit Packed Binary Packet (24 Bytes)
                bin_packet = BINARY_STRUCT.pack(
                    BINARY_PACKET_MAGIC,
                    BINARY_PACKET_VERSION,
                    1,
                    12345,
                    25000,
                    -12000,
                    0,
                    0,
                    255,
                    0,
                    (1 << 0),  # A button
                    0,
                    0,
                    5
                )
                await ws.send(bin_packet)
                await asyncio.sleep(0.05)

                # Verify virtual gamepad received the binary state
                ctrl = server.input_manager.controllers[0]
                assert ctrl.steering == 25000
                assert ctrl.stick_y == -12000
                assert ctrl.throttle == 255
                assert ctrl.buttons.get("A") is True

        finally:
            await server.stop()

    asyncio.run(_async_test())
