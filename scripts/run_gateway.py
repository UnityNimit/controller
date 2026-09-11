#!/usr/bin/env python3
"""
Project Controller - Primary Gateway Server CLI Entrypoint
High-Performance Cyber-Physical Teleoperation Framework
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from config import settings
from gateway.server import ControllerGatewayServer

def parse_args():
    parser = argparse.ArgumentParser(
        description="Project Controller - High-Performance Cyber-Physical Teleoperation Gateway",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("--port", type=int, default=None, help="Server port (defaults to 8443 for HTTPS, 8080 for HTTP)")
    parser.add_argument("--no-ssl", action="store_true", help="Disable TLS/HTTPS (run over standard HTTP/WS)")
    parser.add_argument("--sim", action="store_true", default=False, help="Enable synthetic racing physics simulator (demo only)")
    parser.add_argument("--mock", action="store_true", help="Force in-memory mock gamepad controller (for testing without OS drivers)")
    parser.add_argument("--alpha", type=float, default=settings.filters.EMA_ALPHA, help="EMA filter smoothing factor (0.1 to 0.95)")
    parser.add_argument("--deadband", type=float, default=settings.filters.STEERING_DEADBAND_DEG, help="Steering deadband in degrees")
    parser.add_argument("--debug", action="store_true", help="Enable verbose debug logging")
    return parser.parse_args()

async def main():
    args = parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logging.getLogger("Controller").setLevel(logging.DEBUG)

    # Apply command-line overrides to settings
    settings.filters.EMA_ALPHA = args.alpha
    settings.filters.STEERING_DEADBAND_DEG = args.deadband

    use_ssl = not args.no_ssl

    server = ControllerGatewayServer(
        use_ssl=use_ssl,
        port=args.port,
        enable_simulator=args.sim,
        force_mock_input=args.mock
    )

    try:
        await server.start()
        # Keep server running until interrupted
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        print("\n[*] Shutting down Project Controller Gateway...")
        await server.stop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExited gracefully.")
