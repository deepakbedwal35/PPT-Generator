"""CLI entry point for running deck_maker via python -m deck_maker."""

from __future__ import annotations

import argparse
import json
import os
import sys

from deck_maker.config import DEFAULT_PORT, load_environment, settings
from deck_maker.server import create_server


def main() -> None:
    load_environment()
    parser = argparse.ArgumentParser(
        prog="deck_maker",
        description="Python Beamer Deck Maker: Presentation brief -> Gemini Beamer -> PDF -> PowerPoint",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Print system configuration status and exit",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("PORT", str(DEFAULT_PORT))),
        help=f"Server port (default: {DEFAULT_PORT} or PORT env var)",
    )
    args = parser.parse_args()

    if args.check:
        print(json.dumps(settings(), indent=2))
        sys.exit(0)

    port = args.port
    print(f"Local: http://127.0.0.1:{port}")
    try:
        with create_server("127.0.0.1", port) as server:
            server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
    except OSError as error:
        sys.exit(f"Could not start on port {port}: {error}. Change PORT in .env.")


if __name__ == "__main__":
    main()
