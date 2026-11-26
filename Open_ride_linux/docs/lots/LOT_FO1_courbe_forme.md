# Lot FO1 – « Ma forme » : courbe de forme (condition et fatigue) dans « Ma puissance »

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| « Ma forme » dans « Ma puissance » : condition (CTL) et fatigue (ATL) du coach sur 12 semaines, fraîcheur en mots, séances par semaine | Python + GDScript | PP3, CO1 | Petite | PR ouverte le 22 novembre (empilée sur PP7b), captures à valider par le propriétaire |

## 1. Objectif

Constat M11 de l'audit du 22 novembre (`statut/AUDIT_COHERENCE_QUALITE_2026-11-22.md`) : le coach calcule la charge chronique et la charge aiguë mais ne les montre pas. Les montrer, en mots, dans « Ma puissance ». Cadrage : `plans/CADRAGE_OBJECTIF_SEMAINE_FORME_2026-11-22.md` (dossier du projet), accepté le 22 novembre. Lecture seule, au menu seulement ; points de charge, jamais de watts ni de FTP à l'écran. Les records par année du même constat restent hors de ce lot.

## 2. Travail demandé

### 2.1 Core

- `coach.fitness_series(facts, today, table)` (pur) : condition (CTL, 42 jours) et fatigue (ATL, 7 jours) jour par jour, mêmes constantes et même amorce que `build_signals` ; un point tous les 2 jours sur 84 jours, séances par semaine, tendance sur 7 jours, semaines de hausse, mot de la fraîcheur (condition moins fatigue). Seuils dans `data/coach.toml` `[fitness]` : les mots « très fatigué » et « fatigué » reprennent les bornes des règles R1 et R3.
- `ipc_lists.build_power_curve_message` : objet facultatif `fitness`, depuis `coach.collect_facts` (séances comptées du profil, cache du conseil) ; un échec laisse la courbe de puissance.
- Contrat : ajout compatible, objet facultatif `fitness` de `power_curve` (`power_curve.schema.json`, `ipc_v1.md`) ; **révision numérotée à la fusion** (aucune réservée, `CONTRACT_REV` inchangé).

### 2.2 Engine

- `power_view_model.gd` : ligne « Ma forme : un peu fatigué » (détail « condition 40, en hausse ») après « Ton profil » ; sa carte « MA FORME » : tuiles Condition, Fatigue, Fraîcheur, lignes en mots, légende « —— Condition (42 jours)   - - Fatigue (7 jours) ». Un core sans `fitness` : pas de ligne.
- `detail_card.gd` : `_draw_fitness`, condition en trait plein, fatigue en pointillé, chaque courbe nommée en bout de trait, séances de chaque semaine sous l'axe. Le mot et la forme du trait portent l'information, pas la couleur.

## 3. Critères d'acceptation

1. `core/tests/test_coach_forme.py` : mêmes valeurs que le conseil, reprise puis fatigue, repos, mots couvrant toutes les formes, objet `fitness` du message conforme au schéma et sans watt, profil vide.
2. `engine/tests/unit/test_fitness_menu.gd` : ligne, carte en mots, graphe « fitness », core sans `fitness`.
3. Banc des menus (medium) et **captures low, medium et high validées par le propriétaire avant fusion** (paquets de 8 h, 13 h ou 20 h).

## 4. Livraison

22 novembre 2026, PR empilée sur PP7b (#980). Aucune donnée réelle : cycliste fictif, FTP fictive 250 W.
