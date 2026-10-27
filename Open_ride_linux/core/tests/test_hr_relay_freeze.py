"""Tests du lot Q5 : détection et exclusion de la fréquence cardiaque relayée figée."""

from __future__ import annotations

import asyncio
import dataclasses
import math
import struct
from pathlib import Path

import pytest

from openride_core.config import BikeConfig, Config, ConfigError, TrainerConfig, from_dict
from openride_core.fit_export import write_fit
from openride_core.ftms_driver import FtmsDriver
from openride_core.journal import JournalWriter, Record
from openride_core.sim_scenarios import SCENARIOS, build_world, validate
from openride_core.tools.session_summary import compute_summary, format_text, load_session


def make_ibd_packet(power_w: int = 150, cadence_rpm: float = 85.0, speed_kmh: float = 25.0,
                    hr_bpm: int | None = None) -> bytearray:
    flags = 0x0004 | 0x0040
    if hr_bpm is not None:
        flags |= 0x0200
        return bytearray(struct.pack(
            "<HHHhB", flags, int(round(speed_kmh * 100)), int(round(cadence_rpm * 2)),
            int(round(power_w)), int(round(hr_bpm))
        ))
    return bytearray(struct.pack(
        "<HHHh", flags, int(round(speed_kmh * 100)), int(round(cadence_rpm * 2)),
        int(round(power_w))
    ))


# --- 1. Configuration et bornes ---------------------------------------------------------

def test_config_hr_relay_freeze_s_defaults_and_validation():
    cfg = Config()
    assert cfg.trainer.hr_relay_freeze_s == 15.0

    # Lecture valide
    loaded = from_dict({"trainer": {"hr_relay_freeze_s": 30}})
    assert loaded.trainer.hr_relay_freeze_s == 30.0

    # Bornes : 5 à 120 s
    assert from_dict({"trainer": {"hr_relay_freeze_s": 5}}).trainer.hr_relay_freeze_s == 5.0
    assert from_dict({"trainer": {"hr_relay_freeze_s": 120}}).trainer.hr_relay_freeze_s == 120.0

    with pytest.raises(ConfigError, match="hors de 5 à 120"):
        from_dict({"trainer": {"hr_relay_freeze_s": 4.9}})

    with pytest.raises(ConfigError, match="hors de 5 à 120"):
        from_dict({"trainer": {"hr_relay_freeze_s": 121}})


# --- 2. FC relayée qui varie ±2 bpm : jamais ignorée sur 10 min (critère 2) -------------

def test_varying_relayed_hr_never_ignored_over_10_min(caplog):
    t_now = 0.0

    def clock() -> float:
        return t_now

    driver = FtmsDriver(TrainerConfig(hr_relay_freeze_s=15.0), BikeConfig(), clock=clock)
    driver._link_up = True
    driver._ever_connected = True

    # 10 minutes simulées = 600 secondes
    for sec in range(600):
        t_now = float(sec)
        driver._last_data_at = t_now
        # Variation sinusoïdale de ±2 bpm autour de 135 bpm
        bpm = int(round(135 + 2.0 * math.sin(t_now * 0.5)))
        driver._on_ibd(None, make_ibd_packet(power_w=180, cadence_rpm=88.0, hr_bpm=bpm))
        metrics = driver.poll(t_session=t_now)
        assert metrics.hr_bpm == bpm, f"FC ignorée à t = {t_now} s"
        assert metrics.hr_bpm is not None

    assert "ignorée" not in caplog.text


# --- 3. FC relayée fixe : ignorée après 15 s ± 0,5 s, une seule ligne (critère 3) -------

def test_fixed_relayed_hr_ignored_after_15s_and_single_log(caplog):
    t_now = 0.0

    def clock() -> float:
        return t_now

    driver = FtmsDriver(TrainerConfig(hr_relay_freeze_s=15.0), BikeConfig(), clock=clock)
    driver._link_up = True
    driver._ever_connected = True

    # Début à 105 bpm
    driver._last_data_at = 0.0
    driver._on_ibd(None, make_ibd_packet(hr_bpm=105))
    assert driver.poll().hr_bpm == 105

    # À 14.5 s : toujours valide
    t_now = 14.5
    driver._last_data_at = t_now
    driver._on_ibd(None, make_ibd_packet(hr_bpm=105))
    assert driver.poll().hr_bpm == 105
    assert "ignorée" not in caplog.text

    # À 15.0 s (15 s ± 0.5 s) : figée et ignorée
    t_now = 15.0
    driver._last_data_at = t_now
    driver._on_ibd(None, make_ibd_packet(hr_bpm=105))
    metrics = driver.poll()
    assert metrics.hr_bpm is None
    expected_msg = "Cardio relayée par le trainer figée à 105 bpm depuis 15 s : ignorée"
    assert expected_msg in caplog.text

    # Jusqu'à 45 s : reste ignorée, AUCUNE répétition du message de journal
    for s in range(16, 45):
        t_now = float(s)
        driver._last_data_at = t_now
        driver._on_ibd(None, make_ibd_packet(hr_bpm=105))
        assert driver.poll().hr_bpm is None

    assert caplog.text.count(expected_msg) == 1


# --- 4. Reprise : première valeur différente acceptée aussitôt (critère 4) --------------

def test_recovery_on_different_value(caplog):
    caplog.set_level("INFO")
    t_now = 0.0

    def clock() -> float:
        return t_now

    driver = FtmsDriver(TrainerConfig(hr_relay_freeze_s=15.0), BikeConfig(), clock=clock)
    driver._link_up = True
    driver._ever_connected = True

    driver._on_ibd(None, make_ibd_packet(hr_bpm=105))
    t_now = 15.0
    driver._last_data_at = t_now
    driver._on_ibd(None, make_ibd_packet(hr_bpm=105))
    assert driver.poll().hr_bpm is None
    assert "figée à 105 bpm depuis 15 s : ignorée" in caplog.text

    # Changement de valeur à 108 bpm à 42 s
    t_now = 42.0
    driver._last_data_at = t_now
    driver._on_ibd(None, make_ibd_packet(hr_bpm=108))
    metrics = driver.poll()
    assert metrics.hr_bpm == 108
    assert "Cardio relayée de nouveau valide" in caplog.text


# --- 5. Ceinture connectée directement avec valeur fixe jamais ignorée (critère 5) ------

def test_direct_strap_fixed_hr_never_ignored(tmp_path: Path, monkeypatch):
    """La ceinture connectée directement passe avant la FC du trainer, même figée : jamais ignorée."""
    from types import SimpleNamespace

    from openride_core import fit_export
    from openride_core.input_providers import NullProvider
    from openride_core.journal import read_journal
    from openride_core.mock_driver import MockDriver, TrainerMetrics
    from openride_core.session import CoreSession

    monkeypatch.setattr(fit_export, "ACTIVITIES_DIR", tmp_path / "act")
    cfg = Config()
    cfg.ipc.port_state, cfg.ipc.port_commands = 5874, 5875

    async def scenario(strap: bool, jdir: Path) -> None:
        s = CoreSession(cfg, driver=MockDriver(), inputs=[NullProvider()],
                        journal_dir=jdir, routes_root=tmp_path / "routes")
        # Trainer dont la FC relayée est déclarée figée, ceinture directe fixe à 140 bpm
        s.driver.poll = lambda t: TrainerMetrics(power_w=180.0, cadence_rpm=85.0, hr_bpm=None,
                                                 hr_frozen=True)
        s.hr = SimpleNamespace(bpm=140, connected=True, battery_pct=90, _ever_connected=True) if strap else None
        s._on_command("select_route", {"route_id": "demo"}, 1)
        s._on_command("start", {}, 2)
        for i in range(30 * 50):   # 30 s de séance
            s._step(0.02, 10.0 + i * 0.02)
        s._finish(save=False)

    def records_of(strap: bool) -> list[dict]:
        jdir = tmp_path / ("ceinture" if strap else "trainer")
        asyncio.run(scenario(strap, jdir))
        journal_files = list(jdir.glob("*.jsonl"))
        assert len(journal_files) == 1
        return [r for r in read_journal(journal_files[0]) if r.get("kind") == "record"]

    with_strap = records_of(True)
    assert len(with_strap) >= 25
    assert all(r.get("hr") == 140 for r in with_strap)
    assert not any(r.get("hr_frozen") for r in with_strap)
    # Sans ceinture : FC absente et secondes marquées « figée » (comptées par le résumé)
    trainer_only = records_of(False)
    assert len(trainer_only) >= 25
    assert all(r.get("hr") is None and r.get("hr_frozen") is True for r in trainer_only)


# --- 6. Résumé de séance et export FIT (critère 3 et résumé) ----------------------------

def test_session_summary_and_fit_omits_frozen_hr_and_computes_ignored_duration(tmp_path: Path):
    journal_path = tmp_path / "seance.jsonl"
    fit_path = tmp_path / "seance.fit"

    start_ts = 1730000000.0
    records = []
    events = [{"kind": "event", "event": "start", "ts": start_ts}]

    # 10 s valides à 120 bpm
    for i in range(10):
        records.append(Record(ts=start_ts + i, t=float(i), power=150.0, cadence=85.0,
                              speed=25.0, distance=i * 7.0, hr=120))

    # 15 s avant freeze à 105 bpm
    for i in range(10, 25):
        records.append(Record(ts=start_ts + i, t=float(i), power=150.0, cadence=85.0,
                              speed=25.0, distance=i * 7.0, hr=105))

    # 25 s figées : hr absent (None), marquées par le driver
    for i in range(25, 50):
        records.append(Record(ts=start_ts + i, t=float(i), power=150.0, cadence=85.0,
                              speed=25.0, distance=i * 7.0, hr=None, hr_frozen=True))

    # 10 s reprises à 130 bpm
    for i in range(50, 60):
        records.append(Record(ts=start_ts + i, t=float(i), power=150.0, cadence=85.0,
                              speed=25.0, distance=i * 7.0, hr=130))

    # 5 s sans FC du tout (ceinture pas encore vue, coupure) : pas comptées comme ignorées
    for i in range(60, 65):
        records.append(Record(ts=start_ts + i, t=float(i), power=150.0, cadence=85.0,
                              speed=25.0, distance=i * 7.0, hr=None))

    events.append({"kind": "event", "event": "stop", "ts": start_ts + 65.0})

    with JournalWriter(journal_path) as j:
        j.event("start", start_ts)
        for r in records:
            j.record(r)
        j.event("stop", start_ts + 65.0)

    write_fit([dataclasses.asdict(r) for r in records], events, fit_path)

    # Vérification du résumé depuis le journal
    s_jsonl = compute_summary(load_session(journal_path), ftp_w=250.0)
    assert s_jsonl["duration_s"] == 65.0
    assert s_jsonl["hr"] is not None
    # 35 secondes avec FC : (10*120 + 15*105 + 10*130) / 35 = 4075 / 35 = 116.4 bpm
    assert s_jsonl["hr"]["avg"] == 116.4
    assert s_jsonl["hr"]["max"] == 130.0
    assert s_jsonl["hr"]["ignored_s"] == 25.0
    assert s_jsonl["hr_ignored_s"] == 25.0

    # Vérification du texte formaté
    txt = format_text(s_jsonl)
    assert "FC : moyenne 116, max 130 bpm (durée totale ignorée : 0:00:25)" in txt

    # Vérification depuis le fichier FIT
    s_fit = compute_summary(load_session(fit_path), ftp_w=250.0)
    assert s_fit["hr"] is not None
    assert s_fit["hr"]["avg"] == 116.4
    assert s_fit["hr"]["max"] == 130.0
    assert "ignored_s" not in s_fit["hr"]   # un FIT ne garde pas la raison de l'absence de FC
    assert "hr_ignored_s" not in s_fit


# --- 7. Validation du scénario simulation fc_relayee_figee (critère 6) -------------------

def test_scenario_fc_relayee_figee_structure():
    assert "fc_relayee_figee" in SCENARIOS
    spec = SCENARIOS["fc_relayee_figee"]
    validated = validate(spec)
    assert validated["trainer"]["relayed_hr"] is True
    assert validated["hr"]["asleep"] is True
    actions = [ev["action"] for ev in validated["events"]]
    assert actions == ["bpm", "bpm"]
