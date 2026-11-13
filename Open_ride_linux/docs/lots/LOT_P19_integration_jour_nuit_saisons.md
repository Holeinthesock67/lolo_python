# Lot P19 – Intégration du jour, de la nuit et des saisons (version 2.0)

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Intégration du jour, de la nuit et des saisons | GDScript | P7, P17, P18 | Moyenne | Non : interne, **version 2.0** (issue #143) |

## 1. Objectif

**Version 2.0.** Brancher dans la scène principale le jour et la nuit (P7) et les saisons (P18), puis les recetter sur le matériel. Lot interne : il modifie `main.gd` et se juge à l'œil.

## 2. À lire

1. `docs/lots/00_INDEX.md` (paragraphe « Série P »), cahiers P6, P7, P8, P9, P16, P17 et P18.
2. Code : `engine/scripts/main.gd` (`_apply_sky_params`), `engine/scripts/render_quality.gd`, `engine/scripts/hud_view.gd`, `engine/tests/visual_check.py`.

## 3. Prérequis

P7, P17 et P18 livrés. Version 2.0.

## 4. Travail demandé

- Heure (P7) : soleil, lune, lumière ambiante, couleurs du ciel de P6, étoiles et brouillard mis à jour au plus une fois par seconde, avec transition douce ; direction des ombres mise à jour par petits pas invisibles ; heure transmise à P8 (brume du matin) et P9 (oiseaux, cloches).
- Nuit : lumière ambiante minimale pour que la route reste lisible ; HUD inchangé.
- Saisons (P18) : paramètres appliqués au chargement de la séance, puis suivis si l'heure accélérée change de jour.
- Choix de l'heure et de la saison au menu (section « Réglages » de O4), si le contrat de menu le permet ; sinon par le thème.
- `visual_check.py` : scènes `crépuscule`, `nuit`, `automne`, `hiver` ; références mises à jour.
- Nouveau `docs/RECETTE_P19.md`.

## 4 bis. Deux réglages séparés au menu (décision du propriétaire, 8 novembre)

Demande : « ça doit être désactivable individuellement dans le menu ». Deux réglages de **Réglages › Graphisme**, écrits dans `config.toml` (`[render]`, portée machine), passés à l'engine par le message des réglages (`applies="now"`, comme `render.draft_gauge`) : changés au menu, ils s'appliquent tout de suite, sans relance ni argument du lanceur :

| Clé | Libellé | Choix | Défaut |
| --- | --- | --- | --- |
| `render.day_night` | Jour et nuit | `off` (soleil fixe d'aujourd'hui), `theme` (heure du thème), `real` (heure du PC), `accelerated` (une journée en une heure) | `off` |
| `render.seasons` | Saisons | `off` (l'été d'aujourd'hui), `theme` (saison du thème, l'été sans), `date` (selon la date et l'hémisphère), `spring`, `summer`, `autumn`, `winter` | `off` |

Défauts sûrs : `off` rend exactement l'image d'aujourd'hui, au même coût GPU. Passage du défaut à une autre valeur : seulement après les bancs aux trois qualités (budgets GPU low 8, medium 13, high 16 ms) et la validation des captures par le propriétaire. Chaque réglage coupe tout son effet (lumière, ombres, étoiles, brume du matin et sons pour le jour et la nuit ; teintes, neige, feuilles qui tombent et sons pour les saisons) et l'un ne dépend pas de l'autre. Le réglage `off` l'emporte sur le thème.

## 5. Fichiers concernés

- **Modifiés :** `core/src/openride_core/config.py`, `core/src/openride_core/settings.py`, `docs/SRS_v1.1.md` (exemple du §11), `engine/scripts/settings_view_model.gd`, `engine/scripts/main.gd`, `engine/scripts/atmosphere_view.gd`, `engine/shaders/sky_clouds.gdshader`, `engine/scripts/living_decor.gd`, `engine/scripts/ambience_model.gd`, `engine/tests/visual_check.py`, `engine/tests/README.md`, `docs/GUIDE_UTILISATION.md`, `docs/SUIVI_AVANCEMENT.md`.
- **Nouveaux :** `engine/scripts/sky_cycle.gd`, `engine/tests/unit/test_sky_cycle.gd`, `docs/RECETTE_P19.md`.

## 6. Modifications de contrat autorisées

Aucune, sauf l'ajout éventuel des réglages d'heure et de saison au contrat du menu (à valider par le propriétaire).

## 7. Critères d'acceptation

1. Tous les tests passent (`core`, `compiler`, `run_engine_tests.sh`, `run_e2e.sh`, `run_visual_tests.sh`).
2. Heure accélérée de 5 h à 23 h en 45 min : aube, midi, coucher orangé, heure bleue et nuit étoilée visibles, sans saut de lumière ni d'ombre.
3. Nuit : route et HUD lisibles ; brume du matin qui se lève vers 10 h.
4. Une séance par saison : paysage cohérent avec P18.
5. **Performance sur le PC cible, qualité `low`, toute la série P :** 55 images/s ou plus en moyenne, p99 sous 25 ms, de jour comme de nuit.

## 7 bis. Livraison (8 novembre)

- `sky_cycle.gd` (sans nœud) traduit les deux réglages en paramètres de `DaylightModel.evaluate` (P7) et de `SeasonModel.params` (P18) ; `main.gd` l'évalue au plus une fois par seconde (`CYCLE_PERIOD_S`), avec la latitude et la longitude du premier point du parcours, la date du PC et le temps de séance ; `atmosphere_view` fond la lumière vers la nouvelle valeur (transition douce).
- Nuit : la lune remplace le soleil quand elle éclaire plus ; lumière ambiante plancher (`min_ambient` du thème) : route lisible ; étoiles en 4 niveaux sur le ciel physique (texture `night_sky`), procédurales sur le ciel à nuages.
- Saisons : paramètres globaux des shaders `season_*`, arbres d'hiver avec charpente (`tree_renderer.set_winter`), feuilles qui tombent près des forêts, oiseaux et insectes des sons d'ambiance.
- Message de test `{"type": "_test", "action": "sky_cycle", "day_night", "seasons", "hour", "date"}` : réglages, heure solaire et date imposées pour les captures ; `visual_check.py --jour-nuit` : midi, crépuscule, heure bleue, nuit, automne, hiver, printemps, puis retour aux réglages coupés.
- Reste : brume du matin (P8) et cloches (P9) pas encore liées à l'heure, floraison des vergers non branchée, altitude des nuages selon la saison non appliquée, l'heure accélérée ne fait pas avancer la date. Recette : `docs/RECETTE_P19.md`.

## 7 ter. Banc du 8 novembre (PC cible, r781, low / medium / high)

- Réglages coupés : GPU égal à `main` (0 à +0,4 ms en low, dans le bruit), 9 passes OK.
- `day_night = "theme"` + `seasons = "winter"` : sous les budgets partout (alpine 4,84 / 9,93 / 9,27 ms ; savanna 4,73 / 6,75 / 9,03 ; sand_desert 4,80 / 6,05 / 7,95). Seul surcoût net : alpine medium +3,4 ms.
- À-coups, réglages actifs seulement : alpine low (pire image 104 ms, 7 s d'images lentes, périodicité tous les 174 m) ; savanna medium et high, sand_desert medium (3,2 à 3,7 images lentes par minute). À corriger avant de changer le défaut (pistes : changement de maillage des arbres d'hiver par tuile, texture des étoiles créée à la volée).
- Captures validées par le propriétaire le 8 novembre (nuit gardée telle quelle).

## 8. Hors périmètre

- Éclairage public, phare du vélo, fenêtres éclairées (lot ultérieur si souhaité) : fait par le lot P35 (13 novembre).
