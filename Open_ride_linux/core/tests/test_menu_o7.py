"""Bots choisis au menu : argument `bots` de `start` (lot O7, contrat 1.3)."""

import asyncio

from test_contract_ipc import make_session, run_steps


def bot_session(tmp_path, monkeypatch, port):
    s, cap = make_session(tmp_path, monkeypatch, port=port)
    s.server.send_error = lambda code, message: cap.frames.append({"type": "error", "v": 1, "code": code,
                                                                     "message": message})
    return s, cap


def test_menu_bots_replace_the_session_bots(tmp_path, monkeypatch):
    async def scenario():
        s, cap = bot_session(tmp_path, monkeypatch, 5990)
        s.cfg.rider.ftp_w = 240
        s._on_command("select_route", {"route_id": "demo"}, 1)
        refused = [
            {"bots": "250"},                                                   # pas une liste
            {"bots": [{"kind": "constant"}]},                                  # ni power_w ni ftp_pct
            {"bots": [{"kind": "constant", "power_w": 200, "ftp_pct": 90}]},   # les deux
            {"bots": [{"kind": "constant", "power_w": True}]},
            {"bots": [{"kind": "constant", "power_w": -5}]},
            {"bots": [{"kind": "constant", "power_w": 200}] * 5},              # 5 bots constants
            {"bots": [{"kind": "rival"}]},
            {"bots": [{"kind": "ghost"}]},                                     # aucune séance passée
        ]
        for i, args in enumerate(refused):
            s._on_command("start", args, 10 + i)
            assert cap.of("error")[-1]["code"] == "bot_invalid", args
            assert s.state.session_state == "READY" and s.bots == []
        s._on_command("start", {"bots": [{"kind": "constant", "power_w": 250},
                                         {"kind": "constant", "ftp_pct": 100}]}, 30)
        assert s.state.session_state == "RUNNING"
        assert [(b.id, b.name, b.power_w) for b in s.bots] == [("bot1", "Bot 250 W", 250.0),
                                                                ("bot2", "Bot 100 % FTP", 240.0)]
        run_steps(s, 300)
        assert [b.to_dict()["kind"] for b in s.bots] == ["constant", "constant"] and s.bots[0].s > 0
        s._on_command("end_session", {"save": True}, 31)
        # Séance suivante : le fantôme de la séance enregistrée sur ce parcours, bots recréés au départ.
        s._on_command("select_route", {"route_id": "demo"}, 32)
        s._on_command("start", {"bots": [{"kind": "ghost"}, {"kind": "constant", "power_w": 200}]}, 33)
        assert s.state.session_state == "RUNNING", cap.of("error")
        assert [b.kind for b in s.bots] == ["ghost", "constant"] and s.bots[1].s == 0.0
        s._on_command("end_session", {"save": False}, 34)
        # `bots` absent : ceux de la ligne de commande (aucun ici) ; `bots` vide : séance sans bot.
        s._on_command("select_route", {"route_id": "demo"}, 35)
        s._on_command("start", {}, 36)
        assert s.bots == []
        s._on_command("end_session", {"save": False}, 37)
        s._on_command("select_route", {"route_id": "demo"}, 38)
        s._on_command("start", {"bots": []}, 39)
        run_steps(s, 10, 500.0)
        assert s.bots == []
    asyncio.run(scenario())


def test_command_line_bots_come_back_without_bots_argument(tmp_path, monkeypatch):
    from openride_core.bots import ConstantPowerBot

    async def scenario():
        s, cap = bot_session(tmp_path, monkeypatch, 5994)
        cli = ConstantPowerBot(220.0)
        s.bots = s._cli_bots = [cli]
        s._on_command("select_route", {"route_id": "demo"}, 1)
        s._on_command("start", {"bots": [{"kind": "constant", "power_w": 300}]}, 2)
        assert [b.power_w for b in s.bots] == [300.0]
        s._on_command("end_session", {"save": False}, 3)
        s._on_command("select_route", {"route_id": "demo"}, 4)
        s._on_command("start", {}, 5)
        assert s.bots == [cli]
    asyncio.run(scenario())
