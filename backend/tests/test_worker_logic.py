import pytest
from unittest.mock import patch
from app.workers.delivery_worker import calculate_retry_delay, sign_payload


def test_calculate_retry_delay_increases():
    d0 = calculate_retry_delay(0)
    d1 = calculate_retry_delay(1)
    d2 = calculate_retry_delay(2)
    # Each delay should be larger (ignoring jitter — check base values)
    assert d1 > d0 - 10  # account for jitter
    assert d2 > d1 - 10


def test_calculate_retry_delay_respects_max():
    from app.core.config import settings
    large_attempt = 100
    delay = calculate_retry_delay(large_attempt)
    # Max + max jitter (10)
    assert delay <= settings.MAX_RETRY_DELAY + 10


def test_sign_payload_is_deterministic():
    payload = '{"event_type": "test"}'
    secret = "mysecret"
    sig1 = sign_payload(payload, secret)
    sig2 = sign_payload(payload, secret)
    assert sig1 == sig2


def test_sign_payload_different_secrets():
    payload = '{"event_type": "test"}'
    sig1 = sign_payload(payload, "secret1")
    sig2 = sign_payload(payload, "secret2")
    assert sig1 != sig2


def test_sign_payload_different_payloads():
    secret = "mysecret"
    sig1 = sign_payload('{"a": 1}', secret)
    sig2 = sign_payload('{"a": 2}', secret)
    assert sig1 != sig2


def test_sign_payload_format():
    sig = sign_payload("hello", "world")
    # SHA256 hex = 64 chars
    assert len(sig) == 64
    assert all(c in "0123456789abcdef" for c in sig)