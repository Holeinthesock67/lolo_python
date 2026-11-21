# Lot PP5 – « Se connaître » : profil de cycliste, point fort, forme, record vieillissant, trous

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| « Se connaître » dans « Ma puissance » : profil en un mot, point fort et point faible, forme du moment, record vieillissant, trous de la courbe | Python + GDScript | PP1, PP3 | Petite | PR ouverte le 21 novembre (série PP, 6.0), captures à valider par le propriétaire |

## 1. Objectif

Idées du §8.1 du plan `docs/6.0/PLAN_SERIE_PP.md`, retenues par le propriétaire le 21 novembre (Q4) : dire au joueur, en mots, quel cycliste il est d'après sa propre courbe. Lecture seule, au menu seulement, sans aucune comparaison avec d'autres personnes (§8.5).

## 2. Travail demandé

### 2.1 Core

`core/src/openride_core/tools/power_profile.py` (ligne de commande `python -m openride_core.tools.power_profile [--json]`) :

- **Profil en un mot** : rapports 5 s, 1 min et 5 min sur 20 min, comparés à ceux d'un cycliste sans dominante (`REFERENCE` : 3,4 ; 1,7 ; 1,18) ; la durée qui ressort le plus donne le mot (5 s : sprinteur, 1 min : puncheur, 5 min : grimpeur, 20 min : rouleur), « complet » si aucune ne ressort de plus de 6 %. Sans effort à fond sur l'une des quatre durées : pas de mot, et la durée qui manque.
- **Point fort, point faible** : durée qui ressort le plus, et le moins.
- **Forme du moment** : médiane du rapport 6 semaines / 6 mois, en pour cent.
- **Record vieillissant** : record des 6 mois le plus ancien, s'il a plus de 120 jours, et le temps avant qu'il sorte de la courbe.
- **Trous** : plages de durées sans effort libre depuis 6 semaines (une séance ERG n'est pas un effort à fond), 3 au plus.

Contrat : objet facultatif `profile` du message `power_curve` (même révision 1.29, `power_curve.schema.json`, `ipc_v1.md`).

### 2.2 Engine

`power_view_model.gd` : ligne « Ton profil : rouleur » (détail « point fort : 20 min ») sous « Évolution par mois » ; quand elle est choisie, la carte écrit le point fort et le point faible, la forme, le record vieillissant, les trous et « Tu n'es comparé qu'à toi-même. ». Un core plus ancien sans `profile` : pas de ligne.

## 3. Critères d'acceptation

1. `core/tests/test_power_profile.py` (cinq mots, durée manquante, forme, record vieillissant, trous avec une séance ERG, profil vide) et `test_power_curve_ipc.py` (objet `profile` dans le message conforme au schéma).
2. `engine/tests/unit/test_power_menu.gd` : ligne, carte en mots, profil sans mot, core sans profil.
3. Banc des menus : scénario `ma_puissance` vert, capture `ma_puissance_profil` ; **captures low, medium et high validées par le propriétaire avant fusion**.

## 4. Livraison

21 novembre 2026, PR empilée sur PP4. Aucune donnée réelle : cycliste fictif à 250 W (`tools/courbe_fictive.py`).
