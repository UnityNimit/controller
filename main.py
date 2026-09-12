#!/usr/bin/env python3
"""
Controller - Standalone Native Entrypoint & Double-Click Launcher
High-Performance Cyber-Physical Teleoperation Framework with Tactical Telemetry GUI
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

# Fast-path CLI argument checks before importing heavy server/GUI dependencies
if any(arg in sys.argv for arg in ("--version", "-v", "-V")):
    print("Controller v1.0.0")
    sys.exit(0)

if any(arg in sys.argv for arg in ("--help", "-h", "/?")):
    print("Controller v1.0.0 - High-Performance Mobile Gamepad Server\n")
    print("Usage:")
    print("  Controller.exe [options]\n")
    print("Options:")
    print("  -v, --version    Show application version and exit")
    print("  -h, --help       Show this help message and exit")
    print("  --headless       Run gateway server without GUI")
    print("  --no-gui         Alias for --headless")
    sys.exit(0)

sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BUNDLE_DIR))

from gateway.server import ControllerGatewayServer
from config import settings
from gui.state_bridge import TelemetryBridge, QueueLogHandler

logger = logging.getLogger("Controller.Main")


def setup_console():
    """Sets a clean console title and UTF-8 encoding on Windows."""
    if os.name == "nt":
        try:
            os.system("title Controller")
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
            # Ensure taskbar groups with custom application icon
            try:
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Controller.Gamepad.1.0.0")
            except Exception:
                pass
        except Exception:
            pass


async def run_server_async(server: ControllerGatewayServer):
    """Headless AsyncIO server loop for terminal-only mode."""
    setup_console()
    try:
        await server.start()
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        print("\n[*] Shutting down Controller Gateway...")
        await server.stop()


def start_gui_app():
    """Launches the CustomTkinter Tactical Telemetry GUI with background server thread."""
    setup_console()

    bridge = TelemetryBridge()

    # Route logs to GUI console as well as stdout
    gui_log_handler = QueueLogHandler(bridge.log_queue)
    gui_log_handler.setFormatter(logging.Formatter("%(message)s"))
    logging.getLogger().addHandler(gui_log_handler)

    loop = asyncio.new_event_loop()
    server_holder = {}

    def server_worker():
        asyncio.set_event_loop(loop)
        try:
            server = ControllerGatewayServer(
                use_ssl=True,
                port=8443,
                enable_simulator=False,
                force_mock_input=False,
                bridge=bridge
            )
            server_holder["server"] = server
            loop.run_until_complete(server.start())
            loop.run_forever()
        except Exception as e:
            logger.error(f"Gateway server error: {e}")
        finally:
            server = server_holder.get("server")
            if server:
                try:
                    loop.run_until_complete(server.stop())
                except Exception:
                    pass

    server_thread = threading.Thread(target=server_worker, name="GatewayServerThread", daemon=True)
    server_thread.start()

    def on_window_close():
        logger.info("Closing Controller Tactical HUD...")
        server = server_holder.get("server")
        if server and server_thread.is_alive():
            try:
                future = asyncio.run_coroutine_threadsafe(server.stop(), loop)
                future.result(timeout=2.0)
            except Exception:
                pass
            loop.call_soon_threadsafe(loop.stop)

    # Launch CustomTkinter dashboard immediately on main thread
    from gui.dashboard import ControllerDashboard
    dashboard = ControllerDashboard(bridge=bridge, on_close_callback=on_window_close)
    dashboard.mainloop()


def main():
    if "--headless" in sys.argv or "--no-gui" in sys.argv:
        server = ControllerGatewayServer(
            use_ssl=True,
            port=8443,
            enable_simulator=False,
            force_mock_input=False
        )
        try:
            asyncio.run(run_server_async(server))
        except KeyboardInterrupt:
            print("\nExited.")
    else:
        try:
            start_gui_app()
        except KeyboardInterrupt:
            print("\nExited.")


if __name__ == "__main__":
    main()
