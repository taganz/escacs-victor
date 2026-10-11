"""Writes a finished game as a .pgn file."""

from pathlib import Path

import chess
import chess.pgn

from server.game import Game

EVENT = "Partida contra Bot"
SITE = "escacs-victor"


def format_clock(seconds: float) -> str:
    total = int(seconds)
    return f"{total // 3600}:{total % 3600 // 60:02d}:{total % 60:02d}"


def build_pgn(game: Game) -> chess.pgn.Game:
    pgn = chess.pgn.Game()
    # Adds the SetUp and FEN tags if the game did not start from the usual position.
    pgn.setup(game.board.root())
    pgn.headers["Event"] = EVENT
    pgn.headers["Site"] = SITE
    pgn.headers["Date"] = game.started.strftime("%Y.%m.%d")
    pgn.headers["Round"] = "-"
    pgn.headers["White"] = game.white_name
    pgn.headers["Black"] = game.black_name
    pgn.headers["Result"] = game.result or "*"
    pgn.headers["TimeControl"] = f"{int(game.clock.initial)}+{int(game.clock.increment)}"
    pgn.headers["Termination"] = game.termination or "unterminated"

    node = pgn
    for move, clock in zip(game.board.move_stack, game.clocks_after):
        node = node.add_variation(move)
        node.comment = f"[%clk {format_clock(clock)}]"
    if game.reason:
        node.comment = (node.comment + " " if node.comment else "") + game.reason
    return pgn


def pgn_text(game: Game) -> str:
    return str(build_pgn(game)) + "\n"


def save_pgn(game: Game, folder: Path) -> Path:
    """Write the game to `folder/partida_AAAA-MM-DD_HHMM.pgn`, adding
    `_2`, `_3`... if that name is taken."""
    folder.mkdir(parents=True, exist_ok=True)
    stem = game.started.strftime("partida_%Y-%m-%d_%H%M")
    text = pgn_text(game)
    n = 1
    while True:
        path = folder / (f"{stem}.pgn" if n == 1 else f"{stem}_{n}.pgn")
        try:
            # "x" fails if the file exists, so two games ending at once never share a file.
            with path.open("x", encoding="utf-8", newline="\n") as f:
                f.write(text)
            return path
        except FileExistsError:
            n += 1
