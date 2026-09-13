"""
Unit and Integration tests for Input Pipeline, Slot Manager, and QoS Recorder
"""

import pytest
from pathlib import Path
from gateway.input_manager import InputManager, MockGamepad
from gateway.qos_recorder import QoSRecorder


def test_input_slot_allocation():
    # Force mock controllers for CI / unit tests
    mgr = InputManager(force_mock=True, max_players=4)

    # Allocate Player 1
    s0 = mgr.allocate_slot("client_alpha")
    assert s0 == 0
    assert mgr.get_slot("client_alpha") == 0

    # Allocate Player 2
    s1 = mgr.allocate_slot("client_beta")
    assert s1 == 1

    # Re-allocation for same client returns existing slot
    assert mgr.allocate_slot("client_alpha") == 0

    # Fill slots 3 and 4
    s2 = mgr.allocate_slot("client_gamma")
    s3 = mgr.allocate_slot("client_delta")
    assert s2 == 2
    assert s3 == 3

    # Attempting 5th client when full
    s4 = mgr.allocate_slot("client_epsilon")
    assert s4 is None

    # Release client_beta (slot 1)
    mgr.release_slot("client_beta")
    assert mgr.get_slot("client_beta") is None

    # Now new client takes slot 1
    s_new = mgr.allocate_slot("client_epsilon")
    assert s_new == 1


def test_input_slot_swapping_and_persistent_leasing():
    mgr = InputManager(force_mock=True, max_players=4)

    # Allocate P1 and P2
    p1 = mgr.allocate_slot("client_p1")
    p2 = mgr.allocate_slot("client_p2")
    assert p1 == 0 and p2 == 1

    # Send stick values to both
    mgr.dispatch("client_p1", {"stick_x": 10000, "stick_y": 0, "throttle": 0, "brake": 0, "buttons": {}})
    mgr.dispatch("client_p2", {"stick_x": -10000, "stick_y": 0, "throttle": 0, "brake": 0, "buttons": {}})

    assert mgr.controllers[0].steering == 10000
    assert mgr.controllers[1].steering == -10000

    # Swap P1 and P2 slots atomically
    res = mgr.swap_slots(0, 1)
    assert res is not None
    client_a, client_b = res
    assert client_a == "client_p1" and client_b == "client_p2"

    # Now client_p1 is slot 1, client_p2 is slot 0
    assert mgr.get_slot("client_p1") == 1
    assert mgr.get_slot("client_p2") == 0

    # Disconnect client_p1 and reconnect with preferred_slot=1
    mgr.release_slot("client_p1")
    reconnected_slot = mgr.allocate_slot("client_p1", preferred_slot=1)
    assert reconnected_slot == 1


def test_input_watchdog_reset():
    import time
    mgr = InputManager(force_mock=True, max_players=2)
    mgr.allocate_slot("client_afk")

    # Client pushed stick and then froze/dropped connection without releasing
    mgr.dispatch("client_afk", {"stick_x": 20000, "stick_y": 15000, "throttle": 200, "brake": 0, "buttons": {}})
    assert mgr.controllers[0].steering == 20000
    assert mgr.controllers[0].throttle == 200

    # Sleep past watchdog threshold
    time.sleep(0.06)
    mgr.tick_watchdog(timeout_sec=0.04)

    # Controller should have been reset to neutral automatically!
    assert mgr.controllers[0].steering == 0
    assert mgr.controllers[0].throttle == 0


def test_input_dispatch_to_mock_gamepad():
    mgr = InputManager(force_mock=True, max_players=2)
    mgr.allocate_slot("client_1")

    state = {
        "stick_x": 16384,
        "throttle": 220,
        "brake": 0,
        "buttons": {"HANDBRAKE": True, "SHIFT_UP": True}
    }
    dispatched = mgr.dispatch("client_1", state)
    assert dispatched is True

    ctrl: MockGamepad = mgr.controllers[0]
    assert ctrl.steering == 16384
    assert ctrl.throttle == 220
    assert ctrl.brake == 0
    assert ctrl.buttons["HANDBRAKE"] is True
    assert ctrl.buttons["SHIFT_UP"] is True
    assert ctrl.update_count > 0


def test_qos_recorder_and_export(tmp_path: Path):
    recorder = QoSRecorder(capacity=100)

    for i in range(25):
        recorder.record_uplink(
            client_id="test_node",
            seq=i + 1,
            client_timestamp=1000.0 + i * 0.016,
            raw_steering=float(i),
            filtered_steering=float(i) * 0.9,
            throttle=128,
            brake=0,
            handbrake=False
        )

    metrics = recorder.get_summary_metrics()
    assert metrics["total_packets"] == 25
    assert metrics["effective_rate_hz"] > 0

    # Test CSV export
    csv_file = tmp_path / "qos_test.csv"
    exported = recorder.export_csv(csv_file)
    assert exported.exists()
    assert exported.stat().st_size > 0

    # Test Viva chart generation
    charts = recorder.export_viva_charts(tmp_path)
    assert len(charts) == 2
    for c in charts:
        assert c.exists()
        assert c.stat().st_size > 0


def test_first_client_always_player1_guarantee():
    mgr = InputManager(force_mock=True, max_players=4)

    # 1. First client connecting without preference ALWAYS gets Player 1 (Slot 0)
    assert mgr.allocate_slot("client_first") == 0

    # 2. Second client gets Player 2 (Slot 1)
    assert mgr.allocate_slot("client_second") == 1

    # 3. Disconnect Player 1 while Player 2 is still playing
    mgr.release_slot("client_first")
    assert mgr.slots[0] is None
    assert mgr.slots[1] == "client_second"

    # 4. Incoming new client immediately fills open Player 1 (Slot 0)
    assert mgr.allocate_slot("client_third") == 0

    # 5. Now disconnect all players (server becomes completely empty)
    mgr.release_slot("client_second")
    mgr.release_slot("client_third")
    assert all(s is None for s in mgr.slots)

    # 6. Even if a client connects with preferred_slot=3, when it is the first/only client,
    # it is GUARANTEED to connect as Player 1 (Slot 0)
    assert mgr.allocate_slot("client_solo_with_pref", preferred_slot=2) == 0

