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
         "Les montées raides sont rabotées : jamais plus de 6 % (le passage dure 3 s de plus)."),
    Card("springboard", "Tremplin cinétique", "terraformer",
         "En bas de chaque descente : +15 d'adrénaline et dégâts ×1,5 pendant 5 s."),
    Card("overdrive", "Overdrive", "module",
         "Pousse au-dessus de {overdrive_w} W : dégâts ×2 pendant 8 s. Recharge 45 s."),
    Card("heal", "Soin", "module",
         "Mouline vite et léger (plus de 95 rpm, sous {heal_w} W) : +1 de bouclier par seconde."),
    Card("cursed", "Maudit", "module",
         "Au-dessus de {cursed_w} W : dégâts ×1,35, mais Z ne marche plus."),
    Card("shifter", "Shifter électronique pro", "module",
         "Changement parfait plus facile : 2 fois plus de temps pour changer de vitesse. +3 de bouclier à chaque réussite."),
    Card("siphon", "Siphon d'aspiration", "module", "Contre le Puncheur : chaque parade réussie (Z) donne +50 d'adrénaline."),
    Card("polarity", "Inversion polaire", "active",
         "Maintiens Z, une fois par salle : pendant 8 s, la montée devient une descente douce (−3 % au plus)."),
)}
RELICS = {c.id: c for c in (
    Card("relic_shield", "Blindage de départ", "relic", "Bouclier plus grand : +20 pour toute la run."),
    Card("relic_gold", "Marché noir", "relic", "+25 % d'or gagné pour toute la run."),
    Card("relic_window", "Réflexes affûtés", "relic", "Changement parfait plus facile : +0,3 s pour changer de vitesse, toute la run."),
)}
ALL = {**CARDS, **RELICS}


def draw(seed_key: str, n: int, owned: tuple, pool: dict | None = None) -> tuple:
    """`n` cartes distinctes du réservoir, hors cartes déjà prises ; déterministe pour `seed_key`."""
    pool = CARDS if pool is None else pool
    ids = sorted(i for i in pool if i not in owned)
    if len(ids) < n:                      # réservoir presque vide : on complète avec les cartes déjà prises
        ids = sorted(pool)
    return tuple(random.Random(seed_key).sample(ids, min(n, len(ids))))


def threshold_w(frac: float, ftp_w: float) -> int:
    """Seuil d'une carte en watts, arrondi à 5 W (lot R23 : le joueur lit une puissance, pas un % à calculer)."""
    return int(round(frac * ftp_w / 5.0) * 5)


def card_text(card_id: str, ftp_w: float, b) -> str:
    """Texte d'une carte pour ce cycliste : seuils en watts calculés depuis sa FTP et la table d'équilibrage."""
    return ALL[card_id].text.format(overdrive_w=threshold_w(b.overdrive_power_frac, ftp_w),
                                    heal_w=threshold_w(b.heal_power_frac, ftp_w),
                                    cursed_w=threshold_w(b.cursed_power_frac, ftp_w))


def deck_add(deck: tuple, card_id: str) -> tuple:
    """Ajoute une carte : une carte active remplace l'ancienne carte active ; une carte déjà prise ne se double pas.
    Lot R23 : plus aucune carte n'est liée à une vitesse (`replaces_gear` reste `null` dans le message `loot`)."""
    card = ALL[card_id]
    kept = []
    for other in deck:
        o = ALL[other]
        if o.kind == "active" and card.kind == "active":
            continue
        if other == card_id:
            continue
        kept.append(other)
    return tuple(kept) + (card_id,)
