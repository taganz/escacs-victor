"""Runs the games: turns, the bot, the flag timers, saving the PGN and
telling the connected browsers what changed.

Each browser plays its own game, identified by a random id that the page
keeps and sends back when it reconnects. Starting a new game while one is
in progress counts as resigning it.

A game in progress cannot be left hanging: if the player goes away, their
clock runs out and the game ends on time.
"""

import asyncio
import logging
import random
import secrets
import time
from pathlib import Path
from typing import Callable, Optional

import chess

from server.bot_runner import BotRunner, bot_time_limit
from server.clock import ChessClock
from server.game import (
    INCREMENT_SECONDS,
    INITIAL_SECONDS,
    Game,
    GameError,
    parse_color_choice,
)
from server.pgn_writer import pgn_text, save_pgn

log = logging.getLogger(__name__)

# Each game in progress has its own bot process. A Raspberry Pi 5 has 4 cores.
MAX_ACTIVE_GAMES = 4
MAX_ACTIVE_GAMES_PER_IP = 2
# Finished games stay in memory this long, so reloading the page still shows them.
KEEP_FINISHED_SECONDS = 3600


async def send(client, message: dict) -> bool:
    try:
        await client.send_json(message)
        return True
    except Exception:
        return False


class GameSession:
    """One game, its bot process and the browsers watching it."""

    def __init__(self, game_id: str, game: Game, bot: BotRunner, games_dir: Path, ip: str):
        self.id = game_id
        self.game = game
        self.bot = bot
        self.games_dir = games_dir
        self.ip = ip
        self.clients: set = set()
        self.finished_at: Optional[float] = None
        self._lock = asyncio.Lock()
        self._timer: Optional[asyncio.Task] = None
        self._bot_task: Optional[asyncio.Task] = None

    @property
    def active(self) -> bool:
        return not self.game.over

    @property
    def bot_thinking(self) -> bool:
        return self._bot_task is not None and not self._bot_task.done()

    def state_message(self) -> dict:
        return {
            "type": "state",
            "game_id": self.id,
            "game": self.game.state(),
            "bot_thinking": self.bot_thinking,
            "provisional_bot": self.bot.provisional,
            "pgn": pgn_text(self.game) if self.game.over else None,
        }

    async def broadcast(self, message: Optional[dict] = None) -> None:
        message = message or self.state_message()
        for client in list(self.clients):
            if not await send(client, message):
                self.clients.discard(client)

    # --- Actions ----------------------------------------------------------

    async def start(self) -> None:
        async with self._lock:
            self.game.start()
            self._after_change()

    async def user_move(self, uci: str) -> None:
        async with self._lock:
            try:
                move = chess.Move.from_uci(uci)
            except ValueError:
                raise GameError("Jugada ilegal")
            try:
                self.game.play(move, self.game.user_color)
            finally:
                # A late move can end the game on time; that must be saved too.
                self._after_change()
        await self.broadcast()

    async def resign(self, reason: str = "Abandono") -> None:
        async with self._lock:
            self.game.resign(self.game.user_color, reason)
            self._after_change()
        await self.broadcast()

    async def close(self) -> None:
        self._cancel_timer()
        if self._bot_task is not None:
            self._bot_task.cancel()
        self.bot.close()

    # --- Internals --------------------------------------------------------

    def _after_change(self) -> None:
        """Call with the lock held after anything that changes the game."""
        game = self.game
        self._cancel_timer()
        if game.over:
            self._end_game()
            return
        delay = game.seconds_until_flag()
        if delay is not None:
            self._timer = asyncio.create_task(self._flag_timer(delay))
        if game.is_turn_of(game.bot_color) and not self.bot_thinking:
            self._bot_task = asyncio.create_task(self._bot_turn())

    def _cancel_timer(self) -> None:
        if self._timer is not None and self._timer is not asyncio.current_task():
            self._timer.cancel()
        self._timer = None

    def _end_game(self) -> None:
        if self.finished_at is not None:
            return
        self.finished_at = time.monotonic()
        if self._bot_task is not None and self._bot_task is not asyncio.current_task():
            self._bot_task.cancel()
        # Also stops a search still running in the bot process.
        self.bot.close()
        try:
            self.game.pgn_file = save_pgn(self.game, self.games_dir).name
            log.info("Partida %s guardada en %s", self.id[:8], self.game.pgn_file)
        except OSError as e:
            log.error("No se ha podido guardar el PGN: %s", e)

    async def _flag_timer(self, delay: float) -> None:
        await asyncio.sleep(delay + 0.05)
        async with self._lock:
            if self.game.over:
                return
            self.game.check_flag()
            # Not flagged yet (timer woke up early): this schedules a new timer.
            self._after_change()
        await self.broadcast()

    async def _bot_turn(self) -> None:
        game = self.game
        bot_color = game.bot_color
        limit = bot_time_limit(game.clock.remaining(bot_color), game.clock.increment)
        notice = None
        try:
            move = await self.bot.choose_move(game.board, limit)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.exception("El bot ha fallado")
            notice = f"El bot ha fallado ({e!r}). Se ha jugado una jugada al azar."
            move = None

        async with self._lock:
            if game.over:
                return
            if move is not None and move not in game.board.legal_moves:
                log.error("El bot ha devuelto una jugada ilegal: %s", move.uci())
                notice = f"El bot ha devuelto una jugada ilegal ({move.uci()}). Se ha jugado una jugada al azar."
                move = None
            if move is None:
                move = random.choice(list(game.board.legal_moves))
            try:
                game.play(move, bot_color)
            except GameError:
                pass  # The bot ran out of time while thinking.
            self._bot_task = None
            self._after_change()
        if notice:
            await self.broadcast({"type": "notice", "message": notice})
        await self.broadcast()


class GameManager:
    def __init__(
        self,
        bot_factory: Callable[[], BotRunner],
        games_dir: Path,
        clock_factory: Callable[[], ChessClock] = lambda: ChessClock(INITIAL_SECONDS, INCREMENT_SECONDS),
        rand: Callable[[], float] = random.random,
        max_active: int = MAX_ACTIVE_GAMES,
        max_active_per_ip: int = MAX_ACTIVE_GAMES_PER_IP,
        keep_finished: float = KEEP_FINISHED_SECONDS,
    ):
        self.bot_factory = bot_factory
        self.games_dir = Path(games_dir)
        self.clock_factory = clock_factory
        self.rand = rand
        self.max_active = max_active
        self.max_active_per_ip = max_active_per_ip
        self.keep_finished = keep_finished
        self.sessions: dict[str, GameSession] = {}

    def find(self, game_id: Optional[str]) -> Optional[GameSession]:
        self.cleanup()
        return self.sessions.get(game_id) if game_id else None

    def active_sessions(self) -> list[GameSession]:
        return [s for s in self.sessions.values() if s.active]

    async def new_game(self, choice: str, ip: str, previous: Optional[GameSession] = None) -> GameSession:
        """Start a game. `previous` is the game this browser was playing, if any."""
        color = parse_color_choice(choice, self.rand)
        if previous is not None and previous.active:
            await previous.resign("Abandono (nueva partida)")
        self.cleanup()
        active = self.active_sessions()
        if len(active) >= self.max_active:
            raise GameError("El servidor está ocupado. Prueba otra vez en unos minutos.")
        if sum(1 for s in active if s.ip == ip) >= self.max_active_per_ip:
            raise GameError("Ya tienes demasiadas partidas en curso.")

        game_id = secrets.token_urlsafe(16)
        bot = self.bot_factory()
        bot.start()
        session = GameSession(game_id, Game(color, clock=self.clock_factory()), bot, self.games_dir, ip)
        self.sessions[game_id] = session
        await session.start()
        log.info("Partida %s: %d en curso", game_id[:8], len(active) + 1)
        return session

    def cleanup(self) -> None:
        """Forget finished games nobody is watching after `keep_finished` seconds."""
        now = time.monotonic()
        for game_id, session in list(self.sessions.items()):
            if session.finished_at is not None and not session.clients and now - session.finished_at > self.keep_finished:
                del self.sessions[game_id]

    async def close(self) -> None:
        for session in self.sessions.values():
            await session.close()
