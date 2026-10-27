"""Adapter do contrato BoardGateway para pyserial e firmware demo."""
from contextlib import contextmanager
import threading
import numpy as np
from ..domain.errors import BoardError, ProtocolError
from ..domain.models import AudioWindow, BoardCapture, FROZEN_MODEL_SHA256
from .usb_protocol import Mode, ProtocolClient, validate_inference

class SerialBoardAdapter:
    def __init__(self, serial_factory=None, port_provider=None):
        self.serial_factory = serial_factory
        self.port_provider = port_provider
        self.lock = threading.Lock()

    def ports(self) -> list[dict]:
        from serial.tools.list_ports import comports
        provider = self.port_provider or comports
        return [{"port": p.device, "description": p.description, "vid": p.vid, "pid": p.pid}
                for p in provider() if p.vid == 0x2e8a]

    @contextmanager
    def session(self, port: str):
        import serial
        with self.lock:
            try:
                allowed = [p["port"] for p in self.ports()]
                if port == "auto":
                    if len(allowed) != 1:
                        raise BoardError("Conecte uma única BitDogLab e feche monitores seriais.")
                    port = allowed[0]
                elif port not in allowed:
                    raise BoardError("Escolha uma porta Pico disponível.")
                factory = self.serial_factory or serial.Serial
                with factory(port, 115200, timeout=1, write_timeout=5) as connection:
                    connection.dtr = True
                    connection.reset_input_buffer()
                    client = ProtocolClient(connection)
                    hello = client.request(Mode.HELLO)
                    if not hello.get("ready") or hello.get("model_sha256") != FROZEN_MODEL_SHA256:
                        raise ProtocolError("Modelo da placa diferente ou não inicializado.")
                    if hello.get("app") != "tinyml_aula_v3":
                        raise ProtocolError("Instale o firmware demo compatível com o painel USB.")
                    yield client, hello
            except (serial.SerialException, OSError) as error:
                raise BoardError("Não foi possível usar a USB. Reconecte a placa e feche outros monitores.") from error

    def connect(self, port: str = "auto") -> dict:
        with self.session(port) as (_, hello):
            return hello

    def infer(self, audio: AudioWindow, port: str = "auto") -> dict:
        with self.session(port) as (client, _):
            return validate_inference(client.request(Mode.INFER, audio.pcm.astype("<i2").tobytes()))

    def capture(self, port: str = "auto") -> BoardCapture:
        with self.session(port) as (client, _):
            response, raw = client.request(Mode.CAPTURE)
        if not isinstance(response.get("quality_ok"), bool):
            raise ProtocolError("A placa não informou a qualidade da captura.")
        result = validate_inference(response["result"]) if response["quality_ok"] else None
        audio = AudioWindow(np.frombuffer(raw, "<i2").copy(), {
            "experimental": True, "source": "Microfone da placa: 4 kHz, 3 segundos",
        })
        metadata = {k: v for k, v in response.items() if k != "result"}
        return BoardCapture(audio, response["quality_ok"], response.get("reason", ""), metadata, result)
