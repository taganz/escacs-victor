import chess

from server.clock import ChessClock


class FakeTime:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t

    def advance(self, seconds):
        self.t += seconds


def make_clock(time=None, initial=600.0, increment=5.0):
    return ChessClock(initial, increment, now=time or FakeTime())


def play_sans(game, sans):
    """Play SAN moves, alternating colors, starting from the side to move."""
    for san in sans:
        game.play(game.board.parse_san(san), game.board.turn)
