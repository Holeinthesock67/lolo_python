# Lot NV1 – Paysage « ville néon » (thème et contrat)

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Paysage `ville_neon` du thème (membre `neon`), énumération du contrat des parcours, validation et règle unique de l'engine ; premier lot du parcours « Avenue de la Lagune » | GDScript, Python | U25, DB2 | Petite | **En revue** (26 novembre) |

Demande du propriétaire du 26 novembre 2026 : une ambiance de ville de bord de mer des années 80 (néons rose et cyan, coucher de soleil, palmiers, route mouillée). Après deux prototypes au cloud, choix « parcours vitrine d'abord » puis « lots cloud tout de suite, date libre ». Cadrage hors dépôt : `/mnt/project-files/plans/CADRAGE_AVENUE_LAGUNE_2026-11-26.md` (lots NV0 à NV7).

## 1. Objectif

Déclarer le paysage, sans rien dessiner encore : les lots NV2 à NV5 (ciel et lumière, façades, enseignes et mobilier, voitures et passants) liront tous la même section du thème par la même règle, et le lot NV6 (parcours du compilateur) pourra écrire `ville_neon` dans ses tuiles.

## 2. Contraintes

- **Pas d'exception** (principe du 27 octobre), comme le volcan du lot DB2 : l'ambiance n'est pas un réglage d'une démonstration mais un **paysage** du thème. Toute tuile qui porte `ville_neon` s'affiche ainsi.
- Création originale : on reprend un genre (palette, néons, palmiers), aucun nom, logo, enseigne ni véhicule d'une œuvre existante.
- Contrat des parcours : ajout compatible, `format_version` inchangé. **Aucune révision du contrat IPC**, ni profil, ni ligue.
- Image par défaut inchangée : aucun parcours existant ni aucune zone réelle ne porte ce paysage.

## 3. Réalisation

- Contrat (`docs/contracts/world_format_v1.md` §8 quater et §9, journal) : valeur `ville_neon` de `variant.landscape` ; membre facultatif `neon` d'un paysage du thème, `{pink, cyan, violet, orange, sky_top, sky_mid, sky_horizon, fog, density}` (couleurs `#RRGGBB`, densité de 0 à 2, clé inconnue refusée).
- Schémas : `biome.schema.json`, `theme.schema.json` et sa copie du compilateur.
- Thème par défaut (et sa copie du compilateur) : `landscapes.ville_neon`, posé sur le biome `coast` : sol de dallage sombre, palmiers seuls et rares (6 par hectare), section `neon` aux couleurs du prototype.
- Compilateur : `regional.LANDSCAPES`. Aucune zone de `regional_variants.toml` ne pose ce paysage.
- Engine : `biome_ids.gd` (`LANDSCAPES`), `theme_loader.gd` (`_validate_neon`), `biome_model.gd` (`NEON_DEFAULTS`, `neon_of`, `neon_at`, sur le modèle de `fire_of` et `fire_at`).

## 4. Critères d'acceptation

1. `engine/tests/unit/test_neon_landscape.gd` : thème par défaut valide avec sa section `neon` ; section invalide refusée (densité hors bornes, couleur invalide, clé inconnue, valeur qui n'est pas un objet) ; `neon_at` rend le néon du thème dans une tuile `ville_neon`, rien sans paysage, dans un fjord ou sur le volcan ; pas de feu en ville néon ; section partielle complétée par les valeurs par défaut ; le sol et la végétation du paysage changent bien le biome `coast`.
2. `compiler/tests/test_contract_biome.py` : une tuile `ville_neon` est conforme au schéma.
3. `test_volcano_fx.gd` et `test_biome_model.gd` inchangés et verts.
4. Pas de banc PC : rien n'est dessiné par ce lot (CI et cloud seulement).

## 5. Livraison

PR du 26 novembre (branche `claude/project-thread-j0efty`). Reste : go de fusion du propriétaire.
