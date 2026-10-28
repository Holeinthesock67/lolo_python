"""Tests unitaires du lot Q1 : difficulté du trainer réglable pendant la séance."""

import asyncio
import logging
from pathlib import Path

from openride_core import fit_export
from openride_core.config import Config, TrainerConfig
from openride_core.input_providers import NullProvider
from openride_core.journal import read_journal
from openride_core.mock_driver import MockDriver
from openride_core.session import CoreSession


def make_session(tmp_path, monkeypatch, cfg=None, port=5850):
    monkeypatch.setattr(fit_export, "ACTIVITIES_DIR", tmp_path / "act")
    c = cfg or Config()
    c.ipc.port_state, c.ipc.port_commands = port, port + 1
    s = CoreSession(
        c,
        driver=MockDriver(),
        inputs=[NullProvider()],
        journal_dir=tmp_path / "journal",
        routes_root=tmp_path / "routes",
        config_path=tmp_path / "config.toml",
    )
    return s


def test_default_difficulty_is_50(tmp_path, monkeypatch, caplog):
    """Critère 2 : sans difficulty_pct dans config.toml, défaut à 50 % et log au démarrage."""
    with caplog.at_level(logging.INFO):
        s = make_session(tmp_path, monkeypatch, port=5852)
        assert TrainerConfig().difficulty_pct == 50.0
        assert s.difficulty_pct == 50.0
        assert s.state.difficulty_pct == 50
        assert s.server.hello_config["difficulty_pct"] == 50
        assert any("Difficulté du trainer : 50 %" in r.message for r in caplog.records)


def test_simulated_session_difficulty_change(tmp_path, monkeypatch, caplog):
    """Critère 3 : pente 8 % braquet 12 -> grade_sent à 50 % puis 30 %, rampe lissée, vitesse inchangée."""
    async def scenario():
        cfg = Config()
        cfg.trainer.grade_rate_up_pct_per_s = cfg.trainer.grade_rate_down_pct_per_s = 2.0
        cfg.trainer.latency_tau_s = 0.0

        s = make_session(tmp_path / "main", monkeypatch, cfg=cfg, port=5854)
        ref = make_session(tmp_path / "ref", monkeypatch, cfg=cfg, port=5860)

        for sess in (s, ref):
            sess._on_command("select_route", {"route_id": "demo"}, 1)
            sess._on_command("start", {}, 2)
            sess.gearing.k = 12
            sess.route.grade_at = lambda pos: 8.0

        eff_100 = s.gearing.effective_grade(8.0, 1.0)
        eff_50 = s.gearing.effective_grade(8.0, 0.5)
        assert abs(eff_50 - eff_100 * 0.5) < 1e-6

        # Roule pour atteindre la consigne à 50 %
        for i in range(200):
            for sess in (s, ref):
                sess.driver._power_w = 200.0
                sess._step(0.02, 10.0 + i * 0.02)

        grade_before = s._grade_sent
        assert abs(grade_before - eff_50) < 0.05
        assert abs(s.state.v - ref.state.v) < 1e-9

        with caplog.at_level(logging.INFO):
            s._on_command("set_difficulty", {"pct": 30}, 3)
            assert s.difficulty_pct == 30.0
            assert s.state.difficulty_pct == 30
            assert s.server.hello_config["difficulty_pct"] == 30
            assert any("Difficulté : 50 % -> 30 %" in r.message for r in caplog.records)

        eff_30 = s.gearing.effective_grade(8.0, 0.3)
        assert abs(eff_30 - eff_100 * 0.3) < 1e-6

        # Après 0.5 s (25 pas de 0.02s), la variation de s._grade_sent est limitée par grade_rate * dt
        for i in range(25):
            for sess in (s, ref):
                sess.driver._power_w = 200.0
                sess._step(0.02, 20.0 + i * 0.02)

        # La variation sur 0.5 s ne dépasse pas 2.0 * 0.5 = 1.0 %
        assert abs(s._grade_sent - grade_before) <= 2.0 * 0.5 + 0.01

        # Après stabilisation complète vers eff_30
        for i in range(200):
            for sess in (s, ref):
                sess.driver._power_w = 200.0
                sess._step(0.02, 30.0 + i * 0.02)

        assert abs(s._grade_sent - eff_30) < 0.05
        # La vitesse virtuelle est strictement identique entre les deux séances (la difficulté n'influence pas la physique)
        assert abs(s.state.v - ref.state.v) < 1e-9

    asyncio.run(scenario())


def test_set_difficulty_bounds_and_errors(tmp_path, monkeypatch):
    """Critère 4 : -5 borné à 0, 150 borné à 100, 'abc' refusé avec bad_args, acceptée en RUNNING et PAUSED."""
    async def scenario():
        s = make_session(tmp_path, monkeypatch, port=5856)
        errors = []
        s.server.send_error = lambda code, msg: errors.append((code, msg))

        # En IDLE
        s._on_command("set_difficulty", {"pct": -5}, 1)
        assert s.difficulty_pct == 0.0
        assert s.state.difficulty_pct == 0

        s._on_command("set_difficulty", {"pct": 150}, 2)
        assert s.difficulty_pct == 100.0
        assert s.state.difficulty_pct == 100

        # En READY
        s._on_command("select_route", {"route_id": "demo"}, 3)
        s._on_command("set_difficulty", {"pct": 60}, 4)
        assert s.difficulty_pct == 60.0

        # En RUNNING
        s._on_command("start", {}, 5)
        s._on_command("set_difficulty", {"pct": 40}, 6)
        assert s.difficulty_pct == 40.0

        # En PAUSED
        s._on_command("pause", {}, 7)
        s._on_command("set_difficulty", {"pct": 75}, 8)
        assert s.difficulty_pct == 75.0

        # Valeurs non numériques : bad_args
        errors.clear()
        s._on_command("set_difficulty", {"pct": "abc"}, 9)
        assert len(errors) == 1
        assert errors[0][0] == "bad_args"
        assert s.difficulty_pct == 75.0   # valeur inchangée

        errors.clear()
        s._on_command("set_difficulty", {"pct": True}, 10)
        assert len(errors) == 1
        assert errors[0][0] == "bad_args"

        errors.clear()
        s._on_command("set_difficulty", {}, 11)
        assert len(errors) == 1
        assert errors[0][0] == "bad_args"

        # NaN et infini (acceptés par json.loads) : refusés, valeur inchangée
        for k, bad in enumerate((float("nan"), float("inf"), float("-inf"))):
            errors.clear()
            s._on_command("set_difficulty", {"pct": bad}, 12 + k)
            assert len(errors) == 1 and errors[0][0] == "bad_args"
            assert s.difficulty_pct == 75.0

    asyncio.run(scenario())


def test_difficulty_in_state_hello_ack_and_jsonl(tmp_path, monkeypatch):
    """Critère 5 : difficulty_pct présent dans state, hello_ack.config et journal jsonl."""
    async def scenario():
        s = make_session(tmp_path, monkeypatch, port=5858)
        frames = []
        s.server.send_raw = frames.append

        # hello_ack
        s.server._handle_message({"type": "hello", "v": 1, "engine_version": "test"})
        ack = [f for f in frames if f["type"] == "hello_ack"][0]
        assert ack["config"]["difficulty_pct"] == 50

        # state
        s.server.send_state(s.state)
        st_frame = [f for f in frames if f["type"] == "state"][-1]
        assert st_frame["difficulty_pct"] == 50

        # Enregistrement dans le journal .jsonl
        s._on_command("select_route", {"route_id": "demo"}, 1)
        s._on_command("start", {}, 2)
        # Roulage pour déclencher le premier record
        for i in range(60):
            s._step(0.02, 10.0 + i * 0.02)
        s._on_command("set_difficulty", {"pct": 35}, 3)
        for i in range(60):
            s._step(0.02, 20.0 + i * 0.02)
        s._finish(save=False)

        journal_files = list((tmp_path / "journal").glob("*.jsonl"))
        assert len(journal_files) == 1
        records = [line for line in read_journal(journal_files[0]) if line.get("kind") == "record"]
        assert len(records) >= 2
        assert records[0]["difficulty_pct"] == 50
        assert records[-1]["difficulty_pct"] == 35

    asyncio.run(scenario())


def test_set_difficulty_is_saved_for_the_next_session(tmp_path, monkeypatch):
    """Tout réglage du menu persiste : la difficulté choisie à la pause est écrite dans config.toml."""
    from openride_core import config as config_mod

    async def scenario():
        s = make_session(tmp_path, monkeypatch, port=5880)
        s._on_command("set_difficulty", {"pct": 30}, 1)
        assert config_mod.load(tmp_path / "config.toml").trainer.difficulty_pct == 30
        assert s.cfg.trainer.difficulty_pct == 30

    asyncio.run(scenario())
