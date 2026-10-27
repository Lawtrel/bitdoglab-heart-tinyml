"""Controller HTTP: valida os DTOs e chama os casos de uso."""
import base64
import binascii
from ..bootstrap import Application, provenance
from ..domain.errors import InputError

class ApiController:
    def __init__(self, application: Application):
        self.app = application

    def get(self, path: str) -> dict:
        if path == "/api/info":
            try:
                ports = self.app.service.board.ports()
                warning = None
            except OSError:
                ports, warning = [], "Portas USB indisponíveis. O modo PC continua disponível."
            return {"provenance": provenance(), "ports": ports, "warning": warning}
        if path == "/api/fresh-benchmark":
            return self.app.evidence.fresh_benchmark()
        if path == "/api/examples":
            return self.app.evidence.catalog()
        if path == "/api/results":
            return self.app.evidence.classification()
        if path == "/api/benchmark":
            return self.app.evidence.benchmark()
        raise FileNotFoundError(path)

    def post(self, path: str, data: dict) -> dict:
        if not isinstance(data, dict):
            raise InputError("O pedido precisa ser um objeto JSON.")
        port = data.get("port", "auto")
        if not isinstance(port, str):
            raise InputError("Porta inválida.")
        if path == "/api/connect":
            return self.app.service.board.connect(port)
        if path == "/api/capture":
            return self.app.service.capture(port)
        if path == "/api/analyze":
            compare = data.get("board", False)
            if not isinstance(compare, bool):
                raise InputError("O campo de comparação precisa ser booleano.")
            try:
                wav = base64.b64decode(data["wav"], validate=True)
                start = float(data.get("start", 0))
            except (KeyError, ValueError, TypeError, binascii.Error) as error:
                raise InputError("Áudio ou início do trecho inválido.") from error
            return self.app.service.analyze(wav, start, compare, port)
        raise FileNotFoundError(path)
