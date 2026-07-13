"""WISPGen FastAPI application entry point."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.routers.auth import router as auth_router
from app.api.routers.signup import router as signup_router
from app.config import settings
from app.exceptions import (
    AuthorizationError,
    ConflictError,
    NotFoundError,
    ValidationError,
    WispgenError,
)
from app.middleware.tenancy import TenantMiddleware

app = FastAPI(title="WISPGen", version="0.1.0")

app.state.control_db_path = settings.data_dir + "/control.db"
app.state.data_dir = settings.data_dir

app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(signup_router, prefix="/signup", tags=["signup"])

# C-01: resolve tenant from subdomain and attach per-tenant DB handle.
app.add_middleware(
    TenantMiddleware,
    control_db_path=settings.data_dir + "/control.db",
    data_dir=settings.data_dir,
)


def _error_response(code: str, message: str, status_code: int) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message}},
    )


@app.exception_handler(ValidationError)
async def validation_error_handler(request: Request, exc: ValidationError) -> JSONResponse:
    return _error_response(getattr(exc, "code", "validation_error"), str(exc), 422)


@app.exception_handler(NotFoundError)
async def not_found_error_handler(request: Request, exc: NotFoundError) -> JSONResponse:
    return _error_response("not_found", str(exc), 404)


@app.exception_handler(AuthorizationError)
async def authorization_error_handler(request: Request, exc: AuthorizationError) -> JSONResponse:
    return _error_response(exc.code, str(exc), 401)


@app.exception_handler(ConflictError)
async def conflict_error_handler(request: Request, exc: ConflictError) -> JSONResponse:
    return _error_response(getattr(exc, "code", "conflict"), str(exc), 409)


@app.exception_handler(WispgenError)
async def wispgen_error_handler(request: Request, exc: WispgenError) -> JSONResponse:
    return _error_response("internal_error", str(exc), 500)


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}
