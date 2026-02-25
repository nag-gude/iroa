"""Allow running the CLI as: python -m iroa analyze ..."""
from __future__ import annotations

import sys

from iroa.cli import app

if __name__ == "__main__":
    # When run as "python -m iroa analyze ...", argv is [python, "-m", "iroa", "analyze", ...].
    # Normalize so Typer sees "iroa analyze ...".
    if len(sys.argv) >= 3 and sys.argv[1] == "-m" and sys.argv[2] == "iroa":
        sys.argv = ["iroa"] + sys.argv[3:]
    app()
