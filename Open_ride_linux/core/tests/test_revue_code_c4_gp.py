"""Revue de code, vague 2, lot C4 (constats C4-06, C4-07 et C4-08) : Grand Prix des objets.

- C4-06 : le bilan compte une esquive par coureur frôlé et par super-forme, pas une par pas au contact ;
- C4-07 : l'éclaboussure du nuage d'orage épargne son lanceur (décision du propriétaire du 27/11) ;
- C4-08 : en tête, Z dissipe le nuage d'orage (réserve vidée) ; un bot en tête le dissipe avant une rangée de boîtes.
"""

from __future__ import annotations

from test_grandprix import Sim

from openride_core.grandprix.mode import ME


def test_star_touch_counts_one_hit_or_one_dodge_per_rider():
    sim = Sim({ME: 250.0, "b": 250.0}, gap_m=1.0)
    sim.give("b", "star")
    assert sim.mode.use("b")
    sim.run(6.0)                                           # 6 s au contact, sur la même voie
    me = sim.mode.racers[ME]
    assert me.received == {"star": 1} and me.dodged == 0
    # cible invincible : une esquive, pas une par pas
    sim2 = Sim({ME: 250.0, "b": 250.0}, gap_m=1.0)
    sim2.give(ME, "star")
    assert sim2.mode.use(ME)
    sim2.give("b", "star")
    assert sim2.mode.use("b")
    sim2.run(6.0)
    assert sim2.mode.racers[ME].received == {} and sim2.mode.racers[ME].dodged == 1


def test_storm_held_in_the_lead_is_dissipated():
    sim = Sim({ME: 250.0, "b": 250.0}, gap_m=10.0)          # le cycliste mène
    sim.run(0.5)
    sim.give(ME, "storm")
    assert sim.mode.use(ME)
    me = sim.mode.racers[ME]
    assert me.held is None and me.launched == {} and not sim.mode.objects and not sim.mode.bursts
    assert any(ln["event"] == "discard" and ln["item"] == "storm" for ln in sim.mode.take_journal())
    assert sim.mode.frame()["held"] is None                  # la réserve vide se voit au HUD
    # derrière, le nuage part toujours sur le premier
    sim2 = Sim({"b": 250.0, ME: 250.0}, gap_m=10.0)
    sim2.run(0.5)
    sim2.give(ME, "storm")
    assert sim2.mode.use(ME) and sim2.mode.racers[ME].launched == {"storm": 1}


def test_bot_in_the_lead_dissipates_its_storm_before_boxes():
    from openride_core.grandprix.brain import wants
    sim = Sim({"b": 250.0, ME: 250.0}, gap_m=10.0)
    sim.run(0.5)
    b = sim.mode.racers["b"]
    spec = sim.mode.table.items["storm"]
    sim.give("b", "storm")
    row = sim.mode.boxes.rows[0]
    b.s = row - 500.0
    assert not wants(sim.mode, b, spec)                      # pas de rangée proche : garde
    b.s = row - 50.0
    assert wants(sim.mode, b, spec)                          # rangée dans 50 m : le dissiper pour reprendre


def test_storm_splash_spares_the_thrower():
    """C4-07 : lanceur à 6 m du premier, dans le rayon de l'éclaboussure : seul le premier et l'autre voisin glissent."""
    sim = Sim({"lead": 250.0, ME: 250.0, "near": 250.0}, gap_m=6.0)
    sim.run(1.0)
    sim.give(ME, "storm")
    assert sim.mode.use(ME)
    sim.run(8.0)
    assert sim.mode.racers["lead"].received == {"storm": 1}
    assert sim.mode.racers["near"].received == {"storm": 1}        # à 12 m du premier : éclaboussé
    assert sim.mode.racers[ME].received == {}                       # lanceur à 6 m : épargné
