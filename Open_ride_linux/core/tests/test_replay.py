"""Tests du rejeu d'une séance enregistrée (JSONL ou FIT) dans `MockDriver` (lot H3, SRS §12)."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from openride_core import __main__ as cli_main
from openride_core import fit_export
from openride_core.config import Config
from openride_core.fit_export import write_fit
from openride_core.input_providers import NullProvider
from openride_core.journal import JournalWriter, Record, read_journal
from openride_core.mock_driver import MockDriver
from openride_core.replay import ReplayError, ReplaySample, load_replay
from openride_core.session import CoreSession

T0 = 1_790_000_000.0


def write_ramp_journal(path: Path, duration_s: int = 120, p_start: float = 100.0,
                       p_end: float = 300.0) -> Path:
    """Crée un journal synthétique de `duration_s` secondes (échantillons de t = 0 à duration_s)."""
    with JournalWriter(path, route_id="demo") as j:
        j.event("start", T0)
        for i in range(duration_s + 1):
            frac = i / duration_s
            p = p_start + frac * (p_end - p_start)
            cad = 70.0 + 20.0 * frac
            hr = 120 + int(round(40 * frac))
            j.record(Record(
                ts=T0 + i,
                t=float(i),
                lat=45.0,
                lon=6.0,
                alt=500.0,
                distance=float(i * 8),
                speed=8.0,
                power=p,
                cadence=cad,
                hr=hr,
            ))
        j.event("stop", T0 + duration_s)
    return path


def test_replay_jsonl_ramp_interpolation(tmp_path: Path) -> None:
    """Critère 2 : journal de 120 s (100 -> 300 W) rejoué ; à t = 60,5 s, valeur interpolée à 1 W près."""
    jpath = write_ramp_journal(tmp_path / "ramp.jsonl", duration_s=120, p_start=100.0, p_end=300.0)
    samples = load_replay(jpath)
    assert len(samples) == 121
    assert samples[0].t == pytest.approx(0.0)
    assert samples[-1].t == pytest.approx(120.0)

    drv = MockDriver(replay=samples)
    expected_60_5 = 100.0 + (60.5 / 120.0) * 200.0
    m = drv.poll(60.5)
    assert m.power_w == pytest.approx(expected_60_5, abs=1.0)
    expected_cad = 70.0 + (60.5 / 120.0) * 20.0
    assert m.cadence_rpm == pytest.approx(expected_cad, abs=0.5)
    # FC prise à l'échantillon précédent (t = 60 s).
    assert m.hr_bpm == samples[60].hr_bpm


def test_replay_fit_matches_jsonl(tmp_path: Path) -> None:
    """Critère 3 : même contenu écrit en FIT par write_fit puis rejoué donne les mêmes puissances (± 1 W)."""
    jpath = write_ramp_journal(tmp_path / "ramp.jsonl", duration_s=120, p_start=100.0, p_end=300.0)
    records = [ln for ln in read_journal(jpath) if ln.get("kind") == "record"]
    events = [ln for ln in read_journal(jpath) if ln.get("kind") == "event"]
    fpath = tmp_path / "ramp.fit"
    write_fit(records, events, fpath)

    drv_jsonl = MockDriver(replay=load_replay(jpath))
    drv_fit = MockDriver(replay=load_replay(fpath))

    for k in range(0, 241):
        t = k * 0.5
        p_j = drv_jsonl.poll(t).power_w
        p_f = drv_fit.poll(t).power_w
        assert p_f == pytest.approx(p_j, abs=1.0), f"écart à t={t}"


def test_replay_loops_after_last_sample(tmp_path: Path) -> None:
    """Critère 4 : au-delà du dernier échantillon, le rejeu reprend au début."""
    jpath = write_ramp_journal(tmp_path / "ramp.jsonl", duration_s=120, p_start=100.0, p_end=300.0)
    drv = MockDriver(replay=load_replay(jpath))

    assert drv.poll(120.5).power_w == pytest.approx(drv.poll(0.5).power_w, abs=0.1)
    assert drv.poll(150.0).power_w == pytest.approx(drv.poll(30.0).power_w, abs=0.1)
    assert drv.poll(240.0).power_w == pytest.approx(drv.poll(0.0).power_w, abs=0.1)


def test_replay_erg_mode_follows_target(tmp_path: Path) -> None:
    """Critère 5 : en ERG, la puissance suit la cible même avec un rejeu chargé."""
    jpath = write_ramp_journal(tmp_path / "ramp.jsonl", duration_s=120, p_start=100.0, p_end=300.0)
    drv = MockDriver(replay=load_replay(jpath))

    drv.set_target_power(275.0)
    for t in (0.0, 10.0, 60.5):
        m = drv.poll(t)
        assert m.power_w == pytest.approx(275.0, abs=3.5)

    # Retour en SIM : le rejeu reprend la main.
    drv.set_sim_grade(2.0)
    assert drv.poll(0.0).power_w == pytest.approx(100.0, abs=1.0)


def test_replay_missing_fields_and_errors(tmp_path: Path) -> None:
    """Champs absents ou None -> puissance/cadence à 0, FC à None ; fichiers invalides -> ReplayError."""
    sparse = tmp_path / "sparse.jsonl"
    sparse.write_text(
        '{"kind":"header","version":1}\n'
        '{"kind":"record","ts":1000.0,"t":10.0,"power":null,"cadence":null,"hr":null}\n'
        '{"kind":"record","ts":1001.0,"t":11.0}\n',
        encoding="utf-8",
    )
    samples = load_replay(sparse)
    assert samples == [
        ReplaySample(t=0.0, power_w=0.0, cadence_rpm=0.0, hr_bpm=None),
        ReplaySample(t=1.0, power_w=0.0, cadence_rpm=0.0, hr_bpm=None),
    ]

    # Extension inconnue
    bad_ext = tmp_path / "seance.csv"
    bad_ext.write_text("t,power\n0,200\n", encoding="utf-8")
    with pytest.raises(ReplayError):
        load_replay(bad_ext)

    # Fichier introuvable
    with pytest.raises(ReplayError):
        load_replay(tmp_path / "absent.jsonl")

    # Journal vide (sans record)
    empty_j = tmp_path / "vide.jsonl"
    with JournalWriter(empty_j, route_id="demo"):
        pass
    with pytest.raises(ReplayError):
        load_replay(empty_j)

    # FIT corrompu
    bad_fit = tmp_path / "corrompu.fit"
    bad_fit.write_bytes(b"not a valid fit file")
    with pytest.raises(ReplayError):
        load_replay(bad_fit)


def test_core_session_60s_with_replay(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Critère 6 : séance CoreSession de 60 s en temps accéléré avec rejeu."""
    monkeypatch.setattr(fit_export, "ACTIVITIES_DIR", tmp_path / "act")
    source_path = write_ramp_journal(tmp_path / "source.jsonl", duration_s=120, p_start=120.0, p_end=240.0)

    cfg = Config()
    cfg.ipc.port_state, cfg.ipc.port_commands = 6030, 6031
    cfg.drivers.trainer = "mock"
    cfg.drivers.mock_replay = str(source_path)

    s = CoreSession(cfg, inputs=[NullProvider()], journal_dir=tmp_path / "journal",
                    routes_root=tmp_path / "routes")
    s._on_command("select_route", {"route_id": "demo"}, 1)
    s._on_command("start", {}, 2)

    for i in range(3000):  # 60 s à 50 Hz
        s._step(0.02, 100.0 + i * 0.02)
    s._on_command("end_session", {"save": False}, 3)

    out_journal = next((tmp_path / "journal").glob("*.jsonl"))
    recorded = [ln for ln in read_journal(out_journal) if ln.get("kind") == "record"]
    assert len(recorded) >= 60
    for rec in recorded:
        t = rec["t"]
        expected_p = 120.0 + (t / 120.0) * 120.0
        assert rec["power"] == pytest.approx(expected_p, abs=1.5)


def test_missing_replay_logs_error_and_falls_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Critère 7 : un chemin de rejeu invalide journalise l'erreur en ERROR et retombe sur le simulateur."""
    monkeypatch.setattr(fit_export, "ACTIVITIES_DIR", tmp_path / "act")
    cfg = Config()
    cfg.ipc.port_state, cfg.ipc.port_commands = 6040, 6041
    cfg.drivers.trainer = "mock"
    cfg.drivers.mock_replay = str(tmp_path / "inexistant.jsonl")

    with caplog.at_level(logging.ERROR, logger="core"):
        s = CoreSession(cfg, inputs=[NullProvider()], journal_dir=tmp_path / "journal",
                        routes_root=tmp_path / "routes")

    assert any(r.levelno == logging.ERROR and "inexistant.jsonl" in r.getMessage()
               for r in caplog.records)
    assert isinstance(s.driver, MockDriver) and s.driver.replay is None

    s._on_command("select_route", {"route_id": "demo"}, 1)
    s._on_command("start", {}, 2)
    s._step(0.02, 10.0)
    assert s.state.session_state == "RUNNING" and s.state.power > 0


def test_cli_run_replay_option_forces_mock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`openride-core run --replay CHEMIN` force trainer = 'mock' et renseigne mock_replay."""
    captured: dict[str, Config] = {}

    class DummySession:
        def __init__(self, cfg: Config) -> None:
            captured["cfg"] = cfg

        async def run(self, autostart: bool = False, **kwargs: object) -> None:
            captured["autostart"] = autostart  # type: ignore[assignment]

    import openride_core.session as session_mod
    monkeypatch.setattr(session_mod, "CoreSession", DummySession)

    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text('[drivers]\ntrainer = "ftms"\n', encoding="utf-8")
    rc = cli_main.main(["run", "--config", str(cfg_file), "--replay", "seance.jsonl"])
    assert rc == 0
    assert captured["cfg"].drivers.trainer == "mock"
    assert captured["cfg"].drivers.mock_replay == "seance.jsonl"
