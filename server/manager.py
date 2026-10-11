"""Runs the current game: turns, the bot, the flag timer, saving the PGN
and telling every connected browser what changed.

There is one game at a time. Starting a new one while a game is in
progress counts as the user resigning it.
"""

import asyncio
import logging
import random
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
from server.pgn_writer import save_pgn

log = logging.getLogger(__name__)


class GameManager:
    def __init__(
        self,
        bot: BotRunner,
        games_dir: Path,
        clock_factory: Callable[[], ChessClock] = lambda: ChessClock(INITIAL_SECONDS, INCREMENT_SECONDS),
        rand: Callable[[], float] = random.random,
    ):
        self.bot = bot
        self.games_dir = Path(games_dir)
        self.clock_factory = clock_factory
        self.rand = rand
        self.game: Optional[Game] = None
        self.clients: set = set()
        self._lock = asyncio.Lock()
        self._timer: Optional[asyncio.Task] = None
        self._bot_task: Optional[asyncio.Task] = None

    # --- Clients ----------------------------------------------------------

    async def connect(self, client) -> None:
        self.clients.add(client)
        await self._send(client, self.state_message())

    def disconnect(self, client) -> None:
        self.clients.discard(client)

    @property
    def bot_thinking(self) -> bool:
        return self._bot_task is not None and not self._bot_task.done()

    def state_message(self) -> dict:
        return {
            "type": "state",
            "game": self.game.state() if self.game else None,
            "bot_thinking": self.bot_thinking,
            "provisional_bot": self.bot.provisional,
        }

    async def broadcast(self, message: Optional[dict] = None) -> None:
        message = message or self.state_message()
        for client in list(self.clients):
            await self._send(client, message)

    async def _send(self, client, message: dict) -> None:
        try:
            await client.send_json(message)
        except Exception:
            self.clients.discard(client)

    # --- User actions -----------------------------------------------------

    async def new_game(self, choice: str) -> None:
        async with self._lock:
            color = parse_color_choice(choice, self.rand)
            if self.game is not None and not self.game.over:
                self.game.resign(self.game.user_color, "Abandono (nueva partida)")
                self._after_change()
            self.game = Game(color, clock=self.clock_factory())
            self.game.start()
            self._after_change()
        await self.broadcast()

    async def user_move(self, uci: str) -> None:
        async with self._lock:
            game = self._require_game()
            try:
                move = chess.Move.from_uci(uci)
            except ValueError:
                raise GameError("Jugada ilegal")
            try:
                game.play(move, game.user_color)
            finally:
                # A late move can end the game on time; that must be saved too.
                self._after_change()
        await self.broadcast()

    async def resign(self) -> None:
        async with self._lock:
            game = self._require_game()
            game.resign(game.user_color)
            self._after_change()
        await self.broadcast()

    def _require_game(self) -> Game:
        if self.game is None:
            raise GameError("No hay ninguna partida")
        return self.game

    # --- Internals --------------------------------------------------------

    def _after_change(self) -> None:
        """Call with the lock held after anything that changes the game."""
        game = self.game
        if game is None:
            return
        self._cancel_timer()
        if game.over:
            self._end_game(game)
            return
        delay = game.seconds_until_flag()
        if delay is not None:
            self._timer = asyncio.create_task(self._flag_timer(game, delay))
        if game.is_turn_of(game.bot_color) and not self.bot_thinking:
            self._bot_task = asyncio.create_task(self._bot_turn(game))

    def _cancel_timer(self) -> None:
        if self._timer is not None and self._timer is not asyncio.current_task():
            self._timer.cancel()
        self._timer = None

    def _end_game(self, game: Game) -> None:
        if self.bot_thinking and self._bot_task is not asyncio.current_task():
            # The worker may be deep in a search; restart it so the next game does not wait.
            self._bot_task.cancel()
            self.bot.restart()
        if game.pgn_file is None:
            try:
                game.pgn_file = save_pgn(game, self.games_dir).name
                log.info("Partida guardada en %s", game.pgn_file)
            except OSError as e:
                log.error("No se ha podido guardar el PGN: %s", e)

    async def _flag_timer(self, game: Game, delay: float) -> None:
        await asyncio.sleep(delay + 0.05)
        async with self._lock:
            if game is not self.game or game.over:
                return
            game.check_flag()
            # Not flagged yet (timer woke up early): this schedules a new timer.
            self._after_change()
        await self.broadcast()

    async def _bot_turn(self, game: Game) -> None:
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
            if game is not self.game or game.over:
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

    async def close(self) -> None:
        self._cancel_timer()
        if self._bot_task is not None:
            self._bot_task.cancel()
