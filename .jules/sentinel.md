## 2024-05-23 - Security Headers Implementation
**Vulnerability:** Missing standard HTTP security headers (HSTS, X-Frame-Options, X-Content-Type-Options, X-XSS-Protection) which exposed the application to clickjacking, MIME sniffing, and MITM attacks.
**Learning:** FastAPI does not include these headers by default. A custom middleware or a library like `secure` is needed. Implemented a custom middleware to avoid dependencies for a simple task.
**Prevention:** Always verify security headers using tools like `curl -I` or browser dev tools. Added `SecurityHeadersMiddleware` to enforce these globally.
