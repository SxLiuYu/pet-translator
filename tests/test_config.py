"""Tests for production security configuration checks."""
import os
import subprocess
import sys
from pathlib import Path

import pytest


SERVER_DIR = Path(__file__).resolve().parent.parent / "server"


def _run_check(env: dict, check_name: str) -> subprocess.CompletedProcess:
    """Run a security check subprocess that imports config and calls the named function."""
    code = (
        "import sys; sys.path.insert(0, '.'); "
        "from config import check_jwt_secret, check_cors_origins, run_security_checks; "
        f"result = {check_name}(); "
        "print('VIOLATIONS:' + ('|'.join(result) if result else 'OK')); "
        "sys.exit(1 if result else 0)"
    )
    full_env = {**os.environ, "PYTHONPATH": str(SERVER_DIR), **env}
    return subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True, env=full_env,
        cwd=SERVER_DIR,
    )


class TestJWTSecret:
    def test_default_secret_flagged(self):
        result = _run_check({"JWT_SECRET": ""}, "check_jwt_secret")
        assert result.returncode == 1
        assert "JWT_SECRET" in result.stdout

    def test_custom_secret_ok(self):
        result = _run_check({"JWT_SECRET": "my-strong-secret-123"}, "check_jwt_secret")
        assert result.returncode == 0
        assert "VIOLATIONS:OK" in result.stdout


class TestCORSCheck:
    def test_wildcard_flagged(self):
        result = _run_check({"CORS_ORIGINS": "*"}, "check_cors_origins")
        assert result.returncode == 1
        assert "CORS_ORIGINS" in result.stdout

    def test_specific_origin_ok(self):
        result = _run_check({"CORS_ORIGINS": "https://app.example.com"}, "check_cors_origins")
        assert result.returncode == 0
        assert "VIOLATIONS:OK" in result.stdout

    def test_unset_flagged(self):
        result = _run_check({"CORS_ORIGINS": ""}, "check_cors_origins")
        assert result.returncode == 1
        assert "CORS_ORIGINS" in result.stdout


class TestRunSecurityChecks:
    def test_development_mode_warns_only(self):
        result = subprocess.run(
            [sys.executable, "-c",
             "import sys; sys.path.insert(0, '.'); "
             "from config import run_security_checks; run_security_checks(); print('SURVIVED')"],
            capture_output=True, text=True,
            env={**os.environ, "PYTHONPATH": str(SERVER_DIR)},
            cwd=SERVER_DIR,
        )
        assert "SURVIVED" in result.stdout  # development mode should not raise

    def test_production_mode_raises(self):
        result = subprocess.run(
            [sys.executable, "-c",
             "import sys; sys.path.insert(0, '.'); "
             "from config import run_security_checks; run_security_checks(); print('SURVIVED')"],
            capture_output=True, text=True,
            env={**os.environ, "PYTHONPATH": str(SERVER_DIR), "ENVIRONMENT": "production"},
            cwd=SERVER_DIR,
        )
        assert result.returncode != 0
        assert "Security configuration violations" in (result.stdout + result.stderr)
