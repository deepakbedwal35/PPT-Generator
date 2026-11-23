"""PDF validation, page rasterization using Poppler pdftoppm, and PowerPoint export."""

from __future__ import annotations

import base64
from http import HTTPStatus
from pathlib import Path
import subprocess
import tempfile

from deck_maker.compiler import ensure_pdf
from deck_maker.config import MAX_SLIDES, executable_path
from deck_maker.exceptions import AppError
from deck_maker.pptx_builder import pptx_from_images


def convert_pdf(pdf: bytes) -> tuple[list[str], bytes]:
    """Convert PDF into list of data URI PNG preview strings and a PPTX byte stream."""
    ensure_pdf(pdf)
    poppler = executable_path("PDFTOPPM_PATH", "pdftoppm")
    if not poppler:
        raise AppError(
            HTTPStatus.SERVICE_UNAVAILABLE,
            "Install Poppler or set PDFTOPPM_PATH to enable PowerPoint export.",
        )

    with tempfile.TemporaryDirectory(prefix="beamer-deck-") as directory:
        folder = Path(directory)
        input_path = folder / "deck.pdf"
        input_path.write_bytes(pdf)
        try:
            subprocess.run(
                [
                    poppler,
                    "-png",
                    "-cropbox",
                    "-f",
                    "1",
                    "-l",
                    str(MAX_SLIDES + 1),
                    "-scale-to",
                    "1800",
                    str(input_path),
                    str(folder / "page"),
                ],
                timeout=45,
                capture_output=True,
                check=True,
            )
        except subprocess.TimeoutExpired as error:
            raise AppError(HTTPStatus.UNPROCESSABLE_ENTITY, "PDF rendering timed out. Try a simpler deck.") from error
        except subprocess.CalledProcessError as error:
            raise AppError(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "Could not render the PDF. Check that it opens and has no password.",
            ) from error
        except OSError as error:
            raise AppError(503, "Poppler could not start. Check PDFTOPPM_PATH and its DLLs.") from error

        images = [
            path.read_bytes()
            for path in sorted(folder.glob("page-*.png"), key=lambda path: int(path.stem.split("-")[-1]))
        ]

    if len(images) > MAX_SLIDES:
        raise AppError(HTTPStatus.UNPROCESSABLE_ENTITY, f"The PDF must contain 1 to {MAX_SLIDES} pages.")

    presentation = pptx_from_images(images)
    previews = [f"data:image/png;base64,{base64.b64encode(image).decode()}" for image in images]
    return previews, presentation
