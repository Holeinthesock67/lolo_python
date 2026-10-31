"""Lot AS5 : ressentir l'abri (watts économisés `draft_w`, bilan `draft_time_s` et `draft_kj`)."""

import json

import jsonschema
import pytest
from openride_core import draft as d
from openride_core.bots import ConstantPowerBot
from openride_core.config import Config
from openride_core.ipc_lists import summary_extras
from openride_core.physics import PhysicsParams, draft_saving_w
from openride_core.tools.session_summary import Session, compute_summary, format_text

from test_draft import IPC_DIR, FlatRoute, flat_params, make_session, run


def test_saving_by_hand_40_kmh():
    """Critère 2 : 40 km/h, abri 0,30, CdA 0,32, sans vent, au niveau de la mer."""
    v = 40.0 / 3.6
    by_hand = 0.5 * 1.225 * 0.32 * 0.30 * v ** 3   # ρ₀ = 1,225 kg/m³ : 80,7 W
    assert draft_saving_w(v, 0.0, PhysicsParams(cda_m2=0.32), 0.30) == pytest.approx(by_hand, abs=2.0)
    assert round(by_hand) == 81


def test_saving_follows_wind_and_is_never_negative():
    v = 10.0
    calm = draft_saving_w(v, 0.0, PhysicsParams(), 0.3)
    assert draft_saving_w(v, 0.0, PhysicsParams(wind_mps=3.0), 0.3) > calm   # vent de face : abri plus utile
    assert draft_saving_w(v, 0.0, PhysicsParams(wind_mps=-3.0), 0.3) < calm
    assert draft_saving_w(v, 0.0, PhysicsParams(wind_mps=-12.0), 0.3) == 0.0   # l'air pousse : rien d'économisé
    assert draft_saving_w(v, 0.0, PhysicsParams(), 0.0) == 0.0
    assert draft_saving_w(v, 2000.0, PhysicsParams(), 0.3) < calm   # air moins dense en altitude


def _wheel_session(tmp_path, monkeypatch, port):
    cfg = Config()
    leader = ConstantPowerBot(250.0, bot_id="b1", params=flat_params(cfg), s=d.BIKE_LENGTH_M + 0.4, v=9.0)
    s, _ = make_session(tmp_path, monkeypatch, port, 200.0, [leader])   # 200 W : reste dans la roue
    s.route = FlatRoute()
    s.physics.v = 9.0
    s._on_command("start", {}, 2)
    return s, cfg


def test_state_carries_draft_w_in_the_wheel(tmp_path, monkeypatch):
    validator = jsonschema.Draft202012Validator(
        json.loads((IPC_DIR / "state.schema.json").read_text(encoding="utf-8")))
    s, _ = _wheel_session(tmp_path, monkeypatch, 6100)
    run(s, 30.0)   # dans la roue (à 20 s, les deux vélos se chevauchent en 1D : abri nul, lot AS2)
    frame = s.state.to_dict()
    assert frame["draft"] >= d.SAVED_W_MIN_DRAFT
    expected = draft_saving_w(s.physics.v, s.state.alt, s.physics.p, s._draft)
    assert isinstance(frame["draft_w"], int) and frame["draft_w"] == pytest.approx(expected, abs=1.0)
    assert frame["draft_w"] > 20
    assert not list(validator.iter_errors(frame))


def test_no_draft_w_without_shelter(tmp_path, monkeypatch):
    """Critère 3 : sans abri (ou sous 0,02), pas de `draft_w` ; sans bot, pas de clé du tout."""
    cfg = Config()
    far = ConstantPowerBot(250.0, bot_id="b1", params=flat_params(cfg), s=200.0, v=9.0)   # 200 m devant
    s, _ = make_session(tmp_path, monkeypatch, 6102, 200.0, [far])
    s.route = FlatRoute()
    s._on_command("start", {}, 2)
    run(s, 5.0)
    frame = s.state.to_dict()
    assert frame["draft"] < d.SAVED_W_MIN_DRAFT and "draft_w" not in frame
    records = [ln for ln in s._rec.lines if ln.get("kind") == "record"]
    assert records and all("draft_w" not in r for r in records)

    s0, _ = make_session(tmp_path / "solo", monkeypatch, 6104, 250.0, [])
    s0._on_command("start", {}, 2)
    run(s0, 5.0)
    assert "draft_w" not in s0.state.to_dict()
    solo = [ln for ln in s0._rec.lines if ln.get("kind") == "record"]
    assert "draft_kj" not in compute_summary(Session(solo, [], "jsonl"), 250.0)
    assert "draft_time_s" not in summary_extras(solo, [], 250.0)


def test_summary_time_and_energy_match_journal(tmp_path, monkeypatch):
    """Critère 5 : temps et énergie du bilan (journal et IPC) cohérents avec le journal à 1 % près."""
    s, cfg = _wheel_session(tmp_path, monkeypatch, 6106)
    run(s, 120.0)
    records = [ln for ln in s._rec.lines if ln.get("kind") == "record"]
    by_journal_j = sum(r.get("draft_w", 0) for r in records)
    in_wheel_s = sum(1 for r in records if r["draft"] >= 0.0225)
    assert by_journal_j > 2000 and in_wheel_s >= 80

    summary = compute_summary(Session(records, [], "jsonl"), cfg.rider.ftp_w)
    assert summary["draft_time_s"] == in_wheel_s
    assert summary["draft_kj"] == pytest.approx(by_journal_j / 1000.0, rel=0.01)
    text = format_text(summary)
    assert "Énergie économisée à l'abri :" in text and "kJ" in text

    extras = summary_extras(records, [], cfg.rider.ftp_w)
    assert extras["draft_time_s"] == in_wheel_s
    assert extras["draft_kj"] == summary["draft_kj"]
    # Énergie physique : l'intégrale à 50 Hz des watts économisés et les relevés à 1 Hz s'accordent à 1 %.
    s2, _ = _wheel_session(tmp_path / "b", monkeypatch, 6108)
    total_j = 0.0
    for i in range(int(120.0 / 0.02)):
        s2._step(0.02, 100.0 + i * 0.02)
        total_j += (s2._draft_w or 0) * 0.02
    assert by_journal_j == pytest.approx(total_j, rel=0.01)
