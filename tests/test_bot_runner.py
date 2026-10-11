import asyncio
import textwrap

import chess

from server.bot_runner import KIND_MAIN, KIND_RANDOM, BotRunner, bot_time_limit, has_choose_move

FAKE_MAIN = textwrap.dedent('''
    import json
    import chess

    with open("opening_book.json", encoding="utf-8") as f:   # relative path, like the real main.py
        BOOK = json.load(f)

    def choose_move(board, time_limit):
        key = " ".join(board.fen().split()[:4])
        if key in BOOK:
            return chess.Move.from_uci(next(iter(BOOK[key])))
        return next(iter(board.legal_moves))

    if __name__ == "__main__":
        input("this must not run on import")
''')


def test_has_choose_move(tmp_path):
    path = tmp_path / "main.py"
    path.write_text("def best_move(board, depth):\n    pass\n", encoding="utf-8")
    assert not has_choose_move(path)
    path.write_text(FAKE_MAIN, encoding="utf-8")
    assert has_choose_move(path)
    assert not has_choose_move(tmp_path / "missing.py")
    assert BotRunner(tmp_path / "missing.py").kind == KIND_RANDOM


def test_bot_time_limit():
    assert bot_time_limit(600, 5) == 25
    assert bot_time_limit(3, 5) == 2
    assert bot_time_limit(0.5, 5) == 0.05


def test_runs_main_py_in_a_separate_process(tmp_path):
    bot_dir = tmp_path / "bot"
    bot_dir.mkdir()
    (bot_dir / "main.py").write_text(FAKE_MAIN, encoding="utf-8")
    start = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq -"
    (bot_dir / "opening_book.json").write_text(f'{{"{start}": {{"g1f3": 1}}}}', encoding="utf-8")

    runner = BotRunner(bot_dir / "main.py")
    assert runner.kind == KIND_MAIN

    async def run():
        runner.start()
        try:
            move = await runner.choose_move(chess.Board(), 1.0)
            assert move == chess.Move.from_uci("g1f3")
            board = chess.Board()
            board.push_san("e4")
            move = await runner.choose_move(board, 1.0)
            assert move in board.legal_moves
        finally:
            runner.close()

    asyncio.run(run())


def test_random_bot(tmp_path):
    runner = BotRunner(tmp_path / "missing.py")

    async def run():
        runner.start()
        try:
            board = chess.Board()
            assert await runner.choose_move(board, 1.0) in board.legal_moves
        finally:
            runner.close()

    asyncio.run(run())
