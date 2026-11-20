"""Parcours propres à un mode de jeu (lot GP13, demande du propriétaire du 15 novembre 2026, module pur).

Règle unique pour tous les modes : un mode de l'accueil peut avoir ses propres parcours, reconnus à une
étiquette de leur fiche (`library.tags` du manifeste, lot O15) ; un parcours de mode est toujours une boucle
(lot GPL1, demande du propriétaire du 20 novembre : le Grand Prix ne se court plus en ligne, une piste est une
boucle) : une trace en ligne qui porte l'étiquette d'un mode reste un parcours libre, partout (core et engine,
`CatalogModel.mode_route_ids`). Un parcours d'un mode n'est que dans ce mode :
l'engine le retire de la liste générale « Parcours » et ne le propose que sur l'écran Prêt du mode ; le core
retient le dernier parcours de chaque mode à part du dernier parcours libre (`last_choices.mode_routes`) et la
séance conseillée ne choisit que des parcours libres. La table est publiée telle quelle à l'engine
(`hello_ack.config.mode_routes`, contrat IPC révision 1.19) : l'engine ne la recopie pas.

- `track` (Vélodrome, épreuves de piste, série VD) : étiquette `velodrome`, posée par `velodrome.py` ;
- `grandprix` (Grand Prix des objets, série GP) : étiquette `grandprix` (Circuit des Prés du jeu de base,
  Boucle de la Corniche et Route des Vignes, ou fiche `.toml` d'une boucle du joueur).
"""
from __future__ import annotations

from typing import Any, Iterable

# Mode de l'accueil → étiquette de ses parcours ; une étiquette n'appartient qu'à un mode.
MODE_ROUTE_TAGS: dict[str, str] = {"track": "velodrome", "grandprix": "grandprix"}


def tags_of(manifest_or_library: Any) -> list[str]:
    """Étiquettes d'un manifeste (`library.tags`) ou d'une fiche (`tags`) ; [] si absentes ou mal formées."""
    if not isinstance(manifest_or_library, dict):
        return []
    lib = manifest_or_library.get("library", manifest_or_library)
    tags = lib.get("tags") if isinstance(lib, dict) else None
    if not isinstance(tags, list):
        return []
    return [str(t) for t in tags if isinstance(t, str)]


def mode_of_tags(tags: Iterable[str], route_type: str | None) -> str | None:
    """Mode auquel appartient un parcours de ces étiquettes et de ce type (`route.json`, `open`, `loop` ou
    `out_and_back`), ou None pour un parcours libre : seule une boucle est un parcours de mode."""
    if route_type != "loop":
        return None
    tags = set(tags)
    for mode, tag in MODE_ROUTE_TAGS.items():
        if tag in tags:
            return mode
    return None


def mode_of(manifest_or_library: Any, route_type: str | None) -> str | None:
    """Mode d'un parcours d'après son manifeste ou sa fiche et son type, ou None pour un parcours libre."""
    return mode_of_tags(tags_of(manifest_or_library), route_type)


def hello_block() -> dict[str, str]:
    """Table publiée dans `hello_ack.config.mode_routes` (copie : l'appelant peut la modifier)."""
    return dict(MODE_ROUTE_TAGS)
