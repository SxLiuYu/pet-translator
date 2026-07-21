# Pet Translator Production Security Hardening Design

## Context

The service already supports audio classification, visual detection, audio/visual fusion,
JWT authentication, and WebSocket delivery, with 55 passing tests and a working CI/Docker
pipeline. The current work adds the production-readiness security boundary that the
reliability optimization iteration explicitly deferred.

This design follows the Superpowers brainstorming and review principles: keep the scope
small, compare alternatives, define observable behavior first, and verify every claim.

## Considered Approaches

### 1. Phased hardening, environment-gated (selected)

Introduce an `ENVIRONMENT` switch (`development`/`production`). In production, unsafe
defaults (hardcoded JWT secret, wildcard CORS) fail fast at startup. In development,
they keep working with a warning. Add lightweight in-memory rate limiting and standard
security response headers behind the same switch.

Trade-off: operators must set environment variables before production deploy, but the
failure mode is loud and explicit instead of silent exposure.

### 2. Full reverse-proxy delegation

Offload TLS, rate limiting, and security headers entirely to nginx/Caddy in front of the
FastAPI process. The application keeps its current permissive defaults.

Trade-off: correct for mature deployments, but leaves the application itself unsafe when
run directly (Docker `CMD` exposes `:8000` with no proxy), and the current docker-compose
does not include a proxy. This is a future option, not a replacement for app-level guards.

### 3. Big-bang security rewrite

Replace CORS, JWT, and auth dependencies in one pass and add a full WAF.

Trade-off: high regression risk against the 55-test baseline for marginal benefit over
targeted guards. YAGNI for an MVP production boundary.

## Selected Design

### Environment switch

- Read `ENVIRONMENT` (values: `development`, `production`). Default: `development`.
- A single helper `is_production()` centralizes the check so tests and startup share it.

### JWT secret enforcement

- `JWT_SECRET` remains the source of truth in `auth/dependencies.py`.
- In production, if `JWT_SECRET` is empty or equals the documented default
  `pet-translator-secret-key-change-in-production`, startup raises and the process exits.
- In development, the default is still allowed but logs a warning.

### CORS enforcement

- `CORS_ORIGINS` parsing stays in `app.py`.
- In production, a value of `*` (or an empty list) raises at startup.
- In development, `*` is still allowed and logs a warning.

### Rate limiting

- Add `slowapi` to the test and production requirements.
- Limits (per client IP, in-memory sliding window):
  - `POST /api/auth/login` and `POST /api/auth/register`: 5/minute
  - `POST /api/upload_audio`: 10/minute
  - `POST /api/camera/detect`: 30/minute
  - All other routes: 100/minute
- Rate-limit responses use the standard `429 Too Many Requests` status.
- Limits are no-ops in tests via dependency injection of a shared limiter instance.

### Security response headers

- Add a small `SecureHeadersMiddleware` that sets:
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `X-XSS-Protection: 1; mode=block`
  - `Referrer-Policy: strict-origin-when-cross-origin`
  - `Strict-Transport-Security: max-age=31536000; includeSubDomains` (production only)
  - `Content-Security-Policy: default-src 'self'; frame-ancestors 'none'` (production only)

### Startup security self-check

- A `run_security_checks()` function runs during `lifespan` startup, after CORS and auth
  setup, before accepting traffic.
- It collects violations; in production any violation raises, in development it logs.
- The check covers: JWT secret, CORS origins, and (informational) whether rate limiting
  is active.

## Error Handling

- Startup security violations in production raise `RuntimeError` with a clear message
  listing every failing check, so the operator sees all problems in one start attempt.
- Rate-limit overages return `429` with a `Retry-After` header.
- Missing `slowapi` import degrades gracefully: startup logs a warning and the app runs
  without rate limiting (tests still require it, so CI catches a missing dependency).

## Acceptance Criteria

1. In `ENVIRONMENT=production`, an unset or default `JWT_SECRET` prevents startup with a
   clear error.
2. In `ENVIRONMENT=production`, `CORS_ORIGINS=*` or empty prevents startup with a clear
   error.
3. In `ENVIRONMENT=development`, the same unsafe configs start with logged warnings.
4. Auth, upload, and detect endpoints return `429` after their configured burst.
5. Every response includes the security headers; HSTS and CSP appear only in production.
6. The existing 55-test suite still passes, plus new tests for the security checks,
   rate limiting, and headers.
7. `server/requirements.txt`, `server/requirements-test.txt`, and `.env.example`
   document the new variables.
8. Design, implementation, and acceptance evidence are documented.

## Out of Scope

- TLS termination / reverse proxy (nginx/Caddy) deployment
- Persistent or distributed rate limiting (Redis-backed)
- User-level Pet/Event/Report authorization (later phase)
- Fusion history persistence (later phase)
- Continuous camera analysis worker (later phase)
- Docker image size / CPU-only dependency optimization (later phase)
