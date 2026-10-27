"""Scénariste de run du Cyber-Rogue (lot R15).

`compose_run` compose échauffement, salles, couloirs à portes, boss et retour au calme à partir de
l'objectif et de la durée (décision Q6). `adapt_after_room` rattrape un joueur en retard : couloirs
raccourcis, puis une salle retirée (échec signalé). Modules purs, déterministes.
"""

from __future__ import annotations

import random
from dataclasses import replace

from .balance import DEFAULT_BALANCE, RogueBalance
from .run import Scenario, Step

DURATIONS = (30, 45, 60, 90)
OBJECTIVES = ("endurance", "threshold", "vo2max")


def _room_durations(rng: random.Random, n: int, mean_s: float, b: RogueBalance) -> list:
    """`n` durées de salle tirées autour de `mean_s`, dans 3 à 5 min, de somme n × mean_s."""
    u = [rng.uniform(-b.room_spread_s, b.room_spread_s) for _ in range(n)]
    shift = sum(u) / n
    d = [mean_s + x - shift for x in u]
    for _ in range(8):
        clamped = [min(max(x, b.room_min_s), b.room_max_s) for x in d]
        diff = n * mean_s - sum(clamped)
        free = [i for i, x in enumerate(clamped) if b.room_min_s < x < b.room_max_s]
        if abs(diff) < 1e-6 or not free:
            d = clamped
            break
        d = [x + (diff / len(free) if i in free else 0.0) for i, x in enumerate(clamped)]
    return [round(x, 1) for x in d]


def _door_layers(rng: random.Random, objective: str, layers: int, b: RogueBalance) -> tuple:
    """Archétype de la première salle et couples de portes de chaque couloir.

    Rotation des trois archétypes du réservoir : deux couples consécutifs partagent un seul archétype,
    trois couples consécutifs n'en partagent aucun, donc aucun chemin ne joue trois fois le même
    archétype de suite, quelles que soient les portes choisies.
    """
    pool = list(b.reservoirs[objective])
    rng.shuffle(pool)
    first = rng.choice((pool[0], pool[1]))           # jamais l'archétype commun aux deux premiers couples
    pairs = [(pool[k % 3], pool[(k + 1) % 3]) for k in range(1, layers + 1)]
    if objective == "threshold" and pairs:           # Sprinteur au plus une fois : il remplace une porte
        k = rng.randrange(len(pairs))
        a, c = pairs[k]
        pairs[k] = (a, b.sprinter_extra) if rng.random() < 0.5 else (b.sprinter_extra, c)
    return first, pairs


def compose_run(objective: str, duration_min: int, seed: int, rider=None,
                balance: RogueBalance = DEFAULT_BALANCE) -> Scenario:
    b = balance
    if objective not in OBJECTIVES:
        raise ValueError(f"objectif inconnu : {objective!r}")
    if duration_min not in b.calendars:
        raise ValueError(f"durée hors liste : {duration_min!r}")
    warm, n, mean_min, corr_min, boss_min, weights, cool = b.calendars[duration_min]
    rng = random.Random(f"{seed}|compose|{objective}|{duration_min}")
    durations = _room_durations(rng, n, mean_min * 60.0, b)
    first, pairs = _door_layers(rng, objective, n - 1, b)

    def spec(archetype: str, nominal: float) -> Step:
        return Step("room", nominal, archetype, "", objective)

    steps = [Step("warmup", warm * 60.0), spec(first, durations[0])]
    for k in range(1, n):
        doors = tuple(spec(a, durations[k]) for a in pairs[k - 1])
        steps.append(Step("corridor", corr_min * 60.0, doors=doors))
    steps.append(Step("corridor", corr_min * 60.0))               # dernier couloir : une carte, pas de porte
    combat = boss_min * 60.0 - 3 * b.transition_s
    for i, w in enumerate(weights):
        steps.append(Step("boss", round(combat * w / sum(weights) + b.transition_s, 1), "boss",
                          f"phase{i + 1}", objective))
    steps.append(Step("cooldown", cool * 60.0))
    return Scenario(objective, duration_min, seed, tuple(steps))


def _span_s(st: Step) -> float:
    """Durée nominale d'une étape ; un couloir à portes compte la salle jouée après lui."""
    return st.nominal_s + (st.doors[0].nominal_s if st.kind == "corridor" and st.doors else 0.0)


def planned_end_s(sc: Scenario, idx: int, elapsed_s: float, slow: float = 1.0) -> float:
    """Fin prévue de la run après l'étape `idx` : couloirs et retour au calme au nominal, salles et boss
    ralentis du facteur `slow` observé jusque-là."""
    end = elapsed_s
    for st in sc.steps[idx + 1:]:
        if st.kind == "corridor":
            end += st.nominal_s + (st.doors[0].nominal_s * slow if st.doors else 0.0)
        elif st.kind in ("room", "boss"):
            end += st.nominal_s * slow
        else:
            end += st.nominal_s
    return end


def adapt_after_room(sc: Scenario, idx: int, elapsed_s: float, b: RogueBalance = DEFAULT_BALANCE) -> tuple:
    """Rattrape un joueur en retard après une salle (étape `idx`, `elapsed_s` écoulées).

    Renvoie `(scénario, salles_retirées)`. Les couloirs suivants sont raccourcis (jusqu'à
    `corridor_min_s`) ; si le retard dépasse encore la marge, une salle avant le boss est retirée (le
    dernier couloir à portes et sa salle). Le boss et le retour au calme ne sont jamais retirés.
    """
    played = sum(_span_s(s) for s in sc.steps[:idx + 1])
    slow = max(elapsed_s / max(played, 1e-9), 1.0)
    target = sc.duration_min * 60.0
    steps = list(sc.steps)
    skipped = 0

    def over() -> float:
        return planned_end_s(replace(sc, steps=tuple(steps)), idx, elapsed_s, slow) - target

    if over() > b.late_margin_s:
        for i in range(idx + 1, len(steps)):
            if steps[i].kind == "corridor":
                steps[i] = replace(steps[i], nominal_s=min(steps[i].nominal_s, b.corridor_min_s))
                if over() <= b.late_margin_s:
                    break
    while over() > b.late_margin_s:
        doors = [i for i in range(idx + 1, len(steps)) if steps[i].kind == "corridor" and steps[i].doors]
        if not doors:
            break
        del steps[doors[-1]]
        skipped += 1
    return replace(sc, steps=tuple(steps)), skipped
