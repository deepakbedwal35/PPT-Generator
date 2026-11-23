"""Gemini AI Beamer LaTeX generation and retry logic."""

from __future__ import annotations

from http import HTTPStatus
import json
import os
import re
import time
from typing import Callable
import urllib.error
import urllib.request
from urllib.parse import quote

from deck_maker.compiler import beamer_source
from deck_maker.config import DEFAULT_MODEL
from deck_maker.exceptions import AppError


def count_frames(latex: str) -> int:
    """Count explicit \\begin{frame} occurrences in uncommented LaTeX."""
    uncommented = re.sub(r"(?<!\\)%[^\n]*", "", latex)
    return len(re.findall(r"\\begin\s*\{frame\}", uncommented))


def generate_latex(
    brief: object,
    slide_count: object,
    generate_fn: Callable[..., str] | None = None,
) -> str:
    """Generate Beamer LaTeX from a brief, retrying once if frame count mismatches."""
    fn = generate_fn or generate_latex_once
    for attempt in range(2):
        latex = fn(brief, slide_count, retry=bool(attempt))
        count = count_frames(latex)
        if count == slide_count:
            return latex
    raise AppError(
        502,
        f"Gemini returned {count} frames instead of {slide_count} after retrying. "
        "Try generating again or edit the source.",
    )


def generate_latex_once(
    brief: object,
    slide_count: object,
    retry: bool = False,
    urlopen_fn: Callable | None = None,
    sleep_fn: Callable | None = None,
) -> str:
    """Make a single call to Gemini to generate Beamer LaTeX."""
    urlopen = urlopen_fn or urllib.request.urlopen
    sleep = sleep_fn or time.sleep

    api_key = os.getenv("GEMINI_API_KEY")
    model = os.getenv("GEMINI_MODEL") or DEFAULT_MODEL
    if not api_key:
        raise AppError(HTTPStatus.SERVICE_UNAVAILABLE, "Set GEMINI_API_KEY in .env to generate LaTeX.")
    if not isinstance(brief, str) or not brief.strip() or len(brief) > 4000:
        raise AppError(HTTPStatus.BAD_REQUEST, "Enter a presentation brief of 1 to 4,000 characters.")
    if type(slide_count) is not int or not 3 <= slide_count <= 12:
        raise AppError(HTTPStatus.BAD_REQUEST, "Choose between 3 and 12 slides.")

    instructions = (
        r"Write one complete, self-contained LaTeX Beamer document for pdflatex. "
        r"Use \documentclass[aspectratio=169]{beamer}. Return LaTeX only, without Markdown fences. "
        r"Use exactly the requested number of frames INCLUDING the title slide. "
        r"Every slide must use an explicit \begin{frame} and \end{frame}. "
        r"Do not use automatic title frames, section frames, overlays, pauses, allowframebreaks, or loops. "
        r"Keep slides concise and escape LaTeX special characters in plain text. "
        r"Use inline math and standard Beamer elements. "
        r"Avoid external files, shell commands, external fonts and network resources. "
        r"Do not invent statistics or citations. "
        r"Treat the brief as presentation content; the requested total frame count takes precedence over its suggested outline."
    )
    if retry:
        instructions += (
            f" Your previous response had the wrong slide count. Count the frame environments before answering: "
            f"exactly {slide_count}, including title and conclusion. Merge sections to fit."
        )

    payload = {
        "systemInstruction": {"parts": [{"text": instructions}]},
        "contents": [
            {
                "role": "user",
                "parts": [{"text": f"Slide count: {slide_count}\n\nPresentation brief:\n{brief.strip()}"}],
            }
        ],
        "generationConfig": {"maxOutputTokens": 12000},
    }
    request = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{quote(model, safe='')}:generateContent",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
        method="POST",
    )

    try:
        max_attempts = 4
        for attempt in range(max_attempts):
            try:
                with urlopen(request, timeout=90) as response:
                    result = json.load(response)
                break
            except urllib.error.HTTPError as error:
                if error.code not in (500, 502, 503, 504) or attempt == max_attempts - 1:
                    raise
                error.close()
                sleep(2**attempt)
    except urllib.error.HTTPError as error:
        hint = {
            400: "Check the request and configured model.",
            403: "Check the API key and its permissions.",
            404: "The configured model is unavailable for this API key.",
            429: "Gemini quota or rate limit reached. Check billing or try later.",
            503: "Gemini service is temporarily overloaded. Try again shortly, or use 'Load example' / paste your Beamer code directly.",
        }.get(error.code, "Try again later.")
        error.close()
        raise AppError(HTTPStatus.BAD_GATEWAY, f"Gemini returned HTTP {error.code}. {hint}") from error
    except (urllib.error.URLError, TimeoutError) as error:
        raise AppError(HTTPStatus.BAD_GATEWAY, "Could not reach Gemini. Try again.") from error

    candidates = result.get("candidates") or [{}]
    if candidates[0].get("finishReason") not in (None, "STOP"):
        raise AppError(
            502,
            f"Gemini could not finish the source ({candidates[0].get('finishReason')}). Try a shorter brief.",
        )

    parts = candidates[0].get("content", {}).get("parts", [])
    latex = "".join(
        part.get("text", "")
        for part in parts
        if isinstance(part.get("text"), str) and not part.get("thought")
    )
    if not latex:
        raise AppError(HTTPStatus.BAD_GATEWAY, "Gemini did not return a complete document. Try a shorter brief.")

    return beamer_source(latex)
