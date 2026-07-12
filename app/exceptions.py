"""WISPGen exception hierarchy."""


class WispgenError(Exception):
    """Base exception for all WISPGen errors."""


class ValidationError(WispgenError):
    """Input validation or business rule violation."""


class NotFoundError(WispgenError):
    """Requested entity was not found."""


class AuthorizationError(WispgenError):
    """Authentication or authorization failure."""

    def __init__(self, message: str, code: str = "unauthorized") -> None:
        super().__init__(message)
        self.code = code


class ConflictError(WispgenError):
    """Entity is in a conflicting state for the requested operation."""


class ExternalServiceError(WispgenError):
    """Outbound integration failed after retry."""
