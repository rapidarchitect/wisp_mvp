"""WISPGen exception hierarchy."""


class WispgenError(Exception):
    """Base exception for all WISPGen errors."""


class ValidationError(WispgenError):
    """Input validation or business rule violation."""

    def __init__(self, message: str, code: str = "validation_error") -> None:
        super().__init__(message)
        self.code = code


class NotFoundError(WispgenError):
    """Requested entity was not found."""


class AuthorizationError(WispgenError):
    """Authentication or authorization failure."""

    def __init__(self, message: str, code: str = "unauthorized") -> None:
        super().__init__(message)
        self.code = code


class ConflictError(WispgenError):
    """Entity is in a conflicting state for the requested operation."""

    def __init__(self, message: str, code: str = "conflict") -> None:
        super().__init__(message)
        self.code = code


class ExternalServiceError(WispgenError):
    """Outbound integration failed after retry."""

    def __init__(self, message: str, code: str = "external_service_error") -> None:
        super().__init__(message)
        self.code = code
