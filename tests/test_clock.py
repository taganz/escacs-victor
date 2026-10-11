import chess

from tests.helpers import FakeTime, make_clock


def test_only_running_clock_counts_down():
    time = FakeTime()
    clock = make_clock(time)
    clock.start(chess.WHITE)
    time.advance(10)
    assert clock.remaining(chess.WHITE) == 590
    assert clock.remaining(chess.BLACK) == 600


def test_press_adds_increment_and_switches():
    time = FakeTime()
    clock = make_clock(time)
    clock.start(chess.WHITE)
    time.advance(10)
    clock.press()
    assert clock.running == chess.BLACK
    assert clock.remaining(chess.WHITE) == 595
    time.advance(3)
    assert clock.remaining(chess.BLACK) == 597
    assert clock.remaining(chess.WHITE) == 595


def test_flagged_and_never_negative():
    time = FakeTime()
    clock = make_clock(time, initial=5)
    clock.start(chess.WHITE)
    time.advance(4.9)
    assert clock.flagged() is None
    time.advance(1)
    assert clock.flagged() == chess.WHITE
    assert clock.remaining(chess.WHITE) == 0


def test_stop_freezes_time():
    time = FakeTime()
    clock = make_clock(time)
    clock.start(chess.BLACK)
    time.advance(7)
    clock.stop()
    time.advance(100)
    assert clock.remaining(chess.BLACK) == 593
    assert clock.running is None
