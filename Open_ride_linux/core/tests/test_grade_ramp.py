"""Tests unitaires du lot Q4 : rampe de pente plus rapide, vitesses distinctes montée et descente."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import pytest

from openride_core import fit_export
from openride_core.config import Config, ConfigError, TrainerConfig, from_dict
from openride_core.input_providers import InputEvent, NullProvider
from openride_core.mock_driver import MockDriver
from openride_core.session import CoreSession


def make_session(tmp_path: Path, monkeypatch, cfg: Config | None = None, port: int = 5860) -> CoreSession:
    monkeypatch.setattr(fit_export, "ACTIVITIES_DIR", tmp_path / "act")
    c = cfg or Config()
    c.ipc.port_state, c.ipc.port_commands = port, port + 1
    s = CoreSession(
        c,
        driver=MockDriver(),
        inputs=[NullProvider()],
        journal_dir=tmp_path / "journal",
        routes_root=tmp_path / "routes",
    )
    return s


def test_default_rates_and_bounds_validation() -> None:
    """Critère 4 : valeurs par défaut (4.0 et 8.0) et validation des bornes (0.1 à 100)."""
    t = TrainerConfig()
    assert t.grade_rate_up_pct_per_s == 4.0
    assert t.grade_rate_down_pct_per_s == 8.0

    # Bornes valides acceptées
    cfg_low = from_dict({"trainer": {"grade_rate_up_pct_per_s": 0.1, "grade_rate_down_pct_per_s": 0.1}})
    assert cfg_low.trainer.grade_rate_up_pct_per_s == 0.1
    assert cfg_low.trainer.grade_rate_down_pct_per_s == 0.1

    cfg_high = from_dict({"trainer": {"grade_rate_up_pct_per_s": 100.0, "grade_rate_down_pct_per_s": 100.0}})
    assert cfg_high.trainer.grade_rate_up_pct_per_s == 100.0
    assert cfg_high.trainer.grade_rate_down_pct_per_s == 100.0

    # Valeurs hors bornes refusées avec message habituel
    for bad in (0.05, 0.0, -1.0, 100.5, 200.0):
        with pytest.raises(ConfigError) as exc_up:
            from_dict({"trainer": {"grade_rate_up_pct_per_s": bad}})
        assert "[trainer] grade_rate_up_pct_per_s" in str(exc_up.value)
        assert "hors de 0.1 à 100" in str(exc_up.value)

        with pytest.raises(ConfigError) as exc_down:
            from_dict({"trainer": {"grade_rate_down_pct_per_s": bad}})
        assert "[trainer] grade_rate_down_pct_per_s" in str(exc_down.value)
        assert "hors de 0.1 à 100" in str(exc_down.value)


def test_legacy_grade_rate_fallback_and_warning(caplog: pytest.LogCaptureFixture) -> None:
    """Critère 3 : ancienne config avec grade_rate_pct_per_s seul, avertissement et réutilisation."""
    with caplog.at_level(logging.WARNING, logger="openride_core.config"):
        cfg = from_dict({"trainer": {"grade_rate_pct_per_s": 3.0}})
    assert cfg.trainer.grade_rate_up_pct_per_s == 3.0
    assert cfg.trainer.grade_rate_down_pct_per_s == 3.0
    assert any("réglage remplacé par" in r.message for r in caplog.records)

    # Si les nouveaux réglages sont spécifiés, pas d'avertissement de remplacement
    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="openride_core.config"):
        cfg_new = from_dict({
            "trainer": {
                "grade_rate_up_pct_per_s": 5.0,
                "grade_rate_down_pct_per_s": 10.0,
            }
        })
    assert cfg_new.trainer.grade_rate_up_pct_per_s == 5.0
    assert cfg_new.trainer.grade_rate_down_pct_per_s == 10.0
    assert not any("réglage remplacé par" in r.message for r in caplog.records)

    # Ancien réglage avec un seul des nouveaux : l'autre garde son défaut
    cfg_mixed = from_dict({"trainer": {"grade_rate_pct_per_s": 2.0, "grade_rate_up_pct_per_s": 5.0}})
    assert cfg_mixed.trainer.grade_rate_up_pct_per_s == 5.0
    assert cfg_mixed.trainer.grade_rate_down_pct_per_s == 8.0


def test_startup_log_records_ramp_rates(tmp_path: Path, monkeypatch, caplog: pytest.LogCaptureFixture) -> None:
    """Une ligne du journal au démarrage donne les deux vitesses."""
    with caplog.at_level(logging.INFO):
        s = make_session(tmp_path, monkeypatch, port=5862)
        assert any(
            "Rampe de pente du trainer : +4.0 %/s (montée), -8.0 %/s (descente)" in r.message
            for r in caplog.records
        )


def test_simulated_session_ramp_step_up_and_down(tmp_path: Path, monkeypatch) -> None:
    """Critère 2 : séance simulée braquet fixe, marche 0 -> 7 % à 4 %/s, marche 7 -> 0 % à 8 %/s."""
    async def scenario():
        cfg = Config()
        cfg.trainer.latency_tau_s = 0.0
        cfg.trainer.difficulty_pct = 100.0  # facilite le calcul : pente effective = pente terrain

        s = make_session(tmp_path, monkeypatch, cfg=cfg, port=5864)
        s._on_command("select_route", {"route_id": "demo"}, 1)
        s._on_command("start", {}, 2)
        s.gearing.k = 12

        grade_sim = 0.0
        s.route.grade_at = lambda pos: grade_sim

        # Initialisation à 0 %
        target_0 = s.gearing.effective_grade(0.0, 1.0)
        for i in range(50):
            s.driver._power_w = 200.0
            s._step(0.02, 10.0 + i * 0.02)
        assert abs(s._grade_sent - target_0) < 1e-6

        # Marche 0 -> 7 %
        grade_sim = 7.0
        target_up = s.gearing.effective_grade(7.0, 1.0)
        delta_eff = target_up - target_0
        dt = 0.02
        t = 11.0
        t_start_up = t
        reached_up_t = None

        while t - t_start_up < 5.0:
            s._step(dt, t)
            t += dt
            if abs(s._grade_sent - target_up) < 1e-6 and reached_up_t is None:
                reached_up_t = t

        assert reached_up_t is not None
        duration_up = reached_up_t - t_start_up
        expected_duration_up = delta_eff / 4.0
        # Durée de la rampe = écart / 4, ± 0.1 s
        assert abs(duration_up - expected_duration_up) <= 0.1
        # Vitesse de montée à 4 %/s ± 5 %
        rate_up = delta_eff / duration_up
        assert abs(rate_up - 4.0) / 4.0 <= 0.05

        # Marche 7 -> 0 %
        grade_sim = 0.0
        t_start_down = t
        reached_down_t = None

        while t - t_start_down < 5.0:
            s._step(dt, t)
            t += dt
            if abs(s._grade_sent - target_0) < 1e-6 and reached_down_t is None:
                reached_down_t = t

        assert reached_down_t is not None
        duration_down = reached_down_t - t_start_down
        expected_duration_down = delta_eff / 8.0
        # Durée de la rampe = écart / 8, ± 0.1 s
        assert abs(duration_down - expected_duration_down) <= 0.1
        # Vitesse de descente à 8 %/s ± 5 %
        rate_down = delta_eff / duration_down
        assert abs(rate_down - 8.0) / 8.0 <= 0.05

    asyncio.run(scenario())


def test_legacy_config_in_session(tmp_path: Path, monkeypatch) -> None:
    """Critère 3 : ancienne config avec grade_rate_pct_per_s = 2 : 2 %/s dans les deux sens."""
    async def scenario():
        cfg = from_dict({
            "trainer": {
                "latency_tau_s": 0.0,
                "difficulty_pct": 100.0,
                "grade_rate_pct_per_s": 2.0,
            }
        })
        s = make_session(tmp_path, monkeypatch, cfg=cfg, port=5866)
        s._on_command("select_route", {"route_id": "demo"}, 1)
        s._on_command("start", {}, 2)
        s.gearing.k = 12

        grade_sim = 0.0
        s.route.grade_at = lambda pos: grade_sim

        # Initialisation à 0 %
        target_0 = s.gearing.effective_grade(0.0, 1.0)
        for i in range(50):
            s.driver._power_w = 200.0
            s._step(0.02, 10.0 + i * 0.02)
        assert abs(s._grade_sent - target_0) < 1e-6

        # Marche 0 -> 4 % à 2 %/s (durée attendue = delta / 2.0 s ± 0.1 s)
        grade_sim = 4.0
        target = s.gearing.effective_grade(4.0, 1.0)
        delta_eff = target - target_0
        dt = 0.02
        t = 11.0
        t_start = t
        reached_t = None

        while t - t_start < 5.0:
            s._step(dt, t)
            t += dt
            if abs(s._grade_sent - target) < 1e-6 and reached_t is None:
                reached_t = t

        assert reached_t is not None
        duration = reached_t - t_start
        assert abs(duration - delta_eff / 2.0) <= 0.1

        # Descente 4 -> 0 % à 2 %/s (durée attendue = delta / 2.0 s ± 0.1 s)
        grade_sim = 0.0
        t_start_down = t
        reached_down_t = None

        while t - t_start_down < 5.0:
            s._step(dt, t)
            t += dt
            if abs(s._grade_sent - target_0) < 1e-6 and reached_down_t is None:
                reached_down_t = t

        assert reached_down_t is not None
        duration_down = reached_down_t - t_start_down
        assert abs(duration_down - delta_eff / 2.0) <= 0.1

    asyncio.run(scenario())


def test_gear_shift_immediate_ramp(tmp_path: Path, monkeypatch) -> None:
    """Critère 5 : le changement de braquet reste immédiat (sans limitation de vitesse)."""
    async def scenario():
        cfg = Config()
        cfg.trainer.latency_tau_s = 0.0
        s = make_session(tmp_path, monkeypatch, cfg=cfg, port=5868)
        s._on_command("select_route", {"route_id": "demo"}, 1)
        s._on_command("start", {}, 2)
        s.route.grade_at = lambda pos: 5.0

        for i in range(10):
            s._step(0.02, 60.0 + i * 0.02)

        before = s._grade_sent
        for _ in range(8):
            s._handle_input(InputEvent.PLUS_SHORT)

        s._step(0.02, 61.0)
        target = s.gearing.effective_grade(s.route.grade_at(s.physics.s), s.difficulty_pct / 100.0)
        # Sauté immédiatement au braquet sans limitation de rampe
        assert abs(s._grade_sent - target) < 0.5 and abs(s._grade_sent - before) > 0.04

    asyncio.run(scenario())
