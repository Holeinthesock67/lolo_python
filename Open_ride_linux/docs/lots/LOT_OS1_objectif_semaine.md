# Lot OS1 – Objectif de la semaine à l'accueil

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Objectif de la semaine : ligne « Semaine : 1 séance sur 2 » de l'accueil sous la ligue, réglage en séances | Python + GDScript | CO3, CH4a | Petite | PR ouverte le 23 novembre, captures à valider par le propriétaire |

## 1. Objectif

Constat M4 de l'audit du 22 novembre (`statut/AUDIT_COHERENCE_QUALITE_2026-11-22.md`) : la ligue donne un rendez-vous, pas un volume. Montrer à l'accueil un objectif de séances par semaine. Cadrage : `plans/CADRAGE_OBJECTIF_SEMAINE_FORME_2026-11-22.md` (dossier du projet) ; défaut de 2 séances retenu le 22 novembre.

## 2. Travail demandé

### 2.1 Core

- `coach.week_goal(facts, today, target, table)` (pur) : séances comptées du profil (mêmes faits que le conseil : journaux `live` et sources comptées, rejeux exclus) de la semaine ISO de `today` (lundi à dimanche, heure locale), d'au moins `[week] min_session_s` (1 200 s, `data/coach.toml`) ; `{target, done, days_left, reached}`, `None` pour un objectif à 0.
- Réglage `coach.seances_semaine` (« Objectif de la semaine », séance, portée profil, 0 à 7, 2 par défaut, 0 : aucun).
- `coach.advice_today(…, week_target)` ajoute `week_goal` au conseil ; message `coach` : objet facultatif `week_goal` (`coach.schema.json`, `ipc_v1.md`). **Révision numérotée à la fusion**, `CONTRACT_REV` inchangé.

### 2.2 Engine

- `coach_view_model.gd` : `week_label()` (« Semaine : 1 séance sur 2 ») et `week_detail()` (« il reste 4 jours », « dernier jour », « objectif atteint ») : l'état est écrit, jamais porté par la couleur seule.
- `menu_model.gd` : ligne `week` de l'accueil sous « Ligue d'hiver » (`set_week_home`) ; `menu_flow.gd` la pose à chaque message `coach` et l'ouvre sur l'Historique.

## 3. Critères d'acceptation

1. `core/tests/test_coach_semaine.py` : semaine ISO, lundi minuit, séance trop courte, objectif atteint, réglage (défaut, bornes, portée), message `coach`.
2. `engine/tests/unit/test_week_goal_home.gd` : libellés en mots, place sous la ligue, pas de ligne sans objectif, ouverture de l'Historique.
3. Menus seuls : banc PC medium, **captures low, medium et high de l'accueil validées par le propriétaire avant fusion**.

## 4. Livraison

23 novembre 2026, PR sur main (après CH4a, #993). Aucune donnée réelle : séances fabriquées.
