"""Séances scriptées du filet « à l'identique » (lot IM0) : une fonction par cas du cadrage (§5.2).

Chaque scénario reçoit `make(configure=None, routes=None)`, qui rend un `identique.Banc` neuf, et rend la liste des
bancs joués (un seul, sauf la reprise après plantage). Les scénarios ne lisent rien hors de leur dossier de travail.
La ligue d'hiver (cas 8 du cadrage) viendra avec le lot IM8 : rien ici ne touche à la ligue ni au profil réel.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from identique import POWER_W, Banc

LOOP_ID = "anneau"
LOOP_M = 1000.0


def prepare_routes(routes: Path) -> None:
    """Parcours des scénarios : « Col du lacet » (`demo`, écrit par le core), une boucle de 1 km et le vélodrome."""
    from openride_core import velodrome
    from openride_core.demo_world import write_world
    from openride_core.tools.route_vectors import _route

    routes.mkdir(parents=True, exist_ok=True)
    n = int(LOOP_M / 10.0) + 1
    headings = [i * 360.0 / (n - 1) for i in range(n)]
    alts = [100.0 + 6.0 * (1.0 - abs(2.0 * i / (n - 1) - 1.0)) for i in range(n)]
    world = write_world(routes, LOOP_ID, LOOP_M, created="2026-01-01T00:00:00+00:00")
    (world / "route.json").write_text(json.dumps(_route(headings, alts, ds=10.0, last=10.0, kind="loop")),
                                      encoding="utf-8")
    velodrome.write_velodrome(routes)


Make = Callable[..., Banc]


# --- 1. session libre ------------------------------------------------------------------------------------

def libre(make: Make) -> list[Banc]:
    """3 bots, braquets, bonus (Z), une pause, un changement de bots, un demi-tour à l'arrêt et en roulant."""
    b = make()
    b.cmd("select_route", {"route_id": "demo"})
    b.cmd("start", {"bots": [{"kind": "profile", "profile": "climber"}, {"kind": "constant", "power_w": 230},
                             {"kind": "profile", "profile": "sprinter", "level_pct": 90}]})
    b.run(40)
    b.press("PLUS_SHORT")
    b.press("PLUS_LONG")
    b.run(20)
    b.press("MINUS_SHORT")
    b.press("Z_SHORT")
    b.run(30, power_w=320.0)
    b.cmd("pause")
    b.run(2)
    b.cmd("set_bots", {"bots": [{"kind": "profile", "profile": "climber"}, {"kind": "constant", "power_w": 260}]})
    b.cmd("u_turn")
    b.cmd("resume")
    b.run(30, power_w=POWER_W)
    b.press("Y_LONG")
    b.run(20)
    b.cmd("end_session", {"save": True})
    return [b]


# --- 2. Course ------------------------------------------------------------------------------------------

def course(make: Make) -> list[Banc]:
    """Course sur une boucle : 3 tours, 7 adversaires, jusqu'à l'arrivée, cote Elo écrite."""
    def cfg(c: Any) -> None:
        c.race.opponents, c.race.laps = 7, 3

    b = make(cfg)
    b.cmd("select_route", {"route_id": LOOP_ID})
    b.cmd("start", {"mode": "race"})
    b.run(60)
    b.press("Z_SHORT")
    b.run(600, power_w=270.0)
    return [b]


# --- 3. Grand Prix des objets --------------------------------------------------------------------------

def grandprix(make: Make) -> list[Banc]:
    """Objets (Z), voies (A, flèches), voitures d'équipe, pause de 3 s, jusqu'à l'arrivée."""
    def cfg(c: Any) -> None:
        c.grandprix.opponents, c.grandprix.laps = 4, 2

    b = make(cfg)
    b.cmd("select_route", {"route_id": LOOP_ID})
    b.cmd("start", {"mode": "grandprix"})
    for i in range(8):
        b.run(15)
        b.press("Z_SHORT")
        b.press(("A_SHORT", "LEFT_SHORT", "RIGHT_SHORT", "UP_SHORT")[i % 4])
        if i == 3:
            b.cmd("pause")
            b.run(3)
            b.cmd("resume")
    b.run(400)
    return [b]


# --- 4. Dernier survivant --------------------------------------------------------------------------------

def _survivor(after_out: str) -> Callable[[Make], list[Banc]]:
    def scenario(make: Make) -> list[Banc]:
        def cfg(c: Any) -> None:
            c.survivor.opponents, c.survivor.spacing_km, c.survivor.after_out = 3, 1, after_out

        b = make(cfg)
        b.cmd("select_route", {"route_id": "demo"})
        b.cmd("start", {"mode": "survivor"})
        b.run(60)
        b.run(600, power_w=150.0)   # le cycliste faiblit : éliminé à une arche
        if b.s.state.session_state in ("RUNNING", "PAUSED"):
            b.cmd("end_session", {"save": True})
        return [b]

    scenario.__doc__ = f"Jusqu'à l'élimination du cycliste, réglage « {after_out} »."
    return scenario


survivant_continuer = _survivor("ride")
survivant_terminer = _survivor("end")


# --- 5. WTF ---------------------------------------------------------------------------------------------

def wtf(make: Make) -> list[Banc]:
    """Au moins quatre règles jouées, un plat du chef refusé (Z court), un Z hors événement, un refus d'ERG."""
    b = make()
    b.cmd("select_route", {"route_id": "demo"})
    b.cmd("start", {"mode": "wtf"})
    b.run(10)
    b.press("Z_SHORT")                          # aucun événement : Z garde son rôle de la séance
    for _ in range(8):
        b.run(150, until=lambda s: s.wtf is not None and s.wtf.event is not None)
        b.run(6)                                # chef : 4 s d'arrivée, puis 5 s pour refuser le plat
        b.press("Z_SHORT")                      # refuse le plat du chef ; sans effet sur les autres règles
        b.run(150, until=lambda s: s.wtf is not None and s.wtf.event is None)
    b.cmd("set_ride_mode", {"mode": "erg"})     # refusé : SIM seulement
    b.run(10)
    b.cmd("end_session", {"save": True})
    return [b]


# --- 6. Piste -------------------------------------------------------------------------------------------

def _track(event: dict, seconds: float, ride_mode: dict | None = None) -> Callable[[Make], list[Banc]]:
    def scenario(make: Make) -> list[Banc]:
        b = make()
        b.s.driver.base_power_w = 400.0
        b.cmd("select_route", {"route_id": "velodrome-250"})
        b.cmd("start", {"mode": "track", "track": event})
        b.run(20)
        if ride_mode is not None:
            b.cmd("set_ride_mode", ride_mode)
        b.run(seconds, until=lambda s: s.track_event is not None and s.track_event.finished)
        b.run(3)
        b.cmd("end_session", {"save": True})
        return [b]

    scenario.__doc__ = f"Épreuve de piste {event}."
    return scenario


piste_scratch = _track({"event": "scratch", "opponents": 3, "laps": 10}, 400)
piste_poursuite = _track({"event": "pursuit", "opponents": 1, "distance_m": 3000}, 400)
piste_americaine = _track({"event": "madison", "opponents": 3, "laps": 20}, 600)
piste_libre_erg = _track({"event": "free", "opponents": 2}, 60, {"mode": "erg", "target_w": 220})


# --- 7. Cyber-Rogue --------------------------------------------------------------------------------------

def _rogue_follow(b: Banc, ratio: float, z_every: int = 0) -> Callable[[Any], None]:
    """Cycliste qui suit la cible de la salle à `ratio` près ; Z court tous les `z_every` pas en salle."""
    from openride_core.rogue.combat import target_at

    def follow(s: Any) -> None:
        rg = s.rogue
        if rg is not None and rg.in_fight:
            s.driver.base_power_w = target_at(rg.engine.room, s.physics.s) * POWER_W * ratio
            if z_every and b.step_no[0] % z_every == 0:
                b.press("Z_SHORT")
        else:
            s.driver.base_power_w = 0.6 * POWER_W

    return follow


def rogue_gagnee(make: Make) -> list[Banc]:
    """Run courte gagnée (boss battu) en suivant la cible des salles, Z appuyé en salle."""
    b = make()
    b.cmd("start_run", {"objective": "threshold", "duration_min": 30, "seed": 5})
    b.cmd("start", {})
    b.run(40 * 60, dt=0.5, each=_rogue_follow(b, 1.15, z_every=20))
    return [b]


def rogue_perdue(make: Make) -> list[Banc]:
    """Run où le cycliste reste sous la cible : une vie perdue, fin de run."""
    b = make()
    b.cmd("start_run", {"objective": "vo2max", "duration_min": 30, "seed": 3})
    b.cmd("start", {})
    b.run(40 * 60, dt=0.5, each=_rogue_follow(b, 0.5))
    return [b]


def rogue_reprise(make: Make) -> list[Banc]:
    """Run interrompue (plantage du core simulé), reprise depuis le journal par un core neuf."""
    a = make()
    a.cmd("start_run", {"objective": "threshold", "duration_min": 30, "seed": 7})
    a.cmd("start", {})
    a.run(6 * 60, dt=0.5, each=_rogue_follow(a, 1.0))
    journal = a.s._rec.path if a.s._rec is not None else None
    b = make(continue_from=a)
    if journal is not None:
        b.s.resume_session(Path(journal))
        b.cmd("resume")
        b.run(4 * 60, dt=0.5, each=_rogue_follow(b, 1.0))
        b.cmd("end_session", {"save": True})
    return [a, b]


# --- 9. Refus -------------------------------------------------------------------------------------------

def refus(make: Make) -> list[Banc]:
    """Chaque refus de `start`, `set_ride_mode`, `set_bots` et `u_turn`, par mode, avec son texte."""
    def cfg(c: Any) -> None:
        c.survivor.opponents, c.survivor.spacing_km = 2, 1   # 2 km de course : tient sur le « Col du lacet »

    b = make(cfg)
    b.cmd("start", {"mode": "turbo"})                                     # avant tout parcours : ignoré
    b.cmd("select_route", {"route_id": "demo"})
    for args in ({"mode": "turbo"}, {"mode": "race", "objective": "dodo"},
                 {"mode": "track", "track": {"event": "kilo"}},          # pas un vélodrome
                 {"bots": [{"kind": "constant", "power_w": -5}]}, {"bots": [{"kind": "ghost"}]},
                 {"bots": "trois"}):
        b.cmd("start", args)
    b.cmd("set_ride_mode", {"mode": "erg"})                              # hors séance
    b.cmd("u_turn")
    b.cmd("set_bots", {"bots": []})
    for mode, route in (("ride", "demo"), ("wtf", "demo"), ("survivor", "demo"), ("grandprix", LOOP_ID),
                        ("race", LOOP_ID)):
        b.cmd("select_route", {"route_id": route})
        b.cmd("start", {"mode": mode})
        b.run(3)
        b.cmd("u_turn")                                                  # en roulant
        b.cmd("set_bots", {"bots": [{"kind": "constant", "power_w": 200}]})
        for ride in ({"mode": "erg"}, {"mode": "cadence"}, {"mode": "velo"}, {"mode": "erg", "target_w": True}):
            b.cmd("set_ride_mode", ride)
        b.cmd("pause")
        b.cmd("set_bots", {"bots": [{"kind": "constant", "power_w": 200}]})
        b.cmd("u_turn")
        b.cmd("set_ride_mode", {"mode": "sim"})
        b.cmd("end_session", {"save": False})
    b.cmd("select_route", {"route_id": "velodrome-250"})
    for args in ({"mode": "ride"}, {"mode": "track"}, {"mode": "track", "track": {"event": "nage"}},
                 {"mode": "track", "track": {"event": "pursuit", "opponents": 4}},
                 {"mode": "track", "track": {"event": "scratch", "opponents": 3}, "bots": []},
                 {"mode": "track", "track": {"event": "scratch", "opponents": 3, "laps": 11}}):
        b.cmd("start", args)
        if b.s.state.session_state != "READY":
            b.cmd("end_session", {"save": False})
            b.cmd("select_route", {"route_id": "velodrome-250"})
    b.cmd("start", {"mode": "track", "track": {"event": "scratch", "opponents": 3, "laps": 10}})
    b.run(3)
    b.cmd("set_ride_mode", {"mode": "erg"})
    b.cmd("pause")
    b.cmd("set_bots", {"bots": []})
    b.cmd("u_turn")
    b.cmd("end_session", {"save": False})
    b.cmd("select_route", {"route_id": "demo"})
    b.cmd("start", {"mode": "survivor", "bots": []})
    return [b]


# --- 10. Fin forcée -------------------------------------------------------------------------------------

def fin_sans_enregistrer(make: Make) -> list[Banc]:
    """`end_session` sans enregistrement, au milieu d'une Course."""
    b = make()
    b.cmd("select_route", {"route_id": LOOP_ID})
    b.cmd("start", {"mode": "race"})
    b.run(45)
    b.cmd("end_session", {"save": False})
    return [b]


def fin_arret_du_core(make: Make) -> list[Banc]:
    """Arrêt du core en pleine séance de Grand Prix : la séance est enregistrée (`_shutdown`)."""
    b = make()
    b.cmd("select_route", {"route_id": LOOP_ID})
    b.cmd("start", {"mode": "grandprix"})
    b.run(45)
    b.s._finish(True)
    return [b]


def fin_trainer_refuse(make: Make) -> list[Banc]:
    """Le trainer refuse la prise de contrôle pendant une séance libre avec bots (statut ERROR du pilote)."""
    b = make()
    b.cmd("select_route", {"route_id": "demo"})
    b.cmd("start", {"bots": [{"kind": "profile", "profile": "rouleur"}]})
    b.run(20)
    b.s.driver.status = "CONTROL_REFUSED"
    b.s.driver.connected = False
    b.run(10)
    b.s.driver.status = "MOCK"
    b.s.driver.connected = True
    b.run(10)
    b.cmd("end_session", {"save": True})
    return [b]


SCENARIOS: dict[str, Callable[[Make], list[Banc]]] = {
    "libre": libre,
    "course": course,
    "grandprix": grandprix,
    "survivant_continuer": survivant_continuer,
    "survivant_terminer": survivant_terminer,
    "wtf": wtf,
    "piste_scratch": piste_scratch,
    "piste_poursuite": piste_poursuite,
    "piste_americaine": piste_americaine,
    "piste_libre_erg": piste_libre_erg,
    "rogue_gagnee": rogue_gagnee,
    "rogue_perdue": rogue_perdue,
    "rogue_reprise": rogue_reprise,
    "refus": refus,
    "fin_sans_enregistrer": fin_sans_enregistrer,
    "fin_arret_du_core": fin_arret_du_core,
    "fin_trainer_refuse": fin_trainer_refuse,
}
