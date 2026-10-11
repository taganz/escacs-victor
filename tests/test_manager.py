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
        self.started = False
        self.closed = False

    def start(self):
        self.started = True

    def close(self):
        self.closed = True

    async def choose_move(self, board, time_limit):
        self.limits.append(time_limit)
        await asyncio.sleep(self.delay)
        if self.moves:
            return chess.Move.from_uci(self.moves.pop(0))
        return next(iter(board.legal_moves))


class FakeClient:
    def __init__(self):
        self.messages = []

    async def send_json(self, message):
        self.messages.append(message)

    def last_state(self):
        return [m for m in self.messages if m["type"] == "state"][-1]


async def settle(session, timeout=2.0):
    """Wait until the bot is not thinking."""
    for _ in range(int(timeout / 0.01)):
        await asyncio.sleep(0.01)
        if not session.bot_thinking:
            await asyncio.sleep(0.01)
            return


def make_manager(tmp_path, bots, initial=600.0, **kwargs):
    """`bots` is a list of FakeBot, one per game started."""
    queue = list(bots)
    return GameManager(lambda: queue.pop(0), tmp_path, clock_factory=lambda: ChessClock(initial, 5.0), **kwargs)


async def start(manager, color, ip="1.1.1.1", previous=None, client=None):
    session = await manager.new_game(color, ip, previous)
    if client is not None:
        session.clients.add(client)
    return session


def test_bot_moves_first_when_user_is_black(tmp_path):
    async def run():
        bot = FakeBot(["e2e4"])
        manager = make_manager(tmp_path, [bot])
        client = FakeClient()
        session = await start(manager, "black", client=client)
        assert bot.started
        await settle(session)
        message = client.last_state()
        assert message["game_id"] == session.id
        state = message["game"]
        assert state["moves"] == ["e4"]
        assert "e7e5" in state["legal_moves"]
        assert bot.limits and 0 < bot.limits[0] <= 25
        await manager.close()

    asyncio.run(run())


def test_full_game_saves_pgn_and_stops_bot(tmp_path):
    async def run():
        bot = FakeBot(["f2f3", "g2g4"])
        manager = make_manager(tmp_path, [bot])
        client = FakeClient()
        session = await start(manager, "black", client=client)
        await settle(session)
        await session.user_move("e7e5")
        await settle(session)
        await session.user_move("d8h4")
        message = client.last_state()
        state = message["game"]
        assert state["status"] == "over"
        assert state["reason"] == "Jaque mate"
        files = list(tmp_path.glob("*.pgn"))
        assert [f.name for f in files] == [state["pgn_file"]]
        assert files[0].read_text(encoding="utf-8") == message["pgn"]
        assert "Qh4#" in message["pgn"]
        assert bot.closed
        await manager.close()

    asyncio.run(run())


def test_illegal_user_move_is_rejected(tmp_path):
    async def run():
        manager = make_manager(tmp_path, [FakeBot()])
        session = await start(manager, "white")
        with pytest.raises(GameError):
            await session.user_move("e2e5")
        with pytest.raises(GameError):
            await session.user_move("nonsense")
        assert session.game.board.fullmove_number == 1
        await manager.close()

    asyncio.run(run())


def test_each_player_has_their_own_game(tmp_path):
    async def run():
        manager = make_manager(tmp_path, [FakeBot(), FakeBot()])
        a = await start(manager, "white", ip="1.1.1.1")
        b = await start(manager, "white", ip="2.2.2.2")
        assert a.id != b.id
        await a.user_move("e2e4")
        assert b.game.board.move_stack == []
        assert manager.find(a.id) is a
        assert manager.find("unknown") is None
        assert manager.find(None) is None
        await manager.close()

    asyncio.run(run())


def test_new_game_resigns_the_previous_one(tmp_path):
    async def run():
        first_bot = FakeBot()
        manager = make_manager(tmp_path, [first_bot, FakeBot()])
        old = await start(manager, "white")
        new = await start(manager, "white", previous=old)
        assert old.game.result == "0-1"
        assert old.game.reason == "Abandono (nueva partida)"
        assert old.game.pgn_file is not None
        assert first_bot.closed
        assert new.active
        await manager.close()

    asyncio.run(run())


def test_limits_on_games_in_progress(tmp_path):
    async def run():
        manager = make_manager(tmp_path, [FakeBot() for _ in range(5)], max_active=3, max_active_per_ip=2)
        await start(manager, "white", ip="1.1.1.1")
        mine = await start(manager, "white", ip="1.1.1.1")
        with pytest.raises(GameError, match="demasiadas"):
            await start(manager, "white", ip="1.1.1.1")
        await start(manager, "white", ip="2.2.2.2")
        with pytest.raises(GameError, match="ocupado"):
            await start(manager, "white", ip="3.3.3.3")
        # Starting over from a game in progress frees its place first.
        await start(manager, "white", ip="1.1.1.1", previous=mine)
        await manager.close()

    asyncio.run(run())


def test_finished_games_are_forgotten(tmp_path):
    async def run():
        manager = make_manager(tmp_path, [FakeBot()], keep_finished=0)
        session = await start(manager, "white")
        await session.resign()
        session.clients.add(FakeClient())
        assert manager.find(session.id) is session  # still watched
        session.clients.clear()
        await asyncio.sleep(0.01)
        assert manager.find(session.id) is None
        await manager.close()

    asyncio.run(run())


def test_user_flag_ends_game(tmp_path):
    async def run():
        manager = make_manager(tmp_path, [FakeBot()], initial=0.2)
        client = FakeClient()
        session = await start(manager, "white", client=client)
        await asyncio.sleep(0.5)
        state = client.last_state()["game"]
        assert state["status"] == "over"
        assert state["result"] == "0-1"
        assert state["reason"] == "Tiempo agotado"
        assert state["pgn_file"]
        assert not session.active
        await manager.close()

    asyncio.run(run())


def test_bot_flag_while_thinking(tmp_path):
    async def run():
        bot = FakeBot(delay=1.0)
        manager = make_manager(tmp_path, [bot], initial=0.2)
        session = await start(manager, "black")
        await asyncio.sleep(0.5)
        assert session.game.result == "0-1"  # bot was white and lost on time
        assert bot.closed
        await asyncio.sleep(0.7)
        assert session.game.board.move_stack == []  # the late move was ignored
        await manager.close()

    asyncio.run(run())


def test_illegal_bot_move_falls_back_to_random(tmp_path):
    async def run():
        manager = make_manager(tmp_path, [FakeBot(["e2e5"])])
        client = FakeClient()
        session = await start(manager, "black", client=client)
        await settle(session)
        assert len(session.game.board.move_stack) == 1
        notices = [m for m in client.messages if m["type"] == "notice"]
        assert notices and "ilegal" in notices[0]["message"]
        await manager.close()

    asyncio.run(run())
