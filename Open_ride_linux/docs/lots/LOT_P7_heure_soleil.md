# Lot P7 – Jour et nuit : heure de la journée, coucher de soleil, nuit (sans affichage, version 2.0)

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Jour et nuit : heure, coucher de soleil, nuit étoilée (sans affichage) | GDScript | P1, P17 | Petite | Oui, **version 2.0** (issue #131) |

## 1. Objectif

**Version 2.0** (décision du propriétaire, 25 octobre : saisons et jour/nuit en 2.0). Le soleil est aujourd'hui fixe (élévation du thème, azimut constant). Ce lot calcule la lumière d'une heure donnée : position du soleil selon la latitude du parcours, couleur et intensité de la lumière, teinte du ciel et du brouillard, avec un vrai coucher de soleil orangé, une heure bleue et une **nuit** lisible (ciel étoilé, clair de lune). L'heure est fixe, réelle (horloge du PC) ou accélérée (une journée en 1 h de séance), selon `sky.time_of_day` du thème 1.2. Le modèle est pur et testé sans écran ; P19 l'applique à la scène.

## 2. À lire

1. `docs/lots/00_INDEX.md`, `docs/lots/LOT_P1_contrat_vent_decor.md` §4.4, `docs/contracts/world_format_v1.md` §2 et §3 (origine `lat`, `lon` du manifeste).
2. Code : `engine/scripts/theme_render_params.gd` (`sky_params`), `engine/scripts/route_data.gd` (lecture du manifeste), `engine/scripts/render_quality.gd` (`apply_fog`), `engine/scripts/main.gd` (`_apply_sky_params`, lecture seulement).

## 3. Prérequis

P1 et P17 livrés. À faire pour la version 2.0, pas avant.

## 4. Travail demandé

- Nouveau `engine/scripts/daylight_model.gd` (`extends RefCounted`, sans `class_name`) :
  - `sun_position(lat_deg, day_of_year, solar_hour) -> {elevation_deg, azimuth_deg}` : formule astronomique simple (déclinaison, angle horaire), précision de 1° suffisante ;
  - `light(elevation_deg) -> Dictionary` : `{sun_color, sun_energy, ambient_color, ambient_energy, sky_top, sky_horizon, fog_color}` par interpolation entre des paliers (nuit, heure bleue, aube et crépuscule orangés, matin, midi) ; en dessous de −6°, nuit : ciel bleu nuit, lumière de lune (phase calculée d'après la date, direction opposée approximative), route toujours lisible (lumière ambiante minimale réglable) ;
  - `stars(elevation_deg) -> float` : visibilité des étoiles de 0 (jour) à 1 (nuit noire), pour le shader du ciel de P6 ;
  - `clock(mode, hour, factor, elapsed_s, now_local) -> solar_hour` : `fixed`, `real` (heure locale du PC, convertie en heure solaire approximative avec la longitude), `accelerated` (`factor` fois plus vite, depuis `hour`) ;
  - pour tout thème sans `time_of_day` : résultat identique à aujourd'hui (élévation du thème, azimut actuel), sans changement de couleur.
- `theme_render_params.gd` : `time_of_day_params(theme)` (valeurs par défaut, bornes).
- La latitude n'est lue qu'à l'exécution depuis le manifeste ; aucune coordonnée réelle dans le dépôt ni dans les tests (latitudes de test rondes : 45°, 60°, 0°).

## 5. Fichiers concernés

- **Nouveaux :** `engine/scripts/daylight_model.gd`, `engine/tests/unit/test_daylight_model.gd`.
- **Modifiés :** `engine/scripts/theme_render_params.gd` (une fonction), `engine/tests/unit/test_theme_render_params.gd`, `engine/tests/README.md`, `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Interdits :** `main.gd`, la scène, le core, le contrat.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `engine/tests/run_engine_tests.sh` passe en entier.
2. Latitude 45°, 21 juin, midi solaire : élévation 68,4° ± 1°, azimut 180° ± 2° ; 21 décembre : 21,6° ± 1° ; équinoxe à 6 h : élévation 0° ± 1,5°, azimut 90° ± 3°.
3. `light` : couleur du soleil de plus en plus orangée quand l'élévation descend de 20° à 0° (composante bleue décroissante), énergie continue, aucune discontinuité de plus de 5 % entre deux paliers voisins sur un balayage au pas de 0,1°.
4. `accelerated`, `factor = 24`, départ 7 h : 19 h après 30 min de séance.
5. Thème par défaut sans `time_of_day` : élévation et direction identiques à `sky_params` actuel.
6. `evaluate` (position et lumière) sous 0,05 ms.
7. `stars` : 0 au-dessus de 0° d'élévation, 1 sous −18°, croissante entre les deux ; nuit de pleine lune plus claire qu'une nuit de nouvelle lune, route toujours au-dessus de la lumière ambiante minimale.

## 8. Hors périmètre

- Éclairage public, phare du vélo, fenêtres éclairées (envisageables dans P19 si le coût le permet).
- Application à la scène et transition douce des ombres (P19).
