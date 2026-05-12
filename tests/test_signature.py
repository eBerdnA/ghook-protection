from project import validate_signature
import os

class MockRequest:
    def __init__(self, data, headers):
        self.data = data
        self.headers = headers

def test_validate_signature_success():
    secret = "test-secret"
    data = b'{"foo": "bar"}'
    import hmac
    import hashlib
    sig = hmac.new(secret.encode(), data, hashlib.sha256).hexdigest()
    
    request = MockRequest(data, {"X-Hub-Signature-256": f"sha256={sig}"})
    assert validate_signature(request) is True

def test_validate_signature_missing_header():
    request = MockRequest(b'{}', {})
    assert validate_signature(request) is False

def test_validate_signature_malformed_header():
    # No sha256= prefix
    request = MockRequest(b'{}', {"X-Hub-Signature-256": "wrong"})
    assert validate_signature(request) is False
    
    # Empty
    request = MockRequest(b'{}', {"X-Hub-Signature-256": ""})
    assert validate_signature(request) is False
    
    # Wrong length (too short)
    request = MockRequest(b'{}', {"X-Hub-Signature-256": "sha256=abc"})
    assert validate_signature(request) is False

def test_validate_signature_wrong_secret():
    data = b'{"foo": "bar"}'
    import hmac
    import hashlib
    sig = hmac.new(b"wrong-secret", data, hashlib.sha256).hexdigest()
    
    request = MockRequest(data, {"X-Hub-Signature-256": f"sha256={sig}"})
    assert validate_signature(request) is False

def test_validate_signature_tampered_body():
    secret = "test-secret"
    data = b'{"foo": "bar"}'
    import hmac
    import hashlib
    sig = hmac.new(secret.encode(), data, hashlib.sha256).hexdigest()
    
    # Body tampered
    tampered_data = b'{"foo": "baz"}'
    request = MockRequest(tampered_data, {"X-Hub-Signature-256": f"sha256={sig}"})
    assert validate_signature(request) is False

def test_validate_signature_constant_time():
    # Behavioral test: both wrong-length and right-length-wrong-value signatures must return False.
    # We can't easily measure time in a unit test, but we can verify both return False.
    
    # Right length, wrong value
    request1 = MockRequest(b'{}', {"X-Hub-Signature-256": "sha256=" + "a" * 64})
    assert validate_signature(request1) is False
    
    # Wrong length
    request2 = MockRequest(b'{}', {"X-Hub-Signature-256": "sha256=abc"})
    assert validate_signature(request2) is False
