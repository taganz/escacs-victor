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


def unique_path(folder: Path, stem: str) -> Path:
    """`folder/stem.pgn`, or `stem_2.pgn`, `stem_3.pgn`... if it already exists."""
    path = folder / f"{stem}.pgn"
    n = 2
    while path.exists():
        path = folder / f"{stem}_{n}.pgn"
        n += 1
    return path


def save_pgn(game: Game, folder: Path) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = unique_path(folder, game.started.strftime("partida_%Y-%m-%d_%H%M"))
    text = str(build_pgn(game))
    path.write_text(text + "\n", encoding="utf-8", newline="\n")
    return path
