"""One game between the user and the bot: board, clocks and result.

This module has no I/O and no asyncio, so it can be tested directly.
"""

from datetime import datetime
from typing import Callable, Optional

import chess

from server.clock import ChessClock

BOT_NAME = "Bot"
USER_NAME = "user"
INITIAL_SECONDS = 600.0
INCREMENT_SECONDS = 5.0

# Termination reasons as (text shown to the user, PGN Termination tag).
_OUTCOME_REASONS = {
    chess.Termination.CHECKMATE: "Jaque mate",
    chess.Termination.STALEMATE: "Rey ahogado",
    chess.Termination.INSUFFICIENT_MATERIAL: "Material insuficiente",
    chess.Termination.THREEFOLD_REPETITION: "Triple repetición",
    chess.Termination.FIVEFOLD_REPETITION: "Quíntuple repetición",
    chess.Termination.FIFTY_MOVES: "Regla de los 50 movimientos",
    chess.Termination.SEVENTYFIVE_MOVES: "Regla de los 75 movimientos",
}


class GameError(Exception):
    """A move or action that is not allowed. The message is shown to the user."""


def color_name(color: chess.Color) -> str:
    return "white" if color == chess.WHITE else "black"


class Game:
    def __init__(
        self,
        user_color: chess.Color,
        clock: Optional[ChessClock] = None,
        started: Optional[datetime] = None,
    ):
        self.user_color = user_color
        self.bot_color = not user_color
        self.board = chess.Board()
        self.clock = clock or ChessClock(INITIAL_SECONDS, INCREMENT_SECONDS)
        self.started = started or datetime.now()
        self.sans: list[str] = []
        # Clock of the side that moved, right after each move (increment included).
        self.clocks_after: list[float] = []
        self.result: Optional[str] = None
        self.reason: Optional[str] = None
        self.termination: Optional[str] = None
        self.pgn_file: Optional[str] = None

    @property
    def over(self) -> bool:
        return self.result is not None

    @property
    def white_name(self) -> str:
        return USER_NAME if self.user_color == chess.WHITE else BOT_NAME

    @property
    def black_name(self) -> str:
        return USER_NAME if self.user_color == chess.BLACK else BOT_NAME

    def start(self) -> None:
        self.clock.start(chess.WHITE)

    def is_turn_of(self, color: chess.Color) -> bool:
        return not self.over and self.board.turn == color

    def play(self, move: chess.Move, by: chess.Color) -> None:
        """Play `move` for `by`. Raises GameError if it is not allowed."""
        if self.over:
            raise GameError("La partida ha terminado")
        if self.board.turn != by:
            raise GameError("No es tu turno")
        if self.check_flag():
            raise GameError("Se ha agotado el tiempo")
        if move not in self.board.legal_moves:
            raise GameError("Jugada ilegal")

        self.sans.append(self.board.san(move))
        self.board.push(move)
        self.clock.press()
        self.clocks_after.append(self.clock.remaining(by))

        outcome = self.board.outcome()
        if outcome is not None:
            self._finish(outcome.result(), _OUTCOME_REASONS.get(outcome.termination, "Fin de la partida"), "normal")
        # Drawn as soon as they happen, without waiting for a claim. Not
        # outcome(claim_draw=True): that also ends the game when the *next*
        # move could repeat the position.
        elif self.board.is_repetition(3):
            self._finish("1/2-1/2", _OUTCOME_REASONS[chess.Termination.THREEFOLD_REPETITION], "normal")
        elif self.board.is_fifty_moves():
            self._finish("1/2-1/2", _OUTCOME_REASONS[chess.Termination.FIFTY_MOVES], "normal")

    def check_flag(self) -> bool:
        """End the game if the running clock has reached 0. Returns whether the game is over."""
        if self.over:
            return True
        loser = self.clock.flagged()
        if loser is None:
            return False
        winner = not loser
        if self.board.has_insufficient_material(winner):
            self._finish("1/2-1/2", "Tiempo agotado, pero el rival no tiene material para dar mate", "time forfeit")
        else:
            self._finish(self._win_for(winner), "Tiempo agotado", "time forfeit")
        return True

    def seconds_until_flag(self) -> Optional[float]:
        """Seconds until the running clock reaches 0, or None if no clock runs."""
        if self.over or self.clock.running is None:
            return None
        return self.clock.remaining(self.clock.running)

    def resign(self, color: chess.Color, reason: str = "Abandono") -> None:
        if self.over:
            raise GameError("La partida ha terminado")
        self._finish(self._win_for(not color), reason, "normal")

    def _win_for(self, color: chess.Color) -> str:
        return "1-0" if color == chess.WHITE else "0-1"

    def _finish(self, result: str, reason: str, termination: str) -> None:
        self.clock.stop()
        self.result = result
        self.reason = reason
        self.termination = termination

    def state(self) -> dict:
        """Everything the browser needs to draw the game."""
        board = self.board
        last = board.move_stack[-1].uci() if board.move_stack else None
        check = None
        if board.is_check():
            check = chess.square_name(board.king(board.turn))
        legal = []
        if self.is_turn_of(self.user_color):
            legal = [m.uci() for m in board.legal_moves]
        running = self.clock.running
        return {
            "status": "over" if self.over else "playing",
            "fen": board.fen(),
            "turn": color_name(board.turn),
            "user_color": color_name(self.user_color),
            "white_name": self.white_name,
            "black_name": self.black_name,
            "clock": {
                "white": self.clock.remaining(chess.WHITE),
                "black": self.clock.remaining(chess.BLACK),
                "running": color_name(running) if running is not None else None,
            },
            "moves": list(self.sans),
            "last_move": last,
            "check": check,
            "legal_moves": legal,
            "result": self.result,
            "reason": self.reason,
            "pgn_file": self.pgn_file,
        }


def parse_color_choice(choice: str, rand: Callable[[], float]) -> chess.Color:
    """'white', 'black' or 'random' to a color."""
    if choice == "white":
        return chess.WHITE
    if choice == "black":
        return chess.BLACK
    if choice == "random":
        return chess.WHITE if rand() < 0.5 else chess.BLACK
    raise GameError("Color no válido")
