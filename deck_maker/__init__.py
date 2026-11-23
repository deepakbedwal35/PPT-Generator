"""Python Beamer Deck Maker package.

Local Gemini -> Beamer -> PDF -> PowerPoint deck maker using Python's standard library.
"""

from __future__ import annotations

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
    beamer_source,
    compile_latex,
    compile_overleaf,
    compiler_message,
)
from deck_maker.converter import convert_pdf, ensure_pdf
from deck_maker.exceptions import AppError
from deck_maker.generator import generate_latex, generate_latex_once
from deck_maker.pptx_builder import content_types, png_dimensions, pptx_from_images
from deck_maker.server import (
    COMPILE_LOCK,
    CONVERT_LOCK,
    Handler,
    create_server,
)

__all__ = [
    "AppError",
    "COMPILE_LOCK",
    "CONVERT_LOCK",
    "DEFAULT_MODEL",
    "DEFAULT_PORT",
    "Handler",
    "MAX_PDF",
    "MAX_SLIDES",
    "PPTX_TYPE",
    "PUBLIC",
    "ROOT",
    "beamer_source",
    "compile_latex",
    "compile_overleaf",
    "compiler_message",
    "content_types",
    "convert_pdf",
    "create_server",
    "ensure_pdf",
    "executable_path",
    "generate_latex",
    "generate_latex_once",
    "load_environment",
    "png_dimensions",
    "pptx_from_images",
    "settings",
]
