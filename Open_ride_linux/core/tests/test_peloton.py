"""Tests du peloton d'environ 12 bots (lot PL1, version 3.0, contrat IPC révision 1.6).

Critères du cahier `docs/lots/LOT_PL1_peloton.md` :
1. `start.bots` accepte 11 bots à puissance constante ou à profil et un fantôme ; 12 bots ou 13 éléments
   sont refusés (`BotError`) ; la ligne de commande accepte 11 bots et refuse le 12e.
2. Trame allégée (`light_frame`) : jusqu'à 5 bots, rien ne change ; au-delà, les 5 plus proches du cycliste
   gardent tout, les autres perdent `cp_w`, `mass_kg`, `wbal_pct` et `gap_s` (et `name`, `profile` sauf un
   à tour de rôle), `jersey` à null disparaît,
   le maillot porté reste ; sur une boucle, la distance la plus courte compte.
3. Pire trame de la révision 1.6 (12 bots, avec ou sans `devices`) valide et sous 4 096 octets, sans
   allègement par `fit_state`.
4. Séance réelle avec 11 bots à profil : grille de départ sans chevauchement, trame valide et sous 4 096
   octets à chaque pas, pas de physique p99 sous 3 ms.
5. Derniers choix du menu : 11 bots et le fantôme sont gardés.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import jsonschema
import pytest

from openride_core import ipc_budget, last_choices
from openride_core.bots import (FULL_FRAME_BOTS, LIGHT_DROPPED, MAX_BOTS, MAX_CONSTANT_BOTS, BotError, ProfileBot,
                                bots_from_menu, light_frame)
from openride_core.config import Config
from openride_core.draft import BIKE_LENGTH_M, RIDER_WIDTH_M, start_grid
from openride_core.input_providers import NullProvider
from openride_core.mock_driver import MockDriver
from openride_core.physics import PhysicsParams
from openride_core.session import CoreSession

IPC_DIR = Path(__file__).resolve().parents[2] / "docs" / "contracts" / "ipc"
PROFILES = ["rouleur", "climber", "sprinter", "diesel"]


def _validator() -> jsonschema.Draft202012Validator:
    return jsonschema.Draft202012Validator(json.loads((IPC_DIR / "state.schema.json").read_text(encoding="utf-8")))


def _peloton_items(n: int) -> list[dict]:
    return [{"kind": "profile", "profile": PROFILES[i % len(PROFILES)]} for i in range(n)]


# --- critère 1 : limites ------------------------------------------------------------------------

def test_menu_accepts_eleven_bots_and_a_ghost(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    assert (MAX_CONSTANT_BOTS, MAX_BOTS) == (11, 12)
    params = PhysicsParams()
    bots = bots_from_menu(_peloton_items(11), params, 250.0, None, tmp_path)
    assert len(bots) == 11 and len({b.id for b in bots}) == 11 and len({b.name for b in bots}) == 11
    assert all(len(b.id) <= 8 and len(b.name) <= 16 for b in bots)
    with pytest.raises(BotError, match="au plus 11"):
        bots_from_menu(_peloton_items(12), params, 250.0, None, tmp_path)
    with pytest.raises(BotError, match="12 bots au plus"):
        bots_from_menu(_peloton_items(11) + [{"kind": "ghost"}, {"kind": "ghost"}], params, 250.0, None, tmp_path)


def test_cli_accepts_eleven_bots(tmp_path: Path):
    from openride_core.__main__ import build_parser

    argv = ["run", "--trainer", "mock"]
    for i in range(11):
        argv += ["--bot-profile", PROFILES[i % 4]]
    args = build_parser().parse_args(argv)
    assert len(args.bot_profile) == 11


# --- critère 2 : trame allégée -----------------------------------------------------------------

def _frame_bot(i: int, s: float, jersey=None) -> dict:
    return {"id": f"bot{i}", "name": f"Rouleur {i}", "s": s, "v": 10.0, "kind": "constant", "lane_m": 1.2,
            "profile": "rouleur", "cp_w": 250.0, "mass_kg": 75.0, "wbal_pct": 90.0, "jersey": jersey, "gap_s": 1.0}


def test_light_frame_keeps_small_lists():
    bots = [_frame_bot(i, 100.0 + i) for i in range(FULL_FRAME_BOTS)]
    assert light_frame(bots, 100.0) is bots


def test_light_frame_keeps_the_five_nearest():
    # cycliste à 500 m ; bots de 100 m en 100 m derrière et devant
    bots = [_frame_bot(i + 1, 100.0 * i, jersey="kom" if i == 0 else None) for i in range(12)]
    out = light_frame(bots, 500.0)
    assert [b["id"] for b in out] == [b["id"] for b in bots]   # ordre gardé
    full = {b["id"] for b in out if "cp_w" in b}
    assert full == {"bot6", "bot5", "bot7", "bot4", "bot8"}    # 500, 400, 600, 300, 700 m
    for b in out:
        assert {"id", "s", "v", "kind", "lane_m"} <= b.keys()
        if b["id"] not in full:
            assert not set(LIGHT_DROPPED) & b.keys()
    named = [b["id"] for b in out if "name" in b and b["id"] not in full]
    assert named == ["bot1"] and all("profile" in b for b in out if "name" in b)   # un bot loin à tour de rôle
    seen = set()
    for n in range(7):                                          # 7 bots loin : chacun en 7 trames
        seen |= {b["id"] for b in light_frame(bots, 500.0, frame_no=n) if "name" in b and b["id"] not in full}
    assert seen == {b["id"] for b in bots} - full
    assert out[0]["jersey"] == "kom"                            # maillot porté gardé, même loin
    assert all("jersey" not in b for b in out[1:])
    assert all("cp_w" in b for b in bots)                       # la liste reçue n'est pas modifiée


def test_light_frame_uses_shortest_way_on_a_loop():
    bots = [_frame_bot(1, 9_990.0)] + [_frame_bot(i, 3_000.0 + 10.0 * i) for i in range(2, 8)]
    out = light_frame(bots, 5.0, length_m=10_000.0, is_loop=True)
    assert "cp_w" in out[0]                                      # 15 m derrière par la ligne
    assert sum("cp_w" in b for b in out) == FULL_FRAME_BOTS


# --- critère 3 : pire trame ----------------------------------------------------------------------

def test_worst_peloton_frames_fit_without_degradation():
    validator = _validator()
    for frame in (ipc_budget.worst_state("1.6"), ipc_budget.worst_peloton_devices()):
        assert len(frame["bots"]) == 12
        assert [e.message for e in validator.iter_errors(frame)] == []
        assert ipc_budget.size(frame) <= ipc_budget.state_limit("1.6") - 128   # marge gardée pour la 3.0
        assert ipc_budget.fit_state(frame, ipc_budget.state_limit("1.6")) == (frame, [])
    assert "1.6 peloton + devices" in ipc_budget.report()


# --- critère 4 : séance réelle -------------------------------------------------------------------

def _peloton_session(tmp_path: Path) -> CoreSession:
    cfg = Config()
    params = PhysicsParams.from_config(cfg)
    bots = [ProfileBot(PROFILES[i % 4], bot_id=f"bot{i + 1}", name=f"Coureur {i + 1}", params=params)
            for i in range(MAX_CONSTANT_BOTS)]
    session = CoreSession(cfg, driver=MockDriver(), inputs=[NullProvider()], journal_dir=tmp_path / "j",
                          routes_root=tmp_path / "r", bots=bots)
    return session


def test_peloton_session_frames_and_cost(tmp_path: Path):
    session = _peloton_session(tmp_path)
    start_grid(session.bots, session.physics.s)   # comme `start` : grille de départ (lot AS2)
    # par deux, aucun chevauchement, six rangs au plus
    assert min(b.s for b in session.bots) >= session.physics.s - 6 * (BIKE_LENGTH_M + 1.0)
    places = [(b.s, b.lane.m) for b in session.bots]
    for i, (s1, m1) in enumerate(places):
        for s2, m2 in places[i + 1:]:
            assert abs(s1 - s2) >= BIKE_LENGTH_M or abs(m1 - m2) >= RIDER_WIDTH_M
    session.state.session_state = "RUNNING"
    validator = _validator()
    durations = []
    now = 1.0
    for i in range(1500):   # 30 s à 50 Hz
        t0 = time.perf_counter()
        session._step(0.02, now)
        durations.append(time.perf_counter() - t0)
        now += 0.02
        if i % 50 == 0:
            session.state.bots = [b.to_dict() for b in session.bots]
            session._lighten_bots_frame()
            d = session.state.to_dict()
            assert len(d["bots"]) == 11
            assert sum("cp_w" in b for b in d["bots"]) == FULL_FRAME_BOTS
            assert [e.message for e in validator.iter_errors(d)] == []
            assert ipc_budget.size(d) <= ipc_budget.state_limit("1.6")
            pos = [(b.s, b.lane.m) for b in session.bots]
            touching = [(a, c) for a in range(len(pos)) for c in range(a + 1, len(pos))
                        if abs(pos[a][0] - pos[c][0]) < BIKE_LENGTH_M - 0.1 and abs(pos[a][1] - pos[c][1]) < RIDER_WIDTH_M - 0.05]
            assert touching == [], f"bots qui se touchent à {i * 0.02:.1f} s : {touching}"
    durations.sort()
    p99_ms = durations[int(len(durations) * 0.99)] * 1000.0
    assert p99_ms < 3.0, f"pas p99 {p99_ms:.2f} ms avec 11 bots"


# --- critère 5 : derniers choix ------------------------------------------------------------------

def test_last_choices_keep_a_peloton():
    items = _peloton_items(11) + [{"kind": "ghost"}]
    assert last_choices.clean("bots", items) == items
    assert last_choices.clean("bots", items + [{"kind": "ghost"}]) is None
