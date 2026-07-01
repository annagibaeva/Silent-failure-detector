from __future__ import annotations

from pathlib import Path


def load_local_env() -> bool:
    """Load `.env` from the repository root when python-dotenv is installed."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return False
    env_path = Path(__file__).resolve().parents[1] / ".env"
    return load_dotenv(env_path)
