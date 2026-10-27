"""Cartes et reliques du Cyber-Rogue (lot R6) : catalogue, tirage et deck.

Les effets chiffrés sont appliqués par `run.py` ; ce module ne contient que les données et les règles
de deck (une seule carte par vitesse remplacée, une seule carte active). Pur et déterministe.
"""

from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass(frozen=True)
class Card:
    id: str
    name: str
    kind: str                       # "terraformer", "gear", "module", "active", "relic"
    text: str
    replaces_gear: int | None = None


CARDS = {c.id: c for c in (
    Card("roller", "Rouleau compresseur", "terraformer",
         "Les pentes au-dessus de 6 % sont écrêtées à 6 % et durent 3 s de plus."),
    Card("springboard", "Tremplin cinétique", "terraformer",
         "Au fond d'une descente en vitesse 9 ou plus : +15 d'adrénaline et 5 s de dégâts ×1,5."),
    Card("overdrive", "Overdrive", "gear",
         "Vitesse 12 : +4 points de pente et dégâts ×2 pendant 8 s, puis retour en 6. Recharge 45 s.", 12),
    Card("heal", "Soin", "gear",
         "Vitesse 1 au-dessus de 95 rpm : +1 bouclier par seconde.", 1),
    Card("cursed", "Maudit", "gear", "Vitesse 10 : dégâts ×1,35, mais Z sans effet.", 10),
    Card("shifter", "Shifter électronique pro", "module",
         "Fenêtre de Perfect Shift doublée (3 s au plus) ; +3 bouclier à chaque réussite."),
    Card("siphon", "Siphon d'aspiration", "module", "Aspiration réussie : +50 d'adrénaline."),
    Card("polarity", "Inversion polaire", "active",
         "Z long, une fois par salle : pendant 8 s la pente de l'ennemi est inversée (descente bornée à −3 %)."),
)}
RELICS = {c.id: c for c in (
    Card("relic_shield", "Blindage de départ", "relic", "Bouclier maximal +20 pendant toute la run."),
    Card("relic_gold", "Marché noir", "relic", "Or gagné +25 % pendant toute la run."),
    Card("relic_window", "Réflexes affûtés", "relic", "Fenêtre de Perfect Shift +0,3 s pendant toute la run."),
)}
ALL = {**CARDS, **RELICS}


def draw(seed_key: str, n: int, owned: tuple, pool: dict | None = None) -> tuple:
    """`n` cartes distinctes du réservoir, hors cartes déjà prises ; déterministe pour `seed_key`."""
    pool = CARDS if pool is None else pool
    ids = sorted(i for i in pool if i not in owned)
    if len(ids) < n:                      # réservoir presque vide : on complète avec les cartes déjà prises
        ids = sorted(pool)
    return tuple(random.Random(seed_key).sample(ids, min(n, len(ids))))


def deck_add(deck: tuple, card_id: str) -> tuple:
    """Ajoute une carte : elle remplace l'ancienne carte de la même vitesse ou l'ancienne carte active."""
    card = ALL[card_id]
    kept = []
    for other in deck:
        o = ALL[other]
        if o.kind == "gear" and card.kind == "gear" and o.replaces_gear == card.replaces_gear:
            continue
        if o.kind == "active" and card.kind == "active":
            continue
        if other == card_id:
            continue
        kept.append(other)
    return tuple(kept) + (card_id,)
