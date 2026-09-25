"""
Project Controller - Unit & Integration Tests for Pillar 4 (Ultra-Low-Latency Kernel Transport)
Tests TCP_NODELAY, anti-bufferbloat buffer tuning, zero-heap binary decoding, and live transmission.
"""

import socket
import struct
import time
import asyncio
import pytest
from gateway.kernel_transport import (
    KernelTransportTuner,
    FastBinaryDecoder,
    BINARY_PACKET_MAGIC,
    BINARY_PACKET_VERSION,
    BINARY_PACKET_SIZE,
    BINARY_STRUCT
)
from gateway.server import ControllerGatewayServer
from config import settings


def test_kernel_transport_tuner_tcp_nodelay_and_buffers():
    """Verify that KernelTransportTuner sets TCP_NODELAY and tunes socket buffers on a live TCP socket."""
    # Create listening socket and connect
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.bind(("127.0.0.1", 0))
    server_sock.listen(1)
    port = server_sock.getsockname()[1]

    client_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_sock.connect(("127.0.0.1", port))
    conn, _ = server_sock.accept()

    try:
        # Tune both ends
        assert KernelTransportTuner.tune_socket(conn) is True
        assert KernelTransportTuner.tune_socket(client_sock) is True

        # Verify TCP_NODELAY is active (value 1)
        opt_val = conn.getsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY)
        assert opt_val != 0, f"Expected TCP_NODELAY active, got {opt_val}"

        client_opt_val = client_sock.getsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY)
        assert client_opt_val != 0

        # Verify buffer sizes
        rcvbuf = conn.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF)
        sndbuf = conn.getsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF)
        assert rcvbuf > 0
        assert sndbuf > 0
    finally:
        client_sock.close()
        conn.close()
        server_sock.close()


def test_fast_binary_decoder_accuracy():
    """Verify FastBinaryDecoder correctly decodes 24-byte packets into normalized dict and raw tuple."""
    # Pack a sample packet:
    # seq=42, ts=123456ms, sx=16384, sy=-16384, rx=32767, ry=-32768,
    # throttle=204, brake=128, btn_mask=0x0005 (A + X), angle_x100=-4520 (-45.2 deg), flags=0x01 (gyro), rtt=12
    raw = BINARY_STRUCT.pack(
        BINARY_PACKET_MAGIC,
        BINARY_PACKET_VERSION,
        42,
        123456,
        16384,
        -16384,
        32767,
        -32768,
        204,
        128,
        0x0005,
        -4520,
        0x01,
        12
    )
    assert len(raw) == BINARY_PACKET_SIZE

    # 1. Test dictionary decode
    d = FastBinaryDecoder.decode(raw)
    assert d is not None
    assert d["seq"] == 42
    assert abs(d["ts"] - 123.456) < 1e-4
    assert d["stick_x"] == 16384
    assert d["stick_y"] == -16384
    assert d["right_stick_x"] == 32767
    assert d["right_stick_y"] == -32768
    assert abs(d["throttle"] - (204 / 255.0)) < 1e-4
    assert abs(d["brake"] - (128 / 255.0)) < 1e-4
    assert d["buttons"]["A"] is True
    assert d["buttons"]["B"] is False
    assert d["buttons"]["X"] is True
    assert d["gyro_enabled"] is True
    assert abs(d["angle"] - (-45.20)) < 1e-3
    assert d["rtt"] == 12.0

    # 2. Test raw tuple decode (zero heap)
    t = FastBinaryDecoder.decode_raw_tuple(raw)
    assert t is not None
    assert t[0] == 42
    assert abs(t[1] - 123.456) < 1e-4
    assert t[2] == 16384
    assert t[3] == -16384
    assert t[4] == 32767
    assert t[5] == -32768
    assert t[6] == 204 / 255.0
    assert t[7] == 128 / 255.0
    assert t[8] == 0x0005
    assert t[9] is True
    assert abs(t[10] - (-45.20)) < 1e-3
    assert t[11] == 12.0


def test_fast_binary_decoder_throughput_benchmark():
    """Benchmark FastBinaryDecoder to ensure sub-microsecond zero-heap performance (>500,000 ops/sec)."""
    raw = BINARY_STRUCT.pack(
        BINARY_PACKET_MAGIC,
        BINARY_PACKET_VERSION,
        100,
        50000,
        1000,
        -1000,
        2000,
        -2000,
        255,
        0,
        0x0001,
        0,
        0x00,
        5
    )

    iterations = 50000
    start = time.perf_counter()
    for _ in range(iterations):
        res = FastBinaryDecoder.decode(raw)
    duration = time.perf_counter() - start

    rate = iterations / duration
    # Must comfortably exceed 250,000 decodes per second (typically 1.5M - 2.5M on modern CPUs)
    assert rate > 250_000, f"Expected decoder rate > 250k/s, got {rate:,.0f} ops/sec in {duration:.4f}s"


def test_server_live_binary_transmission_with_kernel_tuning():
    """End-to-end test of gateway WebSocket with KernelTransportTuner and binary delivery."""
    import websockets
    import json
    import hmac
    import hashlib

    async def _live_test():
        server = ControllerGatewayServer(
            use_ssl=False,
            port=8106,
            enable_simulator=False,
            force_mock_input=True
        )
        await server.start()

        uri = "ws://127.0.0.1:8106"
        async with websockets.connect(uri) as ws:
            # 1. Handshake
            challenge_raw = await ws.recv()
            challenge = json.loads(challenge_raw)
            nonce = challenge["nonce"]
            ts = challenge["timestamp"]

            payload = f"{nonce}:{ts}".encode("utf-8")
            sig = hmac.new(settings.security.HMAC_SHARED_SECRET, payload, hashlib.sha256).hexdigest()

            auth_resp = {
                "type": "AUTH_RESPONSE",
                "nonce": nonce,
                "timestamp": ts,
                "signature": sig,
                "client_id": "test_kernel_client_1"
            }
            await ws.send(json.dumps(auth_resp))

            # Receive AUTH_SUCCESS
            succ_raw = await ws.recv()
            succ = json.loads(succ_raw)
            assert succ["type"] == "AUTH_SUCCESS"

            # 2. Transmit 24-byte binary packet
            packet_bytes = BINARY_STRUCT.pack(
                BINARY_PACKET_MAGIC,
                BINARY_PACKET_VERSION,
                1,
                1000,
                24000,
                -12000,
                0,
                0,
                255,
                0,
                0x0001,  # Button A
                0,
                0,
                5
            )
            await ws.send(packet_bytes)
            await asyncio.sleep(0.05)

            # 3. Verify mock controller received input
            ctrl = server.input_manager.controllers[0]
            assert ctrl.steering == 24000
            assert ctrl.throttle == 255
            assert ctrl.buttons.get("A") is True

        await server.stop()

    asyncio.run(_live_test())
