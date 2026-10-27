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
