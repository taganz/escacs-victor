import io
from datetime import datetime

import chess
import chess.pgn

from server.game import Game
from server.pgn_writer import format_clock, pgn_text, save_pgn
from tests.helpers import FakeTime, make_clock, play_sans


def finished_game(started):
    time = FakeTime()
    game = Game(chess.BLACK, clock=make_clock(time), started=started)
    game.start()
    for san in ["f3", "e5", "g4", "Qh4#"]:
        time.advance(2)
        play_sans(game, [san])
    return game


def test_save_pgn(tmp_path):
    game = finished_game(datetime(2026, 10, 11, 15, 30))
    path = save_pgn(game, tmp_path)
    assert path.name == "partida_2026-10-11_1530.pgn"

    parsed = chess.pgn.read_game(path.open(encoding="utf-8"))
    h = parsed.headers
    assert h["White"] == "Bot"
    assert h["Black"] == "user"
    assert h["Result"] == "0-1"
    assert h["Date"] == "2026.10.11"
    assert h["TimeControl"] == "600+5"
    assert h["Termination"] == "normal"
    assert [m.uci() for m in parsed.mainline_moves()] == ["f2f3", "e7e5", "g2g4", "d8h4"]
    assert next(iter(parsed.mainline())).clock() == 603
    assert "Jaque mate" in path.read_text(encoding="utf-8")


def test_name_collision_gets_suffix(tmp_path):
    started = datetime(2026, 10, 11, 15, 30)
    first = save_pgn(finished_game(started), tmp_path)
    second = save_pgn(finished_game(started), tmp_path)
    assert first.name == "partida_2026-10-11_1530.pgn"
    assert second.name == "partida_2026-10-11_1530_2.pgn"


def test_format_clock():
    assert format_clock(605.9) == "0:10:05"
    assert format_clock(0) == "0:00:00"


def test_pgn_from_fen_has_setup_tags():
    fen = "4k3/8/8/8/8/8/4P3/4K3 b - - 0 30"
    game = Game(chess.WHITE, clock=make_clock(), board=chess.Board(fen))
    game.start()
    play_sans(game, ["Kd7", "e4"])
    game.resign(chess.WHITE)
    parsed = chess.pgn.read_game(io.StringIO(pgn_text(game)))
    assert parsed.headers["SetUp"] == "1"
    assert parsed.headers["FEN"] == fen
    assert [m.uci() for m in parsed.mainline_moves()] == ["e8d7", "e2e4"]


def test_pgn_from_usual_position_has_no_fen_tag():
    game = finished_game(datetime(2026, 10, 11, 15, 30))
    assert "FEN" not in chess.pgn.read_game(io.StringIO(pgn_text(game))).headers
