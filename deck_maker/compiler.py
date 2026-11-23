"""Beamer LaTeX source validation, local pdflatex compilation, and Overleaf CLSI integration."""

from __future__ import annotations

from http import HTTPStatus
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from urllib.parse import urljoin, urlsplit

from deck_maker.config import MAX_PDF, executable_path
from deck_maker.exceptions import AppError


def beamer_source(value: object) -> str:
    """Validate and clean Beamer LaTeX source code."""
    if not isinstance(value, str):
        raise AppError(HTTPStatus.BAD_REQUEST, "Provide Beamer LaTeX source.")
    latex = re.sub(r"^```(?:latex|tex)?\s*\n([\s\S]*?)\n```$", r"\1", value.strip(), flags=re.I).strip()
    if len(latex.encode()) > 64 * 1024:
        raise AppError(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "Beamer source must be 64 KB or smaller.")
    if not re.search(r"\\documentclass\s*(?:\[[^\]]*\]\s*)?\{beamer\}", latex):
        raise AppError(
            HTTPStatus.UNPROCESSABLE_ENTITY,
            "Provide a complete Beamer document from \\documentclass to \\end{document}.",
        )
    if "\\begin{document}" not in latex or "\\end{document}" not in latex:
        raise AppError(
            HTTPStatus.UNPROCESSABLE_ENTITY,
            "Provide a complete Beamer document from \\documentclass to \\end{document}.",
        )
    return latex


def compiler_message(log_path: Path, fallback: str) -> str:
    """Extract readable compiler error message from pdflatex log."""
    text = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else fallback
    match = re.search(r"^!\s+(.+)$", text, re.M)
    if match:
        excerpt = text[match.start() :].splitlines()[:10]
        return "Beamer compilation failed:\n" + "\n".join(excerpt)
    return "Beamer compilation failed:\n" + text[-3000:]


def ensure_pdf(data: bytes) -> bytes:
    """Validate that data is a non-empty PDF within size limits."""
    if len(data) > MAX_PDF:
        raise AppError(413, "PDF files must be 15 MB or smaller.")
    if not data.startswith(b"%PDF-"):
        raise AppError(HTTPStatus.UNPROCESSABLE_ENTITY, "The supplied file is not a PDF.")
    return data


def compile_latex(value: object) -> bytes:
    """Compile Beamer LaTeX source into PDF bytes using local pdflatex or Overleaf CLSI."""
    latex = beamer_source(value)
    command = executable_path("LATEX_COMMAND", "pdflatex")
    if not command:
        if os.getenv("OVERLEAF_CLSI_URL"):
            return compile_overleaf(latex)
        raise AppError(503, "Install MiKTeX or set LATEX_COMMAND to a valid pdflatex executable.")

    try:
        timeout_ms = int(os.getenv("LATEX_TIMEOUT_MS", "180000"))
    except ValueError as error:
        raise AppError(500, "LATEX_TIMEOUT_MS must be an integer.") from error
    if not 10_000 <= timeout_ms <= 600_000:
        raise AppError(HTTPStatus.INTERNAL_SERVER_ERROR, "LATEX_TIMEOUT_MS must be between 10000 and 600000.")

    executable = shutil.which(command) or command
    with tempfile.TemporaryDirectory(prefix="beamer-compile-") as directory:
        folder = Path(directory)
        input_path = folder / "main.tex"
        output_path = folder / "main.pdf"
        input_path.write_text(latex, encoding="utf-8")
        try:
            deadline = time.monotonic() + timeout_ms / 1000
            # Beamer resolves total frame counts, references and navigation on pass two.
            for _ in range(2):
                result = subprocess.run(
                    [
                        executable,
                        *(["--enable-installer"] if os.name == "nt" else []),
                        "-no-shell-escape",
                        "-interaction=nonstopmode",
                        "-halt-on-error",
                        "-file-line-error",
                        "-output-directory",
                        str(folder),
                        str(input_path),
                    ],
                    cwd=folder,
                    capture_output=True,
                    timeout=max(0.01, deadline - time.monotonic()),
                    check=False,
                )
                if result.returncode:
                    break
        except OSError as error:
            raise AppError(
                HTTPStatus.SERVICE_UNAVAILABLE,
                "LATEX_COMMAND could not be started. Install a TeX distribution or correct its path and permissions.",
            ) from error
        except subprocess.TimeoutExpired as error:
            raise AppError(HTTPStatus.UNPROCESSABLE_ENTITY, "Beamer compilation timed out. Try a simpler deck.") from error

        if result.returncode or not output_path.exists():
            fallback = (result.stderr + result.stdout).decode(errors="replace")
            raise AppError(HTTPStatus.UNPROCESSABLE_ENTITY, compiler_message(folder / "main.log", fallback))

        pdf = output_path.read_bytes()

    return ensure_pdf(pdf)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """Prevent automated redirects to enforce exact origin and path validation."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def compile_overleaf(latex: str) -> bytes:
    """Compile LaTeX using a private Overleaf CLSI service."""
    base = os.getenv("OVERLEAF_CLSI_URL", "").rstrip("/")
    if not base:
        raise AppError(503, "Set LATEX_COMMAND or OVERLEAF_CLSI_URL to compile automatically.")

    project_url = f"{base}/project/{secrets.token_hex(12)}/"
    payload = {
        "compile": {
            "options": {"compiler": "pdflatex", "timeout": 40, "stopOnFirstError": True},
            "rootResourcePath": "main.tex",
            "resources": [{"path": "main.tex", "content": latex}],
        }
    }
    request = urllib.request.Request(
        project_url + "compile",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    opener = urllib.request.build_opener(NoRedirect)
    try:
        with opener.open(request, timeout=60) as response:
            result = json.load(response).get("compile", {})
        if result.get("status") != "success":
            raise AppError(
                422,
                f"Beamer compilation failed ({result.get('status', 'unknown error')}). Check the LaTeX in Overleaf.",
            )
        output = next(
            (
                file
                for file in result.get("outputFiles", [])
                if file.get("type") == "pdf"
                and file.get("url")
                and (file.get("path") == "output.pdf" or file["url"].endswith("/output.pdf"))
            ),
            None,
        )
        if not output:
            raise AppError(502, "Overleaf CLSI returned no PDF.")

        url = urljoin(project_url, output["url"])
        parsed, expected = urlsplit(url), urlsplit(project_url)
        if (parsed.scheme, parsed.netloc) != (expected.scheme, expected.netloc) or not parsed.path.startswith(
            expected.path
        ):
            raise AppError(502, "Configure CLSI to return PDF URLs from its configured origin and project path.")

        with opener.open(url, timeout=60) as response:
            pdf = response.read(MAX_PDF + 1)
        if len(pdf) > MAX_PDF:
            raise AppError(413, "The compiled PDF is too large.")
        return ensure_pdf(pdf)
    except (urllib.error.URLError, TimeoutError) as error:
        raise AppError(502, "Could not complete the Overleaf CLSI request. Check its URL and availability.") from error
