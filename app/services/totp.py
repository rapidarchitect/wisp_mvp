"""TOTP services for two-factor authentication."""

import base64
import secrets

import pyotp


def generate_totp_secret() -> str:
    """Generate a new base32-encoded TOTP secret."""
    # 160 bits of entropy encoded as base32 without padding.
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def get_provisioning_uri(secret: str, email: str, issuer: str) -> str:
    """Return an otpauth:// provisioning URI for an authenticator app."""
    return pyotp.totp.TOTP(secret).provisioning_uri(name=email, issuer_name=issuer)


def verify_totp(secret: str, code: str) -> bool:
    """Verify a TOTP code against a secret."""
    return pyotp.TOTP(secret).verify(code)
