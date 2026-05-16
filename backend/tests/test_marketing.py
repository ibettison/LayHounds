"""Backend tests for new Phase 1 marketing endpoints:
- POST /api/payments/stripe/checkout (placeholder stub)
- POST /api/payments/paypal/checkout (placeholder stub)
- POST /api/contact (persists to MongoDB contact_messages collection)
"""
import os
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    with open('/app/frontend/.env') as f:
        for line in f:
            if line.startswith('REACT_APP_BACKEND_URL='):
                BASE_URL = line.split('=', 1)[1].strip().rstrip('/')
API = f"{BASE_URL}/api"


@pytest.fixture
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ---------- Stripe checkout stub ----------
def test_stripe_checkout_requires_central_mode(client):
    """Without a real Stripe key, the endpoint returns a friendly 500. With
    LICENCE_SERVER_MODE off it would return 400. With both configured, 200."""
    r = client.post(f"{API}/payments/stripe/checkout", timeout=10)
    assert r.status_code in (400, 200, 500), r.text
    if r.status_code == 200:
        d = r.json()
        assert "url" in d and "session_id" in d
    elif r.status_code == 500:
        # Placeholder Stripe key — friendly hint to drop a real one
        assert "STRIPE_API_KEY" in r.json().get("detail", "")


# ---------- PayPal checkout stub ----------
def test_paypal_checkout_returns_placeholder(client):
    r = client.post(f"{API}/payments/paypal/checkout", timeout=10)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["provider"] == "paypal"
    assert d.get("test_mode") is True
    assert d.get("message")
    assert not d.get("url")


# ---------- Contact form ----------
def test_contact_valid_payload(client):
    payload = {"email": "TEST_qa@lay-hounds.co.uk",
               "message": "TEST_ automated qa contact submission"}
    r = client.post(f"{API}/contact", json=payload, timeout=10)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d.get("ok") is True


def test_contact_missing_email(client):
    r = client.post(f"{API}/contact", json={"message": "hello"}, timeout=10)
    # Pydantic validation -> 422
    assert r.status_code == 422


def test_contact_invalid_email(client):
    r = client.post(f"{API}/contact",
                    json={"email": "not-an-email", "message": "hi"}, timeout=10)
    # Server's manual @/. check -> 400
    assert r.status_code == 400


def test_contact_empty_message(client):
    r = client.post(f"{API}/contact",
                    json={"email": "TEST_qa@example.com", "message": ""},
                    timeout=10)
    assert r.status_code == 422


# ---------- Regression: existing endpoints still up ----------
def test_root_api_alive(client):
    r = client.get(f"{API}/", timeout=10)
    assert r.status_code == 200


def test_sessions_list(client):
    r = client.get(f"{API}/sessions", timeout=10)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_daily_stats_alive(client):
    r = client.get(f"{API}/daily-stats", timeout=10)
    assert r.status_code == 200
    assert "days" in r.json()


def test_preview_cap_alive(client):
    r = client.post(f"{API}/preview-cap", json={
        "stake": 0.05, "max_liability_cap": 5.0, "num_favourites": 2,
        "iterations": 100, "max_recovery_level": 3,
    }, timeout=15)
    assert r.status_code == 200
