#!/usr/bin/env python3
"""
Controller - Terminal Edition (Zero-GUI / Maximum Performance)
High-Performance Cyber-Physical Teleoperation Framework
Dedicated Console Server for Esports & Competitive Low-Latency Gaming
"""

import sys
import os
import time
import asyncio
import logging
import threading
from pathlib import Path

# Ensure project root is in sys.path
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
    BUNDLE_DIR = Path(sys._MEIPASS)
else:
    BASE_DIR = Path(__file__).resolve().parent
    BUNDLE_DIR = BASE_DIR

sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BUNDLE_DIR))

from gateway.server import ControllerGatewayServer
from config import settings

logger = logging.getLogger("Controller.Terminal")


def setup_console():
    """Sets a clean console title and UTF-8 encoding on Windows."""
    if os.name == "nt":
        try:
            os.system("title Controller [Terminal Edition - Max Performance]")
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
            try:
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Controller.Terminal.1.1.0")
            except Exception:
                pass
        except Exception:
            pass


async def handle_terminal_commands(server: ControllerGatewayServer, cmd_queue: asyncio.Queue):
    """Processes interactive commands from the terminal without blocking network I/O."""
    while server._running:
        try:
            cmd = await cmd_queue.get()
            cmd_lower = cmd.lower().strip()
            if not cmd_lower:
                continue

            if cmd_lower in ("q", "quit", "exit"):
                print("[*] Exit command received. Shutting down...")
                await server.stop()
                break
            elif cmd_lower in ("s", "swap"):
                ok = server.swap_player_slots(0, 1)
                if ok:
                    print("[*] Successfully swapped Player 1 and Player 2 slots!")
                else:
                    print("[!] Failed to swap slots.")
            elif cmd_lower.startswith("t") or cmd_lower.startswith("test"):
                parts = cmd_lower.split()
                dur = 1.5
                if len(parts) > 1:
                    try:
                        dur = float(parts[1])
                    except ValueError:
                        pass
                if "stop" in cmd_lower or (len(parts) > 1 and parts[1] == "0"):
                    print("[*] Stopping rumble on Player 1...")
                    server._on_rumble_event(0, 0, 0)
                elif "inf" in cmd_lower:
                    print("[*] Starting continuous infinite rumble on Player 1 (type 'stop' to stop)...")
                    server.trigger_test_rumble(0, large=255, small=255, duration_sec=-1)
                else:
                    print(f"[*] Triggering maximum-effect rumble pulse ({dur}s) on Player 1...")
                    server.trigger_test_rumble(0, large=255, small=255, duration_sec=dur)
            elif cmd_lower in ("stop", "off"):
                print("[*] Stopping rumble on Player 1...")
                server._on_rumble_event(0, 0, 0)
            elif cmd_lower in ("p", "pulse"):
                print("[*] Pulsing button 'A' on Player 1 to register with gamepad tester...")
                server.pulse_test_slot(0)
            elif cmd_lower in ("status", "slots", "info"):
                print("\n" + "-" * 50)
                print("  CONTROLLER SLOT STATUS:")
                for i, cid in enumerate(server.input_manager.slots):
                    client_str = cid if cid else "[EMPTY - READY FOR CONNECTION]"
                    is_active = "ACTIVE" if (cid and cid in server.client_sockets) else "IDLE"
                    print(f"  Player {i+1} (Slot {i}): {client_str} [{is_active}]")
                print("-" * 50 + "\n")
            elif cmd_lower in ("h", "help"):
                print("\nAvailable Commands:")
                print("  s, swap        - Swap Player 1 and Player 2")
                print("  t, test [sec]  - Trigger vibration (e.g. 't', 't 5', 't 10', 't inf')")
                print("  stop           - Immediately stop active vibration")
                print("  p, pulse       - Pulse button A on Player 1 to register tester")
                print("  status         - Show active player slots")
                print("  q, quit        - Gracefully shutdown")
                print("  Note: Open /vibration_test.html on your phone for isolated haptic lab.\n")
            else:
                print(f"[?] Unknown command '{cmd}'. Type 'help' for available commands.")
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.debug(f"Command error: {e}")


async def run_terminal_mode(port: int = 8443, use_ssl: bool = True):
    """Main execution loop for the Zero-GUI Terminal Edition."""
    setup_console()

    server = ControllerGatewayServer(
        use_ssl=use_ssl,
        port=port,
        enable_simulator=False,
        force_mock_input=False
    )

    cmd_queue = asyncio.Queue()
    loop = asyncio.get_running_loop()

    def stdin_thread():
        while True:
            try:
                line = sys.stdin.readline()
                if not line:
                    break
                loop.call_soon_threadsafe(cmd_queue.put_nowait, line.strip())
            except Exception:
                break

    input_thread = threading.Thread(target=stdin_thread, name="TerminalStdinThread", daemon=True)
    input_thread.start()

    try:
        await server.start()
        print("  [TIP] Interactive terminal active! Type 'help' for commands, 's' to swap, 't' to test rumble.")
        print("  [TIP] Press Ctrl+C at any time to exit.\n")
        
        cmd_task = asyncio.create_task(handle_terminal_commands(server, cmd_queue))
        
        while server._running:
            await asyncio.sleep(1)
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        print("\n[*] Shutting down Controller Gateway...")
        await server.stop()
        print("[*] Server stopped cleanly. Goodbye!")


def main():
    if any(arg in sys.argv for arg in ("--version", "-v", "-V")):
        print("Controller Terminal Edition v1.1.0 (Zero-GUI Max Performance)")
        sys.exit(0)

    if any(arg in sys.argv for arg in ("--help", "-h", "/?")):
        print("Controller Terminal Edition v1.1.0 - Zero-GUI Max Performance Server\n")
        print("Usage:")
        print("  Controller-Terminal.exe [options]\n")
        print("Options:")
        print("  -v, --version    Show application version and exit")
        print("  -h, --help       Show this help message and exit")
        print("  --port <int>     Specify custom listening port (default: 8443)")
        print("  --no-ssl         Disable SSL (HTTP/WS only, not recommended for mobile camera)")
        print("\nInteractive Commands (type in terminal while running):")
        print("  s, swap          Swap Player 1 and Player 2 slots")
        print("  t, test          Trigger test vibration on Player 1")
        print("  p, pulse         Pulse button A to wake online gamepad testers")
        print("  status           Display connected clients and slot table")
        print("  q, quit, exit    Gracefully shut down the server\n")
        sys.exit(0)

    port = 8443
    use_ssl = True
    if "--no-ssl" in sys.argv:
        use_ssl = False
    if "--port" in sys.argv:
        try:
            idx = sys.argv.index("--port")
            port = int(sys.argv[idx + 1])
        except Exception:
            pass

    try:
        asyncio.run(run_terminal_mode(port=port, use_ssl=use_ssl))
    except KeyboardInterrupt:
        print("\nExited.")


if __name__ == "__main__":
    main()
