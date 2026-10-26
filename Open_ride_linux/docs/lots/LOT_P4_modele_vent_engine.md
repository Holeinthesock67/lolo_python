# Lot P4 – Engine : modèle du vent, indicateur du HUD et budgets du décor vivant (sans affichage)

## 1. Objectif

Socle de la série P côté engine, sans nœud ni affichage :
- un **modèle du vent** qui lit le champ `wind` de `state` (lot P2) et fournit à tout le décor la même valeur lissée : direction, force, rafale, phase d'animation ;
- le **modèle de vue de l'indicateur** du HUD : flèche orientée par rapport au cycliste, vitesse en km/h, « face », « dos » ou « travers », et l'abri derrière un bot (`draft`, lot P3) ;
- la **table des budgets du décor vivant** par préréglage de qualité, lue par les lots P5 à P15, pour tenir l'objectif de la série sur la GTX 1060.

## 2. À lire

1. `docs/lots/00_INDEX.md` (paragraphe « Série P », budget de rendu), `docs/lots/LOT_P1_contrat_vent_decor.md` §4.1, §4.2 et §4.4.
2. Code : `engine/scripts/hud_view_model.gd` (style des modèles sans nœud), `engine/scripts/quality_presets.gd`, `engine/scripts/theme_render_params.gd`, `engine/scripts/sound_model.gd` (hystérésis, lissage), `engine/tests/README.md` (contrat des tests unitaires).

## 3. Prérequis

P1 livré. P2 n'est pas requis : le modèle se teste avec des trames écrites à la main. Version 1.0 publiée.

## 4. Travail demandé

### 4.1 `wind_model.gd` (`extends RefCounted`, sans `class_name`)

- `on_state(state, now_s)` : lit `wind` s'il est présent ; sinon vent du thème (`wind` du thème 1.2) en mode décoratif, sinon calme.
- `evaluate(now_s) -> Dictionary` : `{dir: Vector3 (vers où souffle le vent, repère de Godot), strength (0 à 1, 1 = 60 km/h), gust (0 à 1), phase (s, continue)}` ; lissage à 2 s pour la direction et 0,5 s pour la force ; aucun saut de phase quand la force change.
- Vent apparent pour l'animation proche (herbe, son) : `apparent(rider_speed_mps, heading_deg)` ajoute le vent dû à la vitesse du cycliste.
- Repère : cap et `from_deg` dans le sens horaire depuis le nord ; le nord est −z (`world_format_v1.md` §3).

### 4.2 `wind_view_model.gd`

- `view(state, heading_deg) -> Dictionary` : `{visible, arrow_deg, speed_text, label, verdict, verdict_text, tone, level, level_text, draft_text}` :
  - `arrow_deg` : angle de la flèche à l'écran, 0 = vent de face (flèche vers le bas), relatif au cap de la route ;
  - `speed_text` : « 18 km/h » (entier) ; `label` : « face », « dos », « travers gauche », « travers droit » (secteurs de 45° autour de l'axe, hystérésis de 5°) ;
  - **favorable ou non** (demande du propriétaire du 25 octobre) : `verdict` d'après `head_mps` lissé, `"favorable"` sous − 1 m/s (vent de dos), `"defavorable"` au-dessus de + 1 m/s (vent de face), `"neutre"` entre les deux (travers ou vent faible), hystérésis de 0,3 m/s ; `verdict_text` : « Vent favorable », « Vent défavorable », « Vent neutre » ; `tone` : `"good"` (vert), `"bad"` (rouge) ou `"neutral"` (gris), couleurs prises dans la palette du HUD ;
  - **intensité :** `level` de 0 à 4 d'après `speed_mps` (rafale comprise, lissée sur 2 s) : 0 calme sous 5 km/h, 1 faible de 5 à 15, 2 modéré de 15 à 25, 3 fort de 25 à 40, 4 très fort au-delà, hystérésis de 2 km/h ; `level_text` : « calme », « faible », « modéré », « fort », « très fort » ; affiché en barres (une à quatre) à côté de la vitesse ;
  - `draft_text` : « Abri 30 % » (`draft / 0,45`, arrondi à 5 %), vide sans `draft` ou sous 5 % ;
  - `visible = false` sans `wind` ni `draft` (pas d'indicateur inutile).

### 4.3 Budgets dans `quality_presets.gd`

- Nouvelle table `LIVING` et fonction `living(preset) -> Dictionary`, par préréglage `low`, `medium`, `high` :
  `tree_sway` (bool), `grass_tufts` (nombre max), `clouds` (`"off"`, `"flat"`, `"layered"`), `weather_particles` (max), `birds` (max), `animals` (max), `vehicles` (max), `spectators` (max), `passersby` (max, clé ajoutée par P21), `ambience_voices` (max de sources simultanées), `water_shimmer` (bool).
- Valeurs de départ pour `low` (GTX 1060 du PC cible) : balancement des arbres oui, 0 touffe d'herbe, nuages `flat`, 600 particules, 12 oiseaux, 20 animaux, 3 véhicules, 40 spectateurs, 4 voix, scintillement oui. `medium` et `high` plus généreux.
- Un réglage `[render] living = false` (ou un préréglage) doit pouvoir tout couper : `living("low", false)` renvoie tous les budgets à zéro.

## 5. Fichiers concernés

- **Nouveaux :** `engine/scripts/wind_model.gd`, `engine/scripts/wind_view_model.gd`, `engine/tests/unit/test_wind_model.gd`, `engine/tests/unit/test_wind_view_model.gd`.
- **Modifiés :** `engine/scripts/quality_presets.gd` (table `LIVING` seule), `engine/tests/unit/test_quality_presets.gd`, `engine/tests/README.md` (deux lignes), `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Interdits :** `main.gd`, `hud_view.gd`, scènes, le core, le contrat.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `engine/tests/run_engine_tests.sh` passe en entier (sans écran).
2. Route plein nord, vent du nord à 20 km/h : `label = "face"`, `arrow_deg = 0`, `speed_text = "20 km/h"` ; route plein sud : « dos », 180° ; route plein est : « travers gauche ».
3. Hystérésis : une direction qui oscille de ± 3° autour d'une limite de secteur ne fait pas changer `label`.
4. Changement brusque de 0 à 40 km/h : `strength` atteint 90 % de sa cible en 1,2 s au plus et ne la dépasse pas ; `phase` reste continue.
5. Sans `wind` dans la trame et sans clé `wind` au thème : vent calme, indicateur caché.
6. `draft = 0.135` : « Abri 30 % ».
7. Verdict : `head_mps = 3` : « Vent défavorable », ton `bad` ; `head_mps = -3` : « Vent favorable », ton `good` ; vent de 20 km/h plein travers : « Vent neutre » ; `head_mps` qui oscille entre 0,9 et 1,1 m/s : verdict inchangé.
8. Intensité : 3, 10, 20, 30 et 45 km/h donnent les niveaux 0 à 4 ; une rafale isolée de moins d'une seconde ne change pas le niveau.
9. `evaluate` coûte moins de 0,05 ms par appel (mesure sur 10 000 appels dans le test) et n'alloue rien d'autre que le dictionnaire rendu.
10. `living` : trois préréglages complets, valeurs `low` du §4.3, tout à zéro quand le décor vivant est coupé.

## 8. Hors périmètre

- Dessin de l'indicateur dans le HUD (P16 pour le vent, P17 pour l'abri).
- Vent dans les arbres et le décor (P5 et suivants).
