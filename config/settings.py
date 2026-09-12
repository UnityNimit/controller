"""
Controller - Global Configuration & Parameter Presets
High-Performance Cyber-Physical Teleoperation Framework
"""

import sys
import os
from pathlib import Path
from dataclasses import dataclass, field

APP_NAME: str = "Controller"
APP_VERSION: str = "1.0.0"

if getattr(sys, 'frozen', False):
    BUNDLE_DIR = Path(sys._MEIPASS)
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BUNDLE_DIR = Path(__file__).resolve().parent.parent
    BASE_DIR = Path(__file__).resolve().parent.parent

@dataclass
class NetworkConfig:
    # Gateway Server
    HOST: str = "0.0.0.0"
    HTTP_PORT: int = 8080
    HTTPS_PORT: int = 8443
    USE_SSL: bool = True
    
    # Game Telemetry Downlink (standard OutSim / Forza / Dirt port)
    TELEMETRY_UDP_PORT: int = 20777
    TELEMETRY_BROADCAST_RATE_HZ: float = 60.0
    
    # SSL Certificate Paths
    CERT_DIR: Path = BASE_DIR / "certs"
    CERT_FILE: Path = BASE_DIR / "certs" / "controller_cert.pem"
    KEY_FILE: Path = BASE_DIR / "certs" / "controller_key.pem"


@dataclass
class FilterConfig:
    # Exponential Moving Average (EMA) coefficient
    # Lower = smoother, higher = lower latency. 0.35 is optimal for 60Hz mobile IMU
    EMA_ALPHA: float = 0.35
    
    # Angular Deadband Window in degrees (filters hand tremors around neutral center)
    STEERING_DEADBAND_DEG: float = 1.2
    
    # Maximum physical wrist tilt in degrees mapped to full left/right lock
    STEERING_MAX_ANGLE_DEG: float = 35.0
    
    # Non-linear dynamic sensitivity exponent (gamma)
    # 1.0 = linear, > 1.0 = precision center with progressive snap
    STEERING_CURVE_GAMMA: float = 1.45
    
    # Sharp Acceleration Jerk Threshold (da/dt in G/s) to trigger Handbrake
    JERK_HANDBRAKE_THRESHOLD: float = 2.6
    
    # Proximity / Ambient Light threshold (lux) for high-beam thumb trigger
    LIGHT_SENSOR_LUX_THRESHOLD: float = 10.0


@dataclass
class SecurityConfig:
    # Master HMAC Pre-Shared Key for zero-trust session challenge-response
    # Can be overridden by environment variable
    HMAC_SHARED_SECRET: bytes = os.getenv("CONTROLLER_SECRET", "controller-cyber-physical-key-2026").encode("utf-8")
    
    # Handshake expiration timeout in seconds
    HANDSHAKE_TIMEOUT_SEC: float = 3.0
    
    # Anomaly Firewall: Max allowed client packet frequency (Hz) - Unconstrained 1000Hz peak
    MAX_PACKET_RATE_HZ: float = 1000.0
    
    # Anomaly Firewall: Minimum valid packet inter-arrival time (seconds) - 0.1ms ceiling
    MIN_INTER_ARRIVAL_SEC: float = 0.0001
    
    # Maximum consecutive timing violations before dropping / blacklisting client
    MAX_ANOMALY_BURSTS: int = 50


@dataclass
class MultiClientConfig:
    # Supported simultaneous hardware virtual gamepads
    MAX_PLAYERS: int = 4
    
    # Client heartbeat timeout in seconds before releasing controller slot
    CLIENT_TIMEOUT_SEC: float = 10.0
    
    # Player slot color telemetry markers (Hex colors for minimal HUD styling)
    PLAYER_COLORS: list = field(default_factory=lambda: [
        "#00ffcc",  # P1 - Cyan
        "#ff4444",  # P2 - Crimson
        "#ffcc00",  # P3 - Amber
        "#cc44ff"   # P4 - Violet
    ])


@dataclass
class QoSConfig:
    # Capacity of active in-memory flight telemetry ring buffer
    RING_BUFFER_SIZE: int = 10000
    
    # Directory for logs and Viva graph exports
    LOG_DIR: Path = BASE_DIR / "logs"
    EXPORT_CSV: bool = True


# Unified Settings Instance
network = NetworkConfig()
filters = FilterConfig()
security = SecurityConfig()
clients = MultiClientConfig()
qos = QoSConfig()

# Ensure required directories exist
network.CERT_DIR.mkdir(parents=True, exist_ok=True)
qos.LOG_DIR.mkdir(parents=True, exist_ok=True)
