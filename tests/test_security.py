"""
Unit tests for Project Controller Cyber-Resilient Security & Anomaly Firewall
"""

import hmac
import hashlib
import time
import pytest
from gateway.security import ChallengeResponseAuthenticator, AnomalyFirewall


def test_challenge_response_authentication():
    secret = b"test-secret-key-123"
    auth = ChallengeResponseAuthenticator(shared_secret=secret, timeout_sec=1.5)

    # 1. Generate challenge
    challenge = auth.generate_challenge()
    assert challenge["type"] == "AUTH_CHALLENGE"
    nonce = challenge["nonce"]
    ts = challenge["timestamp"]

    # 2. Correct HMAC signature
    payload = f"{nonce}:{ts}".encode("utf-8")
    valid_sig = hmac.new(secret, payload, hashlib.sha256).hexdigest()

    ok, reason = auth.verify_response(nonce, ts, valid_sig)
    assert ok is True
    assert reason == "AUTHENTICATED"

    # 3. Replay attack rejection (re-using the same nonce)
    ok_replay, reason_replay = auth.verify_response(nonce, ts, valid_sig)
    assert ok_replay is False
    assert "REPLAY_ATTACK" in reason_replay


def test_challenge_response_tampering_and_timeout():
    secret = b"test-secret-key-123"
    auth = ChallengeResponseAuthenticator(shared_secret=secret, timeout_sec=0.1)

    challenge = auth.generate_challenge()
    nonce = challenge["nonce"]
    ts = challenge["timestamp"]

    # Tampered signature
    ok, reason = auth.verify_response(nonce, ts, "00112233445566778899aabbccddeeff")
    assert ok is False
    assert "SIGNATURE_MISMATCH" in reason

    # Test timeout expiration
    challenge2 = auth.generate_challenge()
    nonce2 = challenge2["nonce"]
    ts2 = challenge2["timestamp"]
    time.sleep(0.15)
    payload2 = f"{nonce2}:{ts2}".encode("utf-8")
    sig2 = hmac.new(secret, payload2, hashlib.sha256).hexdigest()
    ok_timeout, reason_timeout = auth.verify_response(nonce2, ts2, sig2)
    assert ok_timeout is False
    assert "HANDSHAKE_TIMEOUT" in reason_timeout


def test_anomaly_firewall_sequence_and_rate():
    firewall = AnomalyFirewall(max_rate_hz=100.0, min_inter_arrival_sec=0.005, max_consecutive_anomalies=5)
    client_id = "test_node"

    # In-order packet
    ok, err = firewall.inspect_packet(client_id, seq=1, client_time=time.time())
    assert ok is True

    # Immediate second packet (< min_inter_arrival 0.005s)
    ok_fast, err_fast = firewall.inspect_packet(client_id, seq=2, client_time=time.time())
    assert ok_fast is False
    assert "INTER_ARRIVAL_VIOLATION" in err_fast

    # Out-of-order / replay sequence number
    time.sleep(0.01)
    ok_regress, err_regress = firewall.inspect_packet(client_id, seq=1, client_time=time.time())
    assert ok_regress is False
    assert "SEQUENCE_REGRESSION" in err_regress

    # Valid progression
    time.sleep(0.01)
    ok_valid, err_valid = firewall.inspect_packet(client_id, seq=3, client_time=time.time())
    assert ok_valid is True
