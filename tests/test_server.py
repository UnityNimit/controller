"""
Integration tests for Gateway HTTP serving and WebSocket protocol handling
"""

import asyncio
import time
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
        assert "VERSION 1.1.0" in index_text
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

        # 5. Test dedicated haptics.js module serving and integrity
        resp_haptics = await server._handle_http_request(None, MockRequest("/js/haptics.js"))
        assert resp_haptics.status_code == 200
        haptics_text = resp_haptics.body.decode("utf-8")
        assert "class HapticAudioEngine" in haptics_text
        assert "timedRumble" in haptics_text
        assert "handleRumble" in haptics_text
        assert "triggerClick" in haptics_text
        assert "_ensureRumbleLoop" in haptics_text
        assert "window.HapticAudioEngine = HapticAudioEngine" in haptics_text

        # 6. Test isolated vibration_test.html workbench serving
        resp_vib_bench = await server._handle_http_request(None, MockRequest("/vibration_test.html"))
        assert resp_vib_bench.status_code == 200
        vib_text = resp_vib_bench.body.decode("utf-8")
        assert "Haptics & Vibration Lab" in vib_text
        assert "testTimedRumble" in vib_text
        assert "startInfinite" in vib_text
        assert "setupFastTouch" in vib_text
        assert "js/haptics.js" in vib_text

    asyncio.run(_test())


def test_settings_page_and_navigation_assets():
    async def _test():
        server = ControllerGatewayServer(
            use_ssl=False,
            port=8104,
            enable_simulator=False,
            force_mock_input=True
        )

        class MockRequest:
            def __init__(self, path: str):
                self.path = path
                self.headers = {"host": "127.0.0.1:8104"}

        # 1. Test settings elements in index.html (and verify layout2 is gone)
        resp_index = await server._handle_http_request(None, MockRequest("/index.html"))
        assert resp_index.status_code == 200
        text = resp_index.body.decode("utf-8")
        assert "settings-frame" in text
        assert "settings-btn-logo" in text
        assert "settings-current-player-text" in text
        assert "btn-switch-player" in text
        assert "btn-toggle-vibration" in text
        assert "settings-slot-p1" in text
        assert "settings-slot-p4" in text
        # Confirm complete removal of layout 2
        assert "layout2-wrapper" not in text
        assert "layout2-frame" not in text
        assert "l2-btn-settings-logo" not in text

        # 2. Test settings styles in cockpit.css (and confirm layout2 styles gone)
        resp_css = await server._handle_http_request(None, MockRequest("/css/cockpit.css"))
        assert resp_css.status_code == 200
        css_text = resp_css.body.decode("utf-8")
        assert ".settings-frame" in css_text
        assert ".settings-card" in css_text
        assert ".settings-slot-pill" in css_text
        assert ".settings-toggle-btn" in css_text
        assert ".controller-layout2" not in css_text

        # 3. Test settings methods in cockpit.js
        resp_js = await server._handle_http_request(None, MockRequest("/js/cockpit.js"))
        assert resp_js.status_code == 200
        js_text = resp_js.body.decode("utf-8")
        assert "openSettings" in js_text
        assert "closeSettings" in js_text
        assert "toggleSettings" in js_text
        assert "syncSettingsDom" in js_text
        assert "setPlayerSlot" in js_text
        assert "updateLayoutScaling" in js_text

        # 4. Test haptics engine vibration toggle support and default OFF
        resp_haptics = await server._handle_http_request(None, MockRequest("/js/haptics.js"))
        assert resp_haptics.status_code == 200
        haptics_text = resp_haptics.body.decode("utf-8")
        assert "setVibrationEnabled" in haptics_text
        assert "toggleVibration" in haptics_text
        assert "vibrationEnabled" in haptics_text
        assert 'localStorage.getItem("controller_vibration_enabled") === "true"' in haptics_text

        # 5. Test gyro engine default OFF and indicator rendering logic
        resp_gyro = await server._handle_http_request(None, MockRequest("/js/gyro.js"))
        assert resp_gyro.status_code == 200
        gyro_text = resp_gyro.body.decode("utf-8")
        assert 'localStorage.getItem("controller_gyro_enabled")' in gyro_text
        assert "renderHorizonLines" in gyro_text
        assert "getEffectiveAngle" in gyro_text

        # 6. Verify default OFF in index.html static markup
        assert 'id="btn-toggle-vibration"' in text
        assert 'id="btn-settings-gyro"' in text
        assert 'class="circle-gyro mod-gyro"' in text
        assert 'class="circle-gyro mod-gyro active"' not in text

        # 7. Test Gamepad SVG assets are served successfully
        for asset in ["Middle_icon.svg", "touchpad_body.svg", "Left_joystick.svg", "LT_LB_containers.svg"]:
            resp_asset = await server._handle_http_request(None, MockRequest(f"/assets/{asset}"))
            assert resp_asset.status_code == 200
            assert len(resp_asset.body) > 50

    asyncio.run(_test())


def test_layout1_customization_system():
    async def _test():
        server = ControllerGatewayServer(
            use_ssl=False,
            port=8105,
            enable_simulator=False,
            force_mock_input=True
        )

        class MockRequest:
            def __init__(self, path: str):
                self.path = path
                self.headers = {"host": "127.0.0.1:8105"}

        # 1. Test index.html contains customization HUD, hold ring, and radius slider elements
        resp_index = await server._handle_http_request(None, MockRequest("/index.html"))
        assert resp_index.status_code == 200
        text = resp_index.body.decode("utf-8")
        assert "logo-hold-ring" in text
        assert "logo-hold-circle" in text
        assert "l1-custom-hud" in text
        assert "l1-reset-btn" in text
        assert "l1-radius-popup" in text
        assert "l1-radius-slider" in text
        assert "left-stick-radius-preview" in text
        assert "right-stick-radius-preview" in text
        assert "data-custom-id" in text
        assert 'data-custom-id="btn-y"' in text
        assert 'data-custom-id="btn-x"' in text
        assert 'data-custom-id="btn-b"' in text
        assert 'data-custom-id="btn-a"' in text
        assert 'data-custom-id="left-stick-zone"' in text
        assert 'data-custom-id="right-stick-zone"' in text
        assert "floating-stick-zone" in text

        # 2. Test cockpit.css contains customizing-mode styles and cyan variables
        resp_css = await server._handle_http_request(None, MockRequest("/css/cockpit.css"))
        assert resp_css.status_code == 200
        css_text = resp_css.body.decode("utf-8")
        assert ".customizing-mode" in css_text
        assert "--cyan-neon" in css_text
        assert ".l1-radius-popup" in css_text
        assert ".l1-resize-handle" in css_text
        assert ".stick-radius-preview" in css_text
        assert ".customizing-mode .abxy-btn" in css_text
        assert ".floating-stick-zone" in css_text
        assert ".floating-zone-label" in css_text
        assert ".customizing-mode .l1-resize-handle" in css_text
        assert "display: block !important;" in css_text
        assert "--l1-dx" in css_text
        assert "--l1-press" in css_text

        # 3. Test cockpit.js has customization engine methods, floating joysticks, and input disablement
        resp_js = await server._handle_http_request(None, MockRequest("/js/cockpit.js"))
        assert resp_js.status_code == 200
        js_text = resp_js.body.decode("utf-8")
        assert "toggleCustomizeMode" in js_text
        assert "_initCustomizationHandlers" in js_text
        assert "openRadiusPopup" in js_text
        assert "closeRadiusPopup" in js_text
        assert "_saveLayout1Config" in js_text
        assert "resetLayout1Config" in js_text
        assert "controller_layout1_custom_config" in js_text
        assert "if (this.isCustomizingLayout1) return;" in js_text
        assert "--l1-dx" in js_text
        assert "--l1-press" in js_text
        assert "_startLeftStick" in js_text
        assert "_startRightStick" in js_text
        assert "_isPointInElement" in js_text
        assert "leftStickOrigin" in js_text

    asyncio.run(_test())


def test_splash_screen_morph_and_layout1_guarantee():
    async def _test():
        server = ControllerGatewayServer(
            use_ssl=False,
            port=8106,
            enable_simulator=False,
            force_mock_input=True
        )

        class MockRequest:
            def __init__(self, path: str):
                self.path = path
                self.headers = {"host": "127.0.0.1:8106"}

        # 1. Verify index.html contains the splash screen elements and Rotate to start hint
        resp_index = await server._handle_http_request(None, MockRequest("/index.html"))
        assert resp_index.status_code == 200
        text = resp_index.body.decode("utf-8")
        assert 'id="splash-screen"' in text
        assert 'class="splash-logo-container"' in text
        assert 'class="splash-logo-img"' in text
        assert 'splash-rotate-hint' in text
        assert 'Rotate to start' in text
        assert 'id="gamepad-frame"' in text

        # 2. Verify cockpit.css has rotate hint and transition classes
        resp_css = await server._handle_http_request(None, MockRequest("/css/cockpit.css"))
        assert resp_css.status_code == 200
        css = resp_css.body.decode("utf-8")
        assert ".splash-rotate-hint" in css
        assert ".splash-morphing" in css
        assert "#gamepad-frame.layout1-entering" in css
        assert ".layout1-blooming" in css
        assert ".morph-complete" in css

        # 3. Verify cockpit.js has rotation-to-start detection, responsive touch handlers, and Layout 1 guarantee
        resp_js = await server._handle_http_request(None, MockRequest("/js/cockpit.js"))
        assert resp_js.status_code == 200
        js = resp_js.body.decode("utf-8")
        assert "_startMorphAnimation" in js
        assert "pointerdown" in js
        assert "touchstart" in js
        assert "this.switchLayout(1, false)" in js
        assert "_isEngaging" in js
        assert "checkRotationToStart" in js
        assert "orientationchange" in js

        # 4. Verify JavaScript syntax integrity
        import subprocess, shutil
        if shutil.which("node"):
            res = subprocess.run(["node", "-c", "client/js/cockpit.js"], capture_output=True, text=True)
            assert res.returncode == 0, f"JS Syntax Error: {res.stderr}"

    asyncio.run(_test())


def test_universal_scaling_gyro_and_customize_removal():
    async def _test():
        server = ControllerGatewayServer(
            use_ssl=False,
            port=8107,
            enable_simulator=False,
            force_mock_input=True
        )

        class MockRequest:
            def __init__(self, path: str):
                self.path = path
                self.headers = {"host": "127.0.0.1:8107"}

        # 1. Test index.html contains gyro indicator (default off) and hidden customize HUD
        resp_index = await server._handle_http_request(None, MockRequest("/index.html"))
        assert resp_index.status_code == 200
        text = resp_index.body.decode("utf-8")
        assert 'class="circle-gyro mod-gyro"' in text
        assert 'id="mod-gyro"' in text
        assert 'gyro-horizon-line' in text
        assert 'id="l1-custom-hud" style="display:none !important;"' in text
        assert 'id="safe-area-probe"' in text

        # 2. Test cockpit.css contains 907x400 canvas, centered logo & gyro, and hidden customize HUD
        resp_css = await server._handle_http_request(None, MockRequest("/css/cockpit.css"))
        assert resp_css.status_code == 200
        css = resp_css.body.decode("utf-8")
        assert "width: 907px" in css
        assert "height: 400px" in css
        assert "aspect-ratio: 907 / 400" in css
        assert ".l1-custom-hud" in css
        assert "display: none !important;" in css
        assert "translate(-50%, -50%)" in css

        # 3. Test cockpit.js contains layout1Scale, ResizeObserver, logo hold state, and dynamic joystick radius scaling
        resp_js = await server._handle_http_request(None, MockRequest("/js/cockpit.js"))
        assert resp_js.status_code == 200
        js = resp_js.body.decode("utf-8")
        assert "this.layout1Scale" in js
        assert "scale1 = Math.max(0.1, Math.min(availW / 907, availH / 400))" in js
        assert "ResizeObserver" in js
        assert "baseRadius * scale" in js
        assert "visualViewport" in js
        assert "_logoHoldState" in js

    asyncio.run(_test())


def test_gateway_rumble_websocket_delivery():
    async def _async_test():
        test_port = 8115
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
                # 1. Handshake
                challenge_raw = await ws.recv()
                challenge = json.loads(challenge_raw)
                nonce = challenge["nonce"]
                ts = challenge["timestamp"]

                payload = f"{nonce}:{ts}".encode("utf-8")
                sig = hmac.new(settings.security.HMAC_SHARED_SECRET, payload, hashlib.sha256).hexdigest()

                await ws.send(json.dumps({
                    "type": "AUTH_RESPONSE",
                    "client_id": "rumble_test_client",
                    "nonce": nonce,
                    "timestamp": ts,
                    "signature": sig
                }))

                auth_raw = await ws.recv()
                auth = json.loads(auth_raw)
                assert auth["type"] == "AUTH_SUCCESS"

                async def recv_rumble():
                    for _ in range(10):
                        raw = await asyncio.wait_for(ws.recv(), timeout=2.0)
                        m = json.loads(raw)
                        if m.get("type") == "RUMBLE":
                            return m
                    raise TimeoutError("No RUMBLE packet received")

                # 2. Trigger direct rumble on slot 0
                server._on_rumble_event(0, 200, 150)
                msg = await recv_rumble()
                assert msg["type"] == "RUMBLE"
                assert msg["large"] == 200
                assert msg["small"] == 150

                # 3. Fallback routing: event on slot 1 with only 1 client connected
                server._on_rumble_event(1, 120, 80)
                msg2 = await recv_rumble()
                assert msg2["type"] == "RUMBLE"
                assert msg2["large"] == 120
                assert msg2["small"] == 80
        finally:
            await server.stop()

    asyncio.run(_async_test())


def test_terminal_mode_and_command_handling():
    import terminal_main
    terminal_main.setup_console()

    async def _term_test():
        server = ControllerGatewayServer(
            use_ssl=False,
            port=8119,
            enable_simulator=False,
            force_mock_input=True
        )
        await server.start()
        cmd_queue = asyncio.Queue()

        task = asyncio.create_task(terminal_main.handle_terminal_commands(server, cmd_queue))

        try:
            # Test pulse command
            await cmd_queue.put("pulse")
            await asyncio.sleep(0.05)

            # Test test rumble command
            await cmd_queue.put("test")
            await asyncio.sleep(0.05)

            # Test swap slots command
            await cmd_queue.put("swap")
            await asyncio.sleep(0.05)

            # Test status command
            await cmd_queue.put("status")
            await asyncio.sleep(0.05)

            # Test exit command
            await cmd_queue.put("quit")
            await asyncio.wait_for(task, timeout=2.0)
        finally:
            await server.stop()

    asyncio.run(_term_test())


def test_early_binary_frame_during_handshake_resilience():
    """Verify that early binary micro-packets sent before handshake completes do not crash the server with UTF-8 decode error."""
    async def _resilience_test():
        test_port = 8121
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
                # 1. Expect AUTH_CHALLENGE
                challenge_raw = await ws.recv()
                challenge = json.loads(challenge_raw)
                assert challenge["type"] == "AUTH_CHALLENGE"
                nonce = challenge["nonce"]
                ts = challenge["timestamp"]

                # 2. Simulate client prematurely blasting binary packets before auth
                # Starting with 0x43, 0x02, and non-UTF8 byte 0x97 (exactly like reported error)
                bad_binary = bytearray(24)
                bad_binary[0] = 0x43
                bad_binary[1] = 0x02
                bad_binary[2] = 0x97
                bad_binary[3] = 0x00
                await ws.send(bytes(bad_binary))

                # Also send non-auth JSON frame
                await ws.send(json.dumps({"type": "PING", "ts": 12345}))

                # 3. Now send valid AUTH_RESPONSE
                payload = f"{nonce}:{ts}".encode("utf-8")
                sig = hmac.new(settings.security.HMAC_SHARED_SECRET, payload, hashlib.sha256).hexdigest()
                await ws.send(json.dumps({
                    "type": "AUTH_RESPONSE",
                    "client_id": "resilience_test_client",
                    "nonce": nonce,
                    "timestamp": ts,
                    "signature": sig
                }))

                # 4. Expect AUTH_SUCCESS without server crashing
                auth_raw = await ws.recv()
                auth = json.loads(auth_raw)
                assert auth["type"] == "AUTH_SUCCESS"
                assert auth["client_id"] == "resilience_test_client"
        finally:
            await server.stop()

    asyncio.run(_resilience_test())


def test_reconnect_superseded_socket_does_not_release_slot():
    """Verify that when a client reconnects, closing the older superseded socket does not release the client's slot."""
    async def _reconnect_test():
        test_port = 8122
        server = ControllerGatewayServer(
            use_ssl=False,
            port=test_port,
            enable_simulator=False,
            force_mock_input=True
        )
        await server.start()

        try:
            url = f"ws://127.0.0.1:{test_port}/ws"
            client_id = "persistent_reconnect_client"

            # Helper for challenge-response auth
            async def _auth(ws):
                ch_raw = await ws.recv()
                ch = json.loads(ch_raw)
                nonce, ts = ch["nonce"], ch["timestamp"]
                payload = f"{nonce}:{ts}".encode("utf-8")
                sig = hmac.new(settings.security.HMAC_SHARED_SECRET, payload, hashlib.sha256).hexdigest()
                await ws.send(json.dumps({
                    "type": "AUTH_RESPONSE",
                    "client_id": client_id,
                    "nonce": nonce,
                    "timestamp": ts,
                    "signature": sig
                }))
                suc_raw = await ws.recv()
                return json.loads(suc_raw)

            # Socket 1 connects and authenticates
            ws1 = await websockets.connect(url)
            suc1 = await _auth(ws1)
            assert suc1["type"] == "AUTH_SUCCESS"
            assert server.input_manager.get_slot(client_id) == 0

            # Socket 2 connects before socket 1 closes (common during fast reconnect / Wi-Fi blips)
            ws2 = await websockets.connect(url)
            suc2 = await _auth(ws2)
            assert suc2["type"] == "AUTH_SUCCESS"
            assert server.input_manager.get_slot(client_id) == 0

            # Now socket 1 closes
            await ws1.close()
            await asyncio.sleep(0.05)

            # Client MUST still own Slot 0 through ws2!
            assert server.input_manager.get_slot(client_id) == 0

            # ws2 sends input successfully
            await ws2.send(json.dumps({
                "type": "INPUT",
                "seq": 1,
                "ts": time.time(),
                "stick_x": 15000,
                "stick_y": 0,
                "throttle": 1.0,
                "brake": 0.0,
                "buttons": {}
            }))
            await asyncio.sleep(0.05)

            # Virtual gamepad should have received stick_x=15000
            ctrl = server.input_manager.controllers[0]
            assert ctrl.steering == 15000

            await ws2.close()
        finally:
            await server.stop()

    asyncio.run(_reconnect_test())


def test_multi_client_live_slot_switching_and_no_donations():
    """Verify multi-client live SWITCH_SLOT, PC swap_player_slots across P1-P4, vibration default OFF, and zero donation references."""
    import pathlib

    # 1. Verify zero donation references in dashboard.py
    dash_text = pathlib.Path("gui/dashboard.py").read_text(encoding="utf-8")
    assert "buymeacoffee" not in dash_text.lower()
    assert "btn_donate" not in dash_text
    assert "btn_coffee" not in dash_text
    assert "btn_swap_23" in dash_text

    # 2. Verify vibration default OFF in haptics.js and cockpit.js
    haptics_text = pathlib.Path("client/js/haptics.js").read_text(encoding="utf-8")
    assert "this.vibrationEnabled = false;" in haptics_text
    cockpit_text = pathlib.Path("client/js/cockpit.js").read_text(encoding="utf-8")
    assert "this.haptics.setVibrationEnabled(false);" in cockpit_text
    assert '"SWITCH_SLOT"' in cockpit_text

    async def _multi_switch_test():
        from gui.state_bridge import TelemetryBridge
        bridge = TelemetryBridge()
        test_port = 8126
        server = ControllerGatewayServer(
            bridge=bridge,
            use_ssl=False,
            port=test_port,
            enable_simulator=False,
            force_mock_input=True
        )
        await server.start()

        try:
            url = f"ws://127.0.0.1:{test_port}/ws"

            async def _auth_client(ws, cid):
                ch = json.loads(await ws.recv())
                nonce, ts = ch["nonce"], ch["timestamp"]
                payload = f"{nonce}:{ts}".encode("utf-8")
                sig = hmac.new(settings.security.HMAC_SHARED_SECRET, payload, hashlib.sha256).hexdigest()
                await ws.send(json.dumps({
                    "type": "AUTH_RESPONSE",
                    "client_id": cid,
                    "nonce": nonce,
                    "timestamp": ts,
                    "signature": sig
                }))
                return json.loads(await ws.recv())

            async def _recv_slot_reassigned(ws):
                for _ in range(10):
                    raw = await asyncio.wait_for(ws.recv(), timeout=2.0)
                    msg = json.loads(raw)
                    if msg.get("type") == "SLOT_REASSIGNED":
                        return msg["player_slot"]
                raise TimeoutError("Did not receive SLOT_REASSIGNED")

            ws_a = await websockets.connect(url)
            ws_b = await websockets.connect(url)

            auth_a = await _auth_client(ws_a, "phone_alpha")
            auth_b = await _auth_client(ws_b, "phone_beta")

            assert auth_a["player_slot"] == 1
            assert auth_b["player_slot"] == 2
            assert server.input_manager.get_slot("phone_alpha") == 0
            assert server.input_manager.get_slot("phone_beta") == 1

            # Phone Alpha taps P2 in Settings while Phone Beta is on P2 -> atomic swap!
            await ws_a.send(json.dumps({"type": "SWITCH_SLOT", "slot": 2}))
            new_slot_a = await _recv_slot_reassigned(ws_a)
            new_slot_b = await _recv_slot_reassigned(ws_b)

            assert new_slot_a == 2
            assert new_slot_b == 1
            assert server.input_manager.get_slot("phone_alpha") == 1
            assert server.input_manager.get_slot("phone_beta") == 0
            assert bridge.slots[0].client_id == "phone_beta"
            assert bridge.slots[1].client_id == "phone_alpha"

            # Phone Alpha taps P4 (unoccupied slot) in Settings -> moves directly to P4!
            await ws_a.send(json.dumps({"type": "SWITCH_SLOT", "slot": 4}))
            new_slot_a_4 = await _recv_slot_reassigned(ws_a)
            assert new_slot_a_4 == 4
            assert server.input_manager.get_slot("phone_alpha") == 3
            assert bridge.slots[3].client_id == "phone_alpha"
            assert bridge.slots[1].connected is False

            # PC Dashboard swaps Slot 0 (P1) and Slot 3 (P4)
            server.swap_player_slots(0, 3)
            re_b = await _recv_slot_reassigned(ws_b)
            re_a = await _recv_slot_reassigned(ws_a)
            assert re_b == 4
            assert re_a == 1
            assert server.input_manager.get_slot("phone_alpha") == 0
            assert server.input_manager.get_slot("phone_beta") == 3
            assert bridge.slots[0].client_id == "phone_alpha"
            assert bridge.slots[3].client_id == "phone_beta"

            await ws_a.close()
            await ws_b.close()
        finally:
            await server.stop()

    asyncio.run(_multi_switch_test())


def test_anti_bufferbloat_and_low_latency_burst_resilience():
    """Verify anti-bufferbloat client guards, adaptive pump, O(1) deque firewall, and low-jitter burst handling."""
    import time
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    cockpit_js = (root / "client" / "js" / "cockpit.js").read_text(encoding="utf-8")

    # 1. Verify client anti-bufferbloat & adaptive rate control in cockpit.js
    assert "this.ws.bufferedAmount > 256" in cockpit_js
    assert "_isInputActiveOrChanged()" in cockpit_js
    assert "_rttSamples" in cockpit_js
    assert "this.ws.bufferedAmount <= 128" in cockpit_js

    # 2. Verify AnomalyFirewall uses O(1) deque and accepts Wi-Fi A-MPDU bursts
    from collections import deque
    from gateway.security import AnomalyFirewall
    from gateway.kernel_transport import BINARY_STRUCT, BINARY_PACKET_MAGIC, BINARY_PACKET_VERSION

    fw = AnomalyFirewall()
    for seq in range(1, 51):
        accepted, reason = fw.inspect_packet("burst_client", seq, 1000.0 + seq * 0.0001)
        assert accepted is True, f"Burst packet {seq} was dropped: {reason}"
    assert isinstance(fw.packet_count_window["burst_client"], deque)

    # 3. Verify live server handles 50-packet A-MPDU burst + PING with zero disconnects & zero idle TELEMETRY spam
    async def _burst_test():
        from gui.state_bridge import TelemetryBridge
        test_port = 8127
        bridge = TelemetryBridge()
        server = ControllerGatewayServer(
            use_ssl=False,
            port=test_port,
            enable_simulator=False,
            force_mock_input=True,
            bridge=bridge,
        )
        await server.start()
        try:
            url = f"ws://127.0.0.1:{test_port}/ws"
            async with websockets.connect(url) as ws:
                ch = json.loads(await ws.recv())
                nonce, ts = ch["nonce"], ch["timestamp"]
                payload = f"{nonce}:{ts}".encode("utf-8")
                sig = hmac.new(settings.security.HMAC_SHARED_SECRET, payload, hashlib.sha256).hexdigest()
                await ws.send(json.dumps({
                    "type": "AUTH_RESPONSE",
                    "client_id": "burst_phone",
                    "nonce": nonce,
                    "timestamp": ts,
                    "signature": sig,
                    "preferred_slot": 1,
                }))
                auth = json.loads(await ws.recv())
                assert auth["type"] == "AUTH_SUCCESS"

                # Blast 50 binary packets in an instantaneous burst + PING
                for seq in range(1, 51):
                    pkt = BINARY_STRUCT.pack(
                        BINARY_PACKET_MAGIC,
                        BINARY_PACKET_VERSION,
                        seq,
                        seq * 2,
                        12000, -8000, 0, 0,
                        200, 0, 1,
                        0, 0, 5
                    )
                    await ws.send(pkt)

                t0 = time.perf_counter() * 1000.0
                await ws.send(json.dumps({"type": "PING", "ts": t0}))
                pong_raw = await asyncio.wait_for(ws.recv(), timeout=1.0)
                pong = json.loads(pong_raw)
                assert pong["type"] == "PONG"
                rtt_ms = (time.perf_counter() * 1000.0) - float(pong["ts"])
                assert rtt_ms < 50.0
        finally:
            await server.stop()

    asyncio.run(_burst_test())

