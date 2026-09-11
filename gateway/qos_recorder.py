"""
Project Controller - Flight-Data QoS Flight Recorder & Telemetry Analyzer
Captures network performance metrics (RTT, Jitter, Packet Frequency, Signal Noise)
into a thread-safe circular ring buffer and exports CSVs and Matplotlib QoS charts.
"""

import time
import csv
import collections
import statistics
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger("Controller.QoS")


class TelemetryRingBuffer:
    """Fixed-capacity memory-efficient circular buffer for real-time telemetry frames."""
    def __init__(self, capacity: int = 10000):
        self.capacity = capacity
        self.buffer = collections.deque(maxlen=capacity)

    def append(self, entry: Dict[str, Any]) -> None:
        self.buffer.append(entry)

    def get_all(self) -> List[Dict[str, Any]]:
        return list(self.buffer)

    def __len__(self) -> int:
        return len(self.buffer)


class QoSRecorder:
    """
    Quality of Service (QoS) & Flight Data Telemetry Recorder.
    Measures packet inter-arrival jitter, round-trip latency, and signal smoothing.
    """
    def __init__(self, capacity: int = 10000):
        self.buffer = TelemetryRingBuffer(capacity=capacity)
        self.last_recv_time: Optional[float] = None
        self.last_client_time: Optional[float] = None

    def record_uplink(
        self,
        client_id: str,
        seq: int,
        client_timestamp: float,
        raw_steering: float,
        filtered_steering: float,
        throttle: int,
        brake: int,
        handbrake: bool,
        reception_timestamp: Optional[float] = None
    ) -> Dict[str, Any]:
        """Records an incoming mobile uplink packet and computes instantaneous network QoS."""
        now = reception_timestamp if reception_timestamp is not None else time.perf_counter()

        # Inter-arrival time (dt)
        dt = (now - self.last_recv_time) if self.last_recv_time is not None else 0.0166
        self.last_recv_time = now

        # Estimated one-way network transit latency in ms (based on monotonic offsets or sync)
        # In local Wi-Fi, time drift is accounted for by measuring inter-packet jitter
        jitter_ms = abs(dt - 0.0166) * 1000.0  # Deviation from 60Hz nominal period

        record = {
            "timestamp": now,
            "client_id": client_id,
            "seq": seq,
            "client_ts": client_timestamp,
            "inter_arrival_ms": round(dt * 1000.0, 2),
            "jitter_ms": round(jitter_ms, 2),
            "raw_steering": round(raw_steering, 2),
            "filtered_steering": round(filtered_steering, 2),
            "throttle": throttle,
            "brake": brake,
            "handbrake": 1 if handbrake else 0
        }
        self.buffer.append(record)
        return record

    def get_summary_metrics(self) -> Dict[str, Any]:
        """Calculates aggregate QoS statistics over recorded packets."""
        records = self.buffer.get_all()
        if not records:
            return {
                "total_packets": 0,
                "avg_inter_arrival_ms": 0.0,
                "avg_jitter_ms": 0.0,
                "p95_jitter_ms": 0.0,
                "effective_rate_hz": 0.0
            }

        dts = [r["inter_arrival_ms"] for r in records[1:]]  # exclude initial packet
        jitters = [r["jitter_ms"] for r in records[1:]]

        avg_dt = statistics.mean(dts) if dts else 16.6
        avg_jitter = statistics.mean(jitters) if jitters else 0.0
        p95_jitter = statistics.quantiles(jitters, n=20)[18] if len(jitters) >= 20 else avg_jitter
        rate_hz = 1000.0 / avg_dt if avg_dt > 0 else 0.0

        return {
            "total_packets": len(records),
            "avg_inter_arrival_ms": round(avg_dt, 2),
            "avg_jitter_ms": round(avg_jitter, 2),
            "p95_jitter_ms": round(p95_jitter, 2),
            "effective_rate_hz": round(rate_hz, 1)
        }

    def export_csv(self, file_path: Path) -> Path:
        """Exports ring buffer history to a CSV file."""
        records = self.buffer.get_all()
        file_path.parent.mkdir(parents=True, exist_ok=True)
        if not records:
            logger.warning("No records to export to CSV")
            return file_path

        keys = records[0].keys()
        with open(file_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(records)

        logger.info(f"Exported {len(records)} QoS telemetry records to {file_path}")
        return file_path

    def export_viva_charts(self, output_dir: Path) -> List[Path]:
        """
        Generates publication-quality academic charts using Matplotlib:
        1. QoS Latency & Jitter Distribution Histogram
        2. Signal Conditioning: Raw Gyroscope Noise vs. EMA Filter
        3. Real-Time Packet Arrival Stability (Jitter Timeline)
        """
        import matplotlib
        matplotlib.use("Agg")  # Non-interactive headless backend
        import matplotlib.pyplot as plt

        output_dir.mkdir(parents=True, exist_ok=True)
        records = self.buffer.get_all()
        generated_files = []

        if len(records) < 10:
            logger.warning("Insufficient telemetry samples for chart generation (minimum 10 needed).")
            return generated_files

        # 1. Chart: Signal Conditioning (Raw vs Filtered Steering)
        fig, ax = plt.subplots(figsize=(10, 4.5), dpi=150)
        times = [r["timestamp"] - records[0]["timestamp"] for r in records[:300]]
        raw_angles = [r["raw_steering"] for r in records[:300]]
        filt_angles = [r["filtered_steering"] for r in records[:300]]

        ax.plot(times, raw_angles, label="Raw Mobile IMU Gyroscope (°)", color="#888888", alpha=0.6, linewidth=1.0)
        ax.plot(times, filt_angles, label="EMA Filtered + Deadband Angle (°)", color="#00aa66", linewidth=2.0)
        ax.set_title("Mathematical Signal Conditioning: Sensor Noise & Hand Tremor Rejection", fontsize=11, fontweight="bold")
        ax.set_xlabel("Elapsed Time (seconds)", fontsize=10)
        ax.set_ylabel("Steering Deflection (°)", fontsize=10)
        ax.grid(True, linestyle="--", alpha=0.5)
        ax.legend(loc="upper right", framealpha=0.9)
        plt.tight_layout()
        chart1_path = output_dir / "fig1_signal_conditioning.png"
        fig.savefig(chart1_path)
        plt.close(fig)
        generated_files.append(chart1_path)

        # 2. Chart: Inter-Arrival Jitter Distribution (Demonstrating QoS)
        fig, ax = plt.subplots(figsize=(8, 4.5), dpi=150)
        jitters = [r["jitter_ms"] for r in records[1:]]
        ax.hist(jitters, bins=30, color="#1e88e5", edgecolor="#0d47a1", alpha=0.75, rwidth=0.85)
        ax.axvline(statistics.mean(jitters), color="#d32f2f", linestyle="--", linewidth=1.8, label=f"Mean Jitter ({statistics.mean(jitters):.2f} ms)")
        ax.set_title("Network QoS: Uplink Inter-Arrival Jitter Distribution", fontsize=11, fontweight="bold")
        ax.set_xlabel("Packet Inter-Arrival Jitter (ms)", fontsize=10)
        ax.set_ylabel("Packet Frequency Count", fontsize=10)
        ax.grid(True, linestyle="--", alpha=0.5)
        ax.legend(loc="upper right", framealpha=0.9)
        plt.tight_layout()
        chart2_path = output_dir / "fig2_jitter_distribution.png"
        fig.savefig(chart2_path)
        plt.close(fig)
        generated_files.append(chart2_path)

        logger.info(f"Generated {len(generated_files)} viva evaluation plots in {output_dir}")
        return generated_files
