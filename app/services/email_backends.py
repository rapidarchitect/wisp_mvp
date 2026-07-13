"""Email backends for transactional messages."""

import asyncio

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.config import settings
from app.exceptions import ExternalServiceError

_sent_messages: list[dict] = []


class ConsoleEmailBackend:
    """Capture emails in memory for tests and print to stdout for dev."""

    async def send(self, *, to: str, subject: str, body: str) -> None:
        """Store the message and echo it to stdout."""
        message = {"to": to, "subject": subject, "body": body}
        _sent_messages.append(message)
        print(f"[EMAIL] To: {to}\nSubject: {subject}\n{body}\n")


class SESEmailBackend:
    """Send transactional email via AWS SES."""

    def __init__(self) -> None:
        self._client = None

    def _get_client(self):
        if self._client is None:
            self._client = boto3.client("ses", region_name=settings.ses_region)
        return self._client

    async def send(self, *, to: str, subject: str, body: str) -> None:
        client = self._get_client()
        try:
            await asyncio.to_thread(
                client.send_email,
                Source=settings.email_from,
                Destination={"ToAddresses": [to]},
                Message={
                    "Subject": {"Data": subject},
                    "Body": {"Text": {"Data": body}},
                },
            )
        except (ClientError, BotoCoreError) as exc:
            raise ExternalServiceError(f"SES send failed: {exc}") from exc


_console_backend: ConsoleEmailBackend | None = None
_ses_backend: SESEmailBackend | None = None


def get_email_backend():
    """Return the configured email backend singleton."""
    global _console_backend, _ses_backend
    if settings.email_backend == "ses":
        if _ses_backend is None:
            _ses_backend = SESEmailBackend()
        return _ses_backend
    if _console_backend is None:
        _console_backend = ConsoleEmailBackend()
    return _console_backend


def reset_email_backend() -> None:
    """Reset the configured email backend singleton.

    Intended for tests and for any runtime switch of email_backend.
    """
    global _console_backend, _ses_backend
    _console_backend = None
    _ses_backend = None


def get_sent_messages() -> list[dict]:
    """Return all messages captured by the console backend."""
    return _sent_messages


def clear_sent_messages() -> None:
    """Clear the captured message list."""
    _sent_messages.clear()
