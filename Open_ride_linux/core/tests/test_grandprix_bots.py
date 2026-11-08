"""Lot GP3 : bots du Grand Prix des objets (usage des objets, garde, esquive, pas d'élastique).

Critères du cahier `docs/lots/LOT_GP3_bots_objets.md` §4 : chaque règle d'usage testée dans les deux sens ;
sur 200 courses simulées, taux d'esquive à ± 5 points de la consigne ; la puissance d'un bot ne dépend jamais
de la position du cycliste."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from openride_core import fit_export, profile
from openride_core.config import Config
from openride_core.demo_world import write_world
from openride_core.grandprix import ITEM_IDS, ME
from openride_core.grandprix.brain import DELAY_S, DODGE_BASE, dodge_chance, threatened, wants
from openride_core.grandprix.items import DEFAULT_ITEMS
from openride_core.grandprix.mode import GpInput, GrandPrixMode, RiderIn
from openride_core.input_providers import NullProvider
from openride_core.mock_driver import MockDriver
from openride_core.session import CoreSession
from openride_core.tools.route_vectors import _route

DT = 0.02
V = 10.0


def race(positions: dict[str, tuple[float, int]], *, seed: int = 1, chaos: str = "normal",
         levels: dict[str, float] | None = None, length_m: float = 20_000.0, **kw) -> GrandPrixMode:
    """Course figée : coureurs à `(s, voie)`, boîtes repoussées loin sauf mention."""
    mode = GrandPrixMode(list(positions), length_m, seed=seed, chaos=chaos, levels=levels, **kw)
    mode.start(0.0, {rid: RiderIn(s, V, V) for rid, (s, _) in positions.items()})
    for rid, (_, lane) in positions.items():
        r = mode.racers[rid]
        r.lane, r.auto = lane, False
    mode.boxes.rows = [length_m * 2.0]
    return mode


def holding(mode: GrandPrixMode, rid: str, item: str):
    r = mode.racers[rid]
    r.held, r.charges = item, DEFAULT_ITEMS[item].charges
    return r, mode.table.items[item]


# --- règles d'usage ---------------------------------------------------------------------------

@pytest.mark.parametrize("item", ["gel", "gel_x3", "star", "team_car", "stealth"])
def test_self_items_used_straight_away(item):
    mode = race({ME: (0.0, 1), "b": (50.0, 1)})
    assert wants(mode, *holding(mode, "b", item))


def test_storm_only_with_a_leader_ahead():
    mode = race({ME: (100.0, 1), "b": (50.0, 1)})
    assert wants(mode, *holding(mode, "b", "storm"))
    mode = race({ME: (0.0, 1), "b": (50.0, 1)})
    assert not wants(mode, *holding(mode, "b", "storm"))          # en tête : personne à viser


def test_bottle_dropped_with_a_follower_within_30_m():
    mode = race({ME: (25.0, 2), "b": (50.0, 1), "c": (100.0, 1)})
    assert wants(mode, *holding(mode, "b", "bottle"))
    mode = race({ME: (15.0, 2), "b": (50.0, 1), "c": (100.0, 1)})
    assert not wants(mode, *holding(mode, "b", "bottle_x3"))      # 35 m derrière : trop loin


def test_leader_keeps_bottle_and_musette_as_shield_until_a_box_row_nears():
    mode = race({ME: (40.0, 1), "b": (50.0, 1)})
    for item in ("bottle", "bottle_x3", "musette", "musette_x3"):
        assert not wants(mode, *holding(mode, "b", item)), item
    mode.boxes.rows = [150.0]                                       # rangée à 100 m : la garde est levée
    assert wants(mode, *holding(mode, "b", "bottle"))


def test_musette_needs_a_target_on_its_lane_within_150_m():
    mode = race({ME: (150.0, 1), "b": (50.0, 1)})
    assert wants(mode, *holding(mode, "b", "musette"))
    mode = race({ME: (150.0, 0), "b": (50.0, 1)})
    assert not wants(mode, *holding(mode, "b", "musette"))         # autre voie
    mode = race({ME: (210.0, 1), "b": (50.0, 1)})
    assert not wants(mode, *holding(mode, "b", "musette_x3"))      # 160 m


def test_homing_needs_a_target_within_lock_range():
    mode = race({ME: (240.0, 0), "b": (50.0, 2)})
    assert wants(mode, *holding(mode, "b", "homing"))              # 190 m, autre voie : verrouillée
    mode = race({ME: (260.0, 1), "b": (50.0, 1)})
    assert not wants(mode, *holding(mode, "b", "homing"))          # 210 m
    mode = race({ME: (0.0, 1), "b": (50.0, 1)})
    mode.boxes.rows = [100.0]                                       # pas de garde : la sonnette n'est pas un bouclier
    assert not wants(mode, *holding(mode, "b", "homing"))          # aucune cible devant


def test_headwind_needs_two_riders_ahead():
    mode = race({ME: (100.0, 1), "c": (80.0, 0), "b": (50.0, 1)})
    assert wants(mode, *holding(mode, "b", "headwind"))
    mode = race({ME: (100.0, 1), "c": (10.0, 0), "b": (50.0, 1)})
    assert not wants(mode, *holding(mode, "b", "headwind"))        # un seul devant
    mode = race({ME: (10.0, 1), "c": (20.0, 0), "b": (50.0, 1)})
    assert not wants(mode, *holding(mode, "b", "headwind"))        # en tête


def test_bell_against_incoming_projectile_or_storm():
    mode = race({ME: (0.0, 1), "b": (50.0, 1)})
    r, spec = holding(mode, "b", "bell")
    assert not wants(mode, r, spec) and not threatened(mode, r)
    mode.objects.add("musette", 30.0, 1, 0.0, 60.0, v=V + 15.0, owner=ME)
    assert wants(mode, r, spec)                                     # 20 m derrière, plus vite, même voie
    mode = race({ME: (0.0, 1), "b": (50.0, 1)})
    r, spec = holding(mode, "b", "bell")
    mode.objects.add("musette", 30.0, 0, 0.0, 60.0, v=V + 15.0, owner=ME)
    assert not wants(mode, r, spec)                                 # autre voie
    mode.objects.add("storm", -500.0, None, 0.0, 60.0, v=V + 30.0, owner=ME, target="b")
    assert wants(mode, r, spec)                                     # le nuage vise le bot, même de loin


def test_bot_uses_its_item_after_a_seeded_delay():
    delays = []
    for seed in range(40):
        mode = GrandPrixMode([ME, "b"], 20_000.0, seed=seed)
        mode.start(0.0, {ME: RiderIn(0.0, V, V), "b": RiderIn(50.0, V, V)})
        mode.boxes.rows = [40_000.0]
        holding(mode, "b", "gel")
        t = 0.0
        while mode.racers["b"].held is not None and t < 5.0:
            t += DT
            mode.step(GpInput(t, DT, {ME: RiderIn(t * V, V, V), "b": RiderIn(50.0 + t * V, V, V)}))
        delays.append(t)
    assert all(DELAY_S[0] <= d <= DELAY_S[1] + DT for d in delays)
    assert max(delays) - min(delays) > 1.5                          # tiré, pas fixe


def test_same_seed_same_decisions():
    def run(seed):
        mode = GrandPrixMode([ME, "a", "b"], 20_000.0, seed=seed)
        mode.start(0.0, {ME: RiderIn(0.0, V, V), "a": RiderIn(10.0, V, V), "b": RiderIn(20.0, V, V)})
        holding(mode, "a", "gel_x3")
        for i in range(1, 400):
            t = i * DT
            mode.step(GpInput(t, DT, {ME: RiderIn(t * V, V, V), "a": RiderIn(10 + t * V, V, V),
                                      "b": RiderIn(20 + t * V, V, V)}))
        return [line for line in mode.journal if line["rider"] != ME]

    assert run(7) == run(7) and run(7)


# --- esquive ----------------------------------------------------------------------------------

def test_dodge_chance_by_chaos_and_level():
    assert [dodge_chance(c, 100.0) for c in ("soft", "normal", "wild")] == [0.30, 0.50, 0.75]
    assert dodge_chance("normal", 50.0) == pytest.approx(0.40)
    assert dodge_chance("normal", 150.0) == pytest.approx(0.60)
    assert dodge_chance("wild", 200.0) == pytest.approx(0.85)       # niveau borné à 150 %


def dodge_race(seed: int, chaos: str, level: float) -> tuple[int, int, int]:
    """Un bot roule à 10 m/s vers un bidon posé sur sa voie, 60 m devant : (jugés, esquives, glissades)."""
    mode = GrandPrixMode([ME, "b"], 20_000.0, seed=seed, chaos=chaos, levels={"b": level})
    mode.start(0.0, {ME: RiderIn(0.0, V, V), "b": RiderIn(100.0, V, V)})
    mode.boxes.rows = [40_000.0]
    mode.objects.add("bottle", 160.0, 1, 0.0, 90.0, owner=ME)
    for i in range(1, 400):
        t = i * DT
        mode.step(GpInput(t, DT, {ME: RiderIn(t * V, V, V), "b": RiderIn(100.0 + t * V, V, V)}))
    return mode.brain.stats.tries, mode.brain.stats.done, mode.racers["b"].received.get("bottle", 0)


@pytest.mark.parametrize("chaos,level", [("soft", 100.0), ("normal", 100.0), ("wild", 100.0),
                                         ("normal", 50.0), ("normal", 150.0)])
def test_dodge_rate_over_200_races(chaos, level):
    tries = done = slipped = 0
    for seed in range(200):
        n, d, s = dodge_race(seed, chaos, level)
        tries, done, slipped = tries + n, done + d, slipped + s
    assert tries == 200                                            # une décision par objet
    assert done / tries == pytest.approx(dodge_chance(chaos, level), abs=0.05)
    assert slipped == tries - done                                  # esquivé : jamais touché ; sinon toujours


def test_no_dodge_for_own_object_other_lane_or_behind():
    mode = race({ME: (0.0, 1), "b": (100.0, 1)}, chaos="wild", levels={"b": 150.0})
    mode.objects.add("bottle", 120.0, 1, 0.0, 90.0, owner="b")      # le sien
    mode.objects.add("bottle", 120.0, 0, 0.0, 90.0, owner=ME)       # autre voie
    mode.objects.add("bottle", 90.0, 1, 0.0, 90.0, owner=ME)        # derrière
    mode.objects.add("bottle", 160.0, 1, 0.0, 90.0, owner=ME)       # 60 m : trop loin pour l'instant
    mode.brain.step(mode, 0.0)
    assert mode.brain.stats.tries == 0 and mode.lane_target("b") == 1


def test_dodge_avoids_blocked_lane():
    mode = race({ME: (0.0, 1), "b": (100.0, 1)}, seed=3, chaos="wild", levels={"b": 150.0})
    mode.brain.chance["b"] = 1.0
    mode.objects.add("bottle", 120.0, 1, 0.0, 90.0, owner=ME)
    mode.objects.add("bottle", 125.0, 0, 0.0, 90.0, owner=ME)
    mode.brain.step(mode, 0.0)
    assert mode.racers["b"].lane_to == 2


def test_player_is_never_driven_and_ghost_free():
    mode = GrandPrixMode([ME, "b"], 10_000.0)
    assert set(mode.brain.minds) == {"b"}
    assert set(GrandPrixMode([ME, "b"], 10_000.0, bots=()).brain.minds) == set()
    with pytest.raises(Exception):
        GrandPrixMode([ME, "b"], 10_000.0, bots=[ME])


# --- pas d'élastique ----------------------------------------------------------------------------

@pytest.fixture
def gp_session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(fit_export, "ACTIVITIES_DIR", tmp_path / "act")
    monkeypatch.setattr(profile, "PROFILE_PATH", tmp_path / "profile.json")
    n = 151
    headings = [i * 360.0 / (n - 1) for i in range(n)]
    alts = [100.0 + 6.0 * (1.0 - abs(2.0 * i / (n - 1) - 1.0)) for i in range(n)]
    world = write_world(tmp_path / "routes", "anneau", 1500.0)
    (world / "route.json").write_text(json.dumps(_route(headings, alts, ds=10.0, last=10.0, kind="loop")),
                                      encoding="utf-8")
    (tmp_path / "grandprix.toml").write_text("[items]\n" + "".join(f"{i} = false\n" for i in ITEM_IDS),
                                             encoding="utf-8")

    def make(port: int, power_w: float) -> CoreSession:
        cfg = Config()
        cfg.ipc.port_state, cfg.ipc.port_commands = port, port + 1
        cfg.ride.vehicle_draft = "off"
        s = CoreSession(cfg, driver=MockDriver(base_power_w=power_w, ramp_amplitude_w=0.0), inputs=[NullProvider()],
                        journal_dir=tmp_path / f"journal{port}", routes_root=tmp_path / "routes",
                        workouts_dir=tmp_path, records_path=tmp_path / "records.json",
                        powerups_path=tmp_path / "powerups.toml", wtf_path=tmp_path / "wtf.toml",
                        grandprix_path=tmp_path / "grandprix.toml")
        s.server.send_raw = lambda m, max_size=None: None
        s.server.send_error = lambda code, msg: pytest.fail(f"{code} : {msg}")
        s.server.send_input_event = lambda ev: None
        s._on_command("select_route", {"route_id": "anneau"}, 1)
        s._on_command("start", {"mode": "grandprix"}, 2)
        return s

    return make


def test_bot_power_never_depends_on_the_rider_gap(gp_session, monkeypatch):
    """Cycliste à 0 W ou à 40 W, parti 200 m derrière le peloton (ni roue, ni groupe, ni abri) : chaque bot
    pousse exactement la même puissance, quel que soit l'écart (pas d'élastique, plan GP §6)."""
    wall = [1_790_000_000.0]
    monkeypatch.setattr(time, "time", lambda: wall[0])
    runs = []
    for port, watts in ((6900, 0.0), (6910, 40.0)):
        wall[0] = 1_790_000_000.0
        s = gp_session(port, watts)
        assert s.grandprix is not None and not s.grandprix.enabled and len(s.bots) == 4
        for b in s.bots:
            b.physics.s += 200.0
        powers = []
        for _ in range(int(120 / DT)):
            wall[0] += DT
            s._step(DT, wall[0])
            powers.append(tuple(round(b.power_w, 9) for b in s.bots))
        runs.append((powers, min(b.s for b in s.bots) - s.physics.s))
    (pa, gap_a), (pb, gap_b) = runs
    assert gap_a > gap_b + 100.0                                    # écarts bien différents
    assert pa == pb
