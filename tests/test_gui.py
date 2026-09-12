"""
Unit and Integration Tests for TelemetryBridge and GUI Components
"""

import time
import logging
from gui.state_bridge import TelemetryBridge, QueueLogHandler


def test_telemetry_bridge_slot_lifecycle():
    bridge = TelemetryBridge(history_len=50)

    # Initially all 4 slots empty
    snap = bridge.get_snapshot()
    assert len(snap["slots"]) == 4
    assert not any(s["connected"] for s in snap["slots"])

    # Register client to slot 0 (Player 1)
    bridge.register_client(0, "client_abc123", "192.168.1.50")
    snap = bridge.get_snapshot()
    assert snap["slots"][0]["connected"] is True
    assert snap["slots"][0]["client_id"] == "client_abc123"
    assert snap["slots"][0]["client_ip"] == "192.168.1.50"

    # Record input frame
    control_state = {
        "stick_x": 15000,
        "stick_y": -20000,
        "throttle": 220,
        "brake": 0,
        "buttons": {"A": True, "RB": True}
    }
    bridge.record_input(
        slot_index=0,
        client_id="client_abc123",
        control_state=control_state,
        client_rtt=2.4,
        inter_arrival_ms=16.6
    )

    snap = bridge.get_snapshot()
    slot0 = snap["slots"][0]
    assert slot0["stick_x"] == 15000
    assert slot0["stick_y"] == -20000
    assert slot0["throttle"] == 220
    assert slot0["buttons"]["A"] is True
    assert slot0["rtt_ms"] == 2.4

    # Check oscilloscope histories (continuously sweeping)
    assert len(snap["latency_wave"]) >= 1
    assert snap["latency_wave"][-1][1] == 2.4
    assert len(snap["stick_x_wave"]) >= 1
    assert snap["stick_x_wave"][-1][1] == 15000

    # Unregister client
    bridge.unregister_client(0, "client_abc123")
    snap = bridge.get_snapshot()
    assert snap["slots"][0]["connected"] is False


def test_queue_log_handler():
    bridge = TelemetryBridge()
    handler = QueueLogHandler(bridge.log_queue)
    logger = logging.getLogger("TestLogger")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    logger.info("Test telemetry log event")
    assert not bridge.log_queue.empty()
    item = bridge.log_queue.get_nowait()
    assert "Test telemetry log event" in item["message"]
    assert item["level"] == "INFO"


def test_right_stick_and_pulse_test():
    bridge = TelemetryBridge()
    bridge.register_client(1, "node_p2", "192.168.1.102")
    
    # Record right stick input
    bridge.record_input(
        slot_index=1,
        client_id="node_p2",
        control_state={"stick_x": 0, "stick_y": 0, "right_stick_x": 12345, "right_stick_y": -23456, "throttle": 0, "brake": 0},
        client_rtt=1.8,
        inter_arrival_ms=16.6
    )
    snap = bridge.get_snapshot()
    assert snap["slots"][1]["right_stick_x"] == 12345
    assert snap["slots"][1]["right_stick_y"] == -23456
    assert "right_stick_x_wave" in snap
    assert "right_stick_y_wave" in snap

    # Test pulse_test callback
    pulsed_slots = []
    bridge.pulse_test_callback = lambda slot: pulsed_slots.append(slot)
    bridge.pulse_test(1)
    assert pulsed_slots == [1]


def test_logo_and_terms_dialog_helpers(tmp_path, monkeypatch):
    from gui.dashboard import (
        get_logo_path,
        get_logo_ctk_image,
        should_show_terms_on_startup,
        save_terms_preference,
        COLOR_BG,
        COLOR_CARD,
        COLOR_WHITE
    )

    # 1. Verify monochrome palette definitions
    assert COLOR_BG == "#08090b"
    assert COLOR_CARD == "#0d1015"
    assert COLOR_WHITE == "#ffffff"

    # 2. Verify logo.png resolves and loads
    logo_p = get_logo_path()
    assert logo_p is not None
    assert logo_p.exists()
    assert logo_p.name == "logo.png"

    img = get_logo_ctk_image((32, 32))
    assert img is not None

    # 3. Test Terms preference persistence in isolated directory
    monkeypatch.chdir(tmp_path)
    # Default should show
    assert should_show_terms_on_startup() is True

    # Save preference dont_show=True
    save_terms_preference(dont_show=True)
    assert should_show_terms_on_startup() is False

    import json
    cfg = json.loads((tmp_path / ".controller_config.json").read_text(encoding="utf-8"))
    assert cfg.get("version") == "1.0.0"

    # Save preference dont_show=False
    save_terms_preference(dont_show=False)
    assert should_show_terms_on_startup() is True

    from config import settings
    assert settings.APP_NAME == "Controller"
    assert settings.APP_VERSION == "1.0.0"
