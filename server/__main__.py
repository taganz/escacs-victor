"""Start the server: python -m server [--host 0.0.0.0] [--port 8000]"""

import argparse
import logging

import uvicorn

from server.app import create_app


def main() -> None:
    parser = argparse.ArgumentParser(description="Escacs Victor: ajedrez contra el bot")
    parser.add_argument("--host", default="127.0.0.1", help="0.0.0.0 para aceptar conexiones de otros equipos")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    # Our messages are tiny; refuse big ones.
    uvicorn.run(create_app(), host=args.host, port=args.port, ws_max_size=16 * 1024)


if __name__ == "__main__":
    main()
