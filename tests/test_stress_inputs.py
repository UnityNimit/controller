"""
Exhaustive Stress Test Suite (100+ iterations each)
Tests:
1. 100 rapid press/release cycles on LT & RT verifying strict zero release (no floating/stuck values).
2. 100 left stick flick/neutral cycles verifying instant discrete snap to (0, 0) without ghost drift.
3. 100 random multi-touch button combinations verifying absolute isolation and zero crosstalk.
4. 100 rapid packets through Security RateLimiter at 1000Hz verifying zero unconstrained drops.
"""

import random
import pytest
from gateway.filters import SensorFusionPipeline
from gateway.input_manager import InputManager, MockGamepad
from gateway.security import AnomalyFirewall
from config import settings


def test_100_cycles_trigger_press_release_strict_zero():
    """
    Stress test: 100 rapid press/release cycles on LT & RT.
    Verifies triggers ALWAYS drop strictly to 0 (never lingering fractional floats or stuck bytes).
    """
    pipeline = SensorFusionPipeline()
    mgr = InputManager(force_mock=True, max_players=2)
    client_id = "stress_trigger_node"
    slot = mgr.allocate_slot(client_id)
    assert slot == 0
    ctrl: MockGamepad = mgr.controllers[0]

    for cycle in range(100):
        # 1. Press RT (throttle = 1.0)
        th_byte, br_byte = pipeline.process_triggers(1.0, 0.0)
        assert th_byte == 255
        assert br_byte == 0
        mgr.dispatch(client_id, {
            "stick_x": 0, "stick_y": 0,
            "throttle": th_byte, "brake": br_byte,
            "buttons": {}
        })
        assert ctrl.throttle == 255
        assert ctrl.brake == 0

        # 2. Release RT (throttle = 0.0)
        th_byte, br_byte = pipeline.process_triggers(0.0, 0.0)
        assert th_byte == 0, f"Cycle {cycle}: throttle byte failed to reach strict 0"
        assert br_byte == 0
        mgr.dispatch(client_id, {
            "stick_x": 0, "stick_y": 0,
            "throttle": th_byte, "brake": br_byte,
            "buttons": {}
        })
        assert ctrl.throttle == 0, f"Cycle {cycle}: gamepad throttle failed to release to 0"
        assert ctrl.brake == 0

        # 3. Press LT (brake = 1.0)
        th_byte, br_byte = pipeline.process_triggers(0.0, 1.0)
        assert th_byte == 0
        assert br_byte == 255
        mgr.dispatch(client_id, {
            "stick_x": 0, "stick_y": 0,
            "throttle": th_byte, "brake": br_byte,
            "buttons": {}
        })
        assert ctrl.throttle == 0
        assert ctrl.brake == 255

        # 4. Release LT (brake = 0.0)
        th_byte, br_byte = pipeline.process_triggers(0.0, 0.0)
        assert th_byte == 0
        assert br_byte == 0, f"Cycle {cycle}: brake byte failed to reach strict 0"
        mgr.dispatch(client_id, {
            "stick_x": 0, "stick_y": 0,
            "throttle": th_byte, "brake": br_byte,
            "buttons": {}
        })
        assert ctrl.throttle == 0
        assert ctrl.brake == 0, f"Cycle {cycle}: gamepad brake failed to release to 0"

        # 5. Dual Hair-trigger press and release
        th_byte, br_byte = pipeline.process_triggers(1.0, 1.0)
        assert th_byte == 255 and br_byte == 255
        th_byte, br_byte = pipeline.process_triggers(0.0, 0.0)
        assert th_byte == 0 and br_byte == 0


def test_100_cycles_left_stick_flicks_and_deadband_snapping():
    """
    Stress test: 100 rapid flick cycles in all 4 cardinal directions and diagonals.
    Verifies immediate snap to (0, 0) on release without trailing hold or menu skip.
    """
    mgr = InputManager(force_mock=True, max_players=2)
    client_id = "stress_stick_node"
    mgr.allocate_slot(client_id)
    ctrl: MockGamepad = mgr.controllers[0]

    flick_vectors = [
        (0, 32767),     # UP
        (0, -32768),    # DOWN
        (-32768, 0),    # LEFT
        (32767, 0),     # RIGHT
        (300, 32767),   # UP with slight horizontal finger wobble (under 1200 noise floor)
        (-32768, -450), # LEFT with slight vertical wobble
    ]

    for cycle in range(100):
        fx, fy = random.choice(flick_vectors)

        # Dispatch flick impulse
        mgr.dispatch(client_id, {
            "stick_x": fx, "stick_y": fy,
            "throttle": 0, "brake": 0,
            "buttons": {}
        })
        assert ctrl.steering == fx
        assert ctrl.left_stick_y == fy

        # Dispatch instant release / neutral packet (from the 75ms discrete impulse engine)
        mgr.dispatch(client_id, {
            "stick_x": 0, "stick_y": 0,
            "throttle": 0, "brake": 0,
            "buttons": {}
        })
        assert ctrl.steering == 0, f"Cycle {cycle}: Left stick X failed to return to 0"
        assert ctrl.left_stick_y == 0, f"Cycle {cycle}: Left stick Y failed to return to 0"


def test_100_random_multi_touch_crosstalk_isolation():
    """
    Stress test: 100 randomized multi-touch button combinations.
    Verifies that button presses and trigger pulls do not leak across channels.
    """
    all_buttons = [
        "A", "B", "X", "Y", "LB", "RB",
        "START", "BACK", "UP", "DOWN", "LEFT", "RIGHT",
        "THUMB_L", "THUMB_R"
    ]
    mgr = InputManager(force_mock=True, max_players=2)
    client_id = "stress_multitouch_node"
    mgr.allocate_slot(client_id)
    ctrl: MockGamepad = mgr.controllers[0]

    for cycle in range(100):
        # Pick 1 to 5 random buttons to press simultaneously
        num_pressed = random.randint(1, 5)
        pressed_buttons = set(random.sample(all_buttons, num_pressed))

        button_dict = {btn: (btn in pressed_buttons) for btn in all_buttons}
        rand_th = 255 if ("RB" in pressed_buttons or random.random() > 0.5) else 0
        rand_br = 255 if ("LB" in pressed_buttons or random.random() > 0.5) else 0
        rand_sx = random.randint(-32768, 32767)

        mgr.dispatch(client_id, {
            "stick_x": rand_sx, "stick_y": 0,
            "throttle": rand_th, "brake": rand_br,
            "buttons": button_dict
        })

        # Verify exact button isolation
        for btn in all_buttons:
            expected = btn in pressed_buttons
            actual = ctrl.buttons.get(btn, False)
            assert actual == expected, (
                f"Cycle {cycle}: Crosstalk detected on {btn}! Expected {expected}, got {actual}. "
                f"Active buttons: {pressed_buttons}"
            )

        # Release all buttons and triggers
        release_dict = {btn: False for btn in all_buttons}
        mgr.dispatch(client_id, {
            "stick_x": 0, "stick_y": 0,
            "throttle": 0, "brake": 0,
            "buttons": release_dict
        })

        # Verify all buttons released cleanly
        for btn in all_buttons:
            assert ctrl.buttons.get(btn, False) is False, f"Cycle {cycle}: Button {btn} stuck True on release"
        assert ctrl.throttle == 0
        assert ctrl.brake == 0


def test_100_packets_rate_limiter_1000hz():
    """
    Stress test: 100 consecutive packets arriving at ultra high rate.
    Verifies that AnomalyFirewall supports unconstrained 1000Hz peak telemetry
    and that safety zero-resets bypass timing constraints.
    """
    import time
    firewall = AnomalyFirewall(
        max_rate_hz=settings.security.MAX_PACKET_RATE_HZ,
        min_inter_arrival_sec=settings.security.MIN_INTER_ARRIVAL_SEC
    )

    client = "speed_gamer_node"

    # 1. 100 ultra-fast uplink packets (> 0.1ms inter-arrival)
    for i in range(100):
        time.sleep(0.0002)
        accepted, reason = firewall.inspect_packet(client, seq=i + 1, client_time=100.0 + i * 0.001)
        assert accepted is True, f"Firewall dropped packet {i}: {reason}"

    # 2. 50 back-to-back zero-reset packets with 0 delay (redundant burst)
    for i in range(100, 150):
        accepted, reason = firewall.inspect_packet(client, seq=i + 1, client_time=100.0 + i * 0.001, is_neutral=True)
        assert accepted is True, f"Neutral packet {i} failed to bypass: {reason}"


def test_simultaneous_joystick_and_all_buttons_concurrency():
    """
    Verifies that simultaneous full deflection on Left Stick and Right Stick
    can be held while all other buttons (RT, LT, A, B, X, Y, RB, LB) are actively
    pressed and released, with zero disruption to the stick axes.
    """
    mgr = InputManager(force_mock=True, max_players=2)
    client_id = "stress_concurrent_node"
    mgr.allocate_slot(client_id)
    ctrl: MockGamepad = mgr.controllers[0]

    # Hold stick continuously deflected
    held_stick_x = 24500
    held_stick_y = -18000
    held_right_x = 15000
    held_right_y = 12000

    face_buttons = ["A", "B", "X", "Y", "LB", "RB"]

    for cycle in range(100):
        # Finger 1 & Finger 2 hold sticks. Finger 3 presses RT. Finger 4 presses face button.
        active_btn = face_buttons[cycle % len(face_buttons)]
        btn_map = {b: (b == active_btn) for b in face_buttons}

        mgr.dispatch(client_id, {
            "stick_x": held_stick_x,
            "stick_y": held_stick_y,
            "right_stick_x": held_right_x,
            "right_stick_y": held_right_y,
            "throttle": 255,
            "brake": 0,
            "buttons": btn_map
        })

        # Stick MUST retain exact deflected values
        assert ctrl.steering == held_stick_x
        assert ctrl.left_stick_y == held_stick_y
        assert ctrl.right_stick_x == held_right_x
        assert ctrl.right_stick_y == held_right_y
        assert ctrl.throttle == 255
        assert ctrl.buttons[active_btn] is True

        # Now release the face button while STILL holding the stick
        btn_map[active_btn] = False
        mgr.dispatch(client_id, {
            "stick_x": held_stick_x,
            "stick_y": held_stick_y,
            "right_stick_x": held_right_x,
            "right_stick_y": held_right_y,
            "throttle": 255,
            "brake": 0,
            "buttons": btn_map
        })

        # Stick STILL deflected, face button is released!
        assert ctrl.steering == held_stick_x
        assert ctrl.left_stick_y == held_stick_y
        assert ctrl.right_stick_x == held_right_x
        assert ctrl.right_stick_y == held_right_y
        assert ctrl.buttons[active_btn] is False

