# Lot P18 – Saisons (sans affichage et shaders, version 2.0)

## 1. Objectif

**Version 2.0** (décision du propriétaire, 25 octobre). Faire changer le paysage avec la saison, choisie par le thème 1.2 (`season`) ou tirée de la date du PC :
- **printemps :** vert tendre, vergers en fleurs (zones `orchard`) ;
- **été :** l'état actuel ;
- **automne :** feuillages jaunes, orange et roux selon les arbres, feuilles qui tombent près des forêts et tourbillonnent au vent ;
- **hiver :** arbres feuillus dénudés (résineux inchangés), herbe jaunie, neige au sol en altitude ou partout selon l'enneigement du thème, ciel plus bas.

Et les sons qui vont avec : insectes l'été seulement, oiseaux plus rares l'hiver.

## 2. À lire

1. `docs/lots/00_INDEX.md`, `docs/lots/LOT_P1_contrat_vent_decor.md` §4.4 (`season`), `docs/lots/LOT_P5_vent_vegetation.md` (teinte du feuillage), `docs/lots/LOT_P8_meteo_legere.md` (particules), `docs/lots/LOT_P9_ambiance_sonore.md`, `docs/lots/LOT_P7_heure_soleil.md` (date).
2. Code : `engine/shaders/tree_sway.gdshader` (P5), `engine/shaders/terrain.gdshader`, `engine/scripts/theme_render_params.gd`, `engine/scripts/tree_renderer.gd`.

## 3. Prérequis

P5, P8, P9 et P17 livrés ; P7 pour la date (même version 2.0). À faire pour la version 2.0, pas avant.

## 4. Travail demandé

- Nouveau modèle pur `engine/scripts/season_model.gd` :
  - `season_for(theme, date) -> String` : `season` du thème, sinon d'après la date (hémisphère tiré du signe de la latitude du manifeste) ;
  - `params(season, progress) -> Dictionary` : teintes du feuillage (palette d'automne variée par arbre), part d'arbres dénudés, teinte de l'herbe, enneigement (altitude de la neige abaissée en hiver), floraison des vergers, densité des feuilles qui tombent, facteurs sonores (insectes, oiseaux) ; `progress` (0 à 1 dans la saison) donne des transitions douces (début et fin d'automne).
- Shaders : teinte du feuillage et arbres dénudés dans le shader de P5 (sans changer les instances : branches seules par masque de couleur des sommets) ; herbe jaunie et neige abaissée dans `terrain.gdshader`, derrière des `uniform` neutres par défaut.
- Feuilles qui tombent : un effet de plus dans `weather_particles.gd` (P8), seulement près des forêts, poussé par le vent, borné par `living(preset).weather_particles`.
- Sons : facteurs de saison passés au modèle d'ambiance de P9.

## 5. Fichiers concernés

- **Nouveaux :** `engine/scripts/season_model.gd`, `engine/tests/unit/test_season_model.gd`, `engine/tests/render/test_season_render.gd`.
- **Modifiés :** `engine/shaders/tree_sway.gdshader`, `engine/shaders/terrain.gdshader`, `engine/scripts/weather_particles.gd`, `engine/scripts/ambience_model.gd`, tests de ces scripts, `engine/tests/README.md`, `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Interdits :** `main.gd` (P19), le core, le contrat.

## 6. Modifications de contrat autorisées

Aucune (P1).

## 7. Critères d'acceptation

1. `engine/tests/run_engine_tests.sh` passe en entier, rendu compris.
2. `season_for` : thème sans `season`, 15 octobre, latitude 45° : `autumn` ; même date, latitude −35° : `spring`.
3. Été : rendu identique à P5 et à E2 (teintes neutres).
4. Rendu : arbre feuillu en automne majoritairement orangé (teinte moyenne), en hiver sans feuillage (pixels de feuillage absents), résineux inchangé ; terrain en hiver plus clair au-dessus de la limite de neige abaissée.
5. Transitions : aucune variation de teinte de plus de 5 % entre deux valeurs de `progress` distantes de 0,01.
6. Feuilles qui tombent : seulement en automne, seulement à moins de 30 m d'une forêt, jamais au-dessus du budget.

**Sur le PC cible (le propriétaire) :** une séance par saison en `low` : paysage cohérent, perte de moins de 1 image/s par rapport à l'été.

## 8. Hors périmètre

- Accumulation progressive de la neige, routes enneigées, glace, lacs gelés.
