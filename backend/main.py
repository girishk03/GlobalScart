from __future__ import annotations

import logging
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Tuple

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.requests import Request
from fastapi.staticfiles import StaticFiles

from .settings import load_settings
from .routes.addresses import router as addresses_router
from .routes.api_admin import router as api_admin_router
from .routes.api_auth import router as api_auth_router
from .routes.api_customer import router as api_customer_router
from .routes.api_events import router as api_events_router
from .routes.api_payments import router as api_payments_router
from .analytics.admin_analytics import router as admin_analytics_router


_PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(_PROJECT_ROOT / ".env")

try:
    _SETTINGS = load_settings()
except Exception as e:
    # Fail fast in prod-like environments. In dev, show a clear startup error.
    raise RuntimeError(f"Invalid environment configuration: {e}")

app = FastAPI(title="GlobalCart Demo API")

_log = logging.getLogger("globalcart")
if not _log.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
    response = await call_next(request)
    response.headers["X-Request-ID"] = rid
    _log.info("rid=%s method=%s path=%s status=%s", rid, request.method, request.url.path, response.status_code)
    return response


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    rid = request.headers.get("x-request-id")
    return JSONResponse(
        status_code=int(getattr(exc, "status_code", 500) or 500),
        content={
            "error": {
                "type": "http_error",
                "message": str(getattr(exc, "detail", "Request failed")),
                "request_id": rid,
            }
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    rid = request.headers.get("x-request-id")
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "type": "validation_error",
                "message": "Invalid request",
                "request_id": rid,
                "details": exc.errors(),
            }
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    rid = request.headers.get("x-request-id")
    _log.exception("Unhandled exception rid=%s path=%s", rid, request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "type": "internal_error",
                "message": "Internal server error",
                "request_id": rid,
            }
        },
    )


_RL_BUCKET: Dict[Tuple[str, str], Tuple[float, int]] = {}


@app.middleware("http")
async def security_headers_and_rate_limit_middleware(request: Request, call_next):
    # Basic in-memory rate limiting (best effort; suitable for demo). Applies to /api/* only.
    try:
        if _SETTINGS.rate_limit_enabled and request.url.path.startswith("/api/"):
            ip = request.headers.get("x-forwarded-for") or (request.client.host if request.client else "")
            ip = (ip or "").split(",")[0].strip() or "unknown"
            key = (ip, request.url.path)
            now = time.time()
            window_start, count = _RL_BUCKET.get(key, (now, 0))
            if now - window_start >= float(_SETTINGS.rate_limit_window_seconds):
                window_start, count = now, 0
            count += 1
            _RL_BUCKET[key] = (window_start, count)
            if count > int(_SETTINGS.rate_limit_requests):
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": {
                            "type": "rate_limited",
                            "message": "Too many requests",
                            "request_id": request.headers.get("x-request-id"),
                        }
                    },
                )
    except Exception:
        # Never block the request due to rate limit errors
        pass

    response = await call_next(request)

    # Security headers (safe defaults for demo)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
    response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
    response.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")

    return response


@app.middleware("http")
async def shop_html_no_cache_middleware(request: Request, call_next):
    try:
        path = request.url.path or ""
        is_shop_html = (
            request.method == "GET"
            and (path == "/shop" or path == "/shop/" or (path.startswith("/shop/") and path.endswith(".html")))
        )
        if is_shop_html:
            # Prevent stale cached HTML for the shop UI (especially on mobile) so changes like
            # updated script version query params take effect immediately.
            hdrs = list(request.scope.get("headers") or [])
            hdrs = [
                (k, v)
                for (k, v) in hdrs
                if k.lower() not in (b"if-none-match", b"if-modified-since")
            ]
            request.scope["headers"] = hdrs
    except Exception:
        pass

    response = await call_next(request)
    try:
        path = request.url.path or ""
        is_shop_html = (
            request.method == "GET"
            and (path == "/shop" or path == "/shop/" or (path.startswith("/shop/") and path.endswith(".html")))
        )
        if is_shop_html:
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
            response.headers.pop("ETag", None)
            response.headers.pop("Last-Modified", None)
    except Exception:
        pass
    return response


@app.middleware("http")
async def admin_no_cache_middleware(request: Request, call_next):
    try:
        path = request.url.path or ""
        if request.method == "GET" and (path == "/admin" or path.startswith("/admin/")):
            # Prevent browser from negotiating 304 Not Modified for admin HTML/CSS/JS.
            # Starlette's StaticFiles supports ETag/Last-Modified, so browsers may cache aggressively.
            hdrs = list(request.scope.get("headers") or [])
            hdrs = [
                (k, v)
                for (k, v) in hdrs
                if k.lower() not in (b"if-none-match", b"if-modified-since")
            ]
            request.scope["headers"] = hdrs
    except Exception:
        pass

    response = await call_next(request)
    try:
        path = request.url.path or ""
        if request.method == "GET" and (path == "/admin" or path.startswith("/admin/")):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
            response.headers.pop("ETag", None)
            response.headers.pop("Last-Modified", None)
    except Exception:
        pass
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"] ,
    allow_headers=["*"],
)

app.include_router(addresses_router)
app.include_router(api_customer_router)
app.include_router(api_events_router)
app.include_router(api_payments_router)
app.include_router(api_admin_router)
app.include_router(admin_analytics_router)
app.include_router(api_auth_router)


_FRONTEND_ROOT = _PROJECT_ROOT / "frontend"
_SHOP_DIR = (_FRONTEND_ROOT / "shop") if (_FRONTEND_ROOT / "shop").exists() else (_FRONTEND_ROOT / "customer")
_ADMIN_DIR = _FRONTEND_ROOT / "admin"
_ASSETS_DIR = _FRONTEND_ROOT / "assets"
_STATIC_ROOT = _PROJECT_ROOT / "static"

if _ASSETS_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(_ASSETS_DIR)), name="assets")

_STATIC_ROOT.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(_STATIC_ROOT)), name="static")

if _SHOP_DIR.exists():
    app.mount("/shop", StaticFiles(directory=str(_SHOP_DIR), html=True), name="shop")

if _ADMIN_DIR.exists():
    app.mount("/admin", StaticFiles(directory=str(_ADMIN_DIR), html=True), name="admin")


@app.get("/")
def home():
    if _SHOP_DIR.exists():
        return RedirectResponse(url="/shop/")
    return {"status": "ok", "message": "Frontend not found. Create frontend/customer and frontend/admin and open /docs for API."}


@app.get("/shop")
def shop_home():
    return RedirectResponse(url="/shop/")


@app.get("/admin")
def admin_home():
    return RedirectResponse(url="/admin/")
