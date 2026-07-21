"""config.py - Environment mode and production safety checks."""
import logging
import os

logger = logging.getLogger("pet_translator.config")

DEFAULT_JWT_SECRET = "pet-translator-secret-key-change-in-production"


def is_production() -> bool:
    return os.environ.get("ENVIRONMENT", "development").strip().lower() == "production"


def check_jwt_secret() -> list[str]:
    """Check JWT secret. Returns list of violation messages (empty = ok)."""
    violations = []
    secret = os.environ.get("JWT_SECRET", "")
    if not secret or secret == DEFAULT_JWT_SECRET:
        msg = (
            f"JWT_SECRET is {'unset' if not secret else 'using the default value'}. "
            f"Set a strong random secret via the JWT_SECRET environment variable."
        )
        violations.append(msg)
    return violations


def check_cors_origins() -> list[str]:
    """Check CORS_ORIGINS. Returns list of violation messages (empty = ok)."""
    violations = []
    origins = os.environ.get("CORS_ORIGINS", "*").strip()
    if not origins or origins == "*":
        msg = (
            f"CORS_ORIGINS is {'unset' if not origins else 'set to *'}. "
            f"Set specific allowed origins via the CORS_ORIGINS environment variable "
            f"(comma-separated, e.g. https://app.example.com,https://admin.example.com)."
        )
        violations.append(msg)
    return violations


def run_security_checks() -> None:
    """Run all security checks. In production, violations raise RuntimeError."""
    all_violations = []
    all_violations.extend(check_jwt_secret())
    all_violations.extend(check_cors_origins())

    if not all_violations:
        return

    message = "Security configuration violations:\n" + "\n".join(
        f"  - {v}" for v in all_violations
    )

    if is_production():
        raise RuntimeError(message)
    else:
        logger.warning(message)
