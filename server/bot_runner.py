"""Runs the bot in a separate process, so the server and the clocks keep
working while it thinks.

The bot is `bot/vicescacs.py`. The server only needs this function from it:

    def choose_move(board: chess.Board, time_limit: float) -> chess.Move

While `bot/vicescacs.py` does not define it, a provisional bot that plays random
legal moves is used instead.
"""

import ast
import asyncio
import importlib.util
import logging
import multiprocessing
import os
import random
import sys
from pathlib import Path
from typing import Optional

import chess

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
BOT_FILE = Path(os.environ.get("ESCACS_BOT_FILE", ROOT / "bot" / "vicescacs.py"))

KIND_BOT = "bot"
KIND_RANDOM = "random"


def has_choose_move(path: Path) -> bool:
    """Whether `path` defines a top-level `choose_move`, checked without importing it."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError):
        return False
    return any(
        isinstance(node, ast.FunctionDef) and node.name == "choose_move"
        for node in tree.body
    )


def bot_time_limit(remaining: float, increment: float) -> float:
    """Seconds the bot may think for one move."""
    return max(0.05, min(remaining / 30 + increment, remaining - 1))


# --- Worker process -------------------------------------------------------

_engine = None


def _random_choose_move(board: chess.Board, time_limit: float) -> chess.Move:
    return random.choice(list(board.legal_moves))


def _load_engine(kind: str, path: str):
    global _engine
    if _engine is not None:
        return _engine
    if kind == KIND_RANDOM:
        _engine = _random_choose_move
        return _engine
    bot_dir = os.path.dirname(path)
    # vicescacs.py opens opening_book.json relative to the working directory.
    os.chdir(bot_dir)
    sys.path.insert(0, bot_dir)
    spec = importlib.util.spec_from_file_location("bot_engine", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _engine = module.choose_move
    return _engine


def _worker_warmup(kind: str, path: str) -> None:
    _load_engine(kind, path)


def _worker_choose(kind: str, path: str, board: chess.Board, time_limit: float) -> str:
    move = _load_engine(kind, path)(board, time_limit)
    if not isinstance(move, chess.Move):
        move = chess.Move.from_uci(str(move))
    return move.uci()


# --- Server side ----------------------------------------------------------


class BotRunner:
    def __init__(self, bot_file: Path = BOT_FILE, kind: Optional[str] = None):
        self.bot_file = Path(bot_file)
        if kind is None:
            kind = KIND_BOT if has_choose_move(self.bot_file) else KIND_RANDOM
        self.kind = kind
        self._pool = None
        self._pending: set[asyncio.Future] = set()

    @property
    def provisional(self) -> bool:
        return self.kind == KIND_RANDOM

    def start(self) -> None:
        if self.provisional:
            log.warning(
                "%s no define choose_move(board, time_limit): se usa un bot provisional que juega al azar",
                self.bot_file,
            )
        else:
            log.info("Bot: %s", self.bot_file)
        # "spawn" is what Windows uses, so the PC and the Raspberry Pi behave the same.
        self._pool = multiprocessing.get_context("spawn").Pool(processes=1)
        self._pool.apply_async(
            _worker_warmup,
            (self.kind, str(self.bot_file)),
            error_callback=lambda e: log.error("El bot no se ha podido cargar: %r", e),
        )

    def close(self) -> None:
        if self._pool is not None:
            self._pool.terminate()
            self._pool.join()
            self._pool = None
        for fut in self._pending:
            if not fut.done():
                fut.cancel()
        self._pending.clear()

    def restart(self) -> None:
        """Stop whatever the bot is thinking and start a fresh worker."""
        self.close()
        self.start()

    async def choose_move(self, board: chess.Board, time_limit: float) -> chess.Move:
        loop = asyncio.get_running_loop()
        fut = loop.create_future()
        self._pending.add(fut)

        def resolve(value, error=False):
            if fut.done():
                return
            if error:
                fut.set_exception(value)
            else:
                fut.set_result(value)

        self._pool.apply_async(
            _worker_choose,
            (self.kind, str(self.bot_file), board.copy(), time_limit),
            callback=lambda r: loop.call_soon_threadsafe(resolve, r),
            error_callback=lambda e: loop.call_soon_threadsafe(resolve, e, True),
        )
        try:
            return chess.Move.from_uci(await fut)
        finally:
            self._pending.discard(fut)
