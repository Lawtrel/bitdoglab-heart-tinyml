"""Entrada única: heart-tinyml serve, doctor e verify-model."""
import argparse
import json
import os
import sys
import threading
import webbrowser

# Deve ocorrer antes da importação de NumPy/LiteRT.
for variable in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[variable] = "1"

def main(argv=None):
    parser = argparse.ArgumentParser(description="TinyML na BitDogLab — Introdução à Inteligência Artificial")
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve", help="Abrir o painel local")
    serve.add_argument("--port", type=int, default=8766)
    serve.add_argument("--no-browser", action="store_true")
    sub.add_parser("doctor", help="Verificar dependências e recursos, sem abrir USB")
    sub.add_parser("verify-model", help="Verificar modelo e normalização congelados")
    args = parser.parse_args(argv)
    from .config import AppConfig
    from .adapters.repositories import FrozenModelRepository
    from .domain.errors import DemoError
    try:
        if args.command in ("doctor", "verify-model"):
            bundle = FrozenModelRepository(AppConfig.default().assets).load()
            result = {"status": "ok", "model_sha256": bundle.manifest["model_sha256"], "threshold": bundle.manifest["threshold"], "hardware_tested": False}
            if args.command == "doctor":
                from .bootstrap import provenance
                result["environment"] = provenance()
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0
        if not 1024 <= args.port <= 65535:
            parser.error("Use uma porta entre 1024 e 65535")
        from .bootstrap import create_application
        from .web.controller import ApiController
        from .web.server import LocalServer, make_handler
        import secrets
        config = AppConfig.default(port=args.port, open_browser=not args.no_browser)
        controller = ApiController(create_application(config))
        handler = make_handler(controller, secrets.token_urlsafe(24), args.port, config.max_body_bytes)
        server = LocalServer(("127.0.0.1", args.port), handler)
        url = f"http://127.0.0.1:{args.port}/"
        print(f"\nTinyML pronto: {url}\nMantenha esta janela aberta. Ctrl+C encerra.\n", flush=True)
        if config.open_browser:
            threading.Timer(1, lambda: webbrowser.open(url)).start()
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
        return 0
    except (DemoError, OSError, ImportError, ValueError) as error:
        print(f"ERRO: {error}", file=sys.stderr)
        return 1
