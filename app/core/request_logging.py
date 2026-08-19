"""Request logging middleware.

Logs one line per request: method, path, status code, and duration - the
operational visibility Step 8 (Task 13) asks for. Deliberately logs
`request.url.path` only, never the query string (which could carry a
token/reset-code in a future endpoint) and never any header - in
particular never the `Authorization` header, which carries the Firebase ID
token. No request/response bodies are logged either, so passwords,
private keys, and other request payload fields are never at risk of
ending up in application logs.

INFO for a normal 2xx/3xx response, WARNING for 4xx, ERROR for 5xx -
mirrors the status-code severity so log-level filtering (`LOG_LEVEL`)
behaves the way an operator would expect.
"""

import logging
import time

from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger("app.request")


class RequestLoggingMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        start = time.perf_counter()
        status_code_holder: dict[str, int] = {}

        async def send_wrapper(message) -> None:  # noqa: ANN001
            if message["type"] == "http.response.start":
                status_code_holder["status_code"] = message["status"]
            await send(message)

        await self.app(scope, receive, send_wrapper)

        duration_ms = (time.perf_counter() - start) * 1000
        status_code = status_code_holder.get("status_code", 0)
        log_line = "%s %s -> %s (%.1fms)"
        args = (request.method, request.url.path, status_code, duration_ms)
        if status_code >= 500:
            logger.error(log_line, *args)
        elif status_code >= 400:
            logger.warning(log_line, *args)
        else:
            logger.info(log_line, *args)
