"""Request metrics middleware exposing a Prometheus /metrics endpoint."""

from __future__ import annotations

import os
import time
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response

from src.monitoring.metrics import metrics

_METRICS_PATH = "/metrics"


def _proc_memory_bytes() -> int:
    """Return RSS memory in bytes (Linux only; guarded on other platforms)."""
    try:
        with open("/proc/self/status", encoding="utf-8") as fh:  # noqa: PTH123
            for line in fh:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) * 1024
    except OSError:
        pass
    return 0


class MetricsMiddleware(BaseHTTPMiddleware):
    """Records request count/latency and serves the /metrics endpoint."""

    def __init__(self, app: Any, *args: Any, **kwargs: Any) -> None:
        super().__init__(app, *args, **kwargs)
        metrics.set_info("app", os.environ.get("APP_NAME", "explaintool"))

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path == _METRICS_PATH:
            return self._render_metrics()

        start = time.monotonic()
        response = await call_next(request)
        duration_ms = (time.monotonic() - start) * 1000.0

        labels = {
            "method": request.method,
            "path": request.url.path,
            "status": str(response.status_code),
        }
        metrics.inc("http_requests_total", labels=labels)
        metrics.observe("http_request_duration_ms", duration_ms, labels=labels)
        metrics.set("process_rss_bytes", _proc_memory_bytes())
        return response

    def _render_metrics(self) -> PlainTextResponse:
        return PlainTextResponse(metrics.render(), media_type="text/plain; version=0.0.4")
