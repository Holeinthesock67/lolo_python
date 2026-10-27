# Lot P16 – Intégration, première vague : vent ressenti et affiché, arbres, nuages, sons

## 1. Objectif

Brancher dans la scène principale les lots les plus rentables de la série P, ceux qui changent le plus l'impression pour le moindre coût sur la GTX 1060 :
- le vent physique du core (P2) et son **indicateur dans le HUD** (modèle P4) ;
- les arbres et l'herbe qui bougent au vent (P5) ;
- les nuages qui défilent (P6) ;
- les sons d'ambiance (P9) et les sons du vélo (P10).

Puis faire la recette sur le matériel. Lot interne : il modifie `main.gd` et `hud_view.gd` et se juge à l'œil, à l'oreille et sur le vélo.

## 2. À lire

1. `docs/lots/00_INDEX.md` (paragraphe « Série P », budget de rendu), cahiers P1, P2, P4, P5, P6, P9 et P10, `docs/RECETTE_E3_E4.md` (forme d'une recette).
2. Code : `engine/scripts/main.gd`, `engine/scripts/hud_view.gd`, `engine/scripts/render_quality.gd`, `engine/scripts/world_streamer.gd`, `engine/scripts/osm_streamer.gd`, `engine/tests/visual_check.py`.

## 3. Prérequis

P2, P4, P5, P6, P9 et P10 livrés ; O4 (section « Réglages » du menu). Version 1.0 publiée.

## 4. Travail demandé

- `main.gd` : un `WindModel` alimenté par chaque trame ; paramètres globaux du vent (P5, P6) mis à jour une fois par image ; matériaux d'arbres et nœud des touffes selon `living(preset)` ; ciel de P6 à la place du ciel actuel ; voisinage sonore (part de forêt et de bâti, eau la plus proche, altitude) calculé au plus 2 fois par seconde à partir des couches déjà chargées et passé à P9.
- `hud_view.gd` : indicateur du vent d'après `wind_view_model.gd` : flèche, « 18 km/h face », barres d'intensité (« modéré ») et pastille « Vent favorable » en vert, « Vent défavorable » en rouge ou « Vent neutre » en gris (demande du propriétaire du 25 octobre) ; lisible d'un coup d'œil sur le vélo, à 2 m de l'écran ; placé sans recouvrir les autres éléments (règle de `banner.gd`), sous les lignes actuelles du HUD ; laisser libre une zone pour les blocs « segment » (chrono, écart au record) et « bonus » (icône, compte à rebours) de la série T de la 2.0 (`docs/2.0/`) ; caché sans vent.
- Section « Réglages » du menu (O4) : mode du vent (coupé, fixe, rafales, thème), force, direction et plafond du supplément de pente (4 points par défaut, de 0 à 8), décisions du propriétaire du 25 octobre (P1).
- Réglage `[render] living` (oui par défaut) relayé par le lanceur comme le préréglage de qualité (L4), pour tout couper en cas de souci de performance.
- `visual_check.py` : une scène `vent` (trame avec `wind`, indicateur visible et dans l'écran) et une scène `nuages` (pixels clairs au-dessus de l'horizon) ; références mises à jour.
- Nouveau `docs/RECETTE_P16.md` : liste d'essais du §7, à cocher par le propriétaire.

## 5. Fichiers concernés

- **Modifiés :** `engine/scripts/main.gd`, `engine/scripts/hud_view.gd`, `engine/scripts/engine_args.gd`, `core/src/openride_core/launcher.py` (option `living`), `engine/tests/visual_check.py`, `engine/tests/README.md`, `docs/SUIVI_AVANCEMENT.md`.
- **Nouveaux :** `docs/RECETTE_P16.md`.

## 6. Modifications de contrat autorisées

Aucune (P1).

## 7. Critères d'acceptation

1. Tous les tests passent (`core`, `compiler`, `run_engine_tests.sh`, `run_e2e.sh`, `run_visual_tests.sh`).
2. **Performance sur le PC cible, qualité `low`, tout activé, vent de 25 km/h, couverture nuageuse 0,5, parcours avec forêt et village :** `[perf-rendu]` à 55 images/s ou plus en moyenne sur 20 min, temps d'image p99 sous 25 ms ; écart avec `living = false` relevé dans la recette (objectif : moins de 3 images/s).
3. Vent de face de 25 km/h en SIM : résistance qui monte, vitesse qui baisse, flèche « face », « Vent défavorable » en rouge, niveau « fort » ; demi-tour sur le parcours : « dos », « Vent favorable » en vert, vitesse qui remonte ; route en travers du vent : « Vent neutre ».
4. Arbres et nuages qui bougent dans le sens de la flèche ; son du vent qui forcit avec le vent de face ; roue libre qui ralentit avec la vitesse.
5. Ambiance qui change entre forêt, champ et village, sans clic ni coupure.
6. `living = false` : rendu et sons identiques à la 1.0.

## 8. Hors périmètre

- Lots P3, P8, P11 à P15 (P17) ; jour, nuit et saisons (P7, P18, P19 : version 2.0).

## 9. Livraison

Livré sur la branche `lot-p16-integration-vent`, qui réunit P10 (et donc P1, P4 à P6, P8, P9), P2 et la branche `lot-o3-reglages` (O3, PR #248). Sans modification du contrat.

- **`living_world.gd`** (nouveau, créé par `main.gd`) rassemble le branchement, testable sans la scène :
  - `WindModel` alimenté par chaque trame. Sans vent du core, le vent décoratif du thème anime le décor.
  - Une fois par image : paramètres globaux du vent des arbres, vent apparent des touffes d'herbe, défilement des nuages (et leur ombre sur le terrain en `high`).
  - Ciel de P6 à la place du ciel actuel, selon `living(preset).clouds`.
  - Voisinage sonore recalculé au plus toutes les 0,5 s. Il part des contours des tronçons OSM déjà chargés : forêts, bâtiments, eaux, limités à ceux qui touchent le cercle d'écoute. L'altitude, la force du vent et la pause sont ajoutées à chaque image pour les fondus de P9. Les cloches sonnent à l'heure du PC.
- **`osm_streamer.gd`** : chaque tronçon garde ses contours en x, z avec leur rectangle englobant (`layer_shapes()`, `shapes_version`). Les forêts sont lues dans la couche `vegetation`. Les bâtiments et les plans d'eau deviennent les exclusions des touffes d'herbe.
- **`hud_view.gd`** : indicateur du vent sous le panneau de gauche, de même largeur. Il montre une flèche vers où souffle le vent (route vers le haut), « 26 km/h face » en 30 px, quatre barres et le niveau, et la pastille du verdict en 24 px (vert, rouge ou gris). Il est caché sans vent du core. Le coin supérieur droit reste libre pour la série T.
- **`main.gd`** : création de `living_world`, `--living`, vent dans `_on_state_received`, pas par image dans `_process` et sur la caméra des menus. L'indicateur est ajouté aux éléments relevés par les captures de test.
- **Réglages** : `wind.mode`, `wind.speed_kmh` (pas de 5 km/h) et `wind.max_grade_offset_pct` (pas d'un point, de 0 à 8) sont ajoutés à la liste fermée de `settings.py` (O3), appliqués à la séance suivante, et affichés par la section « Réglages » du menu (O4). Les réglages d'O3 sont entiers, d'où le pas d'un point. La direction `wind.from_deg` reste dans `config.toml` : avec elle, le message `settings` dépassait 1 400 octets.
- **`[render] living`** (vrai par défaut) dans `config.py`, relayé par le lanceur en `--living=on|off` et lu par `engine_args.gd`. Faux : arbres immobiles, ni herbe, ni nuages, ni fonds d'ambiance, comme en 1.0. Le vent du core reste ressenti et affiché.
- **`visual_check.py`** : scènes `nuages` (pixels de nuage au-dessus de l'horizon) et `vent` (indicateur, textes, pastille rouge, place sous la colonne de gauche). Un pixel de nuage compte comme du ciel dans les vérifications existantes. Les images de référence sont à refaire (`--update-golden`) : le ciel a maintenant des nuages.
- **Tests** : `test_living_world.gd` (18 vérifications ; 0,09 ms par image ici en `low`, voisinage compris), `test_quality_presets.gd` (`--living`), `core/tests/test_settings.py` et `test_launcher.py`.
- **Reste sur le PC cible (le propriétaire)** : [`docs/RECETTE_P16.md`](../RECETTE_P16.md) (performance sur 20 min, vent sur le vélo, ambiance, `living = false`).

## 10. Retours de la première recette (27 octobre 2026)

Retours du propriétaire après la séance sur essai-69 ([RECETTE_P16.md](../RECETTE_P16.md)) : indicateur du vent conforme, nuages invisibles, vent trop fort, sons du vent et de la roue libre désagréables.

- **Nuages invisibles** : en Forward+ (le moteur du PC cible), Godot 4.3 mélange tout le ciel à la couleur du brouillard selon `fog_sky_affect`, qui vaut 1 par défaut ; le ciel entier prenait donc la couleur du brouillard. Le moteur Compatibility des tests ne le fait pas, d'où des tests verts. `RenderQuality.apply_fog` pose maintenant `fog_sky_affect` et `volumetric_fog_sky_affect` à `FOG_SKY_AFFECT` = 0 : le brouillard s'arrête au relief, comme le voulait le lot Y1 (« le ciel ne doit pas changer »). Pour que le relief qui disparaît dans le brouillard raccorde au ciel, `living_world.gd` passe la couleur du brouillard à `SkyClouds.build_material` comme couleur de l'horizon du ciel nuageux.
- **Volume** : vent `WIND_MAX_DB + 20 × 2 × log10(va / 60 km/h)` avec `WIND_MAX_DB` = −12 dB (au lieu de 0) : −43 dB à 10 km/h, −24 dB à 30 km/h, −15 dB à 50 km/h. Hauteur de 0,85 à 1,15 (au lieu de 0,8 à 1,3). Roue libre de −24 à −16 dB (au lieu de −10 à −4), « clac » à −12 dB (au lieu de −6).
- **Son du vent** : un grondement grave (bruit blanc passé deux fois dans un passe-bas à 160 Hz) et un souffle doux (passe-bande à 600 Hz, Q 0,6) qui respire lentement, en boucle de 4 s (au lieu d'une seconde de bruit passe-bande à 500 Hz, qui sifflait et se répétait à l'oreille).
- **Son de la roue libre** : 140 « tic » par seconde à `pitch_scale` = 1 (environ 30 km/h, la vitesse courante en roue libre), chacun un bruit sec de moins de 2 ms à deux résonances (3,2 et 5,4 kHz), d'intensité et de place légèrement irrégulières (± 8 % de période), au lieu d'un bip pur à 2,4 kHz qui devenait un sifflement aigu.
- Les deux boucles restent remplaçables par `~/OpenRide/Sounds/wind.ogg` et `freewheel.ogg`.
- **Tests** : `test_render_quality.gd` (le brouillard ne touche pas le ciel), `test_sky_clouds.gd` (couleur d'horizon transmise), `test_sound_model.gd` et `test_sound_player.gd` (nouveaux volumes, hauteur et rythme du cliquetis).
