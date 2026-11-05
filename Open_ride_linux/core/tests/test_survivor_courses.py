"""Série DS : courses du « Dernier survivant » simulées de bout en bout, sans vélo (demande du propriétaire du
3 novembre : réduire l'essai vélo à une validation du ressenti).

Faux trainer à puissance fixe (MockDriver), séance complète par les commandes de l'engine (`start` avec `mode`
= `survivor`, `pause`, `resume`, `end_session`), trame `state` et messages validés par les schémas du contrat.
Cas : courses à 2 puis à 4 adversaires (une seule élimination par arche, place juste au bilan, aucune erreur au
journal), cycliste faible éliminé qui continue à rouler puis fin et bilan propres (et réglage « terminer la
séance »), cycliste fort vainqueur, parcours fini avant la fin de la course, pause pendant le passage d'une arche, perte du trainer en course, braquets
au Click en course."""

import json
import logging

import pytest

from openride_core.session import CoreSession
from openride_core.zwift_click import InputEvent
from test_survivor_session import DT, STATE_LIMIT_BYTES, env, validator  # noqa: F401  (fixture partagée)


def _frame(s: CoreSession) -> dict:
    s.state.bots = [b.to_dict() for b in s.bots] or None
    s._fill_race_frame()
    s._fill_survivor_frame()
    return s.state.to_dict()


class Course:
    """Course pilotée pas à pas : trames vérifiées, éliminations relevées."""

    def __init__(self, s: CoreSession, sent: list, run_wall: list) -> None:
        self.s, self.sent, self.wall = s, sent, run_wall
        self.frames: list[dict] = []
        self.names = {rid: r.name for rid, r in s.survivor.racers.items()}
        self.state_v = validator("state")
        self.contacts: list[str] = []

    def _count_contacts(self) -> None:
        """Contacts comme le banc les compte (living_decor.gd, lot P32) : roues qui se chevauchent (moins de 1,7 m, longueur d'un vélo du core,
        le long de la route) et moins de 2 × 0,3 m d'écart latéral, bots entre eux et cycliste."""
        riders = [("cycliste", self.s.physics.s, self.s._lane.m)]
        riders += [(b.name, b.s, b.lane.m) for b in self.s.bots if getattr(b, "lane", None) is not None]
        for i, (na, sa, la) in enumerate(riders):
            for nb, sb, lb in riders[i + 1:]:
                if abs(sa - sb) < 1.7 and abs(la - lb) < 0.6:
                    self.contacts.append(f"{na} / {nb} à s={sa:.0f} m, ds={sa - sb:.2f} ({la:.2f} et {lb:.2f} m)")

    def step(self, seconds: float, every: int = 15) -> None:
        for i in range(int(round(seconds / DT))):
            if self.s.state.session_state not in ("RUNNING", "PAUSED"):
                return
            self.wall[0] += DT
            self.s._step(DT, self.wall[0])
            self._count_contacts()
            if i % every == 0 and self.s.state.session_state in ("RUNNING", "PAUSED"):
                d = _frame(self.s)
                self.state_v.validate(d)
                assert len(json.dumps(d, ensure_ascii=False).encode()) < STATE_LIMIT_BYTES
                if d.get("survivor"):
                    self.frames.append(d["survivor"])

    def until(self, cond, limit_s: float = 1200.0) -> bool:
        """Roule jusqu'à `cond` (vérifiée chaque seconde), la fin de la séance ou `limit_s`."""
        t = 0.0
        while t < limit_s and self.s.state.session_state in ("RUNNING", "PAUSED"):
            if cond(self.s):
                return True
            self.step(1.0)
            t += 1.0
        return cond(self.s)

    def eliminations(self) -> list[tuple[int, str]]:
        """(arche, coureur) des messages `elimination`, sans les répétitions."""
        out: list[tuple[int, str]] = []
        for m in self.sent:
            if m.get("type") == "elimination" and (m["arch"], m["rider"]) not in out:
                out.append((m["arch"], m["rider"]))
        return out


@pytest.fixture
def course(env, monkeypatch):
    make, run, tmp_path = env
    import time as time_mod
    wall = [time_mod.time()]

    def start(port: int, **kw) -> Course:
        s, sent, errors = make(port, **kw)
        s._on_command("start", {"mode": "survivor"}, 2)
        assert not errors and s.state.session_state == "RUNNING", errors
        monkeypatch.setattr(time_mod, "time", lambda: wall[0])
        c = Course(s, sent, wall)
        c.errors = errors
        return c

    return start


def _check_bilan(c: Course, opponents: int) -> dict:
    summary = c.s.state.summary["survivor"]
    elim = c.eliminations()
    assert [a for a, _ in elim] == list(range(1, opponents + 1)), "une seule élimination par arche, dans l'ordre"
    assert summary["of"] == opponents + 1 and summary["arches"] == opponents
    assert [e[0] for e in summary["eliminated"]] == list(range(1, opponents + 1))
    assert [e[1] for e in summary["eliminated"]] == [r for _, r in elim]
    winner = summary["winner"]
    assert winner is not None and winner not in [r for _, r in elim]
    assert summary["winner_name"] == c.names[winner][:16]
    me_out = next((a for a, r in elim if r == "me"), None)
    assert summary["place"] == (1 if me_out is None else opponents + 2 - me_out)
    for m in c.sent:
        if m.get("type") == "elimination":
            validator("elimination").validate(m)
    sends = [(m["arch"], m["rider"]) for m in c.sent if m.get("type") == "elimination"]
    assert all(1 <= sends.count(e) <= 3 for e in elim), "chaque élimination envoyée, 3 fois au plus"
    return summary


@pytest.mark.parametrize("opponents,spacing_km,port", [(2, 2, 6800), (4, 1, 6810)])
def test_full_race_one_elimination_per_arch(course, caplog, opponents, spacing_km, port):
    caplog.set_level(logging.WARNING, logger="core")
    c = course(port, power_w=230.0, opponents=opponents, spacing_km=spacing_km, level_pct=100)
    assert len(c.s.bots) == opponents
    c.until(lambda s: s.survivor.winner is not None)
    c.step(2.0)
    assert c.s.survivor.winner is not None
    alive_counts = [len(f["alive"]) for f in c.frames]
    assert alive_counts == sorted(alive_counts, reverse=True), "le plateau ne fait que diminuer"
    assert all(1 <= f["arch"] <= opponents for f in c.frames)
    assert not c.contacts, c.contacts[:5]   # banc du 3 novembre : éliminé rangé sur l'accotement, évité
    c.s._on_command("end_session", {"save": True}, 9)
    _check_bilan(c, opponents)
    errors = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert not errors, [r.getMessage() for r in errors]
    assert not c.errors


@pytest.mark.parametrize("quality_port", [6890])
def test_capture_scenario_is_decided_and_without_contacts(course, quality_port):
    """Scénario des captures (captures_ds) : ~195 W contre 2 bots à 74 % ± 8 % d'une FTP de 250 W (205 et
    165 W), une arche par km : le Rouleur sort à l'arche 1, le cycliste à l'arche 2, sans aucun contact depuis
    le départ ; le Grimpeur reste assez près pour être à l'écran avant la première arche."""
    c = course(quality_port, power_w=195.0, opponents=2, spacing_km=1, level_pct=74, spread="normal")
    grimpeur = next(b for b in c.s.bots if b.id == "bot1")
    c.until(lambda s: s._t_session >= 8.0)   # capture « peloton » : Grimpeur juste devant, à droite du cycliste
    print("Grimpeur à 8 s :", round(grimpeur.s - c.s.physics.s, 1), "m")
    assert 2.0 < grimpeur.s - c.s.physics.s < 10.0 and grimpeur.lane.m - c.s._lane.m > 0.6
    c.until(lambda s: s.physics.s >= 850.0)
    gap = grimpeur.s - c.s.physics.s
    print("écart du Grimpeur à 850 m :", round(gap, 1))
    assert 0.0 < gap < 80.0, gap
    c.until(lambda s: s.survivor.winner is not None)
    c.s._on_command("end_session", {"save": True}, 9)
    summary = _check_bilan(c, 2)
    print("éliminations :", summary["eliminated"])
    assert [r for _, r in c.eliminations()] == ["bot2", "me"] and summary["place"] == 2
    assert not c.contacts, c.contacts[:5]


def test_weak_rider_out_keeps_riding_then_clean_end(course):
    c = course(6820, power_w=100.0, opponents=2, spacing_km=2, level_pct=120)
    assert c.until(lambda s: s.survivor.racers["me"].out_arch is not None)
    assert c.s.survivor.racers["me"].out_arch == 1 and c.s.state.session_state == "RUNNING"
    c.step(3.0)
    assert c.frames[-1]["me_out"] == 1 and c.frames[-1]["d_m"] is None and "me" not in c.frames[-1]["alive"]
    c.until(lambda s: s.survivor.winner is not None)   # la course se finit entre les bots
    assert c.s.survivor.winner in ("bot1", "bot2") and c.s.state.session_state == "RUNNING"
    c.step(5.0)   # route libre ensuite
    c.s._on_command("end_session", {"save": True}, 9)
    assert c.s.state.session_state == "FINISHED"
    summary = _check_bilan(c, 2)
    assert summary["place"] == 3
    assert not c.contacts, c.contacts[:5]


def test_eliminated_bot_pulls_over_to_the_shoulder(course, caplog):
    """Bot éliminé : placement coupé, il glisse vers l'accotement (SURVIVOR_OUT_LANE_M) et le core le journalise."""
    from openride_core.session import SURVIVOR_OUT_LANE_M
    caplog.set_level(logging.INFO, logger="core")
    c = course(6880, power_w=260.0, opponents=2, spacing_km=1, level_pct=70)
    assert c.until(lambda s: bool(s._survivor_out))
    rid = next(iter(c.s._survivor_out))
    bot = next(b for b in c.s.bots if b.id == rid)
    assert not bot.lane.auto and bot.lane.home == SURVIVOR_OUT_LANE_M
    c.step(5.0)
    assert bot.lane.m > 2.6, bot.lane.m
    assert any("éliminé à l'arche 1" in r.getMessage() and bot.name in r.getMessage() for r in caplog.records)
    assert not c.contacts, c.contacts[:5]


def test_weak_rider_out_ends_session_with_end_setting(course):
    c = course(6830, power_w=100.0, opponents=2, spacing_km=2, level_pct=120, after_out="end")
    c.until(lambda s: s.state.session_state == "FINISHED", 900)
    assert c.s.state.session_state == "FINISHED"
    summary = c.s.state.summary["survivor"]
    assert summary["place"] == 3 and summary["eliminated"][-1][1] == "me"
    validator("state").validate(c.s.state.to_dict())


def test_strong_rider_wins(course):
    c = course(6840, power_w=420.0, opponents=2, spacing_km=1, level_pct=70)
    c.until(lambda s: s.survivor is None or s.survivor.winner is not None)
    assert c.s.survivor.winner == "me"
    assert all(len(f["alive"]) >= 1 and f["me_out"] is None for f in c.frames)
    c.s._on_command("end_session", {"save": True}, 9)
    summary = _check_bilan(c, 2)
    assert summary["place"] == 1 and summary["winner"] == "me" and summary["winner_name"]


def test_route_end_before_race_is_decided(course):
    """Cycliste très au-dessus des bots sur un parcours ouvert juste assez long : il arrive au bout du parcours
    avant que les bots n'aient départagé les dernières arches ; la séance finit proprement, place inconnue."""
    c = course(6845, power_w=420.0, opponents=4, spacing_km=1, level_pct=70)
    c.until(lambda s: s.state.session_state == "FINISHED", 1500)
    assert c.s.state.session_state == "FINISHED"
    summary = c.s.state.summary["survivor"]
    assert summary["place"] is None and summary["winner"] is None and summary["winner_name"] is None
    assert len(summary["eliminated"]) < 4
    validator("state").validate(c.s.state.to_dict())


def test_pause_during_arch_crossing_freezes_the_race(course):
    c = course(6850, power_w=230.0, opponents=2, spacing_km=2, level_pct=100)
    arch = c.s.survivor.arches[0]
    # pause dès que le premier coureur est à moins de 15 m de l'arche
    assert c.until(lambda s: max([b.s for b in s.bots] + [s.physics.s]) >= arch - 15.0)
    before = c.eliminations()
    c.s._on_command("pause", {}, 5)
    assert c.s.state.session_state == "PAUSED"
    pos = (c.s.physics.s, [b.s for b in c.s.bots], c.s._t_session)
    c.step(30.0)
    assert c.s.state.session_state == "PAUSED" and c.eliminations() == before, "pas d'élimination pendant une pause"
    assert (c.s.physics.s, [b.s for b in c.s.bots], c.s._t_session) == pos, "tout le monde figé"
    c.s._on_command("resume", {}, 6)
    assert c.s.state.session_state == "RUNNING"
    c.until(lambda s: s.survivor.winner is not None)
    c.s._on_command("end_session", {"save": True}, 9)
    _check_bilan(c, 2)


def test_trainer_lost_in_race_pauses_then_race_goes_on(course):
    c = course(6860, power_w=230.0, opponents=2, spacing_km=2, level_pct=100)
    c.step(60.0)
    before = c.eliminations()
    c.s.driver.simulate_disconnect()
    c.step(6.0)
    assert c.s.state.session_state == "PAUSED" and c.s.state.pause_reason == "trainer_lost"
    t = c.s._t_session
    c.step(20.0)
    assert c.s._t_session == t and c.eliminations() == before
    c.s.driver.simulate_reconnect()
    c.s._on_command("resume", {}, 6)
    assert c.s.state.session_state == "RUNNING"
    c.until(lambda s: s.survivor.winner is not None)
    c.s._on_command("end_session", {"save": True}, 9)
    _check_bilan(c, 2)


def test_gears_on_the_click_during_race(course):
    c = course(6870, power_w=230.0, opponents=2, spacing_km=2, level_pct=100)
    g0 = c.s.gearing.k
    c.s._handle_input(InputEvent.PLUS_SHORT)
    c.s._handle_input(InputEvent.PLUS_SHORT)
    assert c.s.gearing.k == g0 + 2 and c.s.state.gear == g0 + 2
    c.step(30.0)
    c.s._handle_input(InputEvent.MINUS_LONG)
    assert c.s.gearing.k < g0 + 2 and c.s.state.mode == "SIM", "les braquets restent sur + et − (SIM)"
    c.until(lambda s: s.survivor.winner is not None)
    c.s._on_command("end_session", {"save": True}, 9)
    _check_bilan(c, 2)


def test_contact_counter_uses_the_core_bike_length():
    """Le compteur de contacts des bancs (living_decor.gd) prend la longueur de vélo du placement AS2
    (draft.BIKE_LENGTH_M) : deux roues collées par le core ne sont pas un contact (banc du 3 novembre)."""
    import re
    from pathlib import Path

    from openride_core import draft

    gd = (Path(__file__).resolve().parents[2] / "engine" / "scripts" / "living_decor.gd").read_text(encoding="utf-8")
    m = re.search(r"^const CONTACT_BIKE_HALF_M := ([0-9.]+)", gd, re.M)
    assert m, "CONTACT_BIKE_HALF_M absente de living_decor.gd"
    assert float(m.group(1)) * 2.0 == pytest.approx(draft.BIKE_LENGTH_M)


def test_ahead_gap_and_watts_to_catch(course):
    """Coureur juste devant (essai du 4 novembre) : écart en secondes et puissance pour être à sa hauteur à
    l'arche ; en roulant à cette puissance, le cycliste rattrape bien le bot avant l'arche."""
    c = course(6900, power_w=195.0, opponents=2, spacing_km=1, level_pct=74, spread="normal")
    c.until(lambda s: s._t_session >= 60.0)
    ahead = c.frames[-1]["ahead"]
    assert ahead is not None and ahead["id"] == "bot1" and ahead["gap_s"] > 0
    need = ahead["catch_w"]
    assert need is not None and 195 < need < 600, need
    # à cette puissance, le cycliste reprend l'essentiel de l'écart avant l'arche ; pas tout, le calcul suppose
    # que le bot garde son allure du moment, et il accélère à l'approche de l'arche (sprint, lot DS3)
    c.s.driver.base_power_w = float(need)
    arch = c.s.survivor.arches[0]
    bot = next(b for b in c.s.bots if b.id == "bot1")
    gap0 = bot.s - c.s.physics.s
    c.until(lambda s: bot.s >= arch)
    assert bot.s - c.s.physics.s < 0.4 * gap0, (bot.s - c.s.physics.s, gap0)
    c.until(lambda s: s.survivor.winner is not None)
    assert c.frames[-1]["ahead"] is None or c.s.survivor.winner is not None
