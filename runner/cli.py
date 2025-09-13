from __future__ import annotations

import argparse
import os
from pathlib import Path


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse CLI arguments for the smoke runner."""
    parser = argparse.ArgumentParser(description="Stateless KB smoke runner")
    parser.add_argument("--base-url", default=os.getenv("BASE_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--fixtures", default=str(Path(__file__).resolve().parents[1] / "fixtures"))
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--poll", type=float, default=0.25, dest="poll_interval")
    return parser.parse_args(argv)


