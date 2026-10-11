"""FastAPI app: serves the web page and a WebSocket at /ws.

The page opens /ws?game=<id> with the id of the game it was playing, if
any, to get back to it.

Messages from the browser:
    {"type": "new_game", "color": "white" | "black" | "random"}
    {"type": "move", "uci": "e2e4"}
    {"type": "resign"}

Messages to the browser:
    {"type": "state", "game_id": ..., "game": ...}   after every change
    {"type": "notice", "message": ...}
    {"type": "error", "message": ...}   only to the browser that caused it
"""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import urlparse

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

from server.bot_runner import BOT_FILE, BotRunner
from server.game import GameError
from server.manager import GameManager, GameSession, send

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT / "static"
GAMES_DIR = Path(os.environ.get("ESCACS_GAMES_DIR", ROOT / "games"))
LOCAL_HOSTS = {"127.0.0.1", "::1"}


def client_ip(websocket: WebSocket) -> str:
    """The player's IP. Behind Cloudflare Tunnel every connection comes from
    localhost, and Cloudflare sends the real one in a header."""
    host = websocket.client.host if websocket.client else "?"
    if host in LOCAL_HOSTS:
        return websocket.headers.get("cf-connecting-ip", host)
    return host


def same_origin(websocket: WebSocket) -> bool:
    """Browsers send Origin; reject pages from other sites using our WebSocket."""
    origin = websocket.headers.get("origin")
    return origin is None or urlparse(origin).netloc == websocket.headers.get("host")


def create_app(
    bot_factory: Optional[Callable[[], BotRunner]] = None,
    games_dir: Path = GAMES_DIR,
    **manager_kwargs,
) -> FastAPI:
    bot_factory = bot_factory or (lambda: BotRunner(BOT_FILE))
    provisional = bot_factory().provisional

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if provisional:
            log.warning("%s no define choose_move(board, time_limit): se usa un bot provisional que juega al azar", BOT_FILE)
        app.state.manager = GameManager(bot_factory, games_dir, **manager_kwargs)
        try:
            yield
        finally:
            await app.state.manager.close()

    app = FastAPI(lifespan=lifespan)

    def no_game_message() -> dict:
        return {"type": "state", "game_id": None, "game": None, "bot_thinking": False, "provisional_bot": provisional}

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        if not same_origin(websocket):
            await websocket.close(code=1008)
            return
        manager: GameManager = app.state.manager
        ip = client_ip(websocket)
        await websocket.accept()

        session: Optional[GameSession] = manager.find(websocket.query_params.get("game"))
        if session is not None:
            session.clients.add(websocket)
            await send(websocket, session.state_message())
        else:
            await send(websocket, no_game_message())

        try:
            while True:
                try:
                    message = await websocket.receive_json()
                except WebSocketDisconnect:
                    raise
                except Exception:
                    await send(websocket, {"type": "error", "message": "Mensaje no válido"})
                    continue
                kind = message.get("type") if isinstance(message, dict) else None
                try:
                    if kind == "new_game":
                        new = await manager.new_game(str(message.get("color")), ip, session)
                        if session is not None:
                            session.clients.discard(websocket)
                        session = new
                        session.clients.add(websocket)
                        await session.broadcast()
                    elif kind in ("move", "resign"):
                        if session is None:
                            raise GameError("No hay ninguna partida")
                        if kind == "move":
                            await session.user_move(str(message.get("uci")))
                        else:
                            await session.resign()
                    else:
                        raise GameError("Mensaje no válido")
                except GameError as e:
                    await send(websocket, {"type": "error", "message": str(e)})
                    await send(websocket, session.state_message() if session else no_game_message())
        except WebSocketDisconnect:
            pass
        finally:
            if session is not None:
                session.clients.discard(websocket)

    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
    return app
