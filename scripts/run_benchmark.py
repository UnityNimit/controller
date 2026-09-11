#!/usr/bin/env python3
"""
Project Controller - Automated Multi-Client Network Benchmark
Tests end-to-end WebSocket throughput, HMAC authentication, and firewall performance.
"""

import asyncio
import hmac
import hashlib
import json
import time
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from config import settings
import websockets

async def run_benchmark_client(client_idx: int, server_url: str, duration_sec: int = 5):
    client_id = f"benchmark_node_{client_idx}"
    print(f"[*] Client {client_idx} connecting to {server_url}...")
    
    # Disable SSL verification for benchmark self-signed cert
    import ssl
    ssl_context = ssl._create_unverified_context() if server_url.startswith("wss://") else None

    async with websockets.connect(server_url, ssl=ssl_context) as ws:
        # Phase 1: Receive Challenge
        challenge_msg = json.loads(await ws.recv())
        nonce = challenge_msg["nonce"]
        ts = challenge_msg["timestamp"]

        # Phase 2: Compute HMAC Response
        payload = f"{nonce}:{ts}".encode("utf-8")
        sig = hmac.new(settings.security.HMAC_SHARED_SECRET, payload, hashlib.sha256).hexdigest()

        await ws.send(json.dumps({
            "type": "AUTH_RESPONSE",
            "client_id": client_id,
            "nonce": nonce,
            "timestamp": ts,
            "signature": sig
        }))

        # Phase 3: Wait for Auth Success
        auth_succ = json.loads(await ws.recv())
        if auth_succ.get("type") != "AUTH_SUCCESS":
            raise RuntimeError(f"Auth failed: {auth_succ}")

        slot = auth_succ["player_slot"]
        print(f"[+] Client {client_idx} allocated Player Slot: {slot}")

        # Phase 4: Stream 60Hz input for duration
        start_time = time.perf_counter()
        seq = 0
        packets_sent = 0
        interval = 1.0 / 60.0

        while (time.perf_counter() - start_time) < duration_sec:
            seq += 1
            pkt = {
                "type": "INPUT",
                "seq": seq,
                "ts": time.time(),
                "angle": 15.0 * ((seq % 40) - 20) / 20.0,
                "throttle": 0.8,
                "brake": 0.0,
                "accel": {"x": 0.0, "y": 0.0, "z": 9.8},
                "buttons": {"SHIFT_UP": False, "HANDBRAKE": False}
            }
            await ws.send(json.dumps(pkt))
            packets_sent += 1
            await asyncio.sleep(interval)

        elapsed = time.perf_counter() - start_time
        effective_hz = packets_sent / elapsed
        print(f"[OK] Client {client_idx} (P{slot}): Sent {packets_sent} pkts in {elapsed:.2f}s ({effective_hz:.1f} Hz)")
        return packets_sent, effective_hz

async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Multi-Client Teleoperation Load Benchmark")
    parser.add_argument("--url", default="ws://127.0.0.1:8080/ws", help="Gateway WebSocket URL")
    parser.add_argument("--clients", type=int, default=2, help="Number of concurrent clients (1 to 4)")
    parser.add_argument("--duration", type=int, default=5, help="Test duration in seconds")
    args = parser.parse_args()

    print("=" * 70)
    print(f"  PROJECT CONTROLLER // NETWORK BENCHMARK ({args.clients} SIMULTANEOUS CLIENTS)")
    print("=" * 70)

    tasks = [
        run_benchmark_client(i + 1, args.url, duration_sec=args.duration)
        for i in range(min(4, max(1, args.clients)))
    ]

    try:
        results = await asyncio.gather(*tasks)
        total_pkts = sum(r[0] for r in results)
        avg_rate = sum(r[1] for r in results) / len(results)
        print("-" * 70)
        print(f"  Aggregated Bus Throughput : {total_pkts} total packets across {len(results)} clients")
        print(f"  Mean Per-Client Frequency : {avg_rate:.1f} Hz (Target: 60 Hz)")
        print("=" * 70)
    except Exception as e:
        print(f"[!] Benchmark error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
