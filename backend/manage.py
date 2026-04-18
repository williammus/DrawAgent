from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PYTEST_BASETEMP = Path.home() / ".codex" / "memories" / "drawagent_pytest_tmp"


def run_command(args: list[str]) -> int:
    completed = subprocess.run(args, cwd=ROOT)
    return completed.returncode


def dev() -> int:
    host = os.getenv("APP_HOST", "127.0.0.1")
    port = os.getenv("APP_PORT", "8000")
    return run_command(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--reload",
            "--host",
            host,
            "--port",
            port,
        ]
    )


def test() -> int:
    PYTEST_BASETEMP.mkdir(parents=True, exist_ok=True)
    return run_command(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests",
            "--basetemp",
            str(PYTEST_BASETEMP),
            "-p",
            "no:cacheprovider",
        ]
    )


def lint() -> int:
    return run_command([sys.executable, "-m", "ruff", "check", "app", "tests", "manage.py"])


def format_code() -> int:
    return run_command([sys.executable, "-m", "ruff", "format", "app", "tests", "manage.py"])


def diag_llm() -> int:
    return run_command([sys.executable, "-m", "app.diagnostics", "llm"])


def diag_image() -> int:
    return run_command([sys.executable, "-m", "app.diagnostics", "image"])


COMMANDS = {
    "dev": dev,
    "test": test,
    "lint": lint,
    "format": format_code,
    "diag-llm": diag_llm,
    "diag-image": diag_image,
}


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in COMMANDS:
        available = ", ".join(COMMANDS)
        print(f"Usage: python backend/manage.py <{available}>")
        return 1

    return COMMANDS[sys.argv[1]]()


if __name__ == "__main__":
    raise SystemExit(main())
