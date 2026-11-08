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

Demande : « ça doit être désactivable individuellement dans le menu ». Deux réglages de **Réglages › Graphisme**, écrits dans `config.toml` (`[render]`, portée machine), passés à l'engine comme les autres réglages du rendu, sans exception :

| Clé | Libellé | Choix | Défaut |
| --- | --- | --- | --- |
| `render.day_night` | Jour et nuit | `off` (soleil fixe d'aujourd'hui), `theme` (heure du thème), `real` (heure du PC), `accelerated` (une journée en une heure) | `off` |
| `render.seasons` | Saisons | `off` (l'été d'aujourd'hui), `date` (selon la date et l'hémisphère), `spring`, `summer`, `autumn`, `winter` | `off` |

Défauts sûrs : `off` rend exactement l'image d'aujourd'hui, au même coût GPU. Passage du défaut à une autre valeur : seulement après les bancs aux trois qualités (budgets GPU low 8, medium 13, high 16 ms) et la validation des captures par le propriétaire. Chaque réglage coupe tout son effet (lumière, ombres, étoiles, brume du matin et sons pour le jour et la nuit ; teintes, neige, feuilles qui tombent et sons pour les saisons) et l'un ne dépend pas de l'autre. Le réglage `off` l'emporte sur le thème.

## 5. Fichiers concernés

- **Modifiés :** `core/src/openride_core/config.py`, `core/src/openride_core/settings.py`, `core/src/openride_core/launcher.py`, `engine/scripts/engine_args.gd`, `engine/scripts/settings_view_model.gd`, `docs/GUIDE_UTILISATION.md`, `engine/scripts/main.gd`, `engine/scripts/render_quality.gd`, `engine/tests/visual_check.py`, `engine/tests/README.md`, `docs/SUIVI_AVANCEMENT.md` ; écran de réglages si l'option du menu est retenue.
- **Nouveaux :** `docs/RECETTE_P19.md`.

## 6. Modifications de contrat autorisées

Aucune, sauf l'ajout éventuel des réglages d'heure et de saison au contrat du menu (à valider par le propriétaire).

## 7. Critères d'acceptation

1. Tous les tests passent (`core`, `compiler`, `run_engine_tests.sh`, `run_e2e.sh`, `run_visual_tests.sh`).
2. Heure accélérée de 5 h à 23 h en 45 min : aube, midi, coucher orangé, heure bleue et nuit étoilée visibles, sans saut de lumière ni d'ombre.
3. Nuit : route et HUD lisibles ; brume du matin qui se lève vers 10 h.
4. Une séance par saison : paysage cohérent avec P18.
5. **Performance sur le PC cible, qualité `low`, toute la série P :** 55 images/s ou plus en moyenne, p99 sous 25 ms, de jour comme de nuit.

## 8. Hors périmètre

- Éclairage public, phare du vélo, fenêtres éclairées (lot ultérieur si souhaité).
