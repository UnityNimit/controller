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


def test_gateway_http_static_serving():
    async def _http_test():
        server = ControllerGatewayServer(
            use_ssl=False,
            port=8101,
            enable_simulator=False,
            force_mock_input=True
        )
        
        class MockRequest:
            def __init__(self, path: str):
                self.path = path
                self.headers = {"host": "127.0.0.1:8101"}

        resp = await server._handle_http_request(None, MockRequest("/"))
        assert resp is not None
        assert resp.status_code == 200
        assert b"Controller" in resp.body or b"html" in resp.body.lower()

        # 404 test
        resp_404 = await server._handle_http_request(None, MockRequest("/nonexistent.xyz"))
        assert resp_404 is not None
        assert resp_404.status_code == 404

    asyncio.run(_http_test())


def test_mobile_client_assets_and_integrity():
    async def _test():
        server = ControllerGatewayServer(
            use_ssl=False,
            port=8102,
            enable_simulator=False,
            force_mock_input=True
        )

        class MockRequest:
            def __init__(self, path: str):
                self.path = path
                self.headers = {"host": "127.0.0.1:8102"}

        # 1. Test logo.png serving
        resp_logo = await server._handle_http_request(None, MockRequest("/logo.png"))
        assert resp_logo.status_code == 200
        assert len(resp_logo.body) > 1000
        content_type_logo = resp_logo.headers.get("Content-Type", "")
        assert "image/png" in content_type_logo

        # 2. Test index.html contains updated branding, assets, and custom Figma modules
        resp_index = await server._handle_http_request(None, MockRequest("/index.html"))
        assert resp_index.status_code == 200
        index_text = resp_index.body.decode("utf-8")
        assert "<title>Controller</title>" in index_text
        assert "VERSION 1.0.0" in index_text
        assert "logo.png" in index_text
        assert "controller-app" in index_text
        assert "mod-gyro" in index_text
        assert "gyro-canvas" in index_text
        assert "mod-visualizer" in index_text
        assert "visualizer-canvas" in index_text
        assert "mod-settings-nut" in index_text
        assert "btn-settings-logo" in index_text
        assert "mod-left-wing" in index_text
        assert "left-stick-puck" in index_text
        assert "mod-right-wing" in index_text
        assert "right-stick-puck" in index_text
        assert "ROTATE TO LANDSCAPE" not in index_text

        # 3. Test cockpit.css contains forced landscape and tactical monochrome
        resp_css = await server._handle_http_request(None, MockRequest("/css/cockpit.css"))
        assert resp_css.status_code == 200
        css_text = resp_css.body.decode("utf-8")
        assert "forced-landscape-portrait" in css_text
        assert "--bg-dark: #08090b" in css_text
        assert "rotate(90deg)" in css_text
        assert "907 / 400" in css_text
        assert "red-puck" in css_text
        assert "nut-btn" in css_text

        # 4. Test cockpit.js has multi-touch isolation, dual fixed sticks, and canvas render loops
        resp_js = await server._handle_http_request(None, MockRequest("/js/cockpit.js"))
        assert resp_js.status_code == 200
        js_text = resp_js.body.decode("utf-8")
        assert "getGamepadPoint" in js_text
        assert "getGamepadCenter" in js_text
        assert "directBtnPointers" in js_text
        assert "_renderGyroCanvas" in js_text
        assert "_renderVisualizerCanvas" in js_text
        assert "_updateLeftStickFromPointer" in js_text
        assert "_updateRightStickFromPointer" in js_text
        assert "setPointerCapture" not in js_text
        assert "lostpointercapture" not in js_text

    asyncio.run(_test())

