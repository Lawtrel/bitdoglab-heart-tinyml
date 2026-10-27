"""Servidor local injetável. Rotas e política de acesso ficam explícitas."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
import json
import logging
import mimetypes
import secrets
from urllib.parse import urlparse
from ..domain.errors import BoardError, InputError, IntegrityError
from .controller import ApiController

LOGGER = logging.getLogger(__name__)
STATIC = files("heart_tinyml.web").joinpath("static")

class LocalServer(ThreadingHTTPServer):
    daemon_threads = True

def make_handler(controller: ApiController, token: str, port: int, max_body: int):
    origin = f"http://127.0.0.1:{port}"

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            # Não registrar áudio nem nonce no terminal.
            pass

        def reply(self, data, code=200, mime="application/json"):
            if mime == "application/json":
                data = json.dumps(data, ensure_ascii=False, allow_nan=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", mime + ("; charset=utf-8" if mime.startswith("text/") else ""))
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; media-src 'self' blob:; img-src 'self' blob:; object-src 'none'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(data)

        def error_response(self, error):
            if isinstance(error, FileNotFoundError):
                return self.reply({"error": "Recurso inexistente."}, 404)
            if isinstance(error, InputError):
                return self.reply({"error": str(error)}, 400)
            if isinstance(error, IntegrityError):
                return self.reply({"error": str(error)}, 409)
            if isinstance(error, BoardError):
                return self.reply({"error": str(error)}, 503)
            LOGGER.exception("Falha inesperada no pedido local", exc_info=error)
            return self.reply({"error": "Falha interna. Consulte o terminal do aplicativo."}, 500)

        def valid_host(self):
            return self.headers.get("Host") == f"127.0.0.1:{port}"

        def do_GET(self):
            if not self.valid_host():
                return self.reply({"error": "Use o endereço local mostrado no terminal."}, 403)
            path = urlparse(self.path).path
            try:
                if path.startswith("/api/"):
                    return self.reply(controller.get(path))
                if path in ("/audio/1.wav", "/audio/2.wav"):
                    return self.reply(controller.app.evidence.sample(int(path[-5])), mime="audio/wav")
                route = "index.html" if path == "/" else path.lstrip("/")
                allowed = {"index.html", "style.css", "js/app.js", "js/api.js", "js/plots.js", "js/views.js"}
                if route not in allowed:
                    raise FileNotFoundError(route)
                data = STATIC.joinpath(route).read_bytes()
                if route == "index.html":
                    data = data.replace(b"__DEMO_NONCE__", token.encode())
                mime = "text/javascript" if route.endswith(".js") else mimetypes.guess_type(route)[0]
                return self.reply(data, mime=mime or "application/octet-stream")
            except Exception as error:
                return self.error_response(error)

        def do_POST(self):
            supplied = self.headers.get("X-Demo-Token", "")
            if not self.valid_host() or not secrets.compare_digest(supplied, token):
                return self.reply({"error": "Atualize a página para abrir uma sessão válida."}, 403)
            if self.headers.get("Origin") not in (None, origin):
                return self.reply({"error": "Origem recusada."}, 403)
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= max_body:
                    raise InputError("Arquivo vazio ou pedido maior que 30 MB.")
                try:
                    data = json.loads(self.rfile.read(length))
                except (ValueError, UnicodeDecodeError) as error:
                    raise InputError("JSON inválido.") from error
                return self.reply(controller.post(urlparse(self.path).path, data))
            except ValueError as error:
                return self.error_response(InputError(str(error)))
            except Exception as error:
                return self.error_response(error)

    return Handler
