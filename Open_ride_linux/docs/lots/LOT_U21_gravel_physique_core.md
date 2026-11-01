# Lot U21 – Option « gravel » : résistance au roulement dans le core

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Gravel : résistance au roulement dans le core, supplément de pente sous le plafond du vent | Python | U1, P2 | Petite | Livré le 30 octobre (PR #625), **version 3.0** |

## 1. Objectif

**Version 3.0.** Faire sentir le gravel sur le vélo (U-G2) : sur les portions non revêtues, résistance au roulement multipliée (2 à 3 fois celle du bitume), transmise en SIM comme supplément de pente sous le même plafond que le vent ; en ERG, seule la vitesse virtuelle baisse. Option coupée par défaut.

## 2. À lire

1. `docs/3.0/PLAN_SERIE_U.md` §7 (U-G2), `docs/lots/LOT_U1_contrat_biomes.md` §4.4 et §4.6, `docs/lots/LOT_P1_contrat_vent_decor.md` §4.3 (`max_grade_offset_pct`), `docs/lots/LOT_P2_vent_physique_core.md`, `docs/SRS_v1.1.md` §5.
2. Code : `core/src/openride_core/physics.py` (`crr`), `core/src/openride_core/route.py`, `core/src/openride_core/session.py`, `core/src/openride_core/config.py`, `core/src/openride_core/journal.py`.

## 3. Prérequis

U1 et P2 livrés ; U20 pour des parcours réels (U19 suffit pour les tests).

## 4. Travail demandé

- `route.py` : lecture de la colonne `surface` (absente → `paved`), `surface_at(s)` (valeur du point le plus proche en arrière, sans interpolation).
- Module pur `core/src/openride_core/surface_physics.py` : `crr_factor(surface, cfg) -> float` (1 pour `paved`, facteurs de `[gravel]` sinon) ; `effective_surface(route_surface, mode)` : `paved` si `mode` vaut `off`, la surface de la route si `auto`, sinon la surface imposée par `mode` sur tout le parcours (décision U-Q8) ; `grade_offset_pct(crr_base, factor, grade_pct) -> float` : supplément de pente équivalent `(factor − 1) × crr_base × cos θ × 100`.
- Séance : en SIM, supplément de pente du gravel **ajouté** à celui du vent et de l'aspiration (P2), le total borné par `[wind] max_grade_offset_pct` ; transition douce sur 20 m entre deux surfaces ; en ERG, `crr` effectif utilisé pour la vitesse virtuelle seulement.
- Journal : surface et supplément de pente par seconde (clés facultatives), lues par `log_report.py`.
- Configuration `[gravel]` validée dans `config.py` (types et bornes du lot U1).

## 5. Fichiers concernés

- **Nouveaux :** `core/src/openride_core/surface_physics.py`, `core/tests/test_surface_physics.py`, `core/tests/test_session_gravel.py`.
- **Modifiés :** `core/src/openride_core/route.py`, `core/src/openride_core/session.py`, `core/src/openride_core/config.py`, `core/src/openride_core/journal.py`, `core/src/openride_core/tools/log_report.py`, `CLAUDE.md` (modules du core), `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Interdits :** engine, compilateur, contrats.

## 6. Modifications de contrat autorisées

Aucune (U1).

## 7. Critères d'acceptation

1. `pytest` passe dans `core/`.
2. `crr` 0,004, facteur 2,5, sur le plat : supplément de 0,6 point de pente (à 0,01 près).
3. Vent de face qui donne déjà 3,8 points et gravel 0,6 : total borné à 4,0.
4. Gravel coupé : séance simulée identique au bit près à la 2.0 (journal comparé).
4 bis. `mode = "gravel"` sur une route sans colonne `surface` : supplément de 0,6 point sur tout le parcours ; `mode = "auto"` sur la même route : aucun supplément.
5. ERG à 200 W sur 1 km de `dirt` : puissance demandée inchangée, vitesse virtuelle plus faible qu'en `paved`.
6. Passage `paved` → `gravel` : supplément qui monte en 20 m, sans marche.

**Sur le PC cible (le propriétaire, à la recette U18) :** différence nette sur le HomeTrainer, jamais désagréable.

## 8. Hors périmètre

Rendu et sons du gravel (U22), crevaisons, adhérence.

## Livraison

PR #625, fusionnée le 30 octobre 2026. Statut remis à jour par la passe documentaire du 1er novembre, d'après les PR fusionnées ; statut précédent : « Oui, après U1, **version 3.0** (issue #351) ».
