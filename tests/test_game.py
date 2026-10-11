import chess
import pytest

from server.game import Game, GameError, parse_color_choice, parse_fen
from tests.helpers import FakeTime, make_clock, play_sans


def new_game(user=chess.WHITE, time=None, initial=600.0):
    game = Game(user, clock=make_clock(time or FakeTime(), initial=initial))
    game.start()
    return game


def test_rejects_moves_out_of_turn_and_illegal():
    game = new_game()
    with pytest.raises(GameError):
        game.play(chess.Move.from_uci("e7e5"), chess.BLACK)
    with pytest.raises(GameError):
        game.play(chess.Move.from_uci("e2e5"), chess.WHITE)
    game.play(chess.Move.from_uci("e2e4"), chess.WHITE)
    assert game.sans == ["e4"]
    assert game.board.turn == chess.BLACK


def test_checkmate():
    game = new_game()
    play_sans(game, ["f3", "e5", "g4", "Qh4#"])
    assert game.result == "0-1"
    assert game.reason == "Jaque mate"
    assert game.termination == "normal"
    assert game.clock.running is None
    with pytest.raises(GameError):
        game.play(chess.Move.from_uci("a2a3"), chess.WHITE)


def test_threefold_repetition_is_a_draw():
    game = new_game()
    play_sans(game, ["Nf3", "Nf6", "Ng1", "Ng8", "Nf3", "Nf6", "Ng1"])
    assert not game.over  # Ng8 would repeat, but it has not been played yet
    play_sans(game, ["Ng8"])
    assert game.result == "1/2-1/2"
    assert game.reason == "Triple repetición"


def test_stalemate():
    game = new_game()
    game.board = chess.Board("7k/8/5QK1/8/8/8/8/8 w - - 0 1")
    game.play(chess.Move.from_uci("f6f7"), chess.WHITE)
    assert game.result == "1/2-1/2"
    assert game.reason == "Rey ahogado"


def test_timeout_loses():
    time = FakeTime()
    game = new_game(time=time)
    time.advance(601)
    with pytest.raises(GameError):
        game.play(chess.Move.from_uci("e2e4"), chess.WHITE)
    assert game.result == "0-1"
    assert game.termination == "time forfeit"


def test_timeout_is_draw_if_winner_cannot_mate():
    time = FakeTime()
    game = new_game(time=time)
    game.board = chess.Board("4k3/8/8/8/8/8/4P3/4K3 w - - 0 1")  # black has only the king
    time.advance(601)
    assert game.check_flag()
    assert game.result == "1/2-1/2"


def test_resign():
    game = new_game(user=chess.BLACK)
    game.resign(chess.BLACK)
    assert game.result == "1-0"
    assert game.reason == "Abandono"


def test_state_lists_legal_moves_only_on_user_turn():
    game = new_game(user=chess.BLACK)
    assert game.state()["legal_moves"] == []
    game.play(chess.Move.from_uci("e2e4"), chess.WHITE)
    state = game.state()
    assert "e7e5" in state["legal_moves"]
    assert state["white_name"] == "Bot"
    assert state["black_name"] == "user"
    assert state["last_move"] == "e2e4"


def test_parse_color_choice():
    assert parse_color_choice("white", lambda: 0.9) == chess.WHITE
    assert parse_color_choice("black", lambda: 0.1) == chess.BLACK
    assert parse_color_choice("random", lambda: 0.1) == chess.WHITE
    assert parse_color_choice("random", lambda: 0.9) == chess.BLACK
    with pytest.raises(GameError):
        parse_color_choice("green", lambda: 0.5)


def test_fifty_move_rule():
    game = new_game()
    game.board = chess.Board("4k3/8/8/8/8/8/R7/4K3 w - - 99 80")
    game.play(chess.Move.from_uci("a2a3"), chess.WHITE)
    assert game.result == "1/2-1/2"
    assert game.reason == "Regla de los 50 movimientos"


def test_parse_fen():
    assert parse_fen("") is None
    assert parse_fen("   ") is None
    board = parse_fen("  4k3/8/8/8/8/8/4P3/4K3   b - - 0 30 ")
    assert board.turn == chess.BLACK and board.fullmove_number == 30
    with pytest.raises(GameError, match="FEN no válido"):
        parse_fen("esto no es un fen")
    with pytest.raises(GameError, match="no es legal"):
        parse_fen("4k3/8/8/8/8/8/8/4K2K w - - 0 1")  # two white kings
    with pytest.raises(GameError, match="ya ha terminado"):
        parse_fen("rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3")


def test_game_from_fen_starts_black_clock():
    board = parse_fen("4k3/8/8/8/8/8/4P3/4K3 b - - 0 30")
    game = Game(chess.WHITE, clock=make_clock(), board=board)
    game.start()
    assert game.clock.running == chess.BLACK
    state = game.state()
    assert state["turn"] == "black"
    assert state["legal_moves"] == []
    assert state["first_move_number"] == 30
    assert state["first_turn"] == "black"
    play_sans(game, ["Kd7", "e4"])
    assert game.state()["first_move_number"] == 30
