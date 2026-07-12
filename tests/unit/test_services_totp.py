"""Tests for the TOTP service."""

import pyotp

from app.services.totp import generate_totp_secret, get_provisioning_uri, verify_totp


def test_generate_totp_secret_returns_base32_string():
    """generate_totp_secret returns a valid base32 secret."""
    secret = generate_totp_secret()
    assert isinstance(secret, str)
    assert len(secret) > 0
    # pyotp will raise if the secret is not base32-decodable.
    assert pyotp.TOTP(secret).now() is not None


def test_get_provisioning_uri_contains_email_and_issuer():
    """The provisioning URI is an otpauth:// URL with account and issuer."""
    from urllib.parse import quote

    secret = generate_totp_secret()
    email = "admin@palmetto.app.wisp.llc"
    uri = get_provisioning_uri(secret, email, "WISPGen")
    assert uri.startswith("otpauth://totp/")
    assert quote(email) in uri
    assert "issuer=WISPGen" in uri
    assert f"secret={secret}" in uri


def test_verify_totp_accepts_current_code():
    """verify_totp returns True for the currently generated code."""
    secret = generate_totp_secret()
    code = pyotp.TOTP(secret).now()
    assert verify_totp(secret, code) is True


def test_verify_totp_rejects_wrong_code():
    """verify_totp returns False for an arbitrary wrong code."""
    secret = generate_totp_secret()
    assert verify_totp(secret, "000000") is False
