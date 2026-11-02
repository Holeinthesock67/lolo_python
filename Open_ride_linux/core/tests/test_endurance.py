"""Tests d'endurance simulée : séance de 3 h en temps accéléré à 50 Hz (lot H4, SRS §5, §9, §12, audit F7)."""

from __future__ import annotations

import json
import math
import time
import tracemalloc
from pathlib import Path

import pytest
from fit_tool.profile.messages.event_message import EventMessage
from fit_tool.profile.messages.record_message import RecordMessage
from fit_tool.profile.messages.session_message import SessionMessage

from openride_core import fit_export
from openride_core.config import Config
from openride_core.demo_world import build_route, write_world
from openride_core.fit_export import iter_records
from openride_core.input_providers import NullProvider
from openride_core.journal import read_journal
from openride_core.mock_driver import MockDriver
from openride_core.physics import V_MAX
from openride_core.session import CoreSession

DT = 0.02
STEPS_3H = 540_000          # 3 h (10 800 s) à 50 Hz
STEPS_30M = 90_000          # 30 min (1 800 s) à 50 Hz
DURATION_3H_S = 10_800.0
MAX_DATAGRAM_BYTES = 1400
T0_WALL = 1_790_000_000.0

LONG_ERG_ZWO = """<?xml version="1.0" encoding="UTF-8"?>
<workout_file>
    <name>Endurance ERG 3h</name>
    <sportType>bike</sportType>
    <workout>
        <Warmup Duration="1200" PowerLow="0.50" PowerHigh="0.75"/>
        <IntervalsT Repeat="8" OnDuration="600" OffDuration="300" OnPower="0.92" OffPower="0.65"/>
        <FreeRide Duration="1200"/>
        <Cooldown Duration="1200" PowerLow="0.70" PowerHigh="0.45"/>
    </workout>
</workout_file>
"""


def write_loop_10km(routes_root: Path, name: str = "boucle_10km") -> Path:
    """Écrit un parcours synthétique en boucle fermée de 10 km."""
    world = write_world(routes_root, name, 10_000.0)
    route = build_route(10_000.0)
    route["type"] = "loop"
    route["x"][-1] = route["x"][0]
    route["z"][-1] = route["z"][0]
    route["lat"][-1] = route["lat"][0]
    route["lon"][-1] = route["lon"][0]
    route["alt_m"][-1] = route["alt_m"][0]
    (world / "route.json").write_text(json.dumps(route), encoding="utf-8")
    manifest = json.loads((world / "manifest.json").read_text(encoding="utf-8"))
    manifest["route"]["type"] = "loop"
    (world / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return world


def make_endurance_session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                           port: int = 6100) -> tuple[CoreSession, list[float]]:
    """Prépare une session isolée avec horloge murale simulée et parcours en boucle de 10 km."""
    monkeypatch.setattr(fit_export, "ACTIVITIES_DIR", tmp_path / "act")
    wall = [T0_WALL]
    monkeypatch.setattr(time, "time", lambda: wall[0])

    routes_root = tmp_path / "routes"
    write_loop_10km(routes_root)
    workouts_dir = tmp_path / "Workouts"
    workouts_dir.mkdir(parents=True, exist_ok=True)
    (workouts_dir / "endurance_3h.zwo").write_text(LONG_ERG_ZWO, encoding="utf-8")

    cfg = Config()
    cfg.ipc.port_state, cfg.ipc.port_commands = port, port + 1
    driver = MockDriver(base_power_w=210.0, ramp_amplitude_w=45.0, ramp_period_s=120.0)
    s = CoreSession(cfg, driver=driver, inputs=[NullProvider()],
                    journal_dir=tmp_path / "journal",
                    routes_root=routes_root,
                    workouts_dir=workouts_dir)
    return s, wall


@pytest.mark.slow
def test_endurance_sim_3h_physics_and_drift(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scénario 1 : 3 h en SIM (540 000 pas à 0,02 s), sans dérive temporelle ni aberration physique."""
    s, wall = make_endurance_session(tmp_path, monkeypatch, port=6100)
    s._on_command("select_route", {"route_id": "boucle_10km"}, 1)
    s._on_command("start", {}, 2)

    v_sum = 0.0
    v_min = float("inf")
    v_max = 0.0
    has_nan = False

    for i in range(STEPS_3H):
        wall[0] = T0_WALL + (i + 1) * DT
        s._step(DT, (i + 1) * DT)
        v = s.physics.v
        v_sum += v
        if v < v_min:
            v_min = v
        if v > v_max:
            v_max = v
        if math.isnan(v) or math.isnan(s.physics.s):
            has_nan = True

    assert s.state.session_state == "RUNNING"
    assert s._t_session == pytest.approx(DURATION_3H_S, abs=0.1)
    assert not has_nan
    assert v_min >= 0.0
    assert v_max <= V_MAX

    mean_v = v_sum / STEPS_3H
    expected_distance = mean_v * DURATION_3H_S
    rel_err = abs(s.physics.s - expected_distance) / expected_distance
    assert rel_err < 0.005, f"écart distance / vitesse moyenne = {rel_err * 100:.4f} %"


@pytest.mark.slow
def test_endurance_memory_stability(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scénario 2 : croissance mémoire entre la 30e minute et la fin bornée aux seuls relevés de SessionRecorder.

    Sous `tracemalloc`, chaque allocation Python est tracée (~8× plus lent) : un pas de 0,04 s (25 Hz,
    270 000 pas sur 3 h) maintient le test sous 45 s tout en produisant les mêmes 10 800 relevés à 1 Hz.
    """
    s, wall = make_endurance_session(tmp_path, monkeypatch, port=6110)
    s._on_command("select_route", {"route_id": "boucle_10km"}, 1)
    s._on_command("start", {}, 2)

    dt_mem = 0.04
    steps_30m = int(round(1800.0 / dt_mem))
    steps_3h = int(round(DURATION_3H_S / dt_mem))

    tracemalloc.start()
    try:
        for i in range(steps_30m):
            wall[0] = T0_WALL + (i + 1) * dt_mem
            s._step(dt_mem, (i + 1) * dt_mem)

        mem_30m, _ = tracemalloc.get_traced_memory()
        lines_30m = len(s._rec.lines) if s._rec else 0

        for i in range(steps_30m, steps_3h):
            wall[0] = T0_WALL + (i + 1) * dt_mem
            s._step(dt_mem, (i + 1) * dt_mem)

        mem_3h, _ = tracemalloc.get_traced_memory()
        lines_3h = len(s._rec.lines) if s._rec else 0
    finally:
        tracemalloc.stop()

    growth_bytes = mem_3h - mem_30m
    growth_kb = growth_bytes / 1024.0
    added_lines = lines_3h - lines_30m
    print(f"\n[H4 mémoire] 30 min -> 3 h : +{growth_kb:.1f} Ko pour +{added_lines} lignes "
          f"({growth_bytes / max(added_lines, 1):.0f} octets/ligne)")

    # ~9 000 dictionnaires de 14 clés dans SessionRecorder.lines (~650 octets chacun en CPython,
    # soit ~5,8 Mo) ; le seuil de 8 Mo garantit l'absence de fuite sur 3 h.
    assert len(s._power_window) <= 160
    assert growth_bytes < 8 * 1024 * 1024, f"croissance mémoire excessive : {growth_kb:.1f} Ko"


@pytest.mark.slow
def test_endurance_journal_and_fit_3h(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scénario 3 : journal et FIT de 3 h (10 800 ± 1 enregistrements, horodatages croissants, session de 3 h)."""
    s, wall = make_endurance_session(tmp_path, monkeypatch, port=6120)
    s._on_command("select_route", {"route_id": "boucle_10km"}, 1)
    s._on_command("start", {}, 2)

    for i in range(STEPS_3H):
        wall[0] = T0_WALL + (i + 1) * DT
        s._step(DT, (i + 1) * DT)

    s._on_command("end_session", {"save": True}, 3)
    assert s.state.session_state == "FINISHED"
    assert s.state.summary is not None and s.state.summary["fit_path"]

    jpath = next((tmp_path / "journal").glob("*.jsonl"))
    j_records = [ln for ln in read_journal(jpath) if ln.get("kind") == "record"]
    assert abs(len(j_records) - 10_800) <= 1

    ts_list = [r["ts"] for r in j_records]
    assert all(ts_list[i] < ts_list[i + 1] for i in range(len(ts_list) - 1)), (
        "les horodatages du journal doivent être strictement croissants"
    )

    fit_path = Path(s.state.summary["fit_path"])
    assert fit_path.is_file()
    msgs = [r.message for r in iter_records(fit_path)]
    fit_records = [m for m in msgs if isinstance(m, RecordMessage)]
    fit_sessions = [m for m in msgs if isinstance(m, SessionMessage)]

    assert len(fit_records) == len(j_records)
    assert len(fit_sessions) == 1
    assert fit_sessions[0].total_timer_time == pytest.approx(DURATION_3H_S, abs=1.0)


@pytest.mark.slow
def test_endurance_with_five_pauses(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scénario 4 : 3 h de pédalage avec 5 pauses de 2 min réparties (temps chronométré hors pauses, événements FIT)."""
    s, wall = make_endurance_session(tmp_path, monkeypatch, port=6130)
    s._on_command("select_route", {"route_id": "boucle_10km"}, 1)
    s._on_command("start", {}, 2)

    # 5 pauses aux 30, 60, 90, 120 et 150 minutes de séance (pas 90 000, 180 000, ...).
    pause_steps = {90_000 * k for k in range(1, 6)}
    pause_duration_s = 120.0
    pause_ticks = int(round(pause_duration_s / DT))
    cmd_id = 3
    mono = 0.0

    for step in range(1, STEPS_3H + 1):
        wall[0] += DT
        mono += DT
        s._step(DT, mono)
        if step in pause_steps:
            s._on_command("pause", {}, cmd_id)
            cmd_id += 1
            for _ in range(pause_ticks):
                wall[0] += DT
                mono += DT
                s._step(DT, mono)
            s._on_command("resume", {}, cmd_id)
            cmd_id += 1

    s._on_command("end_session", {"save": True}, cmd_id)
    assert s.state.session_state == "FINISHED"
    assert s.state.summary is not None
    assert s.state.summary["duration_s"] == pytest.approx(DURATION_3H_S, abs=1.0)

    fit_path = Path(s.state.summary["fit_path"])
    msgs = [r.message for r in iter_records(fit_path)]
    fit_sessions = [m for m in msgs if isinstance(m, SessionMessage)]
    fit_events = [m for m in msgs if isinstance(m, EventMessage)]

    assert len(fit_sessions) == 1
    assert fit_sessions[0].total_timer_time == pytest.approx(DURATION_3H_S, abs=1.0)
    assert fit_sessions[0].total_elapsed_time == pytest.approx(DURATION_3H_S + 5 * pause_duration_s, abs=1.0)
    # 1 start + 5 * (pause + resume) + 1 stop = 12 événements timer dans le FIT.
    assert len(fit_events) == 12


@pytest.mark.slow
def test_endurance_state_frame_size_under_limit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scénario 5 (audit F7) : pendant 3 h avec entraînement ERG actif, la trame state reste <= 1 400 octets."""
    s, wall = make_endurance_session(tmp_path, monkeypatch, port=6140)
    s._on_command("select_route", {"route_id": "boucle_10km"}, 1)
    s._on_command("select_workout", {"workout_id": "endurance_3h"}, 2)
    s._on_command("start", {}, 3)

    max_size = 0
    seq = 0

    for i in range(STEPS_3H):
        wall[0] = T0_WALL + (i + 1) * DT
        s._step(DT, (i + 1) * DT)
        # Échantillonnage de la trame state chaque seconde (10 800 trames sur 3 h).
        if i % 50 == 0:
            seq += 1
            frame = {**s.state.to_dict(), "seq": seq, "last_cmd_id": 3}
            raw = json.dumps(frame, separators=(",", ":")).encode("utf-8")
            if len(raw) > max_size:
                max_size = len(raw)

    print(f"\n[H4 F7] Taille maximale de la trame state observée sur 3 h (avec ERG) : "
          f"{max_size} octets (limite : {MAX_DATAGRAM_BYTES} octets)")
    assert 0 < max_size <= MAX_DATAGRAM_BYTES


def test_power_window_reset_between_chained_sessions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Séances enchaînées sans quitter le jeu (endurance 7bi) : la fenêtre de la puissance 3 s repart de zéro.

    Le temps de séance revient à 0 à chaque parcours chargé ; la fenêtre gardait les relevés de la séance
    précédente (horodatés plus tard), ne se vidait plus et grossissait de 50 relevés par seconde : +23 Mo/h
    et un pas du core de plus en plus long (somme de toute la fenêtre à chaque pas)."""
    s, wall = make_endurance_session(tmp_path, monkeypatch, port=6150)
    step = 0
    cmd_id = 0
    for _ in range(3):
        cmd_id += 1
        s._on_command("select_route", {"route_id": "boucle_10km"}, cmd_id)
        cmd_id += 1
        s._on_command("start", {}, cmd_id)
        for _ in range(int(300.0 / DT)):
            step += 1
            wall[0] = T0_WALL + step * DT
            s._step(DT, step * DT)
        assert len(s._power_window) <= 160
        assert s.state.power_3s == pytest.approx(s.state.power, abs=60.0)
        cmd_id += 1
        s._on_command("end_session", {"save": False}, cmd_id)
        assert s.state.session_state == "FINISHED"
