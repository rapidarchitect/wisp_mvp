"""Unit tests for notification templates."""

from __future__ import annotations

from app.services.notification_templates import render


def test_domain_submitted_renders():
    subject, body = render("domain_submitted", {"domain_name": "Access Control"})
    assert "ready for review" in subject
    assert "Access Control" in body
    assert "submitted" in body
