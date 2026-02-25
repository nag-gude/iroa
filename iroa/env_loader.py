"""Load environment variables from .env in the project root.

Ensures .env is read from the IROA project root regardless of the current
working directory, so all config (pydantic-settings and os.environ) sees the same values.
"""
from __future__ import annotations

from pathlib import Path


def get_project_root() -> Path:
    """Return the IROA project root (directory containing iroa/ and pyproject.toml)."""
    # This file is at IROA/iroa/env_loader.py -> parent.parent = IROA
    return Path(__file__).resolve().parent.parent


def get_dotenv_path() -> Path:
    """Return the path to the .env file in the project root."""
    return get_project_root() / ".env"


def load_env(override: bool = False) -> None:
    """Load .env from the project root into os.environ.

    Call this at application startup so environment variables are available
    to all code (including code that reads os.environ directly). Safe to call
    multiple times; by default does not override existing env vars (set override=True to override).

    If .env does not exist, no error is raised.
    """
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    path = get_dotenv_path()
    if path.exists():
        load_dotenv(path, override=override)
