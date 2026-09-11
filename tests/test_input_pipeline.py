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
