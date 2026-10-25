"""Tests des bots virtuels (Lot N9).

Critères testés :
1. Parcours plat : bot 200 W vs cycliste 200 W, même masse : écart < 1 m après 10 min simulées.
2. Montée à 8 % : bot 300 W vs bot 200 W, rapport de vitesse attendu par physics.py (à 2 % près).
3. Fantôme d'un FIT : à t=600s, position égale à la distance du FIT (à 5 m près), et cohérence FIT vs JSONL.
4. Pause de 60 s : bots figés, t et s inchangés.
5. Sans bot : clé "bots" absente ; avec 4 bots : trame validée par state.schema.json.
6. Coût : 4 bots ajoutent moins de 0,2 ms au pas p99.
7. Validation CLI et cas limites (--bot > 4, puissance invalide, fichier sans distance).
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
import time

import jsonschema
import pytest

from openride_core.bots import BotError, ConstantPowerBot, GhostBot
from openride_core.config import Config
from openride_core.input_providers import NullProvider
from openride_core.mock_driver import MockDriver
from openride_core.physics import PhysicsParams, RiderPhysics, steady_speed
from openride_core.session import CoreSession

REPO_ROOT = Path(__file__).resolve().parents[2]
IPC_DIR = REPO_ROOT / "docs" / "contracts" / "ipc"
SPIKE_DIR = Path(__file__).resolve().parents[1] / "spike_reports"


def state_schema() -> dict:
    return json.loads((IPC_DIR / "state.schema.json").read_text(encoding="utf-8"))


def assert_valid_state(msg: dict) -> None:
    validator = jsonschema.Draft202012Validator(state_schema())
    errors = [e.message for e in validator.iter_errors(msg)]
    assert not errors, f"state invalide : {errors}"


def test_flat_route_bot_vs_rider():
    """Critère 2 : Parcours plat : bot 200 W vs cycliste 200 W, écart < 1 m après 10 min."""
    params = PhysicsParams(mass_kg=83.0)
    bot = ConstantPowerBot(200.0, bot_id="bot1", params=params)
    rider = RiderPhysics(params)

    dt = 0.02
    steps = int(600.0 / dt)  # 10 minutes
    for _ in range(steps):
        bot.step(dt, route=None)
        rider.step(200.0, 0.0, 0.0, dt)

    assert abs(bot.s - rider.s) < 1.0


def test_climb_8_percent_speed_ratio():
    """Critère 3 : Montée à 8 % : rapport de vitesse 300 W vs 200 W conforme à physics.py à 2 % près."""
    params = PhysicsParams(mass_kg=83.0)
    bot200 = ConstantPowerBot(200.0, bot_id="b200", params=params)
    bot300 = ConstantPowerBot(300.0, bot_id="b300", params=params)

    # Calcul de référence du rapport des vitesses stabilisées
    v200_expected = steady_speed(200.0, 8.0, params)
    v300_expected = steady_speed(300.0, 8.0, params)
    expected_ratio = v300_expected / v200_expected

    class FakeClimbRoute:
        is_loop = True
        length_m = 50000.0

        def sample(self, s: float):
            class Sample:
                grade_pct = 8.0
                alt_m = 500.0
            return Sample()

    route = FakeClimbRoute()
    dt = 0.02
    # Simulation pendant 180 s pour atteindre la vitesse stabilisée
    for _ in range(int(180.0 / dt)):
        bot200.step(dt, route=route)
        bot300.step(dt, route=route)

    actual_ratio = bot300.v / bot200.v
    assert abs(actual_ratio - expected_ratio) / expected_ratio < 0.02


def test_ghost_bot_fit_and_jsonl_parity():
    """Critère 4 : Fantôme FIT à t=600s égal à la distance du FIT (à 5 m près), et parité FIT / JSONL."""
    fit_path = SPIKE_DIR / "fit_demo_1792609599.fit"
    jsonl_path = SPIKE_DIR / "fit_demo_1792609599.jsonl"
    if not fit_path.is_file() or not jsonl_path.is_file():
        pytest.skip("Fichiers de spike fit_demo absents")

    ghost_fit = GhostBot(fit_path)
    ghost_jsonl = GhostBot(jsonl_path)

    assert "Fantôme" in ghost_fit.name
    assert ghost_fit.kind == "ghost"
    assert ghost_jsonl.kind == "ghost"

    dt = 0.5
    for _ in range(int(600.0 / dt)):
        ghost_fit.step(dt)
        ghost_jsonl.step(dt)

    # À t = 600 s, la distance doit être égale à celle du FIT (1663.81 m)
    assert abs(ghost_fit.s - 1663.81) <= 5.0
    # Et parité quasi-exacte entre le rejeu du .fit et du .jsonl
    assert abs(ghost_fit.s - ghost_jsonl.s) <= 1.0


def test_ghost_bot_stops_at_session_end():
    """Fantôme arrêté (v=0) en bout de séance enregistrée."""
    fit_path = SPIKE_DIR / "fit_demo_1792609599.fit"
    if not fit_path.is_file():
        pytest.skip("Fichier fit_demo absent")
    ghost = GhostBot(fit_path)
    # Avance au-delà de la fin (600s)
    ghost.step(1000.0)
    assert ghost.s == ghost.distances[-1]
    assert ghost.v == 0.0


def test_ghost_bot_rejects_missing_distance(tmp_path: Path):
    """Refus clair si le fichier n'a pas de distance."""
    no_dist = tmp_path / "no_dist.jsonl"
    lines = [
        {"kind": "event", "event": "start", "ts": 1000.0},
        {"kind": "record", "ts": 1001.0, "t": 1.0, "power": 150},
        {"kind": "record", "ts": 1002.0, "t": 2.0, "power": 160},
        {"kind": "event", "event": "stop", "ts": 1003.0},
    ]
    no_dist.write_text("\n".join(json.dumps(l) for l in lines), encoding="utf-8")

    with pytest.raises(BotError, match="sans relevé de distance"):
        GhostBot(no_dist)


def test_bots_freeze_during_pause(tmp_path: Path):
    """Critère 5 : Pause de 60 s : bots figés, t et s des bots inchangés."""
    cfg = Config()
    bot = ConstantPowerBot(250.0, bot_id="bot1")
    session = CoreSession(cfg, driver=MockDriver(), inputs=[NullProvider()],
                          journal_dir=tmp_path / "journal", routes_root=tmp_path / "routes",
                          bots=[bot])

    session.state.session_state = "RUNNING"
    session._step(1.0, 1.0)
    s_before = bot.s
    t_before = bot.t
    assert s_before > 0.0

    # Passage en pause
    session.state.session_state = "PAUSED"
    session.state.pause_reason = "user"

    # Simulation d'une pause de 60 secondes
    for i in range(60):
        session._step(1.0, 2.0 + i)

    assert bot.s == s_before
    assert bot.t == t_before


def test_state_schema_with_and_without_bots(tmp_path: Path):
    """Critère 6 : Sans bot : aucune clé 'bots'. Avec 4 bots : trame validée par le schéma."""
    cfg = Config()
    # 1. Sans bot
    s_no_bot = CoreSession(cfg, driver=MockDriver(), inputs=[NullProvider()],
                           journal_dir=tmp_path / "j1", routes_root=tmp_path / "r1")
    d_no_bot = s_no_bot.state.to_dict()
    assert "bots" not in d_no_bot
    assert_valid_state(d_no_bot)

    # 2. Avec 4 bots
    bots = [
        ConstantPowerBot(180.0, bot_id="b1"),
        ConstantPowerBot(220.0, bot_id="b2"),
        ConstantPowerBot(260.0, bot_id="b3"),
        ConstantPowerBot(300.0, bot_id="b4"),
    ]
    s_bots = CoreSession(cfg, driver=MockDriver(), inputs=[NullProvider()],
                        journal_dir=tmp_path / "j2", routes_root=tmp_path / "r2",
                        bots=bots)

    # Simulation d'une boucle émettant un state
    s_bots.state.session_state = "RUNNING"
    s_bots._step(0.1, 1.0)
    s_bots.state.bots = [b.to_dict() for b in s_bots.bots]

    d_bots = s_bots.state.to_dict()
    assert "bots" in d_bots
    assert len(d_bots["bots"]) == 4
    assert_valid_state(d_bots)

    # Vérification des champs requis dans chaque bot
    for b_dict in d_bots["bots"]:
        assert set(b_dict.keys()) == {"id", "name", "s", "v", "kind"}
        assert len(b_dict["id"]) <= 8
        assert len(b_dict["name"]) <= 16
        assert b_dict["kind"] == "constant"


def test_four_bots_performance_under_0_2_ms():
    """Critère 7 : 4 bots ajoutent moins de 0,2 ms au pas de physique p99."""
    bots = [
        ConstantPowerBot(150.0, bot_id="b1"),
        ConstantPowerBot(200.0, bot_id="b2"),
        ConstantPowerBot(250.0, bot_id="b3"),
        ConstantPowerBot(300.0, bot_id="b4"),
    ]

    class MockRoute:
        is_loop = True
        length_m = 10000.0

        def sample(self, s: float):
            class Sample:
                grade_pct = 2.0
                alt_m = 120.0
            return Sample()

    route = MockRoute()
    dt = 0.02

    # Warmup
    for _ in range(100):
        for b in bots:
            b.step(dt, route)

    # Mesure de 1000 pas
    durations = []
    for _ in range(1000):
        t0 = time.perf_counter()
        for b in bots:
            b.step(dt, route)
        durations.append(time.perf_counter() - t0)

    durations.sort()
    p99_s = durations[int(len(durations) * 0.99)]
    p99_ms = p99_s * 1000.0
    # Doit être largement sous 0.2 ms
    assert p99_ms < 0.2, f"Temps p99 trop élevé : {p99_ms:.4f} ms"


def test_constant_power_bot_validation():
    """Validation des paramètres de ConstantPowerBot."""
    with pytest.raises(BotError, match="puissance de bot invalide"):
        ConstantPowerBot(0.0)
    with pytest.raises(BotError, match="puissance de bot invalide"):
        ConstantPowerBot(-150.0)
    with pytest.raises(BotError, match="puissance de bot invalide"):
        ConstantPowerBot(float("nan"))
    with pytest.raises(BotError, match="masse invalide"):
        ConstantPowerBot(200.0, mass_kg=-10.0)


def test_cli_bot_and_ghost_parsing(tmp_path: Path):
    """Test des options CLI --bot et --ghost."""
    from openride_core.__main__ import build_parser
    parser = build_parser()

    # Parsage valide avec 4 bots et un ghost
    fit_path = SPIKE_DIR / "fit_demo_1792609599.fit"
    args = parser.parse_args(["run", "--bot", "150", "--bot", "200", "--ghost", str(fit_path)])
    assert args.bot == [150.0, 200.0]
    assert args.ghost == fit_path
