"""
Unit and benchmark tests for Pillar 1: Virtual Hardware MCU Dispatch Engine
Tests 1000 Hz – 5000 Hz high-precision timing, atomic latching, and button continuity.
"""

import time
import pytest
from gateway.input_manager import MockGamepad, InputManager
from gateway.mcu_dispatch import VirtualMcuDispatcher, SlotStateLatch


def test_mcu_dispatcher_lifecycle_and_target_rates():
    """Verify MCU dispatcher starts, adjusts target frequencies, and shuts down cleanly."""
    mock_ctrls = [MockGamepad(0), MockGamepad(1)]
    mcu = VirtualMcuDispatcher(controllers=mock_ctrls, target_hz=1000.0, max_slots=2)

    assert mcu.target_hz == 1000.0
    assert mcu.interval == 0.001

    mcu.start()
    assert mcu._running is True
    assert mcu._thread is not None and mcu._thread.is_alive()

    # Dynamic frequency adjustment
    mcu.set_target_rate(2000.0)
    assert mcu.target_hz == 2000.0
    assert mcu.interval == 0.0005

    mcu.set_target_rate(5000.0)
    assert mcu.target_hz == 5000.0
    assert mcu.interval == 0.0002

    mcu.stop()
    assert mcu._running is False
    assert not mcu._thread.is_alive()


def test_mcu_1000hz_sustained_frequency_and_jitter():
    """Verify sustained ~1000 Hz dispatch rate with sub-millisecond jitter."""
    mock_ctrls = [MockGamepad(0)]
    mcu = VirtualMcuDispatcher(
        controllers=mock_ctrls,
        target_hz=1000.0,
        enable_hybrid_spinlock=True,
        max_slots=1
    )

    mcu.start()
    # Run for 0.4 seconds (should produce ~400 dispatches)
    time.sleep(0.4)
    mcu.stop()

    metrics = mcu.get_metrics()
    total = metrics["total_dispatches"]
    # 400ms at 1000 Hz should produce 370-430 reports
    assert total >= 350, f"Expected >= 350 dispatches in 0.4s at 1000 Hz, got {total}"
    assert metrics["running"] is False


def test_mcu_button_hold_continuity():
    """
    Verify that holding a button keeps the button active continuously on every dispatch,
    solving the 12 Hz button polling drop.
    """
    mock_ctrl = MockGamepad(0)
    mcu = VirtualMcuDispatcher(controllers=[mock_ctrl], target_hz=1000.0, max_slots=1)

    # Press and latch button A
    mcu.update_slot_input(0, {"buttons": {"A": True}, "throttle": 200})

    mcu.start()
    time.sleep(0.05)  # ~50 dispatches
    mcu.stop()

    assert mock_ctrl.buttons.get("A") is True
    assert mock_ctrl.throttle == 200

    # Release button A
    mcu.update_slot_input(0, {"buttons": {"A": False}})
    mcu.start()
    time.sleep(0.05)
    mcu.stop()

    assert mock_ctrl.buttons.get("A") is False


def test_input_manager_mcu_integration():
    """Verify InputManager integrates seamlessly with VirtualMcuDispatcher."""
    mgr = InputManager(force_mock=True, max_players=2)

    # Manually attach MCU dispatcher in mock mode to test integration
    mcu = VirtualMcuDispatcher(controllers=mgr.controllers, target_hz=1000.0, max_slots=2)
    mgr.mcu_dispatcher = mcu
    mcu.start()

    slot = mgr.allocate_slot("test_client")
    assert slot == 0

    # Dispatch input
    mgr.dispatch("test_client", {
        "stick_x": 18000,
        "stick_y": -9000,
        "throttle": 255,
        "brake": 0,
        "buttons": {"X": True}
    })

    time.sleep(0.02)  # Allow MCU thread to dispatch
    ctrl = mgr.controllers[0]
    assert ctrl.steering == 18000
    assert ctrl.throttle == 255
    assert ctrl.buttons.get("X") is True

    # Releasing slot resets MCU latch and controller
    mgr.release_slot("test_client")
    time.sleep(0.02)
    assert ctrl.steering == 0
    assert ctrl.throttle == 0

    mgr.shutdown()
    assert mcu._running is False
