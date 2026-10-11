import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from server.app import create_app
from server.bot_runner import BotRunner


@pytest.fixture
def client(tmp_path):
    app = create_app(bot_factory=lambda: BotRunner(tmp_path / "missing.py"), games_dir=tmp_path)
    with TestClient(app) as c:
        yield c


def play_until_moves(ws, n):
    while True:
        message = ws.receive_json()
        if message["type"] == "state" and len(message["game"]["moves"]) >= n:
            return message


def test_websocket_game(client, tmp_path):
    assert client.get("/").status_code == 200
    assert client.get("/pieces.svg").status_code == 200
    with client.websocket_connect("/ws") as ws:
        first = ws.receive_json()
        assert first["type"] == "state" and first["game"] is None
        assert first["provisional_bot"] is True

        ws.send_json({"type": "new_game", "color": "white"})
        message = ws.receive_json()
        game_id = message["game_id"]
        assert game_id
        assert "e2e4" in message["game"]["legal_moves"]

        ws.send_json({"type": "move", "uci": "e2e5"})
        assert ws.receive_json() == {"type": "error", "message": "Jugada ilegal"}
        ws.receive_json()

        ws.send_text("not json")
        assert ws.receive_json()["type"] == "error"

        ws.send_json({"type": "move", "uci": "e2e4"})
        play_until_moves(ws, 2)

    # Reconnecting with the id gets back to the same game.
    with client.websocket_connect(f"/ws?game={game_id}") as ws:
        message = ws.receive_json()
        assert message["game_id"] == game_id
        assert len(message["game"]["moves"]) == 2

        ws.send_json({"type": "resign"})
        message = ws.receive_json()
        assert message["game"]["result"] == "0-1"
        assert (tmp_path / message["game"]["pgn_file"]).exists()
        assert message["pgn"].startswith("[Event")

    # Another browser does not see it.
    with client.websocket_connect("/ws?game=someone-else") as ws:
        assert ws.receive_json()["game"] is None
        ws.send_json({"type": "resign"})
        assert ws.receive_json()["message"] == "No hay ninguna partida"


def test_rejects_other_origins(client):
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws", headers={"origin": "https://evil.example"}) as ws:
            ws.receive_json()
    with client.websocket_connect("/ws", headers={"origin": "http://testserver"}) as ws:
        assert ws.receive_json()["type"] == "state"
