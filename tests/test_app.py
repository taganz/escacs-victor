from fastapi.testclient import TestClient

from server.app import create_app
from server.bot_runner import BotRunner


def test_websocket_game(tmp_path):
    app = create_app(bot=BotRunner(tmp_path / "missing.py"), games_dir=tmp_path)
    with TestClient(app) as client:
        assert client.get("/").status_code == 200
        assert client.get("/pieces.svg").status_code == 200
        with client.websocket_connect("/ws") as ws:
            first = ws.receive_json()
            assert first["type"] == "state" and first["game"] is None
            assert first["provisional_bot"] is True

            ws.send_json({"type": "new_game", "color": "white"})
            state = ws.receive_json()["game"]
            assert state["user_color"] == "white"
            assert "e2e4" in state["legal_moves"]

            ws.send_json({"type": "move", "uci": "e2e5"})
            assert ws.receive_json() == {"type": "error", "message": "Jugada ilegal"}
            ws.receive_json()

            ws.send_json({"type": "move", "uci": "e2e4"})
            # First the state after our move, then the one after the bot's reply.
            while True:
                message = ws.receive_json()
                if message["type"] == "state" and len(message["game"]["moves"]) == 2:
                    break

            ws.send_json({"type": "resign"})
            state = ws.receive_json()["game"]
            assert state["result"] == "0-1"
            assert (tmp_path / state["pgn_file"]).exists()

            ws.send_json({"type": "bogus"})
            assert ws.receive_json()["type"] == "error"
