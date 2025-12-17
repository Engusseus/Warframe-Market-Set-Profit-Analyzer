"""Security middleware for FastAPI application."""
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add security headers to all responses."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # HSTS (HTTP Strict Transport Security) - enforce HTTPS
        # Only set if not localhost to avoid issues during dev, or set with short duration
        # For this implementation, we'll set it but generally it's better handled by Nginx/load balancer
        # However, for defense in depth, we add it here.
        if request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        # Content Security Policy (CSP)
        # This is a basic CSP. In a real app, this needs to be carefully tuned.
        # We start with a relatively permissive one for API usage.
        # response.headers["Content-Security-Policy"] = "default-src 'self'"

        return response
