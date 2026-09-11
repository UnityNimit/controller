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
from typing import Dict, Optional, List, Any

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
        f"ViGEmBus driver not active ({e}). Falling back to Keyboard/SendInput emulation. "
        f"Run 'scripts/install_driver.bat' with Admin privileges to enable native Xbox 360 controller emulation."
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
    """Native virtual Xbox 360 controller backed by ViGEmBus."""
    def __init__(self, player_index: int = 0):
        import vgamepad as vg
        self.vg = vg
        self.player_index = player_index
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
            # Rocket League & Racing Aliases
            "JUMP": vg.XUSB_BUTTON.XUSB_GAMEPAD_A,
            "BOOST": vg.XUSB_BUTTON.XUSB_GAMEPAD_B,
            "POWERSLIDE": vg.XUSB_BUTTON.XUSB_GAMEPAD_X,
            "BALL_CAM": vg.XUSB_BUTTON.XUSB_GAMEPAD_Y,
            "HANDBRAKE": vg.XUSB_BUTTON.XUSB_GAMEPAD_A,
            "SHIFT_UP": vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER,
            "SHIFT_DOWN": vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER,
            "HIGH_BEAM": vg.XUSB_BUTTON.XUSB_GAMEPAD_X,
        }
        self.reset()
        logger.info(f"Initialized native ViGEmBus Virtual Xbox 360 controller for Player {player_index + 1}")

    def set_steering(self, val: int) -> None:
        clamped = max(-32768, min(32767, int(val)))
        self.gamepad.left_joystick(x_value=clamped, y_value=0)

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
            "HANDBRAKE": self.VK_SPACE,
            "A": self.VK_SPACE,
            "JUMP": self.VK_SPACE,
            "B": 0xA0,          # VK_LSHIFT (Boost in Rocket League)
            "BOOST": 0xA0,
            "X": 0xA0,          # VK_LSHIFT (Powerslide in Rocket League)
            "POWERSLIDE": 0xA0,
            "Y": 0x46,          # 'F' (Ball Cam toggle in Rocket League)
            "BALL_CAM": 0x46,
            "SHIFT_UP": self.VK_E,
            "RB": self.VK_E,
            "SHIFT_DOWN": self.VK_Q,
            "LB": self.VK_Q,
            "HIGH_BEAM": self.VK_H,
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
        self.throttle: int = 0
        self.brake: int = 0
        self.buttons: Dict[str, bool] = {}
        self.update_count: int = 0

    def set_steering(self, val: int) -> None:
        self.steering = int(val)

    def set_throttle(self, val: int) -> None:
        self.throttle = int(val)

    def set_brake(self, val: int) -> None:
        self.brake = int(val)

    def set_button(self, button_name: str, pressed: bool) -> None:
        self.buttons[button_name.upper()] = bool(pressed)

    def update(self) -> None:
        self.update_count += 1

    def reset(self) -> None:
        self.steering = 0
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
        # Controller instances per slot
        self.controllers: List[AbstractGamepad] = []
        
        self._init_controllers()

    def _init_controllers(self) -> None:
        for i in range(self.max_players):
            if self.force_mock:
                ctrl = MockGamepad(player_index=i)
            elif VIGEM_AVAILABLE:
                try:
                    ctrl = ViGEmXInputGamepad(player_index=i)
                except Exception as e:
                    logger.warning(f"Could not instantiate ViGEm gamepad for slot {i}: {e}. Using keyboard fallback.")
                    ctrl = KeyboardFallbackGamepad(player_index=i)
            else:
                ctrl = KeyboardFallbackGamepad(player_index=i)
            self.controllers.append(ctrl)

    def allocate_slot(self, client_id: str) -> Optional[int]:
        """Assigns an available player slot to a new client."""
        # Check if already assigned
        for idx, owner in enumerate(self.slots):
            if owner == client_id:
                return idx

        # Find first empty slot
        for idx, owner in enumerate(self.slots):
            if owner is None:
                self.slots[idx] = client_id
                self.controllers[idx].reset()
                logger.info(f"Assigned Player {idx + 1} slot to client [{client_id[:8]}]")
                return idx

        logger.warning(f"All {self.max_players} player slots are currently occupied. Cannot assign client [{client_id[:8]}]")
        return None

    def release_slot(self, client_id: str) -> Optional[int]:
        """Frees the controller slot allocated to client_id."""
        for idx, owner in enumerate(self.slots):
            if owner == client_id:
                self.slots[idx] = None
                self.controllers[idx].reset()
                logger.info(f"Released Player {idx + 1} slot from client [{client_id[:8]}]")
                return idx
        return None

    def get_slot(self, client_id: str) -> Optional[int]:
        for idx, owner in enumerate(self.slots):
            if owner == client_id:
                return idx
        return None

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

        ctrl = self.controllers[slot]
        if "stick_x" in control_state:
            ctrl.set_steering(control_state["stick_x"])
        if "throttle" in control_state:
            ctrl.set_throttle(control_state["throttle"])
        if "brake" in control_state:
            ctrl.set_brake(control_state["brake"])
        if "buttons" in control_state:
            for btn_name, pressed in control_state["buttons"].items():
                ctrl.set_button(btn_name, pressed)

        ctrl.update()
        return True

    def shutdown(self) -> None:
        for ctrl in self.controllers:
            ctrl.close()
