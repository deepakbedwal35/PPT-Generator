"""Local Gemini → Beamer → PDF → PowerPoint application, without Python dependencies.

This module provides the primary entry point and backwards-compatible API facade
delegating to the modular `deck_maker` package.
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import logging
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from urllib.parse import quote, urljoin, urlsplit
import zipfile

# Modular components
import deck_maker
from deck_maker.config import (
    DEFAULT_MODEL,
    DEFAULT_PORT,
    MAX_PDF,
    MAX_SLIDES,
    PPTX_TYPE,
    PUBLIC,
    ROOT,
    executable_path,
    load_environment,
    settings,
)
from deck_maker.compiler import (
    NoRedirect,
    beamer_source,
    compile_latex,
    compile_overleaf,
    compiler_message,
)
from deck_maker.converter import convert_pdf, ensure_pdf
from deck_maker.exceptions import AppError
import deck_maker.generator as _gen
from deck_maker.pptx_builder import content_types, png_dimensions, pptx_from_images
from deck_maker.server import (
    COMPILE_LOCK,
    CONVERT_LOCK,
    Handler,
    ThreadingHTTPServer,
    create_server,
)


def generate_latex(brief: object, slide_count: object) -> str:
    """Generate Beamer LaTeX, resolving generate_latex_once dynamically for patch compatibility."""
    generate_fn = getattr(sys.modules[__name__], "generate_latex_once", _gen.generate_latex_once)
    return _gen.generate_latex(brief, slide_count, generate_fn=generate_fn)


def generate_latex_once(brief: object, slide_count: object, retry: bool = False) -> str:
    """Generate Beamer LaTeX once, resolving urllib and time dynamically for patch compatibility."""
    mod = sys.modules[__name__]
    urlopen_fn = getattr(mod.urllib.request, "urlopen", urllib.request.urlopen)
    sleep_fn = getattr(mod.time, "sleep", time.sleep)
    return _gen.generate_latex_once(
        brief,
        slide_count,
        retry=retry,
        urlopen_fn=urlopen_fn,
        sleep_fn=sleep_fn,
    )


def main() -> None:
    load_environment()
    parser = argparse.ArgumentParser(
        description="Local Gemini -> Beamer -> PDF -> PowerPoint deck maker",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check tool availability and exit",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("PORT", str(DEFAULT_PORT))),
        help=f"Port to bind to (default: {DEFAULT_PORT})",
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
