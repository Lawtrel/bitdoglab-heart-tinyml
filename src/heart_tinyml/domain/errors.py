"""Erros conhecidos que podem ser explicados pela interface."""

class DemoError(Exception):
    """Falha operacional esperada, sem alteração do experimento."""

class InputError(DemoError):
    """Entrada de áudio ou parâmetro inválido."""

class IntegrityError(DemoError):
    """Artefato congelado não confere com o manifesto."""

class BoardError(DemoError):
    """Placa indisponível ou comunicação interrompida."""

class ProtocolError(BoardError):
    """Resposta USB incompatível ou corrompida."""
