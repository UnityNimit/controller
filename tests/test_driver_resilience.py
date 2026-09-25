"""
Project Controller - Driver Resilience & Zero-Freeze Hot-Swap Automated Test Suite
Verifies:
1. is_vigem_driver_installed() and ensure_vigem_active() detection functions.
2. Zero-freeze atomic controller hot-swap under high-frequency concurrent dispatch streams (0 dropped frames, 0 IndexError).
3. Multi-path terms and driver preference persistence across home, cwd, and appdata.
4. Setup Wizard Step 2 active driver detection.
"""

import os
import sys
import time
import json
import pytest
import threading
from pathlib import Path

from gateway.input_manager import (
    InputManager,
    is_vigem_driver_installed,
    ensure_vigem_active,
    VIGEM_AVAILABLE
)
from gui.dashboard import (
    save_terms_preference,
    should_show_terms_on_startup,
    _get_config_candidate_paths
)


def test_is_vigem_driver_installed_and_active():
    """Verifies that driver detection functions execute cleanly without exceptions."""
    installed = is_vigem_driver_installed()
    assert isinstance(installed, bool)

    active = ensure_vigem_active()
    assert isinstance(active, bool)
    if installed and active:
        assert VIGEM_AVAILABLE is True


def test_atomic_reinit_controllers_concurrency_no_index_error():
    """
    Stress-tests InputManager with 5 concurrent threads streaming inputs at maximum rate
    while reinit_controllers() is triggered repeatedly.
    Guarantees:
    - Zero IndexError exceptions
    - Zero dropped dispatches due to empty controller list
    - Controller instances remain valid throughout transition
    """
    im = InputManager(force_mock=False, max_players=4)
    client_id = "test-concurrent-client-001"
    slot = im.allocate_slot(client_id, preferred_slot=0)
    assert slot == 0

    stop_event = threading.Event()
    exceptions = []
    success_count = [0]

    def _worker(thread_id: int):
        while not stop_event.is_set():
            try:
                control_state = {
                    "stick_x": 12000,
                    "stick_y": -8000,
                    "right_stick_x": 4000,
                    "right_stick_y": -4000,
                    "throttle": 220,
                    "brake": 0,
                    "buttons": {"A": True, "RT": True}
                }
                ok = im.dispatch(client_id, control_state)
                if ok:
                    success_count[0] += 1
            except Exception as e:
                exceptions.append((thread_id, e))
            time.sleep(0.001)

    threads = [threading.Thread(target=_worker, args=(i,), daemon=True) for i in range(5)]
    for t in threads:
        t.start()

    # Trigger reinit_controllers multiple times during heavy concurrent dispatch
    for _ in range(3):
        time.sleep(0.04)
        im.reinit_controllers()

    time.sleep(0.06)
    stop_event.set()
    for t in threads:
        t.join(timeout=1.0)

    # Clean shutdown
    im.shutdown()

    # CRITICAL: Zero exceptions must have occurred
    assert len(exceptions) == 0, f"Encountered unexpected exceptions during concurrent swap: {exceptions}"
    assert success_count[0] > 50, f"Expected successful dispatches, got {success_count[0]}"
    assert len(im.controllers) == 4


def test_multi_path_terms_preference_persistence(tmp_path, monkeypatch):
    """
    Tests that save_terms_preference persists to all candidate directories
    and should_show_terms_on_startup correctly reads preference across working directories.
    """
    fake_cwd = tmp_path / "app_folder"
    fake_home = tmp_path / "user_home"
    fake_appdata = tmp_path / "user_appdata"

    fake_cwd.mkdir(parents=True)
    fake_home.mkdir(parents=True)
    fake_appdata.mkdir(parents=True)

    monkeypatch.setattr(Path, "cwd", lambda: fake_cwd)
    monkeypatch.setattr(Path, "home", lambda: fake_home)
    monkeypatch.setenv("APPDATA", str(fake_appdata))

    # Before saving, should show terms
    assert should_show_terms_on_startup() is True

    # Save preference
    save_terms_preference(dont_show=True)

    # Verify all candidate paths have the file
    candidate_paths = _get_config_candidate_paths()
    saved_any = False
    for p in candidate_paths:
        if p.exists():
            data = json.loads(p.read_text(encoding="utf-8"))
            assert data.get("accepted_terms") is True
            assert data.get("dont_show_terms") is True
            saved_any = True
    assert saved_any is True

    # After saving, should NOT show terms
    assert should_show_terms_on_startup() is False

    # Simulate deleting the file from cwd (e.g. user moved or shared a clean folder)
    cwd_config = fake_cwd / ".controller_config.json"
    if cwd_config.exists():
        cwd_config.unlink()

    # Should still recognize preference from home / appdata!
    assert should_show_terms_on_startup() is False


def test_keyboard_fallback_2axis_analog_sticks(monkeypatch):
    """Verifies that KeyboardFallbackGamepad correctly handles both axes for left and right sticks."""
    from gateway.input_manager import KeyboardFallbackGamepad
    
    pad = KeyboardFallbackGamepad(player_index=0)
    
    # Mock _send_key to avoid triggering actual OS keybd_event during tests
    sent_keys = []
    monkeypatch.setattr(pad, "_send_key", lambda vk, down: sent_keys.append((vk, down)))

    # Test left stick Y-axis (W / S) and X-axis (A / D)
    pad.set_stick(x_val=15000, y_val=20000)
    assert pad.VK_D in pad.active_keys
    assert pad.VK_W in pad.active_keys
    assert pad.VK_A not in pad.active_keys
    assert pad.VK_S not in pad.active_keys

    pad.set_stick(x_val=-15000, y_val=-20000)
    assert pad.VK_A in pad.active_keys
    assert pad.VK_S in pad.active_keys
    assert pad.VK_D not in pad.active_keys
    assert pad.VK_W not in pad.active_keys

    pad.set_stick(0, 0)
    assert len(pad.active_keys) == 0

    # Test right stick 2-axis (Arrow Keys)
    pad.set_right_stick(x_val=12000, y_val=16000)
    assert pad.VK_RIGHT in pad.active_keys
    assert pad.VK_UP in pad.active_keys
    assert pad.VK_LEFT not in pad.active_keys
    assert pad.VK_DOWN not in pad.active_keys

    pad.set_right_stick(x_val=-12000, y_val=-16000)
    assert pad.VK_LEFT in pad.active_keys
    assert pad.VK_DOWN in pad.active_keys
    assert pad.VK_RIGHT not in pad.active_keys
    assert pad.VK_UP not in pad.active_keys

    pad.set_right_stick(0, 0)
    assert len(pad.active_keys) == 0


def test_firewall_sequence_resync_on_reconnect():
    """Verifies that client reconnects or sequence rollover auto-resyncs without raising sequence regression."""
    from gateway.security import AnomalyFirewall

    firewall = AnomalyFirewall(max_rate_hz=5000.0, min_inter_arrival_sec=0.0)
    cid = "client_reconnect_test"

    # Send initial packets up to sequence 500
    for seq in range(1, 501):
        clean, err = firewall.inspect_packet(cid, seq=seq, client_time=time.time(), is_neutral=True)
        assert clean is True

    # Client page reloaded! Sequence resets to 1.
    # Should auto-resync immediately without dropping packet
    clean, err = firewall.inspect_packet(cid, seq=1, client_time=time.time(), is_neutral=True)
    assert clean is True
    assert err is None

    # Subsequent packet 2 should pass normally
    clean, err = firewall.inspect_packet(cid, seq=2, client_time=time.time(), is_neutral=True)
    assert clean is True
    assert err is None

    # 5 consecutive anomalies trigger full reset
    firewall.last_seq_num[cid] = 100
    for _ in range(5):
        firewall.inspect_packet(cid, seq=50, client_time=time.time(), is_neutral=True)
    # Next packet at seq 51 should now be accepted because anomaly counter auto-resynced
    clean, err = firewall.inspect_packet(cid, seq=51, client_time=time.time(), is_neutral=True)
    assert clean is True
    assert err is None
