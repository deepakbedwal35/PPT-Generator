"""Configuration, environment loading, and tool path discovery."""

from __future__ import annotations

import os
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
MAX_PDF = 15 * 1024 * 1024  # 15 MB
MAX_SLIDES = 30
PPTX_TYPE = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
DEFAULT_MODEL = "gemini-3.5-flash-lite"
DEFAULT_PORT = 3000
DEFAULT_LATEX_TIMEOUT_MS = 180000


def executable_path(variable: str, command: str) -> str | None:
    """Find executable path.

    Order of precedence:
    1. Explicit environment variable
    2. System PATH
    3. Standard platform install locations (macOS, Linux, Windows)
    """
    configured = os.getenv(variable, "").strip().strip('"')
    if configured:
        resolved = shutil.which(configured) or (configured if Path(configured).is_file() else None)
        if resolved:
            return resolved

    found = shutil.which(command)
    if found:
        return found

    # Platform-specific fallback discovery
    if os.name == "nt":
        local = Path(os.getenv("LOCALAPPDATA", str(Path.home() / "AppData/Local")))
        if command == "pdflatex":
            candidates = [
                local / "Programs/MiKTeX/miktex/bin/x64/pdflatex.exe",
                Path("C:/Program Files/MiKTeX/miktex/bin/x64/pdflatex.exe"),
            ]
        elif command == "pdftoppm":
            candidates = [
                Path.home()
                / ".cache/codex-runtimes/codex-primary-runtime/dependencies/native/poppler/Library/bin/pdftoppm.exe"
            ]
        else:
            candidates = []
        return next((str(p) for p in candidates if p.is_file()), None)

    # macOS fallbacks (MacTeX, BasicTeX, Homebrew, MacPorts)
    if sys_platform() == "darwin":
        if command == "pdflatex":
            candidates = [
                Path("/Library/TeX/texbin/pdflatex"),
                Path("/opt/homebrew/bin/pdflatex"),
                Path("/usr/local/bin/pdflatex"),
                Path("/opt/local/bin/pdflatex"),
            ]
        elif command == "pdftoppm":
            candidates = [
                Path("/opt/homebrew/bin/pdftoppm"),
                Path("/usr/local/bin/pdftoppm"),
                Path("/opt/local/bin/pdftoppm"),
            ]
        else:
            candidates = []
        return next((str(p) for p in candidates if p.is_file()), None)

    # Linux fallbacks
    if command == "pdflatex":
        candidates = [
            Path("/usr/bin/pdflatex"),
            Path("/usr/local/bin/pdflatex"),
        ]
    elif command == "pdftoppm":
        candidates = [
            Path("/usr/bin/pdftoppm"),
            Path("/usr/local/bin/pdftoppm"),
        ]
    else:
        candidates = []
    return next((str(p) for p in candidates if p.is_file()), None)


def sys_platform() -> str:
    """Return platform name (helper for easy mocking in unit tests)."""
    import sys

    return sys.platform


def load_environment(env_path: Path | None = None) -> None:
    """Load key-value pairs from .env into os.environ if not already present."""
    path = env_path or (ROOT / ".env")
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def settings() -> dict:
    """Return runtime capability status."""
    compiler = executable_path("LATEX_COMMAND", "pdflatex")
    renderer = executable_path("PDFTOPPM_PATH", "pdftoppm")
    return {
        "generate": bool(os.getenv("GEMINI_API_KEY")),
        "compile": bool(compiler or os.getenv("OVERLEAF_CLSI_URL")),
        "render": bool(renderer),
        "model": os.getenv("GEMINI_MODEL") or DEFAULT_MODEL,
        "compiler": compiler,
        "renderer": renderer,
        "clsi": bool(os.getenv("OVERLEAF_CLSI_URL")),
    }
