"""security_headers.py - Middleware that adds security response headers."""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from config import is_production


class SecureHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to every response.

    Development mode: basic headers (no HSTS, relaxed CSP).
    Production mode: full headers including HSTS and strict CSP.
    """

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)

        # Always set
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        if is_production():
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "frame-ancestors 'none'; "
                "script-src 'self'; "
                "style-src 'self' 'unsafe-inline'"
            )

        return response
