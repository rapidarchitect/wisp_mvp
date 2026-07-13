"""Email backends for transactional messages."""

_sent_messages: list[dict] = []


class ConsoleEmailBackend:
    """Capture emails in memory for tests and print to stdout for dev."""

    async def send(self, *, to: str, subject: str, body: str) -> None:
        """Store the message and echo it to stdout."""
        message = {"to": to, "subject": subject, "body": body}
        _sent_messages.append(message)
        print(f"[EMAIL] To: {to}\nSubject: {subject}\n{body}\n")


def get_sent_messages() -> list[dict]:
    """Return all messages captured by the console backend."""
    return _sent_messages


def clear_sent_messages() -> None:
    """Clear the captured message list."""
    _sent_messages.clear()
