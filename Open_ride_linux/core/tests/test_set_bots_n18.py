"""Bots changés sur l'écran de pause : commande `set_bots` et ligne `bots` du journal (lot N18, révision 1.9)."""

import asyncio

from test_contract_ipc import make_session, run_steps
from test_menu_o7 import bot_session

THREE = [{"kind": "constant", "power_w": 180}, {"kind": "constant", "power_w": 220},
         {"kind": "constant", "power_w": 260}]


def _bot_lines(s):
    return [line for line in s._rec.lines if line.get("kind") == "bots"]


def test_set_bots_in_pause_keeps_moves_adds_and_removes(tmp_path, monkeypatch):
    async def scenario():
        s, cap = bot_session(tmp_path, monkeypatch, 5996)
        s.cfg.rider.ftp_w = 240
        s._on_command("select_route", {"route_id": "demo"}, 1)
        s._on_command("start", {"bots": THREE}, 2)
        assert s.state.session_state == "RUNNING"
        first = _bot_lines(s)
        assert [line["reason"] for line in first] == ["start"]
        assert [b["power_w"] for b in first[0]["bots"]] == [180.0, 220.0, 260.0]
        run_steps(s, 500, 200.0)
        # En roulant : refusé (`busy`), rien ne change.
        s._on_command("set_bots", {"bots": []}, 3)
        assert cap.of("error")[-1]["code"] == "busy" and len(s.bots) == 3
        s._on_command("pause", {}, 4)
        assert s.state.session_state == "PAUSED"
        by_id = {b.id: b for b in s.bots}
        s_before = {b.id: b.s for b in s.bots}
        # Liste refusée : `bot_invalid`, bots inchangés.
        s._on_command("set_bots", {"bots": [{"kind": "rival"}]}, 5)
        assert cap.of("error")[-1]["code"] == "bot_invalid" and list(by_id) == [b.id for b in s.bots]
        # 180 W gardé, 220 W passe à 300 W et 260 W à 100 % de la FTP (mêmes coureurs), un bot 200 W ajouté.
        s._on_command("set_bots", {"bots": [{"kind": "constant", "power_w": 180},
                                            {"kind": "constant", "power_w": 300},
                                            {"kind": "constant", "ftp_pct": 100},
                                            {"kind": "constant", "power_w": 200}]}, 6)
        new_id = s.bots[3].id
        assert [b.id for b in s.bots[:3]] == ["bot1", "bot2", "bot3"] and new_id not in by_id   # id jamais pris
        assert all(s.bots[i] is by_id[f"bot{i + 1}"] and s.bots[i].s == s_before[f"bot{i + 1}"] for i in range(3))
        assert [(b.power_w, b.name) for b in s.bots] == [(180.0, "Bot 180 W"), (300.0, "Bot 300 W"),
                                                          (240.0, "Bot 100 % FTP"), (200.0, "Bot 200 W")]
        assert abs(s.bots[3].s - s.physics.s) < 1.0 and s.bots[3].v == s.physics.v
        line = _bot_lines(s)[-1]
        assert line["reason"] == "set_bots" and [b.get("power_w") for b in line["bots"]] == [180.0, 300.0, 240.0, 200.0]
        # Critère 3 du cahier : un bot retiré n'est plus dans `bots` à la trame suivant la reprise.
        s._on_command("set_bots", {"bots": [{"kind": "constant", "power_w": 180},
                                            {"kind": "constant", "power_w": 200}]}, 7)
        assert [b.id for b in s.bots] == ["bot1", new_id]
        assert [b["id"] for b in _bot_lines(s)[-1]["bots"]] == ["bot1", new_id]
        s._on_command("resume", {}, 8)
        run_steps(s, 2, 200.0)
        assert [b.to_dict()["id"] for b in s.bots] == ["bot1", new_id]   # liste `bots` de la trame suivante
        # Bot ajouté ensuite : jamais bot2 ni bot3 (chronos, écarts et maillots suivent les ids).
        s._on_command("pause", {}, 9)
        s._on_command("set_bots", {"bots": [{"kind": "constant", "power_w": 180},
                                            {"kind": "constant", "power_w": 200},
                                            {"kind": "constant", "power_w": 150}]}, 10)
        assert [b.id for b in s.bots[:2]] == ["bot1", new_id] and s.bots[2].id not in by_id
        s._on_command("resume", {}, 11)
        # Retirer tous les bots.
        s._on_command("pause", {}, 12)
        s._on_command("set_bots", {"bots": []}, 13)
        assert s.bots == [] and _bot_lines(s)[-1]["bots"] == []
        s._on_command("resume", {}, 14)
        run_steps(s, 2, 200.0)
        assert s.bots == []
    asyncio.run(scenario())


def test_set_bots_profile_bot_added_in_pause_is_calibrated(tmp_path, monkeypatch):
    async def scenario():
        s, cap = bot_session(tmp_path, monkeypatch, 5997)
        s._on_command("select_route", {"route_id": "demo"}, 1)
        s._on_command("start", {}, 2)
        assert _bot_lines(s) == []                              # sans bot : pas de ligne au départ
        run_steps(s, 200, 200.0)
        s._on_command("pause", {}, 3)
        s._on_command("set_bots", {"bots": [{"kind": "profile", "profile": "climber"}]}, 4)
        assert len(s.bots) == 1 and s.bots[0].profile == "climber"
        assert getattr(s.bots[0], "scale", 1.0) != 1.0 and abs(s.bots[0].s - s.physics.s) < 1.0   # calibré
        assert _bot_lines(s)[-1]["bots"][0]["profile"] == "climber"
        s._on_command("resume", {}, 5)
        run_steps(s, 100, 200.0)
        assert s.bots[0].s > s.physics.s - 50.0 and s.bots[0].v > 0
    asyncio.run(scenario())


def test_set_bots_refused_outside_a_session(tmp_path, monkeypatch):
    async def scenario():
        s, cap = bot_session(tmp_path, monkeypatch, 5998)
        s._on_command("select_route", {"route_id": "demo"}, 1)
        s._on_command("set_bots", {"bots": THREE}, 2)
        assert cap.of("error")[-1]["code"] == "busy" and s.bots == []
    asyncio.run(scenario())
