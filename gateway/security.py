"""
Project Controller - Cyber-Resilient Security & Network Anomaly Firewall
Addresses Dr. Abhishek Jain's IoT & Cyber-Physical Security domain.
Features HMAC-SHA256 Challenge-Response Authentication, Replay Attack Mitigation,
and a Real-Time Packet Inter-Arrival Anomaly Firewall.
"""

import hmac
import hashlib
import secrets
import time
import logging
from typing import Dict, Optional, Tuple, Set, Any

logger = logging.getLogger("Controller.Security")


class ChallengeResponseAuthenticator:
    """
    Cryptographic Handshake Engine using HMAC-SHA256.
    Ensures that only authorized mobile edge nodes can claim OS-level
    virtual controller interrupt mapping over shared Wi-Fi networks.
    """
    def __init__(self, shared_secret: bytes, timeout_sec: float = 3.0):
        self.shared_secret = shared_secret
        self.timeout_sec = float(timeout_sec)
        # Pending challenges: {nonce_hex: (creation_timestamp, client_uuid)}
        self._pending_challenges: Dict[str, Tuple[float, Optional[str]]] = {}
        # Used nonces to prevent replay attacks
        self._consumed_nonces: Set[str] = set()

    def generate_challenge(self, client_hint: Optional[str] = None) -> Dict[str, Any]:
        """Generates a cryptographically strong 128-bit challenge nonce."""
        nonce = secrets.token_hex(16)
        now = time.time()
        self._pending_challenges[nonce] = (now, client_hint)
        self._cleanup_stale()
        return {
            "type": "AUTH_CHALLENGE",
            "nonce": nonce,
            "timestamp": now,
            "timeout_ms": int(self.timeout_sec * 1000)
        }

    def verify_response(self, nonce: str, timestamp: float, client_signature: str) -> Tuple[bool, str]:
        """
        Validates the client's cryptographic response:
            R = HMAC-SHA256(Secret, nonce || timestamp)
        """
        now = time.time()

        # Check replay protection
        if nonce in self._consumed_nonces:
            return False, "REPLAY_ATTACK_DETECTED: Nonce already consumed"

        # Check pending challenge
        if nonce not in self._pending_challenges:
            return False, "INVALID_CHALLENGE: Nonce not recognized or expired"

        creation_time, _ = self._pending_challenges[nonce]

        # Check handshake timeout
        if (now - creation_time) > self.timeout_sec:
            del self._pending_challenges[nonce]
            return False, f"HANDSHAKE_TIMEOUT: Elapsed {now - creation_time:.2f}s exceeds {self.timeout_sec}s"

        # Compute expected HMAC
        payload = f"{nonce}:{timestamp}".encode("utf-8")
        expected_sig = hmac.new(self.shared_secret, payload, hashlib.sha256).hexdigest()

        # Constant-time comparison to prevent timing side-channel attacks
        is_valid = hmac.compare_digest(expected_sig.lower(), client_signature.lower())

        # Invalidate nonce
        del self._pending_challenges[nonce]
        self._consumed_nonces.add(nonce)

        if not is_valid:
            return False, "SIGNATURE_MISMATCH: Unauthorized authentication token"

        return True, "AUTHENTICATED"

    def _cleanup_stale(self) -> None:
        """Removes expired challenges older than 2x timeout."""
        now = time.time()
        stale = [n for n, (t, _) in self._pending_challenges.items() if (now - t) > (self.timeout_sec * 2)]
        for n in stale:
            del self._pending_challenges[n]


class AnomalyFirewall:
    """
    Stateful Packet Timing Anomaly Firewall.
    Detects packet stuffing, flood attacks, and sequence number manipulation
    on the high-frequency teleoperation uplink bus.
    """
    def __init__(
        self,
        max_rate_hz: float = 1000.0,
        min_inter_arrival_sec: float = 0.0001,
        max_consecutive_anomalies: int = 50
    ):
        self.max_rate_hz = float(max_rate_hz)
        self.min_inter_arrival = float(min_inter_arrival_sec)
        self.max_consecutive_anomalies = int(max_consecutive_anomalies)

        # Per-client state tracking
        self.last_packet_time: Dict[str, float] = {}
        self.last_seq_num: Dict[str, int] = {}
        self.anomaly_count: Dict[str, int] = {}
        self.packet_count_window: Dict[str, list] = {}

    def inspect_packet(self, client_id: str, seq: int, client_time: float, is_neutral: bool = False) -> Tuple[bool, Optional[str]]:
        """
        Inspects an incoming uplink packet.
        Safety critical neutral/zero-reset packets bypass inter-arrival and rate caps
        to guarantee controller inputs never stick or scroll infinitely.
        Returns:
            (is_accepted: bool, drop_reason: Optional[str])
        """
        now = time.perf_counter()

        # 1. Sequence Number Validation (detects replay / out-of-order injection)
        if client_id in self.last_seq_num:
            expected_seq = self.last_seq_num[client_id] + 1
            if seq <= self.last_seq_num[client_id]:
                self._record_anomaly(client_id)
                return False, f"SEQUENCE_REGRESSION: Received seq {seq}, expected > {self.last_seq_num[client_id]}"

        # Neutral / zero-reset packets always bypass timing guards for player safety
        if not is_neutral:
            # 2. Inter-Arrival Time Guard (detects packet-stuffing / micro-burst flooding)
            if client_id in self.last_packet_time:
                dt = now - self.last_packet_time[client_id]
                if dt < self.min_inter_arrival:
                    self._record_anomaly(client_id)
                    return False, f"INTER_ARRIVAL_VIOLATION: dt {dt*1000:.2f}ms < {self.min_inter_arrival*1000:.1f}ms limit"

            # 3. Frequency Rate Limiting Window (1.0 second sliding window)
            timestamps = self.packet_count_window.setdefault(client_id, [])
            timestamps.append(now)
            # Purge timestamps older than 1.0s
            cutoff = now - 1.0
            while timestamps and timestamps[0] < cutoff:
                timestamps.pop(0)

            if len(timestamps) > self.max_rate_hz:
                self._record_anomaly(client_id)
                return False, f"RATE_LIMIT_EXCEEDED: {len(timestamps)} pkts/sec exceeds {self.max_rate_hz} Hz cap"

        # Packet accepted: Update state
        self.last_packet_time[client_id] = now
        self.last_seq_num[client_id] = seq
        self.anomaly_count[client_id] = max(0, self.anomaly_count.get(client_id, 0) - 1)
        return True, None

    def _record_anomaly(self, client_id: str) -> None:
        self.anomaly_count[client_id] = self.anomaly_count.get(client_id, 0) + 1

    def is_blacklisted(self, client_id: str) -> bool:
        """Returns True if client exceeded maximum anomalous behavior threshold."""
        return self.anomaly_count.get(client_id, 0) >= self.max_consecutive_anomalies

    def reset_client(self, client_id: str) -> None:
        self.last_packet_time.pop(client_id, None)
        self.last_seq_num.pop(client_id, None)
        self.anomaly_count.pop(client_id, None)
        self.packet_count_window.pop(client_id, None)
