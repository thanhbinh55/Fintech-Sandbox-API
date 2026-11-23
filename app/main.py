"""Main FastAPI Application Entrypoint for Fintech Sandbox API."""
from contextlib import asynccontextmanager
import time
import uuid
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import (
    accounts,
    contacts,
    demo,
    events,
    health,
    offers,
    payment_intents,
    split_bills,
    transactions,
)
from app.core.config import get_settings
from app.core.exceptions import FintechSandboxException
from app.core.logging import logger
from app.database.base import Base
from app.database.session import engine
import app.models  # Ensure all models are registered with Base.metadata

# Ensure tables exist immediately on engine
Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing Fintech Sandbox database schema...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database schema initialized successfully.")
    yield
    logger.info("Shutting down Fintech Sandbox application...")


settings = get_settings()

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=(
        "Stateful Fintech Sandbox Backend simulating modern Vietnamese e-wallet capabilities "
        "(payment lifecycle, smart routing, double-entry ledger, and exact VND group bill splitting). "
        "Built for AI Financial Copilot execution in MoMo Tech Contest 2026.\n\n"
        "**NOTE: ALL BALANCES, TRANSFERS, AND CARDS ARE FICTIONAL SANDBOX SIMULATIONS.**"
    ),
    openapi_url="/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_tracing_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or f"req_{uuid.uuid4().hex[:12]}"
    request.state.request_id = request_id

    start_time = time.time()
    response = await call_next(request)
    duration_ms = (time.time() - start_time) * 1000

    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time-Ms"] = f"{duration_ms:.2f}"
    return response


# Exception Handlers
@app.exception_handler(FintechSandboxException)
async def fintech_exception_handler(request: Request, exc: FintechSandboxException):
    request_id = getattr(request.state, "request_id", f"req_{uuid.uuid4().hex[:12]}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            },
            "request_id": request_id,
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    request_id = getattr(request.state, "request_id", f"req_{uuid.uuid4().hex[:12]}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Invalid request parameters or payload format.",
                "details": {"validation_errors": exc.errors()},
            },
            "request_id": request_id,
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    request_id = getattr(request.state, "request_id", f"req_{uuid.uuid4().hex[:12]}")
    code = "HTTP_ERROR"
    if exc.status_code == 401:
        code = "UNAUTHORIZED"
    elif exc.status_code == 403:
        code = "FORBIDDEN"
    elif exc.status_code == 404:
        code = "RESOURCE_NOT_FOUND"

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "code": code,
                "message": str(exc.detail),
                "details": {},
            },
            "request_id": request_id,
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", f"req_{uuid.uuid4().hex[:12]}")
    logger.error(f"Unhandled server error on {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred in the sandbox.",
                "details": {"exception_type": type(exc).__name__},
            },
            "request_id": request_id,
        },
    )


# Register Routers
# Root Health
app.include_router(health.router)

# Versioned API routes under /v1
v1_prefix = settings.API_V1_PREFIX
app.include_router(demo.router, prefix=v1_prefix)
app.include_router(accounts.router, prefix=v1_prefix)
app.include_router(contacts.router, prefix=v1_prefix)
app.include_router(payment_intents.router, prefix=v1_prefix)
app.include_router(offers.router, prefix=v1_prefix)
app.include_router(split_bills.router, prefix=v1_prefix)
app.include_router(transactions.router, prefix=v1_prefix)
app.include_router(events.router, prefix=v1_prefix)
