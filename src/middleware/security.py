"""Security middleware for the API.

Provides (all additive, controlled by settings):
- API key authentication for protected routes (settings.API_KEY_AUTH_ENABLED)
- simple in-process rate limiting (settings.RATE_LIMIT_ENABLED)
- request body size limit (settings.REQUEST_MAX_BODY_BYTES)
- security response headers
"""

from __future__ import annotations

import secrets
import time
from collections import defaultdict, deque
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from src.config.settings import settings

# Routes that never require an API key (probes + OpenAPI docs).
_PUBLIC_PATH_PREFIXES = ("/api/v1/health", "/api/v1/ready", "/api/v1/live")
_OPTIONAL_AUTH_PATH_PREFIXES = ("/api/v1/check",)
# Multipart uploads are validated against their own limit inside the endpoint.
_BODY_SIZE_EXEMPT_PREFIXES = ("/api/v1/documents/upload",)


class RateLimitError(Exception):
    """Raised when a client exceeds the configured request rate limit."""


class APIKeyError(Exception):
    """Raised when a protected route is called without a valid API key."""


class RequestTooLargeError(Exception):
    """Raised when an incoming request body exceeds the configured limit."""


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class SecurityMiddleware(BaseHTTPMiddleware):
    """Enforce API key, rate limit, body size, and security headers."""

    def __init__(self, app: Any, *args: Any, **kwargs: Any) -> None:
        super().__init__(app, *args, **kwargs)
        self._window_start: dict[str, float] = {}
        self._window_hits: dict[str, deque[float]] = defaultdict(deque)
        self._api_key_enabled = settings.API_KEY_AUTH_ENABLED
        self._api_key = settings.API_KEY
        self._rate_enabled = settings.RATE_LIMIT_ENABLED
        self._rate_per_minute = max(settings.RATE_LIMIT_PER_MINUTE, 1)
        self._max_body_bytes = settings.REQUEST_MAX_BODY_BYTES

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        try:
            self._enforce_api_key(request)
            self._enforce_rate_limit(request)
            await self._enforce_body_size(request)
        except APIKeyError:
            return JSONResponse(status_code=401, content={"detail": "Missing or invalid API key"})
        except RateLimitError:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded. Please retry later.",
                    "code": "rate_limited",
                },
            )
        except RequestTooLargeError:
            return JSONResponse(
                status_code=413,
                content={"detail": "Request body too large.", "code": "payload_too_large"},
            )

        response = await call_next(request)
        self._apply_security_headers(response)
        return response

    def _enforce_api_key(self, request: Request) -> None:
        if not self._api_key_enabled:
            return
        path = request.url.path
        if path.startswith(_PUBLIC_PATH_PREFIXES) or path.startswith(_OPTIONAL_AUTH_PATH_PREFIXES):
            return
        provided = request.headers.get("x-api-key", "")
        if not provided or not secrets.compare_digest(provided, self._api_key):
            raise APIKeyError()

    def _enforce_rate_limit(self, request: Request) -> None:
        if not self._rate_enabled:
            return
        now = time.monotonic()
        ip = _client_ip(request)
        window_start, hits = self._window_start.get(ip), self._window_hits[ip]
        if window_start is None or now - window_start >= 60:
            self._window_start[ip] = now
            window_start = now
            hits.clear()
        while hits and now - hits[0] >= 60:
            hits.popleft()
        hits.append(now)
        if len(hits) > self._rate_per_minute:
            raise RateLimitError()

    async def _enforce_body_size(self, request: Request) -> None:
        if request.url.path.startswith(_BODY_SIZE_EXEMPT_PREFIXES):
            return
        content_length = request.headers.get("content-length")
        if (
            content_length
            and content_length.isdigit()
            and int(content_length) > self._max_body_bytes
        ):
            raise RequestTooLargeError()

    @staticmethod
    def _apply_security_headers(response: Response) -> None:
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("X-XSS-Protection", "1; mode=block")
        response.headers.setdefault(
            "Permissions-Policy", "geolocation=(), microphone=(), camera=()"
        )
