"""Email backends for transactional messages."""

import asyncio

import boto3

from app.config import settings

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

    async def send(self, *, to: str, subject: str, body: str) -> None:
        client = boto3.client("ses", region_name=settings.ses_region)
        await asyncio.to_thread(
            client.send_email,
            Source=settings.email_from,
            Destination={"ToAddresses": [to]},
            Message={
                "Subject": {"Data": subject},
                "Body": {"Text": {"Data": body}},
            },
        )


def get_email_backend():
    """Return the configured email backend."""
    if settings.email_backend == "ses":
        return SESEmailBackend()
    return ConsoleEmailBackend()


def get_sent_messages() -> list[dict]:
    """Return all messages captured by the console backend."""
    return _sent_messages


def clear_sent_messages() -> None:
    """Clear the captured message list."""
    _sent_messages.clear()
