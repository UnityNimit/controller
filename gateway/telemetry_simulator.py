"""
Project Controller - Synthetic Racing Physics & Telemetry Simulator
Generates a continuous, high-fidelity physics telemetry stream replicating
a racing circuit lap (RPM sweeps, gear shifts, cornering tire slip, braking Gs,
curb vibrations, and collision pulses) for testing and academic viva defense.
"""

import math
import time
import asyncio
import logging
from typing import Dict, Any, Optional, Callable

logger = logging.getLogger("Controller.Simulator")


class RacingLapSimulator:
    """
    Simulates a high-performance GT3 car driving around a racing circuit.
    Physics model includes gear shifting, engine RPM curves, tire slip dynamics,
    braking deceleration, and curb strikes.
    """
    def __init__(self, update_rate_hz: float = 60.0):
        self.update_rate_hz = update_rate_hz
        self.dt = 1.0 / update_rate_hz
        
        # Vehicle Constants
        self.max_rpm = 8800.0
        self.idle_rpm = 1000.0
        self.redline_rpm = 8200.0
        self.gear_ratios = [3.2, 2.1, 1.6, 1.25, 1.0, 0.85]  # Gears 1 to 6
        self.final_drive = 3.6
        self.tire_radius = 0.33  # meters

        # State Variables
        self.lap_time: float = 0.0
        self.gear: int = 1
        self.rpm: float = self.idle_rpm
        self.speed_kmh: float = 0.0
        self.slip_ratio: float = 0.0
        self.g_lat: float = 0.0
        self.g_long: float = 0.0
        self.impact_g: float = 0.0
        self.abs_active: bool = False
        self.tcs_active: bool = False
        
        # Track timeline phase (0.0 to 1.0 of lap)
        self.phase: float = 0.0
        self.lap_duration_sec: float = 45.0  # 45 second simulated sprint lap

    def step(self) -> Dict[str, Any]:
        """Advances simulation by one time-step (dt) and returns the telemetry frame."""
        self.lap_time += self.dt
        self.phase = (self.lap_time % self.lap_duration_sec) / self.lap_duration_sec
        p = self.phase

        # Track Sectors:
        # Phase 0.00 - 0.25: Main Straight (Full acceleration 1st -> 5th gear)
        # Phase 0.25 - 0.35: Turn 1 Heavy Braking & Downshift (ABS, negative Gs)
        # Phase 0.35 - 0.55: S-Curves (High lateral Gs, tire slip, understeer)
        # Phase 0.55 - 0.65: Curb strike & Short Chute (rumble)
        # Phase 0.65 - 0.75: Hairpin corner (drift, high slip, handbrake zone)
        # Phase 0.75 - 0.95: Final Sweeper into Straight (full throttle)
        # Phase 0.95 - 1.00: Simulated barrier brush / collision spike test

        self.impact_g = 0.0
        self.abs_active = False
        self.tcs_active = False

        if p < 0.25:
            # Main Straight Acceleration
            accel_pct = p / 0.25
            self.gear = min(6, 1 + int(accel_pct * 4.5))
            # RPM sawtooth sweep per gear
            gear_progress = (accel_pct * 4.5) % 1.0
            self.rpm = self.idle_rpm + gear_progress * (self.redline_rpm - self.idle_rpm + 400)
            self.speed_kmh = 40.0 + accel_pct * 190.0  # up to 230 km/h
            self.g_long = 0.8
            self.g_lat = 0.05 * math.sin(self.lap_time * 2.0)
            self.slip_ratio = 0.05

        elif p < 0.35:
            # Turn 1 Heavy Braking Zone
            brake_pct = (p - 0.25) / 0.10
            self.gear = max(2, 5 - int(brake_pct * 3.0))
            self.rpm = self.redline_rpm - brake_pct * 3500.0
            self.speed_kmh = max(65.0, 230.0 - brake_pct * 165.0)
            self.g_long = -1.6  # Heavy deceleration
            self.g_lat = 0.1
            self.slip_ratio = 0.25
            self.abs_active = True  # ABS active under heavy braking

        elif p < 0.55:
            # S-Curves: High Lateral Acceleration & Understeer
            curve_pct = (p - 0.35) / 0.20
            self.gear = 3
            self.speed_kmh = 85.0 + 20.0 * math.sin(curve_pct * math.pi * 4)
            self.rpm = 5500.0 + 1800.0 * math.sin(curve_pct * math.pi * 4)
            self.g_lat = 1.4 * math.sin(curve_pct * math.pi * 4)  # High lateral Gs
            self.g_long = 0.2
            # Tire slip when cornering hard
            self.slip_ratio = 0.35 + 0.30 * abs(math.sin(curve_pct * math.pi * 4))
            self.tcs_active = self.slip_ratio > 0.50

        elif p < 0.65:
            # Curb Strike / Rumble Strip
            self.gear = 3
            self.speed_kmh = 115.0
            self.rpm = 6400.0
            self.g_lat = 0.4
            self.g_long = 0.5
            # Rapid oscillation simulating rumble strip texture
            self.slip_ratio = 0.15 + 0.25 * math.sin(self.lap_time * 40.0)

        elif p < 0.75:
            # Hairpin Drift Corner (Oversteer & Slip)
            hairpin_pct = (p - 0.65) / 0.10
            self.gear = 2
            self.speed_kmh = 55.0 + hairpin_pct * 25.0
            self.rpm = 6800.0 + hairpin_pct * 1200.0
            self.g_lat = -1.5
            self.g_long = 0.3
            self.slip_ratio = 0.68  # Heavy tire slip
            self.tcs_active = True

        elif p < 0.95:
            # Exit Sweeper into Main Straight
            exit_pct = (p - 0.75) / 0.20
            self.gear = min(5, 2 + int(exit_pct * 3.0))
            self.speed_kmh = 80.0 + exit_pct * 130.0
            self.rpm = self.idle_rpm + ((exit_pct * 3.0) % 1.0) * (self.redline_rpm - self.idle_rpm)
            self.g_lat = 0.3 * (1.0 - exit_pct)
            self.g_long = 0.9
            self.slip_ratio = 0.12

        else:
            # 0.95 - 1.00: Simulated Barrier Clip / Impact Spike
            self.gear = 5
            self.speed_kmh = 190.0
            self.rpm = 7500.0
            self.g_lat = 0.0
            self.g_long = 0.0
            self.slip_ratio = 0.1
            # Trigger collision G-force spike for 0.2 seconds
            if p > 0.97 and p < 0.985:
                self.impact_g = 4.2  # 4.2G impact spike

        # Clamp RPM
        self.rpm = max(self.idle_rpm, min(self.max_rpm, self.rpm))

        return {
            "format": "simulated",
            "speed_kmh": round(self.speed_kmh, 1),
            "rpm": round(self.rpm, 0),
            "max_rpm": self.max_rpm,
            "gear": self.gear,
            "slip_ratio": round(self.slip_ratio, 2),
            "g_lat": round(self.g_lat, 2),
            "g_long": round(self.g_long, 2),
            "impact_g": round(self.impact_g, 2),
            "abs_active": self.abs_active,
            "tcs_active": self.tcs_active,
            "timestamp": time.time()
        }


class TelemetrySimulatorRunner:
    """Async background task that generates telemetry at 60 Hz."""
    def __init__(self, callback: Callable[[Dict[str, Any]], None], rate_hz: float = 60.0):
        self.simulator = RacingLapSimulator(update_rate_hz=rate_hz)
        self.callback = callback
        self.rate_hz = rate_hz
        self.running = False
        self._task: Optional[asyncio.Task] = None

    async def _loop(self) -> None:
        interval = 1.0 / self.rate_hz
        logger.info(f"Synthetic physics telemetry generator started at {self.rate_hz} Hz")
        while self.running:
            start_t = time.perf_counter()
            frame = self.simulator.step()
            try:
                self.callback(frame)
            except Exception as e:
                logger.debug(f"Simulator callback exception: {e}")
            elapsed = time.perf_counter() - start_t
            sleep_time = max(0.001, interval - elapsed)
            await asyncio.sleep(sleep_time)

    def start(self) -> None:
        if not self.running:
            self.running = True
            self._task = asyncio.create_task(self._loop())

    def stop(self) -> None:
        self.running = False
        if self._task:
            self._task.cancel()
            self._task = None
            logger.info("Synthetic physics telemetry generator stopped")
