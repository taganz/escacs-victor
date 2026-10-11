"""FastAPI app: serves the web page and a WebSocket at /ws.

Messages from the browser:
    {"type": "new_game", "color": "white" | "black" | "random"}
    {"type": "move", "uci": "e2e4"}
    {"type": "resign"}

Messages to the browser:
    {"type": "state", ...}       the whole game, after every change
    {"type": "notice", "message": ...}
    {"type": "error", "message": ...}   only to the browser that caused it
"""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

from server.bot_runner import BOT_FILE, BotRunner
from server.game import GameError
from server.manager import GameManager

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT / "static"
GAMES_DIR = Path(os.environ.get("ESCACS_GAMES_DIR", ROOT / "games"))


def create_app(bot: BotRunner | None = None, games_dir: Path = GAMES_DIR, **manager_kwargs) -> FastAPI:
    bot = bot or BotRunner(BOT_FILE)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        bot.start()
        app.state.manager = GameManager(bot, games_dir, **manager_kwargs)
        try:
            yield
        finally:
            await app.state.manager.close()
            bot.close()

    app = FastAPI(lifespan=lifespan)

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        manager: GameManager = app.state.manager
        await websocket.accept()
        await manager.connect(websocket)
        try:
            while True:
                message = await websocket.receive_json()
                try:
                    await handle(manager, message)
                except GameError as e:
                    await websocket.send_json({"type": "error", "message": str(e)})
                    await websocket.send_json(manager.state_message())
        except WebSocketDisconnect:
            pass
        finally:
            manager.disconnect(websocket)

    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
    return app


async def handle(manager: GameManager, message: dict) -> None:
    kind = message.get("type") if isinstance(message, dict) else None
    if kind == "new_game":
        await manager.new_game(str(message.get("color")))
    elif kind == "move":
        await manager.user_move(str(message.get("uci")))
    elif kind == "resign":
        await manager.resign()
    else:
        raise GameError("Mensaje no válido")
