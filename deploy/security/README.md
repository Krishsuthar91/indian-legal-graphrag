# Security

Reserved for security policy and hardening artifacts.

The active security controls live in `src/middleware/security.py` and are
covered by `tests/test_security_middleware.py`:

- API-key authentication (`X-API-Key`) on protected routes
- in-process per-IP rate limiting (60s sliding window)
- request body size limit
- security response headers

Production hardening checklist: see `docs/PRODUCTION.md`.
