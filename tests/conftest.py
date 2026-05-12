import os
import pytest
import hmac
import hashlib
import json as _json

# Set environment variables BEFORE importing the app
os.environ["APP_URL"] = "http://test.local"
os.environ["GITHUB_SECRET"] = "test-secret"
os.environ["GITHUB_TOKEN"] = "test-token"
os.environ["GITHUB_OWNER"] = "test-owner"

from project import app as flask_app

@pytest.fixture
def app():
    flask_app.testing = True
    flask_app.debug = False
    return flask_app

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def signed_request(client):
    def _signed_request(path, payload, secret, event="repository", content_type="application/json"):
        body = _json.dumps(payload).encode("utf-8")
        sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        headers = {
            "Content-Type": content_type,
            "X-Github-Event": event,
        }
        if sig is not None:
            headers["X-Hub-Signature-256"] = sig
        
        return client.post(
            path,
            data=body,
            headers=headers,
        )
    return _signed_request

@pytest.fixture
def raw_signed_request(client):
    def _raw_signed_request(path, body, secret, event="repository", content_type="application/json", sig_override=None):
        if sig_override is not None:
            sig = sig_override
        elif secret is not None:
            sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        else:
            sig = None
            
        headers = {
            "Content-Type": content_type,
            "X-Github-Event": event,
        }
        if sig is not None:
            headers["X-Hub-Signature-256"] = sig
            
        return client.post(
            path,
            data=body,
            headers=headers,
        )
    return _raw_signed_request
