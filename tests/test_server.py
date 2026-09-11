"""
Integration tests for Gateway HTTP serving and WebSocket protocol handling
"""

import asyncio
import hmac
import hashlib
import json
import websockets
from config import settings
from gateway.server import ControllerGatewayServer


def test_gateway_server_handshake_and_input():
    async def _async_test():
        # Use mock input and no SSL on ephemeral test port
        test_port = 8099
        server = ControllerGatewayServer(
            use_ssl=False,
            port=test_port,
            enable_simulator=True,
            force_mock_input=True
        )
        
        await server.start()

        try:
            url = f"ws://127.0.0.1:{test_port}/ws"
            async with websockets.connect(url) as ws:
                # 1. Expect AUTH_CHALLENGE
                challenge_raw = await ws.recv()
                challenge = json.loads(challenge_raw)
                assert challenge["type"] == "AUTH_CHALLENGE"
                nonce = challenge["nonce"]
                ts = challenge["timestamp"]

                # 2. Compute HMAC Response
                payload = f"{nonce}:{ts}".encode("utf-8")
                sig = hmac.new(settings.security.HMAC_SHARED_SECRET, payload, hashlib.sha256).hexdigest()

                await ws.send(json.dumps({
                    "type": "AUTH_RESPONSE",
                    "client_id": "test_suite_client",
                    "nonce": nonce,
                    "timestamp": ts,
                    "signature": sig
                }))

                # 3. Expect AUTH_SUCCESS
                auth_raw = await ws.recv()
                auth = json.loads(auth_raw)
                assert auth["type"] == "AUTH_SUCCESS"
                assert auth["player_slot"] == 1

                # 4. Send INPUT packet
                input_pkt = {
                    "type": "INPUT",
                    "seq": 1,
                    "ts": 100.0,
                    "angle": 12.5,
                    "throttle": 0.75,
                    "brake": 0.0,
                    "accel": {"x": 0.0, "y": 0.0, "z": 9.8},
                    "buttons": {"SHIFT_UP": True}
                }
                await ws.send(json.dumps(input_pkt))

                # 5. Receive TELEMETRY broadcast
                telem_raw = await ws.recv()
                telem = json.loads(telem_raw)
                assert telem["type"] == "TELEMETRY"
                assert "data" in telem
                assert "haptics" in telem
        finally:
            await server.stop()

    asyncio.run(_async_test())
