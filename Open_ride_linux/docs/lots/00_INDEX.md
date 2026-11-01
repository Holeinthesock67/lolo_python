# Lots de travail sous-traitables – index et règles communes

23 octobre 2026. Ces cahiers des charges permettent de confier une partie d'OpenRide à une autre IA (ou à un développeur) sans le contexte des conversations précédentes. Chaque lot est **autonome** : il dit quoi lire, quoi produire, quels fichiers toucher et comment la livraison sera recettée.

## 1. Liste des lots

Depuis le 31 octobre (lot X54), le tableau des lots n'est plus écrit ici : deux PR qui ajoutaient chacune leur ligne en fin de série entraient en conflit à chaque fusion. La ligne d'un lot (titre, langage, dépendances, taille, statut) est écrite **dans son cahier**, juste sous le titre, et le tableau complet se calcule :

```bash
python3 scripts/index_lots.py                    # tableau Markdown de tous les lots, triés par série
python3 scripts/index_lots.py --stats            # nombre de lots et de lots livrés par série
python3 scripts/index_lots.py --verifier         # code 1 si un cahier n'a pas sa ligne
```

- **Nouveau lot :** créer `LOT_<id>_<sujet>.md` avec, sous le titre, le bloc ci-dessous ; rien à ajouter dans ce fichier.
- **Changement de statut :** modifier la ligne dans le cahier du lot (avec sa section « Livraison » quand le lot est livré).
- **PR d'avant X54 qui modifie encore le tableau :** fusionner `main` ; au conflit sur ce fichier, reprendre la version de la branche (`git checkout --ours -- docs/lots/00_INDEX.md`), puis lancer `python3 scripts/index_lots.py --migrer`. Seules les lignes que la branche a ajoutées ou modifiées vont dans leur cahier ; l'introduction et les changements de `main` sont gardés.

```markdown
<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Titre court | Python | O4 | Petite | Prêt |
```

`core/tests/test_docs_coherence.py` vérifie que chaque cahier a sa ligne, qu'un lot « Livré » a sa section « Livraison » et qu'aucune ligne de lot n'est revenue ici. La CI ajoute le nombre de lots par série au résumé de chaque run.

Les paragraphes et le graphe ci-dessous décrivent les séries et l'ordre des lots ; ils ne changent qu'à la création d'une série.

**Restent en interne** (matériel nécessaire) :
- stabilité du Zwift Click (déconnexions spontanées) ;
- essais sur le vélo ;
- validation des fichiers FIT dans GoldenCheetah et Garmin Connect.

**À rédiger plus tard** (contrôle visuel ou décision du propriétaire nécessaire) :
- F2 : affichage du bandeau ERG, de l'histogramme et son du bip (s'appuie sur I6) : rédigé le 24 octobre sous le nom N7 ;
- G : contrat IPC v1.1 (listes de parcours et d'entraînements, état des appareils), affichage des menus pilotés au Click et écran de fin de séance (s'appuie sur I2, K5, K6 et K7) : rédigé le 24 octobre et découpé en N1 (contrat), N2 et N3 (core et client), N4 et N5 (modèles sans affichage), N6 (affichage) ;
- affichage des bots dans l'engine (après N9) et réglages modifiables depuis le menu (après N6) : rédigés le 25 octobre sous les noms O7 et O4 (réglages côté core : O3).

Leur forme dépendra des choix faits dans E1 et D.

**Ordre conseillé :** A, A2, B1, B2, C, D, F, H1 à H8 et I1 à I6 sont livrés (23 octobre). E1 est livré (PR #7, fusionnée le 24 octobre) ; reste l'essai sur le PC cible. I5 et I6 ont été fusionnés **avant** E1, contrairement à l'ordre prévu ; le conflit qui en résultait dans `engine/tests/` est résolu sur la branche d'E1 (les trois étapes rendu, thèmes et ERG s'enchaînent). Série J (audit J du 23 octobre au soir) : J2, J3, J6, J7 et J8 sont livrés, J4 et J5 en partie ; J1 et le reste de J4 et J5 peuvent démarrer en parallèle. J1 est le plus utile pour les essais sur le vélo (parcours compilés et essai ERG).

**Série K (23 octobre au soir) :** tous les lots sont livrés le 24 octobre (K6 et K7 faits directement le 23). K2 à K5 déposent leur test dans `engine/tests/unit/` (découverte par `run_engine_tests.sh`, lot K1). Les lots K préparent E3 (K2, K3), E4 (K3, K4) et G (K5, K6, K7) sans les remplacer : le rendu, l'affichage et le contrat IPC v1.1 restent internes.

**Série N (24 octobre, après E3 et E4) :** lanceur et menus (ancien lot G), ERG à l'écran (ancien F2), reprise après un plantage du core, bots, packs de thèmes et compilation au lancement. N1 (contrat IPC v1.1) est une décision du propriétaire et bloque N2, N3, N5 et N8. N6 et N7 restent internes : ils modifient `main.gd` et se recettent à l'œil. Délégables tout de suite : N4, N9, N10 et N11 ; après N1 : N2, N3, N5 et N8. Fichiers partagés : `ipc_client.gd` et `fake_core.py` (N3 seul) ; `session.py` (N2, N8, N9 : à faire l'un après l'autre) ; `launcher.py` (N8, N11, puis N6) ; `__main__.py` (N8, N9) ; `docs/contracts/ipc/state.schema.json` (N1, puis N9 pour `bots`). N4 et N5 ne touchent que leur propre script et leur test. Ajout du 25 octobre (demande du propriétaire) : N12 enregistre le matériel trouvé dans la configuration locale, délégable tout de suite (`session.py` aussi, après N2) ; N13, interne, en fait une section « Appareils » du menu après N6. N14 (même demande : lancer sans ligne de commande) complète L8, N6, N11 et N13 : `launcher.py` après N11 et avant N6.

**Série O (25 octobre, dernière avant la 1.0) :** ce qui manque encore après la série N pour une version 1.0 jouable (liste du 25 octobre). Délégables : O1 tout de suite ; O2 après N3 ; O3 après N12 ; O5 après N11 ; O6 après N14. Internes : O4 (contrat et menu), O7 (bots à l'écran, facultatif) et O8 (recette sur le matériel et publication, par le propriétaire). Fichiers partagés : `config.toml` écrit par N12 puis O3 (module commun `config_writer.py`) ; révision du contrat de N13 reprise par O4 puis O7 (l'un après l'autre) ; `catalog.py` (O5 seul) ; `README.md` (O6 en dernier). Les fins de J4 (#50) et J5 (#51) restent ouvertes ; J4 compte pour l'installation hors du dépôt (O8). Ajouts du 25 octobre au soir (demande du propriétaire : entraînement « comme GoldenCheetah ») : O9 formats `.erg`/`.mrc`, O10 test de FTP, O11 plans d'entraînement, O13 modèle des courbes en direct, O15 bibliothèque de parcours, O16 pack de cols célèbres (délégables) ; O12 menu de ces fonctions et O14 courbes à l'écran (internes). Fichiers partagés : `workout.py` (O9 seul ; O10 et O11 le lisent), `journal.py` (O10 puis O11), `catalog.py` (O5 puis O15), révision du contrat reprise par O4, O12 puis O7.

**Série P (25 octobre, après la 1.0) : décor vivant, vent et aspiration.** Demande du propriétaire : rendre le décor plus vivant, rendre le vent et l'aspiration physiques avec leur indicateur, améliorer le son du vent et de la roue libre. Les lots devaient attendre la publication de la 1.0 (O8) ; le 26 octobre, le propriétaire a lancé la série sans l'attendre (« Lance les lots O et P »), ce qui ne change rien à la 1.0 puisque le vent reste coupé par défaut et que chaque animation se coupe par préréglage. Jour, nuit et saisons (P7, P18, P19) sont reportés à la **version 2.0** par décision du propriétaire, comme les packs de textures selon les performances (P20, demande du même jour). P1 (contrat) est une décision du propriétaire et bloque le reste. Délégables : P2 à P15, P18, P20 et P21, dans l'ordre du graphe ; internes : P16 et P17 (et P19 en 2.0), qui branchent les lots dans `main.gd` et font la recette sur le matériel. Ordre conseillé, du plus rentable au plus coûteux : P2, P4, P5, P6, P9, P10, puis P16 ; ensuite P3, P8, P11 à P15 et P21, puis P17. **Budget de rendu :** sur le PC cible (GTX 1060), qualité `low`, toute la série activée, 55 images/s ou plus en moyenne et temps d'image p99 sous 25 ms (ligne `[perf-rendu]` d'E3) ; chaque lot délégable mesure le coût de sa mise à jour par image dans son test, et tout se coupe par `living(preset)` (P4) ou `[render] living`. Fichiers partagés : `session.py` (P2 puis P3) ; `quality_presets.gd` (P4, puis la clé `passersby` de P21) ; `theme_render_params.gd` (P6, P7) ; `tree_sway.gdshader` (P5 puis P18) ; `sound_player.gd` (P9, P10, P13, P15, P21, l'un après l'autre) ; `crowd_renderer.gd` (P15 puis P21) ; `quality_presets.gd` reçoit aussi la clé `passersby` de P21 ; `weather_particles.gd` et `ambience_model.gd` (P8 et P9, puis P18) ; `osm_layers.gd` et `water_mesh.gd` (P12 seul) ; `main.gd`, `hud_view.gd` et `osm_streamer.gd` (P16, P17, P19 seulement). Les bots à l'écran restent dans O7 ; P3 leur ajoute l'abri.

**Série Q (25 octobre, retours de l'essai sur le HomeTrainer) :** six lots tirés de l'essai de 1 h 27 sur le circuit synthétique `essai-69` (séance trop dure, pente qui paraît faible à l'écran, environ 22 s avant que la résistance se relâche, FC relayée figée, boîtier gauche du Click muet). Aucun ne demande de matériel pour sa recette automatique ; chacun se termine par un essai court du propriétaire sur le PC cible. Q1 ajoute la commande `set_difficulty` au contrat (v1.2, accepté par le propriétaire le 25 octobre, avec un défaut à 50 % et un réglage par curseur dans le menu, sans bouton du Click) ; le curseur lui-même est ajouté à O3 et O4. Q2 ne touche que l'engine et n'exagère que l'affichage, jamais la physique. Fichiers partagés : `session.py` (Q1 puis Q4) ; `ftms_driver.py` (Q3 puis Q5) ; `config.py` (Q2 à Q6, sections différentes) ; `main.gd` (Q2 seul). Q3 avant Q4 permet de mesurer le gain sur le trainer.

**Série T (2.0, mode classique : sprints, montées chronométrées, bonus, bots à profil) :** plan dans `docs/2.0/PLAN_SERIE_T.md` (questions T-Q1 à T-Q6 tranchées le 25 octobre). La série commence en principe après la 1.0, mais quatre lots sont des modules purs du core, testables sans contrat ni engine ni matériel, et ont été avancés le 26 octobre à la demande du propriétaire : T2 (détection), T4 (chronométrage), T6 (bonus) et T16 (écarts en temps de passage). Aucun ne modifie `session.py`, l'IPC ou le format `.world` : leur branchement dans la séance vient avec le contrat T1. **Numérotation du contrat :** la révision 1.2 a été prise par Q1 et N13 ; la série P passe donc en 1.3 (P1) et les séries R, T et V en **1.4**, en un seul lot de contrat, T1 (décision D4 du 27 octobre ; les anciens lots R1 et V1 y sont réunis). T5 (records et classement local) et T14 (points et maillots) ont suivi le 27 octobre, avec les décisions du propriétaire du même jour. Le contrat T1 (révision 1.4) est validé et fusionné le 27 octobre (PR #392), et T3 écrit la couche `segments` dans le compilateur. Cahiers T7 (branchement dans la séance, qui reprend le supplément vent et aspiration avec le CdA courant), T8 à T11 et T15 rédigés le 27 octobre ; T8, T9, T10 et T15 se codent d'abord et se valident ensemble à la recette T11 (décision du 27 octobre). Restent à rédiger T12 et T13, qui attendent le modèle W'bal de la série R (lot R2).

**Série S (25 octobre, performances du rendu) :** demande du propriétaire d'explorer l'optimisation du moteur graphique en ne modélisant pas ce qui est invisible pour le cycliste (au-delà du brouillard, derrière la caméra, masqué par le relief, ombres hors champ). S1 commence par une mesure au banc simulé (`engine/tests/sim_bench.py`) et ne garde que les pistes qui font gagner des images par seconde sans changement visible. Fichiers partagés : `tree_renderer.gd` (O1 d'abord), `terrain_tiles.gd` (Q2 d'abord).

**Série Y (27 octobre, fin de projet) : rendu et IA des bots.** Recherche et propositions : `docs/RECHERCHE_GODOT_PERFORMANCE_GRAPHISMES.md` (PR #355). Décisions du propriétaire du 27 octobre : série validée ; ordre Y1, Y2, puis Y4, Y6 et Y3, puis Y5 et Y7, puis Y8, Y9 et Y10 ; **Y1 avancé** (tout de suite, avant S1, mêmes fichiers) avec un brouillard opaque à 4 km en `low`, 6 km en `medium` et 9 km en `high` ; migration directe vers Godot 4.7.x (Y2) au début de la phase finale, avant les autres optimisations ; préréglage de référence `medium` (utilisé au quotidien par le propriétaire) ; priorités de l'habillage (Y8) : toits et façades, étalonnage, marquages ; imposteurs des arbres écrits par nous, sans extension externe (Y5) ; essai du moteur Mobile maintenu (Y7) ; résolution adaptative acceptée (75–85 % avec FSR 1.0 quand le GPU sature, Y6) ; bots affichés avec environ 0,1 s de retard pour le lissage (Y9) ; bots réalistes, avec attaques, fatigue et abri calculés dans le core (Y10). Le reste de la série vient après tous les autres lots et chaque lot mesure avant et après au banc simulé avec la sonde X13, sous les seuils d'X2, avec l'endurance X16 à la fin. Une piste n'est retenue que si elle gagne au moins 3 % d'images/s ou 1 ms de p99. Les cahiers de Y2 à Y10 ont été rédigés le 28 octobre, à la demande du propriétaire (tous les cahiers manquants) ; Y6 est réécrit après la consigne du 27 octobre au soir (résolution native, cahier Y13 de la PR #446) et gardé sous cette forme par le propriétaire le 28 octobre. Les issues #357 (Y1) à #366 (Y10) renvoient au suivi #48, qui a atteint la limite de 100 sous-issues de GitHub. Fichiers partagés : `quality_presets.gd`, `render_quality.gd` et `world_streamer.gd` (Y1, puis S1, puis Y4 et Y6) ; `tree_renderer.gd` (O1, S1, puis Y5) ; `osm_streamer.gd` et `building_mesh.gd` (S1, Y3, puis Y8).

**Série GP (31 octobre, version 4.0 proposée) : mode « Grand Prix des objets ».** Demande du propriétaire du 31 octobre : un mode type jeu de kart, avec des objets qui ont les effets de la peau de banane, des carapaces ou de l'étoile. Plan et étude : `docs/4.0/PLAN_SERIE_GP.md` (questions ouvertes au §10, réponses par défaut appliquées). Mode à part (`grandprix`), SIM seulement ; treize objets propres à OpenRide (bidon glissant, musettes, nuage d'orage, super-forme, sonnette, voiture d'équipe…), chacun désactivable au menu ; boîtes de ravitaillement et tirage selon le retard sur le premier ; effets sur la vitesse virtuelle seulement, jamais sur la pente envoyée ; effets ajoutés à la table unique de TT2 (pas de second système). Délégables : GP1, GP2, GP3, GP5 ; GP4 attend AS6 et TT4 ; GP6 (maquettes) est validé par le propriétaire avant GP7 et GP8 ; GP9 interne ; GP10 attend le peloton d'environ 12 bots prévu après Y18 ; GP11 recette du propriétaire. Fichiers partagés : `powerups.py` (TT2, puis GP1) ; `session.py` et `settings.py` (GP2 seul) ; `bots.py` (GP3, puis GP10) ; `hud_view.gd` et `summary_view.gd` (GP8) ; `menu_flow.gd` (GP9). Chaque lot d'affichage est mesuré en low, medium et high, captures validées avant fusion.

**Série AS (29 octobre) : aspiration plus fine.** Demande du propriétaire du 29 octobre (« une gestion plus exhaustive et fine du drafting », puis « abri derrière les véhicules ou les groupes à intégrer »). Proposition : https://claude.ai/artifact/3JHTrS62DRBMQiSfABva9s. La lettre G étant déjà prise (ancien lot G, devenu la série N), la série s'appelle AS. Décisions du propriétaire du 29 octobre : AS1 en version 1.x, AS2 à AS7 en version 2.0 ; placement automatique dans la roue activé par défaut (AS2) ; abri derrière un véhicule lent activé par défaut et désactivable dans le menu (AS6) ; plafond de 55 % au cœur d'un groupe (AS4). Ordre conseillé : AS1, AS2, puis AS4 et AS7, AS6, AS3 et AS5. Principe commun : la physique ne dépend jamais de l'affichage ; véhicules et cyclistes du décor proches du cycliste sont calculés par le core et envoyés à l'engine (AS6, AS7), le préréglage ne règle plus que le décor lointain. Chaque lot qui touche l'affichage montre ses captures en low, medium et high au propriétaire avant la fusion. Fichiers partagés : `draft.py` et `session.py` (tous, l'un après l'autre) ; `bots.py` (AS1, AS2, AS4) ; contrat `state` (AS2, AS5, AS6, AS7, même révision de la 2.0) ; `draft_gauge.gd` (AS6, AS7).

**Série MJ (29 octobre, version 2.0) : profils de joueurs et profil d'essai.** Plan : `docs/2.0/PLAN_SERIE_MJ.md` (étude du 29 octobre, réponses du propriétaire au §10, maquettes A à F validées). Un profil = un dossier `~/OpenRide/Profils/<id>/` ; le profil d'essai `_essai` est un profil comme les autres où les séances simulées comptent, jamais par défaut, signalé « ESSAI ». Ordre : MJ0, MJ1, MJ2, MJ3 (profil d'essai utilisable, sert à tester la série V), MJ6 en parallèle, puis MJ4, MJ5, MJ7, MJ8, MJ9, MJ10. Ajustement du 29 octobre : la « Session simulée » passe sur `_essai` dès MJ2. Fichiers partagés : `profiles.py` (MJ1, puis MJ2, MJ4, MJ7) ; `session.py` (MJ1, MJ2, puis MJ7) ; `launcher.py` (MJ1, MJ2, MJ5, MJ7) ; `progression.py` (MJ2) ; `config.py` et `settings.py` (MJ4).

**Série CT (29 octobre, version 5.0) : mode « Course tactique ».** Demande du propriétaire du 29 octobre : étude du document de conception « Triangle Tactique Unifié » (réserve W′ symétrique et Burnout, sillage et catapulte, pacte de relais et capacités, virages et bifurcations). Plan : `docs/5.0/PLAN_SERIE_CT.md`. La lettre TT étant prise par les power-ups de la 4.0, la série s'appelle CT. Décisions du propriétaire du 29 octobre : nouveau mode `tactical`, SIM seulement, et socle réaliste dans le classique (W′ visible en option, bots réactifs, freinage automatique en virage) ; bifurcations sur des circuits générés d'abord, monde ouvert ensuite ; capacités payées par les relais avec les effets de la 4.0 ; Burnout = puissance prise en compte plafonnée à 70 % de la CP pendant 8 s, jamais la résistance ; effets flashy et exagérés façon cartoon, charte propre (CT9) validée sur maquettes avant tout code. Chaque lot d'affichage est mesuré en low, medium et high.

**Série DS (31 octobre, version 3.0 proposée) : mode « Dernier survivant ».** Demande du propriétaire du 31 octobre : le joueur affronte les bots et, à chaque arche, le dernier arrivé est éliminé, jusqu'au dernier en course. Plan et étude : `docs/3.0/PLAN_SERIE_DS.md` (questions ouvertes au §9, réponses par défaut appliquées). Mode à part (`survivor`), SIM seulement, physique et aspiration du classique, sans bonus, segments ni fantôme ; une arche par adversaire tous les 1 à 3 km ; tout se règle dans le menu. Délégables : DS1, DS2, DS3 ; DS4 (maquettes) est validé par le propriétaire avant DS5 et DS6 ; DS7 interne ; DS8 attend le peloton d'environ 12 bots prévu après Y18 ; DS9 recette du propriétaire. Fichiers partagés : `session.py` et `settings.py` (DS2 seul) ; `bots.py` (DS3, puis DS8) ; `segment_markers.gd` (DS5) ; `hud_view.gd` et `summary_view.gd` (DS6) ; `menu_flow.gd` (DS7). Chaque lot d'affichage est mesuré en low, medium et high, captures validées avant fusion.

**Série WF (31 octobre, version 5.0) : trainer en Wi-Fi et mesures rapides.** Remarque du propriétaire du 31 octobre (« le race mode en wifi […] rafraîchir la résistance plus rapidement »), mise en 5.0 le même jour. Plan : `docs/5.0/PLAN_SERIE_WF.md`. Le retard ressenti vient du frein du trainer (1 à 4,6 s) bien plus que du Bluetooth (estimé 30 à 100 ms) : WF1 mesure d'abord la liaison, et le pilote Direct Connect (WF2 à WF6) n'est lancé que si le critère du §4 du plan est rempli. Les leviers de réalisme côté core relèvent de la série RC.

**Série R (version 2.0, cahiers rédigés le 26 octobre) : mode Cyber-Rogue.** Plan, décisions du propriétaire, corrections du GDD et questions ouvertes R-Q1 à R-Q10 : `docs/2.0/PLAN_SERIE_R.md`. La série démarre après la 1.0 ; les issues des lots seront ouvertes à ce moment-là, sous l'issue de suivi #117. Seul le script de R0 (même outil que X5) peut être fait avant. Le contrat 1.4 (lot T1, commun aux séries R, T et V) est une décision du propriétaire et bloque R8 et l'engine. Délégables : R2, R3, R4, R5, R6, R7, R9, R15, R16, le script de R0 le modèle de R11 et les shaders de R17 ; internes : R8, R10, R12, R13 (et le contrat T1) ; propriétaire : R0 (essai) et R14. Les modules du jeu sont dans un nouveau paquet `rogue` du core (un fichier par lot), avec une seule table de valeurs `RogueBalance` (`rogue/balance.py`, complétée par R2 à R6 et R15, l'un après l'autre, puis chargée depuis `balance.toml` par R7). Fichiers partagés : `session.py`, `zwift_click.py` et `config.py` (R8 ; R2 ajoute seulement la section `[rogue]`) ; `main.gd` (R10 puis R13) ; `rogue.tscn` (R10, puis R11 et R12) ; `menu_model.gd` (R13).

**Série V (26 octobre, version 2.0) : progression, équipement et avatar.** Plan `docs/2.0/PLAN_SERIE_V.md` ; V-Q4 réglée le 26 octobre (révision 1.4 en un seul lot de contrat, T1, décision D4 du 27 octobre) ; questions V-Q5 à V-Q13 réglées le 27 octobre (V-Q10 remplacée par les pièces à l'effort). Délégables : V2 tout de suite, puis V3 et V4, puis V3b : modules purs du core, sans effet sur la séance tant que V11 n'est pas livré (V-Q5). Le contrat 1.4 (lot T1, commun aux séries R, T et V) est une décision du propriétaire et bloque V11, V6, V8 et V9 ; V11, ajouté au découpage du plan, branche les modules dans la séance. V5 attend les séries T et R. Fichiers partagés : `progression.toml` (V2, puis V3 pour le catalogue, puis V3b pour les pièces) ; `progression.py` (V2, puis V5) ; `session.py` et `ipc_server.py` (V11 seul) ; `main.gd` (V6) ; `menu_model.gd` (V8) ; `summary_view.gd` (V9) ; `sound_player.gd` (V7, après P10).

**Série W (26 octobre, version 2.0) : monde ouvert généré en direct.** Plan : `docs/2.0/PLAN_SERIE_W.md` (questions W-Q1 à W-Q5 tranchées par le propriétaire le 25 octobre, PR #159). Cahiers rédigés le 26 octobre. W0 (outil de mesure, sans effet sur le jeu) peut se faire tout de suite ; W1 (contrat) est une décision du propriétaire et bloque le reste. Le générateur vit dans le compilateur (nouveau sous-paquet `worldgen` du paquet `openride_compiler`), dans un processus séparé `openride-worldgen` ; le core reste sans numpy. Numérotation : la révision de l'IPC est la première libre à la fusion de W1 (1.5 si P1 prend 1.3 et les séries R, T et V 1.4) ; le format `.world` prend de même le mineur libre suivant. Délégables : W2 à W8 et W13 à W15 (W0 pour le script) ; internes : W1, W9 à W12 ; propriétaire : W16. Fichiers partagés : `compiler/src/openride_compiler/cli.py` (W0, W2, W3, l'un après l'autre) ; `compiler/pyproject.toml` (W3 extra `worldgen`, W8 et W15 points d'entrée) ; `worldgen/process.py` (W8 puis W13) ; `osm_layers.py` (W7 seul, fonctions rendues publiques) ; `core/src/openride_core/config.py` (W2 section `[open_world]`, puis W9) ; `session.py` et `ipc_server.py` (W9, puis W11 et W14) ; `main.gd` et `ipc_client.gd` (W10, puis W11 et W12). Réseau : seuls W0, W3, W8, W11 (Nominatim) et W13 accèdent à internet, jamais dans les tests ; rien de téléchargé n'entre dans le dépôt.

**Série U (27 octobre, version 3.0) : biomes, textures régionales, saisons par biome et option « gravel ».** Plan : `docs/3.0/PLAN_SERIE_U.md` (U-Q1 à U-Q5, U-G1 et U-G2 tranchées le 25 octobre ; U-Q6 à U-Q13 posées et toutes validées le 27 octobre au §11). La série commence après la 2.0 : ses issues (#331 à #352, sous le suivi #48) portent l'étiquette `bloqué`. U1 (contrat) est une décision du propriétaire et bloque le reste ; U0 consigne les décisions déjà prises. U19 (parcours fictifs) vient juste après U1 : il sert de données de test à tous les lots de rendu. Premier jalon : U2 à U7, U9, U11, U13 à U15, intégrés par U17 et recettés par U18 ; l'option « gravel » (U20 à U22, avec U16 pour le menu) avance en parallèle. Délégables : U2 à U15 et U19 à U22 ; internes : U1, U16, U17 ; propriétaire : U18. **Numérotation :** IPC, première révision libre à la fusion de U1 (1.6 si la série W prend la 1.5) ; format `.world`, mineur libre suivant celui de W1 ; thème 2.0. Fichiers partagés : `terrain_biomes.gdshader` (U6, puis U8 et U14) ; `biome_model.gd` (U5, puis U13 et U14) ; `vegetation_placer.gd` et `tree_renderer.gd` (U7 seul, après O1) ; `ambience_model.gd` et `sound_player.gd` (U11, puis U22) ; `weather_particles.gd` (U22 seul) ; `osm_layers.gd` (U9 seul) ; `theme_loader.gd` (U5 seul) ; `engine/themes/default/theme.json` (U15 seul) ; `compiler/src/openride_compiler/cli.py` (U2, U3, U4, U15, U20, l'un après l'autre) ; `route_stats.py` (U20, copie exacte core et compilateur) ; `session.py` et `config.py` (U21, puis U16) ; `main.gd` (U17 seul). Réseau : seuls U2 (WorldCover), U3 et U20 (Overpass) et U15 (packs) accèdent à internet, jamais dans les tests ; rien de téléchargé n'entre dans le dépôt, et aucune coordonnée plus fine que le degré.

**Série X (26 octobre, outils de test) :** les 31 outils et programmes de test qui manquent pour mener le projet jusqu'à la 1.0, puis aux versions 2.0 et 3.0 (plan du 26 octobre : besoin, mesure, lieu d'exécution, priorité, taille). Une issue par lot, #199 (X1) à #229 (X31), sous le suivi #48 ; les cahiers des lots restants (X3 à X31) et des lots X32 à X38 ont été rédigés le 28 octobre, à la demande du propriétaire (« rédige les cahiers des charges manquants puis finalise la réalisation de tous les outils »), après l'audit de couverture des tests du même jour et les propositions des fils de travail. Ordre : X1 (tests de `main` au vert), X25 (pire trame IPC), X23 (scanner de confidentialité), puis les autres lots P0 : X2, X4, X5 (banc de latence du trainer, outil de l'essai R0), X8, X13, X16 et X29. Les essais matériels se font sur le PC cible.

Lots de la série X (P0 = avant la 1.0, P1 = pour la 1.0, P2 = 2.0 ; X1, X2, X4, X5, X8, X13, X16, X23, X25 et X29 livrés le 27 octobre sans cahier, leur description est dans `docs/OUTILS_DE_TEST.md`) :

- X1 : remettre la CI de main au vert (Cloud, P0, issue #199) ;
- X2 : séparer les tests de budget de temps des tests de fonction (Cloud + PC, P0, issue #200) ;
- X3 : rapport d'instabilité et de durée des tests (Cloud + PC, P1, issue #201) ;
- X4 : recette du PC en une commande (PC, P0, issue #202) ;
- X5 : banc de latence du trainer par paliers (Vélo, P0, issue #203) ;
- X6 : trainer simulé réaliste (Cloud, P1, issue #204) ;
- X7 : latence appui Click → commande et → écran (Vélo, P1, issue #205) ;
- X8 : recette guidée du Click (30 min) (Vélo, P0, issue #206) ;
- X9 : recette de la fréquence cardiaque (Vélo, P1, issue #207) ;
- X10 : coupures volontaires, attendu contre obtenu (Vélo, P1, issue #208) ;
- X11 : contrôle d'un FIT de séance réelle (PC, P1, issue #209) ;
- X12 : analyse automatique d'une séance réelle (PC, P1, issue #210) ;
- X13 : sonde de performance du moteur (PC, P0, issue #211) ;
- X14 : parcours de référence et alerte de régression (PC, P1, issue #212) ;
- X15 : saccades et temps de démarrage (Cloud + PC, P1, issue #213) ;
- X16 : endurance 1 h et fuites (PC, P0, issue #214) ;
- X17 : gigue de la boucle physique et de l'IPC (Cloud + PC, P1, issue #215) ;
- X18 : contrôle d'apparition et comparaison avant/après (Cloud + PC, P1, issue #216) ;
- X19 : micro-banc par image pour le décor vivant (Cloud, P2, issue #217) ;
- X20 : non-régression visuelle, version 2 (Cloud + PC, P1, issue #218) ;
- X21 : tour visuel guidé (PC, P1, issue #219) ;
- X22 : lisibilité du HUD à 2 m (Cloud, P2, issue #220) ;
- X23 : scanner de confidentialité (Cloud + PC, P0, issue #221) ;
- X24 : audit des dépendances (Cloud, P2, issue #222) ;
- X25 : pire trame IPC et matrice des révisions (Cloud, P0, issue #223) ;
- X26 : fuzz des fichiers d'entrée (Cloud, P2, issue #224) ;
- X27 : cycliste virtuel pour les essais simulés (Cloud, P1, issue #225) ;
- X28 : réseau dégradé pour le monde ouvert (Cloud, P2, issue #226) ;
- X29 : installation sur un système vierge (Cloud + PC, P0, issue #227) ;
- X30 : tableau de recette 1.0 (Cloud, P1, issue #228) ;
- X31 : pente maximale face à Garmin Connect (PC, P2, issue #229) ;
- X32 : garde-fou de la qualité réellement appliquée (Cloud, P0) ;
- X33 : séance simulée de la série T et des boutons de l'ERG (Cloud, P0) ;
- X34 : hygiène des suites (Cloud, P1) ;
- X35 : fiabilité du banc simulé (Cloud + PC, P0) ;
- X36 : pré-vol avant une séance vélo (PC, P1) ;
- X37 : persistance de tous les réglages (Cloud, P1) ;
- X38 : couleurs du thème (Cloud, P2) ;
- X39 : écart de progression avant/après une PR (Cloud + PC, P2, proposition du fil V5).

Répartition du 28 octobre (règle du coordinateur : les fils graphiques livrent eux-mêmes leurs petits outils locaux) : S1 livre la détection des « pop », les captures tous les N mètres, la colonne `culled_near` et `compare_captures.py` (X18) ; la série U livre la comparaison des vitrines des biomes et des sols, le contrôle d'exposition et les coutures de tuiles ; Y8 livre le test de rendu des façades et le détecteur de pixels isolés ; la série P livre les comptes du décor dans le rapport du banc, les sons du décor joués et le décor figé en pause ; la série R livre la run Cyber-Rogue simulée de bout en bout, son banc visuel et la cohérence entre sons et événements ; le banc des menus (clic, clavier, souris, Garage et Cyber-Rogue) est fait par son propre fil. Ordre de réalisation : X32, X33, X34, X35, X36, X14, X37, X38, puis X20, X22, X27, X12, X15, X3, puis les autres.

**Série N, suite (27 octobre, version 1.x) : réglages de séance au menu.** Demande du propriétaire (décision D11 de l'audit de cohérence) : le demi-tour sur la route (N17) et le réglage des bots (N18), envisagés par la SRS §14 « par appui long », se font dans les menus (écran de pause, réglages), sans geste du Click, pour garder le plan de boutons commun (spécification générale §7.1). Les deux lots appartiennent à la série N (menus) mais à la version 1.x : ils attendent la publication de la 1.0. Fichiers partagés : `session.py` (N17 puis N18), l'écran de pause de l'engine (N17 puis N18).

**Série M (24 octobre, après le Bluetooth simulé de la PR #74) :** neuf lots Python, tous délégables et testés sans matériel grâce au simulateur (`docs/SIMULATION_BLE.md`). Aucun ne touche l'engine, réservé à E2, E3 et E4. Fichiers partagés : `__main__.py` (M3 seul) ; `ble_sim.py` et `sim_scenarios.py` (M2 seul ; M1, M5 et M6 les lisent) ; `test_ble_sim.py` (M1 seul ; M4 et M6 ont leur propre fichier de tests) ; `compiler/pyproject.toml` (M7 `dependencies`, M9 extra `dev`) ; `docs/SIMULATION_BLE.md` (M1, M2, M5, M6, sections différentes). M6 ne vérifie que des invariants vrais avant et après M1. Les noms « M1 » à « M9 » du tableau des constats de l'audit du 23 octobre (`docs/AUDIT_2026-10-23.md` §3) n'ont aucun rapport avec ces lots.

**Série L (24 octobre) :** tous les lots L1 à L8 sont livrés le 24 octobre (PR #64 à #71). L1 à L5 (GDScript, sans affichage) déposent leur test dans `engine/tests/unit/` ; L4 modifie aussi `engine_args.gd` et `launcher.py` ; L6 à L8 enrichissent le journal (cible ERG), le core (`history`) et le bureau (`.desktop`).

**Lots H, I, J, K, L et M (23 et 24 octobre) :** ces séries sont faites pour une IA externe : recette entièrement automatique, sans essai sur le matériel (série N : seulement les lots marqués « Oui »). Aucun lot des séries I, J, K, L et M, ni aucun lot délégable de la série N, ne touche `main.gd` ni les scripts de rendu d'E1. Fichiers partagés dans la série J : `.github/workflows/openride.yml` (J5 puis J8) ; J1 touche `__main__.py`, déjà modifié par J3 (livré) ; `docs/SUIVI_AVANCEMENT.md` est commun à tous (une ligne chacun, à fusionner à la main).

**Lots H, détail :** petits lots hors du chemin critique, recettés uniquement par des tests automatiques, sans essai sur le matériel. Ils peuvent être confiés en parallèle : aucun ne partage de fichier de code avec un autre (seuls `docs/SUIVI_AVANCEMENT.md` et parfois `README.md` sont communs, à fusionner à la main). H3 est le seul à toucher `config.py`, `session.py` et `__main__.py` ; H5 et H4 touchent tous deux `core/pyproject.toml` (sections différentes).

Les lots livrés gardent leur cahier des charges, complété d'une section « Livraison » qui liste les écarts assumés.

```text
A ──► B1 ──► B2 ──┬──► E1 ──┬──► I5 ──► E2
│                 │          └──► I6 ──► F2
└──► D ───────────┘
B2 ──► I2 ──► G       B2 ──► I3 ──► I4 ;  I3 ──► E4
C ──► F ──► H8        H1 à H8, I1 : indépendants
J4, J5 : indépendants (J1, J2, J3, J6, J7, J8 livrés)
K6, K7, K8 : indépendants (livrés)
E1 ──► K1 ──► K2, K3, K4, K5 (livrés ; préparent E3, E4 et G)
E2 ──► E3 ──► E4 ;  K2, K3, L3, L4 ──► E3 ;  K4, L1, L2, L5 ──► E4
K1 ──► L1, L2, L3, L4, L5 ;  L6, L7, L8 : indépendants
M1 à M9 : indépendants (simulateur Bluetooth de la PR #74)
N1 ──► N2, N3, N5, N8 ;  N2, N3, N4, N5 ──► N6 ;  E3 ──► N6, N7
N4, N9, N10, N11 : indépendants (prérequis livrés)
N6, N12 ──► N13 ;  N12 : indépendant (M3 livré)
N11 ──► N14 ──► N6
E3 ──► O1 ;  N3 ──► O2 ;  N12 ──► O3 ──► O4 ;  Q1 ──► O4 ;  N6, N13 ──► O4 ;  N11 ──► O5 ;  N14 ──► O6 ;  N6, N9 ──► O7
O9 ──► O11 ;  O3 ──► O10 ──► O11 ;  O5 ──► O15 ──► O16 ;  N6, O4, O10, O11, O15 ──► O12 ;  O13, N7 ──► O14
N, O1, O2, O6 ──► O8 (recette 1.0)
O8 ──► P1 ──► P2 ──► P3 (avec N9) ;  P1 ──► P4 ──► P5, P6, P8, P9, P10, P11, P12, P14
P9 ──► P13 ;  P9, P14 ──► P15 ──► P21 ;  P2, P4, P5, P6, P9, P10 ──► P16 ──► P17 (avec P3, P8, P11 à P15, P21, O7) ;  P11, P17, P21 ──► P23 ;  I3, I4, K4, T1 ──► P22 ;  P22, P23, Y14 ──► P24 ;  P13, P17, P22, Y14 ──► P25 ──► P26 (avec P6, P8) ──► P29 (avec P12 ; mer avec U9) ;  P22 à P26, P28, P29 ──► P27 ;  P26, U5 ──► P31 ;  P25, P28 ──► P32
Q1 ──► Q4 ;  Q3 ──► Q5 ;  Q2, Q6 : indépendants
O1, Q2 ──► S1
Version 2.0 : Q3, Q4 ──► R0 ;  P1, PR #287 ──► T1 ;  R3 ──► R4 ;  R0, R2, R3, R4 ──► R5 ──► R6 ──► R15 ──► R7 ;  T1, R6, R15 ──► R8
             R6, V2, V3b, V4 ──► R9 ;  T1 ──► R17 ──► R10 ──► R11, R12 ;  R17 ──► R13 ;  T1, R8, R10, R11, N6, O4 ──► R13 ──► R14
Version 2.0 : P17 ──► P7 ;  P7, P17 ──► P18 ──► P19 ;  N10, O3, P17 ──► P20
Version 2.0, série V : V2 ──► V3, V4 ──► V3b ;  T1, V2, V3, V3b, V4 ──► V11 ;  T1 ──► V6 ──► V7 ;  V6, V11, N6 ──► V8 ;  V11, N4 ──► V9 ;  V11, T4, T5, T13, T14, R9 ──► V5 ;  V2 à V9, V11 ──► V10 ;  V6, O17 ──► V12
Version 2.0, série W : W0 ──► W1 ──► W2 ──► W3 ──► W4 ──► W5, W6 ;  W2, W3, W5 ──► W7 ;  W6, W7 ──► W8 ──► W9 ──► W14
W1 ──► W10, W12, W15 ;  W1, W3 ──► W11 ;  W2, W7 ──► W13 ;  W9, W10, W11, W12 ──► W16
Version 2.0, série T : T2, T6, T16 : indépendants (avancés) ;  T2 ──► T4 ;  P1 ──► T1 ──► T3, T8, T9 ;  T4, N9 ──► T5 ;  T1 à T6, T14, T16, P2, P3 ──► T7 ──► T8, T9, T10 ;  T8, T9 ──► T17 ;  O7, T9, T16 ──► T15 ;  R2 ──► T12 ──► T13 ;  T3 à T10, T12 à T15, T17 ──► T11
Version 3.0, série U : U0 ──► U1 ──► U2, U3, U4, U5, U15, U19, U20, U21 ;  U5 ──► U6, U7, U10, U11, U12, U13 ;  U6 ──► U8 ;  U3, U6 ──► U9 ;  U4, U6 ──► U14
U19 ──► U22 ;  U2, O4 ──► U16 ;  U5 à U15, U19, U22 ──► U17 ──► U18 ;  U19 à U22 ──► U18
Version 4.0, série GP : TT2, AS2, T12, T13 ──► GP1 ──► GP2, GP3, GP6 ;  GP1, GP3 ──► GP5 ;  GP1, AS6, TT4 ──► GP4 ;  GP2, GP6 ──► GP7, GP8 ;  GP2 ──► GP9 ;  GP2, GP3, Y18 ──► GP10 ;  GP3, GP5, GP7, GP8, GP9 ──► GP11
Série AS : P3, T12, T13 ──► AS1 (1.x) ──► AS2 ──► AS3, AS4, AS6 ;  AS2, AS6 ──► AS7 ;  P3, P10, P17 ──► AS5
Série MJ : MJ0 ──► MJ1 ──► MJ2 ──► MJ3 ;  MJ0 ──► MJ6 ;  MJ1 ──► MJ4 ;  MJ2, MJ4 ──► MJ5 ;  MJ4, MJ6 ──► MJ7 ──► MJ8 ──► MJ9 ;  MJ5, MJ9 ──► MJ10
Version 5.0, série CT : Y10, T13 ──► CT0 ──► CT1 ──► CT2, CT7, CT9 ;  CT2, AS1, AS4 ──► CT3 ;  AS2, CT2 ──► CT4 ──► CT5 ;  TT2 à TT5 (4.0) ──► CT6 ;  CT0, CT1 ──► CT8 ;  CT9, CT2 à CT8 ──► CT10 ──► CT11 ──► CT12
Version 5.0, série WF : WF0 ──► WF1 ──► (critère §4) ──► WF2 ──► WF3, WF4 ──► WF5 ──► WF6
Version 2.0, série WTF : WTF1 ──► WTF2 ──► WTF3 ;  WTF1 ──► WTF4 ;  WTF2, WTF4 ──► WTF5, WTF6, WTF7 ──► WTF8
Version 3.0, série DS : T12, T13, AS1 ──► DS1 ──► DS2, DS3, DS4 ;  DS2, DS4 ──► DS5, DS6 ;  DS2 ──► DS7 ;  DS2, Y18 ──► DS8 ;  DS3, DS5, DS6, DS7 ──► DS9
Fin de projet, série Y : Y1 (avancé) ──► S1 ;  Y1 ──► Y13 ;  Y1, X2, X13 ──► Y2 ──► Y4, Y6, Y7 ;  Y2, S1 ──► Y3 ──► Y8 (avec P20) ;  O1, Y2 ──► Y5 ;  O7 ──► Y9 ──► Y10 (avec les séries T et R) ;  Y8, P20, Y2 ──► Y11 ──► Y12 (avec R17)
```

## 2. Prérequis côté propriétaire du projet (avant de confier un lot)

1. Partir de `main` à jour (fusions du 23 octobre faites).
2. Donner à l'IA un accès en écriture au dépôt `Holeinthesock67/lolo_python`, ou lui remettre une copie et récupérer un correctif.
3. Lui transmettre le texte du lot et les documents listés dans sa section « À lire ».

## 3. Règles communes à tous les lots

**Documents qui font loi.** `docs/SRS_v1.1.md`, `docs/contracts/ipc_v1.md`, `docs/contracts/world_format_v1.md` et les schémas JSON de `docs/contracts/`.
- Un lot ne modifie un contrat que si sa section « Modifications de contrat autorisées » le prévoit.
- Si le travail révèle qu'un contrat est faux ou incomplet, l'IA **s'arrête et le signale** dans son rapport, au lieu de l'interpréter.

**Dépôt.**
- Le projet est dans le dossier `Open_ride_linux/` du dépôt `lolo_python`, qui contient d'autres projets sans rapport : ne rien toucher en dehors de `Open_ride_linux/`.
- Chaque lot se fait sur une branche `lot-<id>-<sujet>` partant de `main` à jour. Une demande de fusion (pull request) par lot.
- Ne modifier que les fichiers listés dans « Fichiers concernés ». Un fichier supplémentaire indispensable est signalé et justifié dans le rapport.

**Code.**
- **Python :**
  - version 3.11 minimum, et le code doit aussi tourner en 3.14 (version du PC cible) ;
  - typage avec annotations et dataclasses comme dans le code existant ;
  - aucune entrée-sortie bloquante dans la boucle du core.
- **GDScript :**
  - Godot 4.3 ;
  - pas de `class_name` pour les scripts dont dépend la scène principale : l'engine est lancé sans passer par l'éditeur, et Godot ne connaît alors pas les `class_name`. Utiliser `preload`.
- **Langue :** commentaires, docstrings et messages de journal en français ; identifiants en anglais.
- **Dépendances :** toute nouvelle dépendance est déclarée dans le `pyproject.toml` concerné et justifiée dans le rapport. Pas de bibliothèque pour ce que la bibliothèque standard ou une dépendance existante fait déjà.
- **Hors ligne :** aucun accès réseau à l'exécution, sauf dans le lot B2, qui télécharge des tuiles d'altitude dans un cache.

**Tests.**
- Chaque critère d'acceptation vérifiable par machine a son test automatique.
- `pytest` passe en entier (tests existants compris) dans `Open_ride_linux/core/` et, s'il existe, dans `Open_ride_linux/compiler/`.
- Côté Godot, les tests se lancent sans écran : `godot --headless --path engine ...` (Godot 4.3 officiel, téléchargeable sur GitHub).
- Le matériel (HomeTrainer, Click) n'est pas disponible pour l'IA. Tout ce qui dépend du matériel se teste avec les doublures existantes (`MockDriver`, faux clients BLE dans `core/tests/test_drivers_session.py`). Les essais réels sont listés dans le rapport pour le propriétaire.

**Livraison.** La demande de fusion contient :
1. le résumé de ce qui a été fait ;
2. la liste des critères d'acceptation, cochés, avec la commande qui les prouve ;
3. la sortie des tests ;
4. les écarts ou questions ouvertes ;
5. les essais à faire sur le matériel, s'il y en a.

**Recette.** Le propriétaire (ou Claude) relit la demande, relance les tests, vérifie les critères et fait les essais réels. Un critère non tenu renvoie le lot.

## 4. Modèle de message pour confier un lot

```text
Tu travailles sur OpenRide Linux, dépôt GitHub Holeinthesock67/lolo_python, dossier Open_ride_linux/.
Lis d'abord docs/lots/00_INDEX.md (règles communes), puis docs/lots/LOT_<X>_....md (ton lot), puis
les documents listés dans sa section « À lire ». Respecte strictement les fichiers autorisés et les
contrats. Crée la branche lot-<x>-<sujet> depuis main, fais le travail, fais passer tous les tests,
puis ouvre une pull request avec la liste des critères d'acceptation cochés et la sortie des tests.
Si un contrat te semble faux ou incomplet, arrête-toi et pose la question au lieu d'improviser.
```

## 5. Partage des lots par issues GitHub

Depuis le 24 octobre, chaque lot ouvert a une issue GitHub, rattachée à l'issue de suivi [#48](https://github.com/Holeinthesock67/lolo_python/issues/48). Étiquettes : `lot`, `délégable` (recette automatique, sans matériel), `série J`, `série L`, `série M`, `série N`, `série O`, `série P`, `série Q`, `série R`, `série S` ou `série X`, langage (`python`, `gdscript`, `ci`) et `bloqué` tant qu'un prérequis n'est pas sur `main`.

1. Choisir une issue ouverte sans l'étiquette `bloqué`, sans assigné ni commentaire « Je prends ce lot ».
2. Commenter « Je prends ce lot » sur l'issue, pour que deux IA ne fassent pas le même lot.
3. Suivre le message du §4, puis écrire `Closes #<numéro de l'issue>` dans la description de la pull request : l'issue se ferme à la fusion.
4. Le propriétaire fusionne ; l'IA ne fusionne pas.

Un nouveau lot reçoit son issue au moment où son cahier est ajouté à `docs/lots/`.
