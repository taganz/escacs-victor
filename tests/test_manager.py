import asyncio

import chess
import pytest

from server.clock import ChessClock
from server.game import GameError
from server.manager import GameManager


class FakeBot:
    provisional = False

    def __init__(self, moves=(), delay=0.0):
        self.moves = list(moves)
        self.delay = delay
        self.limits = []
        self.restarts = 0

    async def choose_move(self, board, time_limit):
        self.limits.append(time_limit)
        await asyncio.sleep(self.delay)
        if self.moves:
            return chess.Move.from_uci(self.moves.pop(0))
        return next(iter(board.legal_moves))

    def restart(self):
        self.restarts += 1


class FakeClient:
    def __init__(self):
        self.messages = []

    async def send_json(self, message):
        self.messages.append(message)

    def last_state(self):
        return [m for m in self.messages if m["type"] == "state"][-1]


async def settle(manager, timeout=2.0):
    """Wait until the bot is not thinking."""
    for _ in range(int(timeout / 0.01)):
        await asyncio.sleep(0.01)
        if not manager.bot_thinking:
            await asyncio.sleep(0.01)
            return


def make_manager(tmp_path, bot, initial=600.0, increment=5.0):
    return GameManager(bot, tmp_path, clock_factory=lambda: ChessClock(initial, increment))


def test_bot_moves_first_when_user_is_black(tmp_path):
    async def run():
        bot = FakeBot(["e2e4"])
        manager = make_manager(tmp_path, bot)
        client = FakeClient()
        await manager.connect(client)
        assert client.last_state()["game"] is None
        await manager.new_game("black")
        await settle(manager)
        state = client.last_state()["game"]
        assert state["moves"] == ["e4"]
        assert state["turn"] == "black"
        assert "e7e5" in state["legal_moves"]
        assert bot.limits and 0 < bot.limits[0] <= 25
        await manager.close()

    asyncio.run(run())


def test_full_game_saves_pgn(tmp_path):
    async def run():
        bot = FakeBot(["f2f3", "g2g4"])
        manager = make_manager(tmp_path, bot)
        client = FakeClient()
        await manager.connect(client)
        await manager.new_game("black")
        await settle(manager)
        await manager.user_move("e7e5")
        await settle(manager)
        await manager.user_move("d8h4")
        state = client.last_state()["game"]
        assert state["status"] == "over"
        assert state["result"] == "0-1"
        assert state["reason"] == "Jaque mate"
        files = list(tmp_path.glob("*.pgn"))
        assert [f.name for f in files] == [state["pgn_file"]]
        assert "Qh4#" in files[0].read_text(encoding="utf-8")
        await manager.close()

    asyncio.run(run())


def test_illegal_user_move_is_rejected(tmp_path):
    async def run():
        manager = make_manager(tmp_path, FakeBot())
        await manager.new_game("white")
        with pytest.raises(GameError):
            await manager.user_move("e2e5")
        with pytest.raises(GameError):
            await manager.user_move("nonsense")
        assert manager.game.board.fullmove_number == 1
        await manager.close()

    asyncio.run(run())


def test_new_game_during_game_resigns_and_saves(tmp_path):
    async def run():
        manager = make_manager(tmp_path, FakeBot())
        await manager.new_game("white")
        old = manager.game
        await manager.new_game("white")
        assert old.result == "0-1"
        assert old.reason == "Abandono (nueva partida)"
        assert old.pgn_file is not None
        assert manager.game is not old and not manager.game.over
        await manager.close()

    asyncio.run(run())


def test_resign(tmp_path):
    async def run():
        manager = make_manager(tmp_path, FakeBot())
        await manager.new_game("white")
        await manager.resign()
        assert manager.game.result == "0-1"
        assert manager.game.pgn_file is not None
        with pytest.raises(GameError):
            await manager.resign()
        await manager.close()

    asyncio.run(run())


def test_user_flag_ends_game(tmp_path):
    async def run():
        manager = make_manager(tmp_path, FakeBot(), initial=0.2)
        client = FakeClient()
        await manager.connect(client)
        await manager.new_game("white")
        await asyncio.sleep(0.5)
        state = client.last_state()["game"]
        assert state["status"] == "over"
        assert state["result"] == "0-1"
        assert state["reason"] == "Tiempo agotado"
        assert state["pgn_file"]
        await manager.close()

    asyncio.run(run())


def test_bot_flag_while_thinking(tmp_path):
    async def run():
        bot = FakeBot(delay=1.0)
        manager = make_manager(tmp_path, bot, initial=0.2)
        await manager.new_game("black")
        await asyncio.sleep(0.5)
        assert manager.game.result == "0-1"  # bot was white and lost on time
        assert bot.restarts == 1
        await asyncio.sleep(0.7)
        assert manager.game.board.move_stack == []  # the late move was ignored
        await manager.close()

    asyncio.run(run())


def test_illegal_bot_move_falls_back_to_random(tmp_path):
    async def run():
        manager = make_manager(tmp_path, FakeBot(["e2e5"]))
        client = FakeClient()
        await manager.connect(client)
        await manager.new_game("black")
        await settle(manager)
        assert len(manager.game.board.move_stack) == 1
        notices = [m for m in client.messages if m["type"] == "notice"]
        assert notices and "ilegal" in notices[0]["message"]
        await manager.close()

    asyncio.run(run())
