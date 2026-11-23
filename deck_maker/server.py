"""HTTP request handler and server setup."""

from __future__ import annotations

import base64
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
import threading

from deck_maker.compiler import compile_latex
from deck_maker.config import MAX_PDF, PPTX_TYPE, PUBLIC, settings
from deck_maker.converter import convert_pdf
from deck_maker.exceptions import AppError
from deck_maker.generator import generate_latex

COMPILE_LOCK = threading.Lock()
CONVERT_LOCK = threading.Lock()


class Handler(SimpleHTTPRequestHandler):
    """HTTP request handler for static assets and API routes."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(PUBLIC), **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data:; "
            "form-action 'self' https://www.overleaf.com; "
            "frame-ancestors 'none'; base-uri 'none'",
        )
        super().end_headers()

    def send_json(self, status: int, data: dict):
        encoded = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def read_body(self, expected: str, maximum: int) -> bytes:
        if self.headers.get_content_type() != expected:
            raise AppError(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, f"Send {expected}.")
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as error:
            raise AppError(400, "Invalid Content-Length.") from error
        if length < 0:
            raise AppError(400, "Invalid Content-Length.")
        if length > maximum:
            raise AppError(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "The request is too large.")
        return self.rfile.read(length)

    def read_json(self) -> dict:
        try:
            value = json.loads(self.read_body("application/json", 256 * 1024))
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise AppError(HTTPStatus.BAD_REQUEST, "Send a valid JSON object.") from error
        if not isinstance(value, dict):
            raise AppError(HTTPStatus.BAD_REQUEST, "Send a valid JSON object.")
        return value

    def do_GET(self):
        endpoint = self.path.split("?", 1)[0]
        if endpoint == "/api/config":
            self.send_json(HTTPStatus.OK, settings())
            return
        if endpoint.startswith("/api/"):
            self.send_json(404, {"error": "Endpoint not found."})
            return
        super().do_GET()

    def do_POST(self):
        try:
            # Reject cross-origin browser calls to this local compiler
            origin = self.headers.get("Origin")
            if origin and origin != "http://" + self.headers.get("Host", ""):
                raise AppError(403, "Cross-origin requests are not allowed.")

            endpoint = self.path.split("?", 1)[0]
            if endpoint == "/api/latex":
                payload = self.read_json()
                self.send_json(
                    HTTPStatus.OK,
                    {"latex": generate_latex(payload.get("brief"), payload.get("slideCount"))},
                )
                return

            if endpoint == "/api/compile":
                payload = self.read_json()
                if not COMPILE_LOCK.acquire(blocking=False):
                    raise AppError(429, "Another deck is compiling. Try again shortly.")
                try:
                    pdf = compile_latex(payload.get("latex"))
                finally:
                    COMPILE_LOCK.release()
                self.send_binary(HTTPStatus.OK, "application/pdf", pdf)
                return

            if endpoint == "/api/pptx":
                if not CONVERT_LOCK.acquire(blocking=False):
                    raise AppError(HTTPStatus.TOO_MANY_REQUESTS, "Another deck is exporting. Try again in a moment.")
                try:
                    previews, pptx = convert_pdf(self.read_body("application/pdf", MAX_PDF))
                finally:
                    CONVERT_LOCK.release()
                if self.headers.get("Accept") == "application/json":
                    self.send_json(
                        HTTPStatus.OK,
                        {"slides": previews, "pptx": base64.b64encode(pptx).decode()},
                    )
                else:
                    self.send_binary(
                        HTTPStatus.OK,
                        PPTX_TYPE,
                        pptx,
                        {"Content-Disposition": 'attachment; filename="deck.pptx"'},
                    )
                return

            raise AppError(HTTPStatus.NOT_FOUND, "Page or endpoint not found.")
        except AppError as error:
            self.send_json(error.status, {"error": error.message})
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception:
            logging.exception("Request failed")
            self.send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "The app could not complete the request."})

    def send_binary(self, status: int, content_type: str, data: bytes, headers: dict[str, str] | None = None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt: str, *args):
        print(f"{self.address_string()} - {fmt % args}")


def create_server(host: str = "127.0.0.1", port: int = 3000) -> ThreadingHTTPServer:
    """Create a configured ThreadingHTTPServer instance."""
    return ThreadingHTTPServer((host, port), Handler)
