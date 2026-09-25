"""
Project Controller - OS-Level Input Emulation Driver & Multi-Client Slot Manager
Supports ViGEmBus Native Xbox 360 virtual controllers with graceful fallback to
Windows SendInput Keyboard/Mouse and Mock Testing backends.
"""

import os
import sys
import subprocess
import logging
import platform
import ctypes
import time
import threading
from abc import ABC, abstractmethod
from typing import Dict, Optional, List, Any, Tuple

try:
    import winreg
except ImportError:
    winreg = None

logger = logging.getLogger("Controller.Input")


def is_vigem_driver_installed() -> bool:
    """Checks if the ViGEmBus kernel driver is installed on the Windows host system."""
    if platform.system() != "Windows":
        return False
    # 1. Check registry service entry
    if winreg is not None:
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Services\ViGEmBus")
            winreg.CloseKey(key)
            return True
        except Exception:
            pass
    # 2. Check kernel driver binary in System32\drivers
    sys_path = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "drivers", "ViGEmBus.sys")
    if os.path.exists(sys_path):
        return True
    # 3. Check service manager via sc.exe
    try:
        res = subprocess.run(["sc.exe", "query", "ViGEmBus"], capture_output=True, text=True, timeout=3)
        if res.returncode == 0:
            return True
    except Exception:
        pass
    return False


def ensure_vigem_active() -> bool:
    """
    Verifies that the ViGEmBus kernel driver is operational.
    If the driver is installed but in STOPPED state, attempts to start it automatically.
    Purges stale vgamepad Python module state so VBUS binds cleanly to the running driver.
    """
    if platform.system() != "Windows":
        return False

    installed = is_vigem_driver_installed()
    if not installed:
        return False

    # Check if the kernel driver service is running; if stopped, start it
    try:
        res = subprocess.run(["sc.exe", "query", "ViGEmBus"], capture_output=True, text=True, timeout=3)
        if "RUNNING" not in res.stdout:
            subprocess.run(["sc.exe", "start", "ViGEmBus"], capture_output=True, timeout=5)
            time.sleep(0.4)
    except Exception as e:
        logger.debug(f"ViGEm service query/start note: {e}")

    # Purge any cached vgamepad modules to ensure fresh VBus binding
    for mod_name in list(sys.modules.keys()):
        if mod_name.startswith("vgamepad"):
            del sys.modules[mod_name]

    try:
        import vgamepad as vg
        _probe = vg.VX360Gamepad()
        del _probe
        return True
    except Exception as e:
        logger.debug(f"ViGEmBus probe verification failed: {e}")
        return False


# Detect ViGEmBus Driver Availability on module load
VIGEM_AVAILABLE = False
try:
    if platform.system() == "Windows":
        VIGEM_AVAILABLE = ensure_vigem_active()
        if VIGEM_AVAILABLE:
            logger.info("ViGEmBus kernel driver detected and active. Native XInput emulation ENABLED.")
        else:
            logger.warning(
                "ViGEmBus driver not active. Falling back to Keyboard emulation. "
                "Click 'INSTALL DRIVER' on the dashboard to enable native Xbox 360 controller emulation for all PC games."
            )
except Exception as e:
    VIGEM_AVAILABLE = False
    logger.warning(f"ViGEmBus driver initialization note: {e}")


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


# Retain permanent references to ViGEm CFUNCTYPE thunks so Windows kernel driver callbacks never jump into freed ctypes memory
_PERMANENT_VIGEM_CALLBACK_THUNKS: List[Any] = []


class ViGEmXInputGamepad(AbstractGamepad):
    """Native virtual Xbox 360 controller backed by ViGEmBus with force feedback rumble."""
    def __init__(self, player_index: int = 0, on_rumble=None):
        import vgamepad as vg
        self.vg = vg
        self.player_index = player_index
        self.on_rumble = on_rumble
        self.large_motor_rumble = 0
        self.small_motor_rumble = 0
        self._notification_cb_ref = None
        self._closed = False
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
        """Registers closed-loop force-feedback notification callback with Windows kernel ViGEmBus driver."""
        # Signature required by vgamepad: (client, target, large_motor, small_motor, led_number, user_data)
        def _notification_cb(client, target, large_motor, small_motor, led_number, user_data):
            if getattr(self, "_closed", False):
                return
            try:
                lm = int(large_motor)
                sm = int(small_motor)
                self.large_motor_rumble = lm
                self.small_motor_rumble = sm
                if self.on_rumble is not None:
                    self.on_rumble(self.player_index, lm, sm)
            except Exception as e:
                logger.debug(f"Rumble callback dispatch error on Player {self.player_index + 1}: {e}")

        self._notification_cb_ref = _notification_cb
        try:
            self.gamepad.register_notification(callback_function=_notification_cb)
            if hasattr(self.gamepad, "cmp_func") and self.gamepad.cmp_func is not None:
                _PERMANENT_VIGEM_CALLBACK_THUNKS.append(self.gamepad.cmp_func)
            logger.info(f"Registered ViGEmBus force-feedback haptic rumble notification for Player {self.player_index + 1}")
        except Exception as e:
            logger.warning(f"Could not register ViGEm rumble notification for Player {self.player_index + 1}: {e}")

    def set_stick(self, x_val: int, y_val: int = 0) -> None:
        clamped_x = max(-32768, min(32767, int(x_val)))
        clamped_y = max(-32768, min(32767, int(y_val)))
        self.gamepad.left_joystick(x_value=clamped_x, y_value=clamped_y)

    def set_right_stick(self, x_val: int, y_val: int = 0) -> None:
        clamped_x = max(-32768, min(32767, int(x_val)))
        clamped_y = max(-32768, min(32767, int(y_val)))
        self.gamepad.right_joystick(x_value=clamped_x, y_value=clamped_y)

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
        if getattr(self, "_closed", False):
            return
        self._closed = True
        try:
            if hasattr(self.gamepad, "unregister_notification"):
                self.gamepad.unregister_notification()
        except Exception:
            pass
        try:
            self.reset()
        except Exception:
            pass
        time.sleep(0.04)
        try:
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
    VK_UP = 0x26
    VK_DOWN = 0x28
    VK_LEFT = 0x25
    VK_RIGHT = 0x27

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
        thresh = 8000
        if y_val > thresh:
            self._press_key(self.VK_W)
            self._release_key(self.VK_S)
        elif y_val < -thresh:
            self._press_key(self.VK_S)
            self._release_key(self.VK_W)
        else:
            self._release_key(self.VK_W)
            self._release_key(self.VK_S)

    def set_right_stick(self, x_val: int, y_val: int = 0) -> None:
        thresh = 8000
        if x_val < -thresh:
            self._press_key(self.VK_LEFT)
            self._release_key(self.VK_RIGHT)
        elif x_val > thresh:
            self._press_key(self.VK_RIGHT)
            self._release_key(self.VK_LEFT)
        else:
            self._release_key(self.VK_LEFT)
            self._release_key(self.VK_RIGHT)

        if y_val > thresh:
            self._press_key(self.VK_UP)
            self._release_key(self.VK_DOWN)
        elif y_val < -thresh:
            self._press_key(self.VK_DOWN)
            self._release_key(self.VK_UP)
        else:
            self._release_key(self.VK_UP)
            self._release_key(self.VK_DOWN)


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
        self.is_mock = True
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
        self._dispatch_lock = threading.RLock()
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

        # Pillar 1: Dedicated Virtual Hardware MCU Dispatch Engine (1000 Hz - 5000 Hz)
        self.mcu_dispatcher = None
        if not self.force_mock:
            try:
                from gateway.mcu_dispatch import VirtualMcuDispatcher
                from config import settings
                self.mcu_dispatcher = VirtualMcuDispatcher(
                    controllers=self.controllers,
                    target_hz=getattr(settings.mcu, "DISPATCH_RATE_HZ", 1000.0),
                    enable_hybrid_spinlock=getattr(settings.mcu, "ENABLE_HYBRID_SPINLOCK", True),
                    max_slots=self.max_players
                )
                if getattr(settings.mcu, "AUTO_START", True):
                    self.mcu_dispatcher.start()
            except Exception as e:
                logger.warning(f"Could not initialize Virtual MCU Dispatcher: {e}")

    def set_rumble_callback(self, cb) -> None:
        """Sets external force-feedback callback for relaying XInput rumble to clients."""
        self.rumble_callback = cb
        for ctrl in self.controllers:
            if hasattr(ctrl, "on_rumble"):
                ctrl.on_rumble = cb
                if hasattr(ctrl, "gamepad") and getattr(ctrl.gamepad, "cmp_func", None) is None:
                    if hasattr(ctrl, "_register_rumble_cb"):
                        ctrl._register_rumble_cb()

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
        Assigns a player slot with first-connection Player 1 guarantee and persistent device leasing.
        When the first client connects (no active clients), it ALWAYS connects as Player 1 (Slot 0).
        """
        # 1. Check if already actively assigned
        for idx, owner in enumerate(self.slots):
            if owner == client_id:
                return idx

        active_count = sum(1 for owner in self.slots if owner is not None)

        # 2. GUARANTEE: When the first client connects, it ALWAYS connects as Player 1 (Slot 0)
        if active_count == 0:
            self.slots[0] = client_id
            self._client_leases[client_id] = 0
            self.controllers[0].reset()
            logger.info(f"First client [{client_id[:8]}] connected -> Guaranteed Player 1 (Slot 0)")
            return 0

        # 3. If Slot 0 (Player 1) is free, incoming client takes Player 1 unless actively reconnecting to another slot
        if self.slots[0] is None:
            if client_id in self._client_leases and self._client_leases[client_id] != 0:
                leased = self._client_leases[client_id]
                if 0 <= leased < self.max_players and self.slots[leased] is None and preferred_slot == leased:
                    self.slots[leased] = client_id
                    self.controllers[leased].reset()
                    logger.info(f"Restored Player {leased + 1} slot to reconnecting client [{client_id[:8]}]")
                    return leased
            self.slots[0] = client_id
            self._client_leases[client_id] = 0
            self.controllers[0].reset()
            logger.info(f"Assigned free Player 1 (Slot 0) to client [{client_id[:8]}]")
            return 0

        # 4. Check if client explicitly requested a preferred slot and it is free
        if preferred_slot is not None and 0 <= preferred_slot < self.max_players:
            if self.slots[preferred_slot] is None:
                self.slots[preferred_slot] = client_id
                self._client_leases[client_id] = preferred_slot
                self.controllers[preferred_slot].reset()
                logger.info(f"Assigned preferred Player {preferred_slot + 1} slot to client [{client_id[:8]}]")
                return preferred_slot

        # 5. Check if client has a persistent lease on a slot and that slot is free
        if client_id in self._client_leases:
            leased_idx = self._client_leases[client_id]
            if 0 <= leased_idx < self.max_players and self.slots[leased_idx] is None:
                self.slots[leased_idx] = client_id
                self.controllers[leased_idx].reset()
                logger.info(f"Restored persistent Player {leased_idx + 1} slot to client [{client_id[:8]}]")
                return leased_idx

        # 6. Fill lowest available slot in sequential order (Player 1 -> Player 2 -> Player 3 -> Player 4)
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
        with self._dispatch_lock:
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

            if getattr(self, "mcu_dispatcher", None) is not None:
                self.mcu_dispatcher.reset_slot(slot_a)
                self.mcu_dispatcher.reset_slot(slot_b)

            self.controllers[slot_a].reset()
            self.controllers[slot_b].reset()

            logger.info(f"Swapped Player {slot_a + 1} ({client_a}) with Player {slot_b + 1} ({client_b})")
            return client_a, client_b

    def release_slot(self, client_id: str) -> Optional[int]:
        """Frees the controller slot allocated to client_id while preserving device lease."""
        for idx, owner in enumerate(self.slots):
            if owner == client_id:
                self.slots[idx] = None
                if getattr(self, "mcu_dispatcher", None) is not None:
                    self.mcu_dispatcher.reset_slot(idx)
                if 0 <= idx < len(self.controllers):
                    self.controllers[idx].reset()
                self._last_input_time.pop(client_id, None)
                logger.info(f"Released Player {idx + 1} slot from client [{client_id[:8]}]")
                if all(s is None for s in self.slots):
                    self._client_leases.clear()
                return idx
        return None

    def get_slot(self, client_id: str) -> Optional[int]:
        for idx, owner in enumerate(self.slots):
            if owner == client_id:
                return idx
        return None

    def tick_watchdog(self, timeout_sec: float = 0.120) -> None:
        """Deadman's switch: resets virtual controls to neutral if client becomes silent for >120ms."""
        now = time.perf_counter()
        for idx, client_id in enumerate(self.slots):
            if client_id is not None:
                last_time = self._last_input_time.get(client_id, 0.0)
                if last_time > 0 and (now - last_time) > timeout_sec:
                    if getattr(self, "mcu_dispatcher", None) is not None:
                        self.mcu_dispatcher.reset_slot(idx)
                    if 0 <= idx < len(self.controllers):
                        ctrl = self.controllers[idx]
                        ctrl.set_stick(0, 0)
                        ctrl.set_right_stick(0, 0)
                        ctrl.set_throttle(0)
                        ctrl.set_brake(0)
                        ctrl.update()
                    self._last_input_time[client_id] = 0.0

    def dispatch(
        self,
        client_id: str,
        control_state: Dict[str, Any],
        timestamp: Optional[float] = None,
        rtt_ms: float = 5.0
    ) -> bool:
        """
        Dispatches parsed sensor controls to the assigned OS virtual controller.
        Expected control_state dict keys:
            - stick_x: int [-32768, 32767]
            - throttle: int [0, 255]
            - brake: int [0, 255]
            - buttons: dict of {name: bool}
        """
        with self._dispatch_lock:
            slot = self.get_slot(client_id)
            if slot is None or slot < 0 or slot >= len(self.controllers):
                return False

            t = timestamp if timestamp is not None else time.perf_counter()
            self._last_input_time[client_id] = t
            ctrl = self.controllers[slot]
            try:
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

                # Pillar 1 & 2: Asynchronous high-rate dispatch via Virtual MCU Engine
                if getattr(self, "mcu_dispatcher", None) is not None and self.mcu_dispatcher._running:
                    self.mcu_dispatcher.update_slot_input(slot, control_state, timestamp=t, rtt_ms=rtt_ms)
                else:
                    ctrl.update()
            except Exception as e:
                logger.debug(f"Transient dispatch error on slot {slot}: {e}")

            return True

    def pulse_test_button(self, slot_idx: int) -> None:
        """Sends a momentary Button A press (for 120ms) on slot_idx and triggers a test rumble burst."""
        if 0 <= slot_idx < len(self.controllers):
            ctrl = self.controllers[slot_idx]
            def _pulse():
                try:
                    ctrl.set_button("A", True)
                    ctrl.update()
                    # Trigger momentary hardware rumble test if callback is active
                    if self.rumble_callback is not None:
                        self.rumble_callback(slot_idx, 255, 255)
                    time.sleep(0.15)
                    ctrl.set_button("A", False)
                    ctrl.update()
                    time.sleep(0.20)
                    if self.rumble_callback is not None:
                        self.rumble_callback(slot_idx, 0, 0)
                except Exception as e:
                    logger.debug(f"Pulse test error on slot {slot_idx}: {e}")
            threading.Thread(target=_pulse, daemon=True, name=f"PulseTest-P{slot_idx+1}").start()

    def reinit_controllers(self) -> bool:
        """
        Safely upgrades controllers from keyboard fallback to native ViGEmBus Xbox 360.
        Performs an atomic swap under self._dispatch_lock so active streams are never interrupted,
        never encounter empty controller lists, and never drop client connections.
        """
        global VIGEM_AVAILABLE
        if self.force_mock:
            return False

        if platform.system() == "Windows":
            if not ensure_vigem_active():
                logger.warning("ViGEmBus driver is not active or could not be initialized.")
                return False
            VIGEM_AVAILABLE = True
            logger.info("ViGEmBus driver confirmed active for hot-swap upgrade.")
        else:
            return False

        # Construct new native controllers completely BEFORE touching the active controllers
        new_controllers: List[AbstractGamepad] = []
        try:
            for i in range(self.max_players):
                ctrl = ViGEmXInputGamepad(player_index=i, on_rumble=self.rumble_callback)
                new_controllers.append(ctrl)
        except Exception as e:
            logger.warning(f"Failed to instantiate new ViGEm controllers during hot-swap: {e}")
            for c in new_controllers:
                try:
                    c.close()
                except Exception:
                    pass
            return False

        if len(new_controllers) != self.max_players:
            return False

        # Atomically swap controllers under the dispatch lock
        old_controllers: List[AbstractGamepad] = []
        with self._dispatch_lock:
            old_controllers = list(self.controllers)
            self.controllers = new_controllers

            # Atomically update MCU Dispatcher's reference
            if getattr(self, "mcu_dispatcher", None) is not None:
                self.mcu_dispatcher.controllers = self.controllers

            # Re-register rumble callbacks if configured
            if self.rumble_callback is not None:
                self.set_rumble_callback(self.rumble_callback)

        # Close old controllers asynchronously in a background thread to prevent blocking dispatch
        def _cleanup_old():
            time.sleep(0.15)
            for old_c in old_controllers:
                try:
                    old_c.close()
                except Exception:
                    pass

        threading.Thread(target=_cleanup_old, daemon=True, name="OldControllerCleanup").start()
        logger.info("Successfully hot-swapped controllers to ViGEmBus Native Xbox 360 with zero downtime.")
        return True

    def shutdown(self) -> None:
        with self._dispatch_lock:
            if getattr(self, "mcu_dispatcher", None) is not None:
                self.mcu_dispatcher.stop()
            for ctrl in self.controllers:
                try:
                    ctrl.close()
                except Exception:
                    pass

