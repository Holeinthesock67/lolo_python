"""Lot GP1 : règles du mode « Grand Prix des objets » (paquet pur `grandprix`, module `route_objects`)."""

from __future__ import annotations

import inspect
import json
import random
from dataclasses import replace

import pytest

from openride_core import route_objects
from openride_core.grandprix import boxes, draw, effects, items, mode
from openride_core.grandprix.boxes import BoxRows, row_positions
from openride_core.grandprix.draw import DrawContext, bracket, weights_for
from openride_core.grandprix.effects import EffectSpec, gain_s
from openride_core.grandprix.items import (DEFAULT_ITEMS, DEFAULT_TABLE, DEFAULT_WEIGHTS, ITEM_IDS,
                                           GrandPrixError, load_table, table_from)
from openride_core.grandprix.mode import (HIT_GRACE_S, ME, RESUME_GRACE_S, GpInput, GrandPrixMode, RiderIn,
                                          lane_index)
from openride_core.physics import PhysicsParams, RiderPhysics, steady_speed
from openride_core.route_objects import RouteObjects, Runner

DT = 0.02
P = PhysicsParams()
V_EQ = steady_speed(250.0, 0.0, P)


# --- chiffres du plan §3 (cycliste de 84 kg à 250 W, écart 60 s après) --------------------------

PLAN_GAINS = {      # objet : (plat, 6 %, −4 %)
    "gel": (3.9, 1.9, 3.4),
    "bottle": (-3.9, -1.5, -3.7),
    "musette": (-3.9, -1.5, -3.7),
    "homing": (-3.9, -1.5, -3.7),
    "storm": (-6.9, -3.0, -7.0),
    "star": (4.2, 2.8, 3.9),
    "headwind": (-2.1, -1.1, -1.9),
    "team_car": (9.5, 6.4, 8.5),
}


@pytest.mark.parametrize("item", sorted(PLAN_GAINS))
def test_plan_gains_within_10_pct(item):
    spec = DEFAULT_ITEMS[item]
    fx = spec.self_fx if spec.target == "self" else spec.hit_fx
    for grade, expected in zip((0.0, 6.0, -4.0), PLAN_GAINS[item]):
        got = gain_s(fx, 250.0, grade)
        assert got == pytest.approx(expected, rel=0.10), (item, grade, got)


def test_chaos_scales_strength_not_duration():
    kick = EffectSpec("kick", 1.3)
    assert kick.scaled(0.7).factor == pytest.approx(1.21)
    assert kick.scaled(1.3).factor == pytest.approx(1.39)
    cap = EffectSpec("cap", 0.5, 1.5)
    assert cap.scaled(1.3) == EffectSpec("cap", 0.35, 1.5)
    assert EffectSpec("wind", 5.0, 6.0).scaled(0.7).factor == pytest.approx(3.5)
    assert EffectSpec("immune", 1.0, 8.0).scaled(1.3) == EffectSpec("immune", 1.0, 8.0)
    soft = gain_s(DEFAULT_TABLE.scaled(0.7).items["gel"].self_fx)
    wild = gain_s(DEFAULT_TABLE.scaled(1.3).items["gel"].self_fx)
    assert soft < gain_s(DEFAULT_ITEMS["gel"].self_fx) < wild


def test_unknown_effect_refused():
    with pytest.raises(ValueError):
        EffectSpec("teleport", 1.0)


# --- catalogue et fichier de valeurs ------------------------------------------------------------

def test_catalogue_has_thirteen_items_described_by_data():
    assert len(ITEM_IDS) == 13 and set(DEFAULT_ITEMS) == set(ITEM_IDS)
    assert {DEFAULT_ITEMS[i].charges for i in ("gel_x3", "bottle_x3", "musette_x3")} == {3}
    for spec in DEFAULT_ITEMS.values():
        assert spec.label


def test_weights_follow_plan_rows():
    plan = {   # lignes du plan §4.2 : (tête, < 5 s, 5 à 15 s, > 15 s)
        ("bottle", "bottle_x3"): (40, 20, 5, 0), ("musette", "musette_x3"): (20, 25, 20, 10),
        ("homing",): (0, 20, 20, 10), ("bell",): (25, 5, 0, 0), ("gel", "gel_x3"): (15, 20, 25, 20),
        ("headwind",): (0, 5, 10, 10), ("storm",): (0, 0, 10, 10), ("star",): (0, 5, 10, 15),
        ("team_car",): (0, 0, 0, 20), ("stealth",): (0, 0, 0, 5),
    }
    for i, b in enumerate(items.BRACKETS):
        assert sum(DEFAULT_WEIGHTS[b].values()) == pytest.approx(100.0)
        for group, row in plan.items():
            assert sum(DEFAULT_WEIGHTS[b].get(k, 0.0) for k in group) == pytest.approx(row[i]), (b, group)


def test_values_file(tmp_path):
    f = tmp_path / "grandprix.toml"
    assert load_table(f) is DEFAULT_TABLE
    f.write_text("[gel]\nkick = 1.4\n[storm]\nduration_s = 2.0\nslip = 0.8\n[weights.lead]\nbell = 0\n")
    t = load_table(f)
    assert t.items["gel"].self_fx[0].factor == 1.4
    assert t.items["storm"].hit_fx[0].duration_s == 2.0 and t.items["storm"].splash_fx[0].factor == 0.8
    assert t.weights["lead"]["bell"] == 0.0
    for bad in ("[gel]\nkick = 3.0\n", "[gel]\nslip = 0.5\n", "[banana]\nx = 1\n", "[gel]\ncolor = 1\n",
                "[weights.top]\ngel = 1\n", "[weights.lead]\nbanana = 1\n", "[gel]\nrange_m = 100\n",
                "[gel]\nkick = true\n"):
        f.write_text(bad)
        with pytest.raises(GrandPrixError):
            load_table(f)
    f.write_text("[gel\n")
    with pytest.raises(GrandPrixError):
        load_table(f)


# --- tirage ---------------------------------------------------------------------------------------

CTX = {"lead": DrawContext(1, 0.0, 0, False), "lt5": DrawContext(3, 2.0, 2, False),
       "5to15": DrawContext(3, 9.0, 2, False), "gt15": DrawContext(4, 30.0, 3, False)}


def test_brackets():
    assert [bracket(CTX[b]) for b in items.BRACKETS] == list(items.BRACKETS)
    assert bracket(DrawContext(2, 5.0, 1, False)) == "5to15"
    assert bracket(DrawContext(2, 15.0, 1, False)) == "5to15"


@pytest.mark.parametrize("b", items.BRACKETS)
def test_draw_frequencies_within_2_points(b):
    rng = random.Random(7)
    ctx = CTX[b]
    expected = weights_for(ctx, DEFAULT_WEIGHTS, ITEM_IDS)
    counts: dict[str, int] = {}
    for _ in range(10_000):
        k = draw.draw(ctx, DEFAULT_WEIGHTS, ITEM_IDS, rng)
        counts[k] = counts.get(k, 0) + 1
    assert set(counts) <= set(expected)
    for k, w in expected.items():
        assert 100.0 * counts.get(k, 0) / 10_000 == pytest.approx(w, abs=2.0), (b, k)


def test_draw_never_useless_nor_disabled():
    rng = random.Random(1)
    alone = DrawContext(2, 9.0, 0, False)             # personne devant (le premier vient d'arriver)
    second = DrawContext(2, 9.0, 1, False)
    flying = DrawContext(4, 30.0, 3, True)
    enabled = [i for i in ITEM_IDS if i != "gel"]
    for _ in range(3000):
        assert draw.draw(alone, DEFAULT_WEIGHTS, ITEM_IDS, rng) not in ("homing", "headwind", "stealth", "storm")
        assert draw.draw(second, DEFAULT_WEIGHTS, ITEM_IDS, rng) != "storm"
        assert draw.draw(flying, DEFAULT_WEIGHTS, ITEM_IDS, rng) != "storm"
        assert draw.draw(CTX["gt15"], DEFAULT_WEIGHTS, enabled, rng) != "gel"
    assert sum(weights_for(CTX["gt15"], DEFAULT_WEIGHTS, enabled).values()) == pytest.approx(100.0)
    assert draw.draw(CTX["lead"], DEFAULT_WEIGHTS, ["team_car"], rng) is None


# --- boîtes ---------------------------------------------------------------------------------------

def test_rows_line_and_circuit():
    assert row_positions(5000.0, 1500.0) == [500.0, 2000.0, 3500.0]
    assert row_positions(4100.0, 1500.0) == [500.0, 2000.0, 3500.0]
    assert row_positions(3600.0, 1500.0) == [500.0, 2000.0]          # jamais à moins de 200 m de l'arrivée
    laps = row_positions(9000.0, 1500.0, lap_m=3000.0)
    assert laps == [500.0, 2000.0, 3500.0, 5000.0, 6500.0, 8000.0]
    assert {x % 3000.0 for x in laps} == {500.0, 2000.0}


def test_box_reforms_after_2_s():
    rows = BoxRows([500.0])
    assert rows.crossed(499.0, 500.0) == [0] and rows.crossed(500.0, 501.0) == []
    assert rows.take(0, 1, 10.0) and not rows.take(0, 1, 11.9)
    assert rows.take(0, 2, 11.0)
    assert rows.take(0, 1, 12.0)


# --- objets sur la route --------------------------------------------------------------------------

def test_route_objects_cap_evicts_oldest_bottle():
    ro = RouteObjects()
    for i in range(route_objects.MAX_OBJECTS):
        assert ro.add("bottle", float(i), 1, float(i), 90.0, evictable=True)
    assert len(ro) == 32
    ro.add("bottle", 100.0, 1, 100.0, 90.0, evictable=True)
    assert len(ro) == 32 and min(o.s for o in ro) == 1.0
    full = RouteObjects(max_objects=2)
    full.add("musette", 0.0, 1, 0.0, 60.0)
    full.add("musette", 1.0, 1, 0.0, 60.0)
    assert full.add("musette", 2.0, 1, 0.0, 60.0) is None


def test_route_objects_contact_by_lane_and_sweep():
    ro = RouteObjects()
    ro.add("bottle", 100.0, 1, 0.0, 90.0)
    assert ro.step(0.1, 0.1, [Runner("a", 95.0, 99.0, 2)]) == []          # autre voie
    hits = ro.step(0.2, 0.1, [Runner("a", 99.0, 103.0, 1)])                # croisé pendant le pas
    assert [c.runner for c in hits] == ["a"] and len(ro) == 0
    ro.add("musette", 0.0, 0, 0.0, 60.0, v=20.0, range_m=50.0, owner="x")
    assert ro.step(2.0, 2.0, [Runner("x", 0.0, 10.0, 0)]) == []            # pas son lanceur au départ
    assert ro.step(3.0, 2.0, []) == [] and len(ro) == 0                    # portée de 50 m dépassée


# --- mode -----------------------------------------------------------------------------------------

class Sim:
    """Petite course simulée : physique du core, objets du mode, puissance constante par coureur."""

    def __init__(self, powers: dict[str, float], length_m: float = 10_000.0, grade: float = 0.0,
                 seed: int = 1, gap_m: float = 3.0, **kw):
        self.powers, self.grade = powers, grade
        self.mode = GrandPrixMode(list(powers), length_m, seed=seed, **kw)
        self.phys = {}
        for i, rid in enumerate(powers):
            v = steady_speed(powers[rid], grade, P)
            self.phys[rid] = RiderPhysics(replace(P), -i * gap_m, v)
        self.v_eq = {rid: steady_speed(w, grade, P) for rid, w in powers.items()}
        self.t = 0.0
        self.lanes: dict[str, float | None] = {rid: None for rid in powers}
        self.mode.start(0.0, self.inputs())

    def inputs(self):
        return {rid: RiderIn(ph.s, ph.v, self.v_eq[rid], self.lanes[rid], self.grade) for rid, ph in self.phys.items()}

    def step(self, dt: float = DT, paused: bool = False):
        self.t += dt
        if not paused:
            for rid, ph in self.phys.items():
                ph.p = replace(P, wind_mps=self.mode.wind_mps(rid))
                ph.step(self.powers[rid], self.grade, dt=dt)
        out = self.mode.step(GpInput(self.t, dt, self.inputs(), paused))
        for rid, v in out.items():
            self.phys[rid].v = v
        return out

    def run(self, seconds: float, dt: float = DT, **kw):
        for _ in range(int(round(seconds / dt))):
            self.step(dt, **kw)

    def give(self, rid: str, item: str):
        r = self.mode.racers[rid]
        r.held, r.charges, r.roll = item, DEFAULT_ITEMS[item].charges, None


def test_gel_kicks_once_and_matches_plan():
    sim = Sim({ME: 250.0, "ref": 250.0}, gap_m=0.0)
    sim.mode.set_lane("ref", 0)
    sim.run(1.0)
    sim.give(ME, "gel")
    assert sim.mode.use(ME) and sim.mode.racers[ME].held is None and not sim.mode.use(ME)
    v0 = sim.phys[ME].v
    sim.step()
    assert sim.phys[ME].v == pytest.approx(v0 * 1.3, rel=0.01)
    sim.run(60.0)
    gain = (sim.phys[ME].s - sim.phys["ref"].s) / V_EQ
    assert gain == pytest.approx(3.9, rel=0.10)


def test_gel_x3_one_charge_per_second():
    sim = Sim({ME: 250.0, "b": 250.0})
    sim.give(ME, "gel_x3")
    assert sim.mode.use(ME) and not sim.mode.use(ME)
    sim.run(1.0)
    assert sim.mode.use(ME) and sim.mode.racers[ME].charges == 1
    sim.run(1.0)
    assert sim.mode.use(ME) and sim.mode.racers[ME].held is None


def test_bottle_slips_follower_on_same_lane_only():
    sim = Sim({"lead": 250.0, ME: 250.0, "other": 250.0}, gap_m=10.0)
    sim.mode.set_lane("other", 2)
    sim.run(1.0)
    sim.give("lead", "bottle")
    assert sim.mode.use("lead")
    sim.run(5.0)
    assert sim.mode.racers[ME].received == {"bottle": 1}
    assert sim.mode.racers["other"].received == {}
    msgs = sim.mode.due_results(sim.t + 10)
    assert msgs and msgs[0]["type"] == "gp_hit" and msgs[0]["target"] == ME and msgs[0]["by"] == "lead"
    assert msgs[0]["loss_s"] == pytest.approx(3.9, rel=0.10)            # perte estimée, en secondes
    assert len(sim.mode.due_results(sim.t + 11)) == 1 and len(sim.mode.due_results(sim.t + 12)) == 1
    assert sim.mode.due_results(sim.t + 13) == []                         # répété 3 fois
    assert sim.mode.summary()["lost_s"]["bottle"] > 0
    assert sim.mode.summary("lead")["launched"] == {"bottle": 1}


def test_musette_hits_first_runner_ahead_on_lane():
    sim = Sim({"a": 250.0, "b": 250.0, ME: 250.0}, gap_m=20.0)
    sim.run(0.5)
    sim.give(ME, "musette")
    assert sim.mode.use(ME)
    sim.run(5.0)
    assert sim.mode.racers["b"].received == {"musette": 1}
    assert sim.mode.racers["a"].received == {}


def test_homing_follows_lane_and_is_parried_by_shield():
    sim = Sim({"a": 250.0, ME: 250.0}, gap_m=30.0)
    sim.run(0.5)
    sim.give(ME, "homing")
    assert sim.mode.use(ME)
    sim.mode.set_lane("a", 2)
    sim.run(5.0)
    assert sim.mode.racers["a"].received == {"homing": 1}
    sim2 = Sim({"a": 250.0, ME: 250.0}, gap_m=30.0)
    sim2.run(0.5)
    sim2.give(ME, "homing")
    sim2.give("a", "bottle_x3")
    assert sim2.mode.use(ME)
    sim2.run(5.0)
    assert sim2.mode.racers["a"].received == {} and sim2.mode.racers["a"].charges == 2


def test_hit_grace_2_s():
    sim = Sim({"a": 250.0, ME: 250.0}, gap_m=10.0)
    sim.run(1.0)
    sim.give("a", "bottle_x3")
    assert sim.mode.use("a")
    sim.run(1.0)
    assert sim.mode.use("a")       # second bidon : touché moins de 2 s après le premier
    sim.run(3.0)
    me = sim.mode.racers[ME]
    assert me.received == {"bottle": 1} or me.received == {"bottle_x3": 1}
    assert me.dodged == 1
    assert HIT_GRACE_S == 2.0


def test_storm_hits_leader_and_splash_and_one_in_flight():
    sim = Sim({"lead": 250.0, "near": 250.0, "mid": 250.0, ME: 250.0}, gap_m=8.0)
    sim.run(1.0)
    sim.give(ME, "storm")
    assert sim.mode.use(ME)
    assert sim.mode._storm_flying()
    sim.run(2.0)
    frame_lead = sim.mode.frame("lead")
    assert frame_lead["warn"] is None or frame_lead["warn"][0] == "storm"
    sim.run(5.0)
    assert sim.mode.racers["lead"].received == {"storm": 1}
    assert sim.mode.racers["near"].received == {"storm": 1}       # à 8 m du premier : glissade
    assert sim.mode.racers["mid"].received == {}                    # à 16 m : rien
    assert not sim.mode._storm_flying()


def test_bell_chases_storm_and_clears_objects():
    sim = Sim({"lead": 250.0, ME: 250.0}, gap_m=30.0)
    sim.run(1.0)
    sim.give(ME, "storm")
    sim.give("lead", "bell")
    assert sim.mode.use(ME)
    while not sim.mode.bursts:
        sim.step()
    assert sim.mode.frame("lead")["warn"][0] == "storm"
    assert sim.mode.use("lead")
    sim.run(3.0)
    assert sim.mode.racers["lead"].received == {} and sim.mode.racers["lead"].dodged == 1


def test_star_immune_floor_and_touch():
    sim = Sim({ME: 250.0, "b": 250.0}, gap_m=1.0)
    sim.give(ME, "star")
    assert sim.mode.use(ME)
    sim.step()
    assert sim.phys[ME].v >= 1.2 * V_EQ - 1e-6
    assert sim.mode.racers["b"].received == {"star": 1}             # frôlé sur la même voie
    assert sim.mode.frame()["fx"] == [["star", 8.0]] or sim.mode.frame()["fx"][0][0] == "star"
    assert sim.mode.bot_frame(ME) == {"item": None, "fx": ["star"]}
    sim.run(8.0)
    assert not sim.mode.frame()["fx"]


def test_headwind_slows_all_ahead_without_grade():
    sim = Sim({"a": 250.0, "b": 250.0, ME: 250.0}, gap_m=20.0)
    sim.give(ME, "headwind")
    assert sim.mode.use(ME)
    assert sim.mode.wind_mps("a") == pytest.approx(5.0) and sim.mode.wind_mps("b") == pytest.approx(5.0)
    assert sim.mode.wind_mps(ME) == 0.0
    sim.run(6.1)
    assert sim.mode.wind_mps("a") == 0.0


def test_team_car_fixed_speed_and_stealth_steals():
    sim = Sim({ME: 250.0, "b": 250.0})
    sim.give(ME, "team_car")
    assert sim.mode.use(ME)
    sim.run(1.0)
    assert sim.phys[ME].v == pytest.approx(1.5 * V_EQ, rel=1e-6)
    sim2 = Sim({"a": 250.0, ME: 250.0}, gap_m=20.0)
    sim2.give(ME, "stealth")
    sim2.give("a", "star")
    assert sim2.mode.use(ME)
    assert sim2.mode.racers[ME].held == "star" and sim2.mode.racers["a"].held is None
    assert sim2.mode.frame()["fx"] == [["stealth", 10.0]]


def test_pause_freezes_and_grace_after_resume():
    sim = Sim({"a": 250.0, ME: 250.0}, gap_m=10.0)
    sim.run(1.0)
    sim.give("a", "bottle")
    assert sim.mode.use("a")
    n = len(sim.mode.objects)
    obj_s = [o.s for o in sim.mode.objects]
    sim.run(5.0, paused=True)
    assert len(sim.mode.objects) == n and [o.s for o in sim.mode.objects] == obj_s
    sim.run(RESUME_GRACE_S - 0.1)
    assert sim.mode.racers[ME].received == {}                       # touché dans les 3 s : rien


def test_boxes_give_item_after_roulette():
    sim = Sim({ME: 250.0, "b": 250.0}, length_m=3000.0)
    sim.run(500.0 / V_EQ + 0.5)
    me = sim.mode.racers[ME]
    assert me.roll is not None and me.held is None and sim.mode.frame()["roll_s"] > 0
    sim.run(2.0)
    assert me.held is not None and me.roll is None


def test_lane_change_and_auto():
    sim = Sim({ME: 250.0, "b": 250.0})
    assert lane_index(None) == 1 and lane_index(1.2) == 1 and lane_index(2.1) == 2 and lane_index(0.5) == 0
    assert sim.mode.set_lane(ME, 0) and not sim.mode.set_lane(ME, 3) and not sim.mode.set_lane(ME, True)
    sim.step()
    assert sim.mode.racers[ME].lane == 1 and sim.mode.frame()["lane"] == 0
    sim.run(0.6)
    assert sim.mode.racers[ME].lane == 0 and not sim.mode.frame()["auto"]
    sim.run(20.0)
    assert sim.mode.frame()["auto"]                                  # 20 s sans objet en vue
    assert sim.mode.set_lane(ME, 2) and sim.mode.set_lane(ME, None) and sim.mode.frame()["auto"]


def test_settings_refused():
    with pytest.raises(GrandPrixError):
        GrandPrixMode([ME, "b"], 5000.0, chaos="crazy")
    with pytest.raises(GrandPrixError):
        GrandPrixMode([ME, "b"], 5000.0, box_every_km=1.2)
    with pytest.raises(GrandPrixError):
        GrandPrixMode([ME, "b"], 5000.0, enabled=["banana"])
    with pytest.raises(GrandPrixError):
        GrandPrixMode(["a", "b"], 5000.0)


def test_no_function_returns_a_grade():
    """La pente envoyée ne dépend pas des objets : aucune fonction du paquet ne parle de pente."""
    for module in (mode, items, effects, boxes, draw, route_objects):
        for name, obj in inspect.getmembers(module):
            if inspect.isfunction(obj) or inspect.isclass(obj):
                if getattr(obj, "__module__", "") != module.__name__:
                    continue
                assert "grade" not in name.lower() and "feel" not in name.lower(), name
                members = inspect.getmembers(obj, inspect.isfunction) if inspect.isclass(obj) else []
                for mname, _ in members:
                    assert "grade" not in mname.lower() and "feel" not in mname.lower(), (name, mname)
    sim = Sim({ME: 250.0, "b": 250.0})
    assert not any("grade" in k for k in sim.mode.frame())


# --- course simulée -------------------------------------------------------------------------------

def simulated_race(n_bots: int, seed: int, laps: int = 0) -> tuple[list[str], int, int, dict]:
    rng = random.Random(seed)
    powers = {ME: 250.0}
    powers.update({f"bot-{i}": 230.0 + 40.0 * rng.random() for i in range(n_bots)})
    kw = {"lap_m": 2000.0} if laps else {}
    sim = Sim(powers, length_m=6000.0 if not laps else 2000.0 * laps, seed=seed, gap_m=2.7, **kw)
    worst, most = 0, 0
    dt = 0.1
    while not sim.mode.finished and sim.t < 2000:
        sim.step(dt)
        for rid, r in sim.mode.racers.items():
            if r.held and rng.random() < 0.05:
                sim.mode.use(rid)
            if rid != ME and rng.random() < 0.01:
                sim.mode.set_lane(rid, rng.randrange(3))
        frame = sim.mode.frame()
        worst = max(worst, len(json.dumps(frame, separators=(",", ":"))))
        most = max(most, len(sim.mode.objects))
    order = [r.id for r in sim.mode.order()]
    return order, worst, most, sim.mode.summary()


@pytest.mark.parametrize("n_bots", [4, 11])
def test_simulated_race(n_bots):
    order, worst, most, summary = simulated_race(n_bots, seed=3)
    assert len(order) == n_bots + 1
    assert worst < 500, worst
    assert most <= route_objects.MAX_OBJECTS
    assert summary["of"] == n_bots + 1 and summary["distance_km"] == 6.0
    assert sum(summary["launched"].values()) > 0
    again = simulated_race(n_bots, seed=3)
    assert again == (order, worst, most, summary)


def test_circuit_frame_has_laps():
    order, worst, most, summary = simulated_race(4, seed=5, laps=3)
    assert summary["laps"] == 3 and worst < 500


def test_worst_frame_under_520_bytes():
    """Pire trame `gp` (avec `pick` du lot GP2) d'une course de 30 km (plan §2.1) : 12 objets aux identifiants à 2 chiffres, menace,
    deux objets en effet (le Furtif vole une Voiture d'équipe et l'utilise), deux rangées, tours."""
    m = GrandPrixMode([ME] + [f"bot-{i}" for i in range(11)], 30_000.0, lap_m=6_000.0)
    me = m.racers[ME]
    me.s = 29_000.0
    me.held, me.charges, me.auto = "musette_x3", 3, False
    m.objects._next_id = 90
    for i in range(12):
        m.objects.add("musette_x3" if i % 2 else "homing", 29_100.0 + i * 1.123, 2, 0.0, 60.0, target=ME)
    me.fx = [effects.Active(e, 9.9, item, ME) for item in ("team_car", "stealth")
             for e in DEFAULT_ITEMS[item].self_fx]
    m.boxes = BoxRows([29_142.857, 29_285.714])
    frame = m.frame()
    assert len(frame["obj"]) == 12 and frame["warn"] and frame["lap"] == [5, 5]
    assert {o[1] for o in frame["obj"]} == {"musette", "homing"}          # objet dessiné, jamais « _x3 »
    assert frame["pick"] is True
    assert len(json.dumps(frame, separators=(",", ":"))) < 520


def test_object_ids_cycle_below_100():
    ro = RouteObjects()
    ro._next_id = 98
    a, b, c = (ro.add("bottle", 0.0, 1, 0.0, 90.0) for _ in range(3))
    assert (a.id, b.id, c.id) == (98, 99, 1)
    ro._next_id = 98
    assert ro.add("bottle", 0.0, 1, 0.0, 90.0).id == 2               # 98, 99 et 1 encore sur la route
