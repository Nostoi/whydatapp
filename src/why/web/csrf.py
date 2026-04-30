from __future__ import annotations

import secrets
from urllib.parse import parse_qs

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

CSRF_COOKIE = "why_csrf"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        token = request.cookies.get(CSRF_COOKIE)
        if request.method not in SAFE_METHODS:
            sent = request.headers.get("x-csrf-token") or await _form_token(request)
            if not token or not sent or not secrets.compare_digest(token, sent):
                return Response("CSRF token missing or invalid", status_code=403)
        response = await call_next(request)
        if not token:
            new_token = secrets.token_urlsafe(32)
            response.set_cookie(
                CSRF_COOKIE, new_token, httponly=False, samesite="strict", path="/"
            )
        return response


async def _form_token(request: Request) -> str | None:
    ct = request.headers.get("content-type", "")
    if not (
        ct.startswith("application/x-www-form-urlencoded")
        or ct.startswith("multipart/form-data")
    ):
        return None
    body = await request.body()
    # Cache the body so downstream handlers can re-read it.
    async def _receive() -> dict:  # type: ignore[return]
        return {"type": "http.request", "body": body, "more_body": False}

    request._receive = _receive  # type: ignore[attr-defined]
    if ct.startswith("application/x-www-form-urlencoded"):
        parsed = parse_qs(body.decode("utf-8", errors="ignore"))
        val = parsed.get("csrf_token", [None])[0]
        return val
    # multipart: do a simple search for the token field — best-effort.
    try:
        text = body.decode("utf-8", errors="ignore")
        import re
        m = re.search(r'name="csrf_token"\r?\n\r?\n([^\r\n]+)', text)
        return m.group(1) if m else None
    except Exception:
        return None
