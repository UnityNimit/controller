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


def test_independent_per_slot_dsp_and_rumble():
    bridge = TelemetryBridge(history_len=20)
    bridge.register_client(0, "p1_client", "192.168.1.10")
    bridge.register_client(1, "p2_client", "192.168.1.11")

    # Record angle telemetry only for Slot 0
    bridge.record_input(
        slot_index=0,
        client_id="p1_client",
        control_state={"stick_x": 0, "stick_y": 0, "steering_angle": 35.0, "filtered_angle": 32.5, "throttle": 0, "brake": 0},
        client_rtt=1.5,
        inter_arrival_ms=16.6
    )

    # Sample tick to advance history
    bridge.sample_tick()
    snap = bridge.get_snapshot()

    # Slot 0 has non-zero angle telemetry
    s0 = snap["slots"][0]
    assert s0["steering_angle"] == 35.0
    assert s0["raw_angle_wave"][-1][1] == 35.0
    assert s0["kalman_angle_wave"][-1][1] == 32.5

    # Slot 1 and Slot 2 must have 0.0 baseline, isolated from Slot 0
    s1 = snap["slots"][1]
    assert s1["steering_angle"] == 0.0
    assert s1["raw_angle_wave"][-1][1] == 0.0
    assert s1["kalman_angle_wave"][-1][1] == 0.0

    s2 = snap["slots"][2]
    assert s2["steering_angle"] == 0.0
    assert s2["raw_angle_wave"][-1][1] == 0.0
    assert s2["kalman_angle_wave"][-1][1] == 0.0

    # Test per-slot rumble
    bridge.record_rumble(0, 32768, 65535)
    bridge.record_rumble(1, 10000, 20000)

    snap = bridge.get_snapshot()
    assert snap["slots"][0]["large_motor_rumble"] == 32768
    assert snap["slots"][0]["small_motor_rumble"] == 65535
    assert snap["slots"][1]["large_motor_rumble"] == 10000
    assert snap["slots"][1]["small_motor_rumble"] == 20000

    # Test slot swap between Slot 0 and Slot 1
    swapped = bridge.swap_slots(0, 1)
    assert swapped is True

    snap = bridge.get_snapshot()
    # Now Slot 0 has client "p2_client" and rumble 10000/20000
    assert snap["slots"][0]["client_id"] == "p2_client"
    assert snap["slots"][0]["large_motor_rumble"] == 10000
    # And Slot 1 has client "p1_client" and rumble 32768/65535
    assert snap["slots"][1]["client_id"] == "p1_client"
    assert snap["slots"][1]["large_motor_rumble"] == 32768


def test_setup_wizard_dialog_and_dark_title_bar():
    from gui.dashboard import SetupWizardDialog, TermsDialog, enable_dark_title_bar

    # Verify backward-compatibility alias
    assert TermsDialog is SetupWizardDialog

    # Test enable_dark_title_bar handles dummy object safely without crashing
    class DummyWindow:
        def update_idletasks(self):
            pass
        def winfo_id(self):
            return 0

    enable_dark_title_bar(DummyWindow())


def test_zero_copy_snapshot_performance():
    from collections import deque
    bridge = TelemetryBridge(history_len=30)
    bridge.register_client(0, "fast_node", "10.0.0.2")

    # get_snapshot should return deque objects directly for zero heap re-allocation
    snap = bridge.get_snapshot()
    assert isinstance(snap["latency_wave"], deque)
    assert isinstance(snap["slots"][0]["latency_wave"], deque)
    assert isinstance(snap["slots"][0]["stick_x_wave"], deque)


def test_vigem_rumble_registration_and_callback():
    from gateway.input_manager import ViGEmXInputGamepad, VIGEM_AVAILABLE
    if not VIGEM_AVAILABLE:
        return

    received = []
    def _cb(slot, large, small):
        received.append((slot, large, small))

    pad = ViGEmXInputGamepad(player_index=0, on_rumble=_cb)
    try:
        # Check that cmp_func is actively registered with ViGEmBus
        assert getattr(pad.gamepad, "cmp_func", None) is not None
        assert pad._notification_cb_ref is not None

        # Test notification callback execution
        pad._notification_cb_ref(None, None, 255, 128, 0, None)
        assert len(received) == 1
        assert received[0] == (0, 255, 128)
        assert pad.large_motor_rumble == 255
        assert pad.small_motor_rumble == 128
    finally:
        pad.close()


def test_gateway_rumble_event_relay():
    from gateway.server import ControllerGatewayServer
    from gui.state_bridge import TelemetryBridge

    bridge = TelemetryBridge()
    server = ControllerGatewayServer(force_mock_input=True, bridge=bridge)
    try:
        # Trigger rumble event on Slot 0
        server._on_rumble_event(0, 255, 180)

        # Verify bridge recorded the rumble
        snap = bridge.get_snapshot()
        assert snap["slots"][0]["large_motor_rumble"] == 255
        assert snap["slots"][0]["small_motor_rumble"] == 180
        assert snap["large_motor_rumble"] == 255
        assert snap["small_motor_rumble"] == 180
    finally:
        server.telemetry_receiver.stop()
