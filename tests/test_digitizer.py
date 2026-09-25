"""
Project Controller - Unit & Integration Tests for Pillar 3 (Mobile Touch Digitizer & High-Rate Ticker)
"""

import asyncio
import os
from pathlib import Path
import pytest
from gateway.server import ControllerGatewayServer
from config import settings


def test_digitizer_static_serving_and_cache_control():
    """Verify digitizer.js and high_rate_ticker.js are served over HTTP with zero-cache headers."""
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

        # 1. Test digitizer.js
        resp_dig = await server._handle_http_request(None, MockRequest("/js/digitizer.js"))
        assert resp_dig.status_code == 200
        assert b"TouchDigitizerEngine" in resp_dig.body
        assert b"pointerrawupdate" in resp_dig.body
        assert b"getCoalescedEvents" in resp_dig.body
        assert "no-store" in resp_dig.headers.get("Cache-Control", "")

        # 2. Test high_rate_ticker.js
        resp_tick = await server._handle_http_request(None, MockRequest("/js/high_rate_ticker.js"))
        assert resp_tick.status_code == 200
        assert b"HighRateWorkerTicker" in resp_tick.body
        assert b"Worker" in resp_tick.body
        assert "no-store" in resp_tick.headers.get("Cache-Control", "")

    asyncio.run(_test())


def test_index_html_includes_pillar3_scripts_in_order():
    """Ensure index.html loads digitizer and worker ticker before cockpit.js."""
    index_path = Path("client/index.html")
    assert index_path.exists()

    content = index_path.read_text(encoding="utf-8")
    assert "js/high_rate_ticker.js" in content
    assert "js/digitizer.js" in content
    assert "js/cockpit.js" in content

    idx_tick = content.find("js/high_rate_ticker.js")
    idx_dig = content.find("js/digitizer.js")
    idx_cockpit = content.find("js/cockpit.js")

    assert idx_tick < idx_cockpit, "high_rate_ticker.js must load before cockpit.js"
    assert idx_dig < idx_cockpit, "digitizer.js must load before cockpit.js"


def test_digitizer_js_syntax_and_structure():
    """Verify JavaScript modules are well-formed and contain essential methods."""
    dig_path = Path("client/js/digitizer.js")
    tick_path = Path("client/js/high_rate_ticker.js")

    dig_content = dig_path.read_text(encoding="utf-8")
    assert "class TouchDigitizerEngine" in dig_content
    assert "pointerrawupdate" in dig_content
    assert "_handleRawUpdate" in dig_content
    assert "_extractAndDispatch" in dig_content
    assert "preventDefault" in dig_content

    tick_content = tick_path.read_text(encoding="utf-8")
    assert "class HighRateWorkerTicker" in tick_content
    assert "_initWorker" in tick_content
    assert "start()" in tick_content
    assert "stop()" in tick_content
    assert "setIntervalMs" in tick_content


def test_high_frequency_burst_ingestion_into_gateway():
    """Simulate high-frequency (500 Hz) touch digitizer packets arriving at the server."""
    from gateway.input_manager import InputManager
    from gateway.mcu_dispatch import VirtualMcuDispatcher

    input_mgr = InputManager(force_mock=True)
    mcu = VirtualMcuDispatcher(controllers=input_mgr.controllers, target_hz=1000.0)
    mcu.start()
    input_mgr.mcu_dispatcher = mcu

    # Allocate player 1
    slot = input_mgr.allocate_slot("client_digitizer_test")
    assert slot == 0

    # Simulate 50 packets arriving at 2ms intervals (500 Hz)
    for seq in range(50):
        packet = {
            "stick_x": int(seq * 500),
            "stick_y": int(-seq * 400),
            "right_stick_x": 0,
            "right_stick_y": 0,
            "throttle": 0,
            "brake": 0,
            "buttons": {"A": True}
        }
        input_mgr.dispatch("client_digitizer_test", packet, timestamp=1000.0 + (seq * 0.002))

    # Verify slot latch is updated and contains active button state
    latch = mcu.latches[0]
    assert latch is not None
    assert latch.buttons["A"] is True
    assert latch.stick_x == 49 * 500
    assert latch.stick_y == -49 * 400

    # Allow MCU thread to dispatch to virtual controller
    import time
    time.sleep(0.02)
    ctrl = input_mgr.controllers[0]
    assert ctrl.buttons.get("A") is True

    mcu.stop()
    input_mgr.release_slot("client_digitizer_test")
