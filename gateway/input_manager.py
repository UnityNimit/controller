"""
Project Controller - OS-Level Input Emulation Driver & Multi-Client Slot Manager
Supports ViGEmBus Native Xbox 360 virtual controllers with graceful fallback to
Windows SendInput Keyboard/Mouse and Mock Testing backends.
"""

import logging
import platform
import ctypes
import time
from abc import ABC, abstractmethod
from typing import Dict, Optional, List, Any, Tuple

logger = logging.getLogger("Controller.Input")

# Detect ViGEmBus Driver Availability
VIGEM_AVAILABLE = False
try:
    if platform.system() == "Windows":
        import vgamepad as vg
        # Test creating and destroying a probe instance to verify kernel driver bus connection
        _probe = vg.VX360Gamepad()
        del _probe
        VIGEM_AVAILABLE = True
        logger.info("ViGEmBus kernel driver detected. Native XInput emulation ENABLED.")
except Exception as e:
    VIGEM_AVAILABLE = False
    logger.warning(
        f"ViGEmBus driver not active ({e}). Falling back to Keyboard emulation. "
        f"Click '⚡ INSTALL DRIVER' on the dashboard to enable native Xbox 360 controller emulation for all PC games."
    )


class AbstractGamepad(ABC):
    """Abstract interface for virtual game controllers."""
    @abstractmethod
    def set_steering(self, val: int) -> None:
        """val in [-32768, 32767]"""
        pass

    @abstractmethod
    def set_throttle(self, val: int) -> None:
        """val in [0, 255]"""
        pass

    @abstractmethod
    def set_brake(self, val: int) -> None:
        """val in [0, 255]"""
        pass

    def set_right_stick(self, x_val: int, y_val: int = 0) -> None:
        """val in [-32768, 32767]"""
        pass

    def set_stick(self, x_val: int, y_val: int = 0) -> None:
        """val in [-32768, 32767]"""
        pass

    @abstractmethod
    def set_button(self, button_name: str, pressed: bool) -> None:
        pass

    @abstractmethod
    def update(self) -> None:
        """Commits and sends hardware state to OS."""
        pass

    @abstractmethod
    def reset(self) -> None:
        """Restores neutral controller state."""
        pass

    @abstractmethod
    def close(self) -> None:
        pass


class ViGEmXInputGamepad(AbstractGamepad):
    """Native virtual Xbox 360 controller backed by ViGEmBus with force feedback rumble."""
    def __init__(self, player_index: int = 0, on_rumble=None):
        import vgamepad as vg
        self.vg = vg
        self.player_index = player_index
        self.on_rumble = on_rumble
        self.gamepad = vg.VX360Gamepad()
        
        self.button_map = {
            "A": vg.XUSB_BUTTON.XUSB_GAMEPAD_A,
            "B": vg.XUSB_BUTTON.XUSB_GAMEPAD_B,
            "X": vg.XUSB_BUTTON.XUSB_GAMEPAD_X,
            "Y": vg.XUSB_BUTTON.XUSB_GAMEPAD_Y,
            "LB": vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER,
            "RB": vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER,
            "START": vg.XUSB_BUTTON.XUSB_GAMEPAD_START,
            "BACK": vg.XUSB_BUTTON.XUSB_GAMEPAD_BACK,
            "LS": vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_THUMB,
            "RS": vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_THUMB,
            "DPAD_UP": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP,
            "DPAD_DOWN": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN,
            "DPAD_LEFT": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_LEFT,
            "DPAD_RIGHT": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_RIGHT,
        }
        self._register_rumble_cb()
        self.reset()
        logger.info(f"Initialized native ViGEmBus Virtual Xbox 360 controller for Player {player_index + 1}")

    def _register_rumble_cb(self) -> None:
        if self.on_rumble is not None:
            def _notification_cb(client, target, large_motor, small_motor, led_number, user_data):
                try:
                    if self.on_rumble is not None:
                        self.on_rumble(self.player_index, int(large_motor), int(small_motor))
                except Exception:
                    pass
            try:
                self.gamepad.register_notification(callback_function=_notification_cb)
            except Exception as e:
                logger.debug(f"Could not register rumble notification: {e}")

    def set_stick(self, x_val: int, y_val: int = 0) -> None:
        if x_val == 0 and y_val == 0:
            self.gamepad.left_joystick(x_value=0, y_value=0)
            return
        import math
        clamped_x = max(-32768, min(32767, int(x_val)))
        clamped_y = max(-32768, min(32767, int(y_val)))
        mag = math.hypot(clamped_x, clamped_y)
        noise_floor = 1200  # Minimal ~3.6% noise floor to prevent resting touch jitter
        if mag < noise_floor:
            final_x = 0
            final_y = 0
        else:
            scale = (mag - noise_floor) / (32767.0 - noise_floor)
            scale = min(1.0, max(0.0, scale))
            final_x = int((clamped_x / mag) * scale * 32767)
            final_y = int((clamped_y / mag) * scale * 32767)
        self.gamepad.left_joystick(x_value=final_x, y_value=final_y)

    def set_right_stick(self, x_val: int, y_val: int = 0) -> None:
        if x_val == 0 and y_val == 0:
            self.gamepad.right_joystick(x_value=0, y_value=0)
            return
        import math
        clamped_x = max(-32768, min(32767, int(x_val)))
        clamped_y = max(-32768, min(32767, int(y_val)))
        mag = math.hypot(clamped_x, clamped_y)
        noise_floor = 1200  # Minimal ~3.6% noise floor to prevent resting touch jitter
        if mag < noise_floor:
            final_x = 0
            final_y = 0
        else:
            scale = (mag - noise_floor) / (32767.0 - noise_floor)
            scale = min(1.0, max(0.0, scale))
            final_x = int((clamped_x / mag) * scale * 32767)
            final_y = int((clamped_y / mag) * scale * 32767)
        self.gamepad.right_joystick(x_value=final_x, y_value=final_y)

    def set_steering(self, val: int) -> None:
        self.set_stick(val, 0)

    def set_throttle(self, val: int) -> None:
        clamped = max(0, min(255, int(val)))
        self.gamepad.right_trigger(value=clamped)

    def set_brake(self, val: int) -> None:
        clamped = max(0, min(255, int(val)))
        self.gamepad.left_trigger(value=clamped)

    def set_button(self, button_name: str, pressed: bool) -> None:
        btn_key = button_name.upper()
        btn = self.button_map.get(btn_key)
        if btn is not None:
            if pressed:
                self.gamepad.press_button(button=btn)
            else:
                self.gamepad.release_button(button=btn)

    def update(self) -> None:
        self.gamepad.update()

    def reset(self) -> None:
        self.gamepad.reset()
        self.gamepad.update()

    def close(self) -> None:
        try:
            self.reset()
            del self.gamepad
        except Exception:
            pass


class KeyboardFallbackGamepad(AbstractGamepad):
    """
    Windows SendInput Keyboard Fallback for environments lacking the ViGEm kernel driver.
    Translates analog stick and triggers into standard racing keyboard controls (WASD / Space / Q / E).
    """
    VK_W = 0x57
    VK_A = 0x41
    VK_S = 0x53
    VK_D = 0x44
    VK_SPACE = 0x20
    VK_Q = 0x51
    VK_E = 0x45
    VK_H = 0x48

    def __init__(self, player_index: int = 0):
        self.player_index = player_index
        self.active_keys: set = set()
        logger.info(f"Initialized SendInput Keyboard Fallback controller for Player {player_index + 1}")

    def _send_key(self, vk: int, down: bool) -> None:
        if platform.system() != "Windows":
            return
        try:
            KEYEVENTF_KEYUP = 0x0002
            flags = 0 if down else KEYEVENTF_KEYUP
            ctypes.windll.user32.keybd_event(vk, 0, flags, 0)
        except Exception as e:
            logger.debug(f"Keyboard event error: {e}")

    def set_steering(self, val: int) -> None:
        # Threshold: +/- 25% steering input
        thresh = 8000
        if val < -thresh:
            self._press_key(self.VK_A)
            self._release_key(self.VK_D)
        elif val > thresh:
            self._press_key(self.VK_D)
            self._release_key(self.VK_A)
        else:
            self._release_key(self.VK_A)
            self._release_key(self.VK_D)

    def set_stick(self, x_val: int, y_val: int = 0) -> None:
        self.set_steering(x_val)

    def set_right_stick(self, x_val: int, y_val: int = 0) -> None:
        pass

    def set_throttle(self, val: int) -> None:
        if val > 40:
            self._press_key(self.VK_W)
        else:
            self._release_key(self.VK_W)

    def set_brake(self, val: int) -> None:
        if val > 40:
            self._press_key(self.VK_S)
        else:
            self._release_key(self.VK_S)

    def set_button(self, button_name: str, pressed: bool) -> None:
        btn_map = {
            "A": self.VK_SPACE,
            "B": 0xA0,          # VK_LSHIFT (Boost in Rocket League)
            "X": 0x58,          # 'X' (Powerslide / Air Roll)
            "Y": 0x46,          # 'F' (Ball Cam toggle in Rocket League)
            "RB": self.VK_E,
            "LB": self.VK_Q,
            "START": 0x1B,      # ESC
            "BACK": 0x09,       # TAB
        }
        vk = btn_map.get(button_name.upper())
        if vk:
            if pressed:
                self._press_key(vk)
            else:
                self._release_key(vk)

    def _press_key(self, vk: int) -> None:
        if vk not in self.active_keys:
            self.active_keys.add(vk)
            self._send_key(vk, True)

    def _release_key(self, vk: int) -> None:
        if vk in self.active_keys:
            self.active_keys.remove(vk)
            self._send_key(vk, False)

    def update(self) -> None:
        pass

    def reset(self) -> None:
        for vk in list(self.active_keys):
            self._send_key(vk, False)
        self.active_keys.clear()

    def close(self) -> None:
        self.reset()


class MockGamepad(AbstractGamepad):
    """In-memory telemetry mock controller for automated test suites and headless verification."""
    def __init__(self, player_index: int = 0):
        self.player_index = player_index
        self.steering: int = 0
        self.stick_y: int = 0
        self.throttle: int = 0
        self.brake: int = 0
        self.right_stick_x: int = 0
        self.right_stick_y: int = 0
        self.buttons: Dict[str, bool] = {}
        self.update_count: int = 0

    def set_steering(self, val: int) -> None:
        self.steering = int(val)

    def set_stick(self, x_val: int, y_val: int = 0) -> None:
        self.steering = int(x_val)
        self.stick_y = int(y_val)

    def set_right_stick(self, x_val: int, y_val: int = 0) -> None:
        self.right_stick_x = int(x_val)
        self.right_stick_y = int(y_val)

    def set_throttle(self, val: int) -> None:
        self.throttle = int(val)

    def set_brake(self, val: int) -> None:
        self.brake = int(val)

    def set_button(self, button_name: str, pressed: bool) -> None:
        self.buttons[button_name.upper()] = bool(pressed)

    def update(self) -> None:
        self.update_count += 1

    @property
    def left_stick_x(self) -> int:
        return self.steering

    @property
    def left_stick_y(self) -> int:
        return self.stick_y

    def reset(self) -> None:
        self.steering = 0
        self.stick_y = 0
        self.right_stick_x = 0
        self.right_stick_y = 0
        self.throttle = 0
        self.brake = 0
        self.buttons.clear()

    def close(self) -> None:
        self.reset()


class InputManager:
    """
    High-Level Multi-Client Gamepad Slot Manager.
    Maps up to 4 simultaneous mobile edge nodes to physical OS controllers.
    """
    def __init__(self, force_mock: bool = False, max_players: int = 4):
        self.max_players = max_players
        self.force_mock = force_mock
        # Active slot mappings: slot_index (0..3) -> client_id (str)
        self.slots: List[Optional[str]] = [None] * max_players
        # Persistent device lease table: client_id -> slot_index
        self._client_leases: Dict[str, int] = {}
        # Watchdog timestamps: client_id -> last_input_timestamp
        self._last_input_time: Dict[str, float] = {}
        # Rumble callback: fn(slot_idx, large_motor, small_motor)
        self.rumble_callback = None
        # Controller instances per slot
        self.controllers: List[AbstractGamepad] = []
        
        self._init_controllers()

    def set_rumble_callback(self, cb) -> None:
        """Sets external force-feedback callback for relaying XInput rumble to clients."""
        self.rumble_callback = cb
        for ctrl in self.controllers:
            if hasattr(ctrl, "on_rumble"):
                ctrl.on_rumble = cb

    def _init_controllers(self) -> None:
        for i in range(self.max_players):
            if self.force_mock:
                ctrl = MockGamepad(player_index=i)
            elif VIGEM_AVAILABLE:
                try:
                    ctrl = ViGEmXInputGamepad(player_index=i, on_rumble=self.rumble_callback)
                except Exception as e:
                    logger.warning(f"Could not instantiate ViGEm gamepad for slot {i}: {e}. Using keyboard fallback.")
                    ctrl = KeyboardFallbackGamepad(player_index=i)
            else:
                ctrl = KeyboardFallbackGamepad(player_index=i)
            self.controllers.append(ctrl)

    def allocate_slot(self, client_id: str, preferred_slot: Optional[int] = None) -> Optional[int]:
        """
        Assigns a player slot with persistent device leasing and user preference support.
        Guarantees that reconnecting clients reclaim their exact previous slot.
        """
        # 1. Check if already actively assigned
        for idx, owner in enumerate(self.slots):
            if owner == client_id:
                return idx

        # 2. Check if client explicitly requested a preferred slot and it is free
        if preferred_slot is not None and 0 <= preferred_slot < self.max_players:
            if self.slots[preferred_slot] is None:
                self.slots[preferred_slot] = client_id
                self._client_leases[client_id] = preferred_slot
                self.controllers[preferred_slot].reset()
                logger.info(f"Assigned preferred Player {preferred_slot + 1} slot to client [{client_id[:8]}]")
                return preferred_slot

        # 3. Check if client has a persistent lease on a slot and that slot is free
        if client_id in self._client_leases:
            leased_idx = self._client_leases[client_id]
            if 0 <= leased_idx < self.max_players and self.slots[leased_idx] is None:
                self.slots[leased_idx] = client_id
                self.controllers[leased_idx].reset()
                logger.info(f"Restored persistent Player {leased_idx + 1} slot to client [{client_id[:8]}]")
                return leased_idx

        # 4. Find first unallocated slot that is NOT actively leased by another client
        leased_slots = set(self._client_leases.values())
        for idx, owner in enumerate(self.slots):
            if owner is None and idx not in leased_slots:
                self.slots[idx] = client_id
                self._client_leases[client_id] = idx
                self.controllers[idx].reset()
                logger.info(f"Assigned unreserved Player {idx + 1} slot to client [{client_id[:8]}]")
                return idx

        # 5. Fallback: claim any empty slot
        for idx, owner in enumerate(self.slots):
            if owner is None:
                self.slots[idx] = client_id
                self._client_leases[client_id] = idx
                self.controllers[idx].reset()
                logger.info(f"Assigned Player {idx + 1} slot to client [{client_id[:8]}]")
                return idx

        logger.warning(f"All {self.max_players} player slots are currently occupied. Cannot assign client [{client_id[:8]}]")
        return None

    def swap_slots(self, slot_a: int, slot_b: int) -> Tuple[Optional[str], Optional[str]]:
        """
        Atomically swaps the two controller slots and their device assignments.
        Returns (client_a, client_b) so callers can notify clients of their new slots.
        """
        if not (0 <= slot_a < self.max_players and 0 <= slot_b < self.max_players):
            return None, None
        if slot_a == slot_b:
            return self.slots[slot_a], self.slots[slot_b]

        client_a = self.slots[slot_a]
        client_b = self.slots[slot_b]

        self.slots[slot_a] = client_b
        self.slots[slot_b] = client_a

        if client_a:
            self._client_leases[client_a] = slot_b
        if client_b:
            self._client_leases[client_b] = slot_a

        self.controllers[slot_a].reset()
        self.controllers[slot_b].reset()

        logger.info(f"Swapped Player {slot_a + 1} ({client_a}) with Player {slot_b + 1} ({client_b})")
        return client_a, client_b

    def release_slot(self, client_id: str) -> Optional[int]:
        """Frees the controller slot allocated to client_id while preserving device lease."""
        for idx, owner in enumerate(self.slots):
            if owner == client_id:
                self.slots[idx] = None
                self.controllers[idx].reset()
                self._last_input_time.pop(client_id, None)
                logger.info(f"Released Player {idx + 1} slot from client [{client_id[:8]}] (lease preserved)")
                return idx
        return None

    def get_slot(self, client_id: str) -> Optional[int]:
        for idx, owner in enumerate(self.slots):
            if owner == client_id:
                return idx
        return None

    def tick_watchdog(self, timeout_sec: float = 0.120) -> None:
        """Deadman's switch: resets virtual controls to neutral if client becomes silent for >120ms."""
        now = time.time()
        for idx, client_id in enumerate(self.slots):
            if client_id is not None:
                last_time = self._last_input_time.get(client_id, 0.0)
                if last_time > 0 and (now - last_time) > timeout_sec:
                    ctrl = self.controllers[idx]
                    ctrl.set_stick(0, 0)
                    ctrl.set_right_stick(0, 0)
                    ctrl.set_throttle(0)
                    ctrl.set_brake(0)
                    ctrl.update()
                    self._last_input_time[client_id] = 0.0

    def dispatch(self, client_id: str, control_state: Dict[str, Any]) -> bool:
        """
        Dispatches parsed sensor controls to the assigned OS virtual controller.
        Expected control_state dict keys:
            - stick_x: int [-32768, 32767]
            - throttle: int [0, 255]
            - brake: int [0, 255]
            - buttons: dict of {name: bool}
        """
        slot = self.get_slot(client_id)
        if slot is None:
            return False

        self._last_input_time[client_id] = time.time()
        ctrl = self.controllers[slot]
        if "stick_x" in control_state or "stick_y" in control_state:
            sx = control_state.get("stick_x", 0)
            sy = control_state.get("stick_y", 0)
            if hasattr(ctrl, "set_stick"):
                ctrl.set_stick(sx, sy)
            else:
                ctrl.set_steering(sx)
        if "right_stick_x" in control_state or "right_stick_y" in control_state:
            rx = control_state.get("right_stick_x", 0)
            ry = control_state.get("right_stick_y", 0)
            if hasattr(ctrl, "set_right_stick"):
                ctrl.set_right_stick(rx, ry)
        if "throttle" in control_state:
            ctrl.set_throttle(control_state["throttle"])
        if "brake" in control_state:
            ctrl.set_brake(control_state["brake"])
        if "buttons" in control_state:
            for btn_name, pressed in control_state["buttons"].items():
                ctrl.set_button(btn_name, pressed)

        ctrl.update()
        return True

    def pulse_test_button(self, slot_idx: int) -> None:
        """Sends a momentary Button A press (for 120ms in a background thread) on slot_idx
        to satisfy browser W3C Gamepad API user gesture requirements on online testers (e.g. hardwaretester.com/gamepad)."""
        if 0 <= slot_idx < len(self.controllers):
            ctrl = self.controllers[slot_idx]
            import threading
            def _pulse():
                try:
                    ctrl.set_button("A", True)
                    ctrl.update()
                    time.sleep(0.12)
                    ctrl.set_button("A", False)
                    ctrl.update()
                except Exception as e:
                    logger.debug(f"Pulse test error on slot {slot_idx}: {e}")
            threading.Thread(target=_pulse, daemon=True, name=f"PulseTest-P{slot_idx+1}").start()

    def reinit_controllers(self) -> bool:
        """Attempts to re-detect ViGEmBus driver and upgrade controllers from keyboard fallback to native Xbox 360."""
        global VIGEM_AVAILABLE
        if platform.system() == "Windows":
            try:
                import vgamepad as vg
                _probe = vg.VX360Gamepad()
                del _probe
                VIGEM_AVAILABLE = True
                logger.info("ViGEmBus driver successfully detected during re-initialization.")
            except Exception as e:
                logger.warning(f"ViGEmBus still unavailable: {e}")
                return False

        if VIGEM_AVAILABLE:
            for ctrl in self.controllers:
                ctrl.close()
            self.controllers.clear()
            self._init_controllers()
            return True
        return False

    def shutdown(self) -> None:
        for ctrl in self.controllers:
            ctrl.close()
