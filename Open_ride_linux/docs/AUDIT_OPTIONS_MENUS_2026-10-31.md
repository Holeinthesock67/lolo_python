# Audit des options absentes des menus (31 octobre 2026)

Demande du propriétaire (31 octobre, 03:26) : s'assurer qu'il n'y a pas d'autre oubli comme le gravel
(réglage lu par le core ou option de l'engine jamais reliée au menu). Principe : toute option se règle
dans un menu ; à la fin, le jeu s'utilise sans ligne de commande et sans fichier à déposer ou à
modifier à la main dans `~/OpenRide/`. Base : `main` au commit 1f4b60d (fusion de #631). Aucun code
n'est modifié ici ; les lots proposés au §7 attendent l'accord du propriétaire.

## 1. Résumé

- **Un vrai défaut du même genre que le gravel : la ceinture cardio appairée dans le menu n'est
  jamais utilisée.** « Appareils » écrit `drivers.hr_address` et `drivers.hr_name`, mais jamais
  `drivers.hr = "ble"` ; la valeur reste `"none"` (défaut du code et de `scripts/config.example.toml`),
  le lanceur ne passe pas `--hr`, donc `build_hr()` (`core/src/openride_core/session.py`) ne crée
  aucun lecteur de ceinture. Il faut éditer `config.toml` à la main. C'est cohérent avec la ceinture
  « jamais détectée » de l'essai du 25 octobre. Lot O24, à faire en premier.
- **Le biome forcé (`--biome`) suit le même chemin que le gravel** : l'engine le lit, rien ne le
  règle depuis le menu, et `[render] biome` (prévu au lot U1) n'existe pas dans `config.py`. Les deux
  relèvent du lot U16 (« Choix du biome et option gravel dans les réglages »), pris par le fil
  « Vérifier l'activation du gravel dans les menus ».
- **Sept actions demandent encore un terminal** : installer les entraînements et les plans de départ,
  installer le pack de parcours « cols célèbres », installer un thème ou un pack de biomes, relire
  l'historique des séances, vider le profil d'essai, récupérer une séance après un arrêt brutal du PC.
  Le message du premier lancement renvoie même vers `openride-core devices --save`, alors que l'écran
  Appareils existe depuis le lot N13.
- **Trois réglages utiles au joueur ne sont qu'à la main dans `config.toml`** : décor vivant
  (`render.living`, le guide dit « écrivez dans config.toml »), relief exagéré
  (`render.visual_grade_scale`) et ressenti du vent (`wind.feel`).
- **Un réglage sans Click** : la recherche d'un lieu du monde ouvert (choix d'une destination) ne se
  saisit qu'au clavier. Au Click seul, « Destination » ouvre une recherche vide impossible à remplir.
- **Légendes** : `wind.mode` (off, fixed, gusty, theme) et `render.theme` (default) s'affichent avec
  leur valeur technique en anglais. Le guide d'utilisation (§ Réglages) a pris du retard : il parle de
  « quatre volumes » (il y en a six) et ne cite ni FC max, ni niveau des bots, ni vue de caméra, ni
  jauge d'abri.
- **Derniers choix non mémorisés** : parcours, entraînement, bot, fantôme, choix du Cyber-Rogue et
  réglages de départ du monde ouvert repartent à zéro à chaque lancement.
- **Une configuration invalide bloque le démarrage** et demande de corriger le fichier à la main.
- Tout le reste est rangé : réglé par un menu, automatique, ou clé de développement à garder hors
  menu (liste au §4.3). Pour éviter un nouvel oubli, le lot X53 propose un test qui casse dès qu'une
  clé ou un argument n'est ni dans un menu ni dans une liste « expert » ou « développement » écrite.

Déjà prévus et non repris ici : gravel et biome (U16), aide Monde ouvert et Parcours (O22), import de
traces depuis le menu (O23), aide du menu ERG et QWKcode en fichier (O20, PR #629), QWKcode au clavier
(O21), menu des règles du mode WTF (PR #594, qui supprime le besoin d'éditer `~/OpenRide/wtf.toml`).

## 2. Méthode

1. Lecture des analyseurs de ligne de commande : lanceur `openride`
   (`core/src/openride_core/launcher.py`), `openride-core` (`core/src/openride_core/__main__.py`),
   `openride-compiler` (`compiler/src/openride_compiler/cli.py`) et engine
   (`engine/scripts/engine_args.gd`) ; variables d'environnement lues par le core, le compilateur et
   l'engine.
2. Lecture de toutes les sections de `core/src/openride_core/config.py` et comparaison avec la liste
   du menu `SETTINGS` (`core/src/openride_core/settings.py`), les écritures de l'appairage
   (`core/src/openride_core/pairing.py`), du test de FTP (`accept_ftp`) et de la difficulté de la pause.
3. Recherche de tous les chemins `~/OpenRide/…` lus ou écrits, et de tous les endroits du guide
   d'utilisation qui demandent une commande ou une édition de fichier.
4. Pour chaque élément : présent dans un menu ? légende claire en français ? valeur persistée ?
   utilisable au Click et au clavier (lot O17, banc des menus) ?

Légende des tableaux : **Menu** oui / non / auto (fait par le jeu sans rien demander) ; **Verdict**
OK, À FAIRE (lot proposé), PRÉVU (lot déjà prévu), EXPERT (réglage fin, reste dans le fichier,
documenté) ou DEV (outil de développement ou d'essai, hors menu, documenté).

## 3. Arguments de ligne de commande

### 3.1 Lanceur `openride`

| Argument | Rôle | Menu | Verdict |
|---|---|---|---|
| (aucun) | lance core et engine, `--trainer ftms --input click` | icône du bureau | OK |
| `--no-compile`, `--compile-only`, `--compile-timeout` | compilation des traces au lancement | auto | DEV |
| `--release-trainer` | libère le trainer | icône « Libérer le trainer » | OK (une ligne dans Appareils serait un plus, lot O24) |
| `--profil ID` | ouvre un profil | écran « Qui roule ? » et ligne Profil de l'accueil | OK |
| `--config` | autre fichier de configuration | non | DEV |
| options de `openride-core run` | passées au core | voir 3.2 | voir 3.2 |

### 3.2 `openride-core run` (le core)

| Argument | Rôle | Équivalent menu | Verdict |
|---|---|---|---|
| `--trainer`, `--input`, `--hr`, `--sim-scenario` | pilotes | Appareils ; « Session simulée » (code 65) pour `sim` | OK sauf `--hr` : voir O24 |
| `--gear` | braquet de départ | Réglages > Séance > Braquet de départ | OK |
| `--bot`, `--bot-profile`, `--ghost` | bots, fantôme | écran Prêt (lots O7, T12, T13) | OK |
| `--route`, `--workout`, `--autostart` | séance sans menu | menus Parcours, Session ERG | DEV |
| `--ftp-test ramp` | test de FTP | accueil > Test de FTP | OK |
| `--replay` | rejoue un journal ou un FIT | non | DEV |
| `--resume`, `--first-run` | posés par le lanceur | auto | OK |
| `--latence`, `--trace-ftms` | journaux de diagnostic | non | DEV |

### 3.3 Engine (après `--`)

| Argument | Passé par le lanceur depuis | Menu | Verdict |
|---|---|---|---|
| `--ipc-state-port`, `--ipc-cmd-port` | `[ipc]` | non | DEV |
| `--quality`, `--theme`, `--display`, `--camera` | `[render]` | Réglages > Graphisme | OK |
| `--visual-grade` | `render.visual_grade_scale` | non | À FAIRE (O26) |
| `--living` | `render.living` | non | À FAIRE (O26) |
| `--load-guard` | `render.load_guard` | non | EXPERT (coupé pour les mesures) |
| `--gravel` | rien (le lanceur ne le passe pas) | non | PRÉVU (U16, fil gravel) |
| `--biome` | rien | non | PRÉVU (U16) |
| `--routes-dir` | rien | non | DEV |
| `--culling` | rien | non | DEV (lot S1, aucun gain mesuré) |
| `--perf-probe` | `OPENRIDE_PERF_PROBE` | non | DEV |
| `--sim-session` | « Session simulée » | auto | OK |
| `--test-mode` | outils de test | non | DEV |

### 3.4 Sous-commandes d'`openride-core` et d'`openride-compiler`

| Commande | Usage pour le joueur | Menu | Verdict |
|---|---|---|---|
| `devices --save` | appairage | Réglages > Appareils | OK (le message du premier lancement l'ignore : O25) |
| `settings`, `settings set` | réglages | Réglages | OK |
| `ftp-test --accept` | enregistrer la FTP | bilan du test (`accept_ftp`) | OK |
| `ftp-test --history`, `history`, `summary` | relire ses séances | non (seul le bilan de fin s'affiche) | À FAIRE (O28) |
| `plan list/show/start/stop/today` | plans | accueil > Choisir un plan / Séance du jour | OK |
| `plan install` | plans de départ | non | À FAIRE (O25) |
| `plan import` | plan maison à partir d'entraînements | non | À FAIRE (O30) |
| `python -m openride_core.tools.workouts install` | entraînements de départ | non | À FAIRE (O25) |
| `profil list/create/rename/delete` | profils | écrans des profils (série MJ) | OK |
| `profil essai --vider` | remise à zéro du profil d'essai | non | À FAIRE (O33) |
| `recover` | FIT après un arrêt brutal du PC | auto seulement pendant le même lancement | À FAIRE (O34) |
| `release-trainer` | libérer le trainer | icône du bureau | OK |
| `open-world-save` | balade du monde ouvert gardée en parcours | auto à la fin (lot W14) | OK |
| `demo-biomes` | parcours de démonstration des biomes | non | À FAIRE (O25) |
| `route-pack-install`, `route-pack-list` | pack « cols célèbres » | non | À FAIRE (O29, ou avec O23) |
| `theme-install`, `theme-list` | thèmes et packs de biomes | choix du thème seulement | À FAIRE (O29) |
| `build-all` | compilation des traces | auto au lancement | OK (import depuis le menu : O23) |
| `region-add`, `region-update`, `region-list`, `cache-info`, `cache-clean`, `world-prefetch` | cache du monde ouvert | régions du cache et épingles dans le menu du monde ouvert | EXPERT (téléchargement à la volée par défaut) |
| `xp`, `session-report`, `fit-check`, `build`, `add-layer`, `verify`, `info`, `compare-garmin`, `theme-check`, `route-pack-build`, `world-measure` | outils | non | DEV |

### 3.5 Variables d'environnement

Toutes sont des outils d'essai ou de développement, à garder hors menu : `GODOT`, `GODOT_ARGS`,
`OPENRIDE_ENGINE`, `OPENRIDE_LOG`, `OPENRIDE_NO_GUI`, `OPENRIDE_TERMINAL`, `OPENRIDE_GUIDE_MUET`,
`OPENRIDE_PROFIL`, `OPENRIDE_DISPLAY` (doublon temporaire de `render.display`), `OPENRIDE_PERF_PROBE`,
`OPENRIDE_WORLDGEN`, `OPENRIDE_WORLDMENU`, `OPENRIDE_DEM_CACHE`, `OPENRIDE_OSM_CACHE`,
`OPENRIDE_RECORDS_FILE`, `OPENRIDE_RENDER_DIAG`, `OPENRIDE_THEMES_DIR`. Verdict : DEV, aucune n'est
nécessaire au joueur.

## 4. Clés de `config.toml`

### 4.1 Réglées par un menu (OK)

25 clés de la liste `SETTINGS`, toutes persistées (écriture par `config_edit`, couche machine ou
profil), au Click, au clavier et à la souris :

| Sous-écran | Clés | Légende |
|---|---|---|
| Cycliste | `rider.ftp_w`, `rider.mass_kg`, `rider.hr_max_bpm`, `bike.mass_kg` | claire |
| Séance | `trainer.difficulty_pct` (aussi en pause), `gearing.start_gear`, `powerups.mode`, `bots.level_pct` | claire |
| Graphisme | `render.quality`, `render.theme`, `render.chart`, `render.display`, `render.fps`, `render.draft_gauge`, `render.camera` | `render.theme` affiche « default » ; `render.quality` garde low / medium / high (mots du projet, à confirmer) |
| Son | six volumes `audio.*_pct` | claire |
| Vent | `wind.mode`, `wind.speed_kmh`, `wind.from_deg`, `wind.gust_pct`, `wind.max_grade_offset_pct` | `wind.mode` affiche off / fixed / gusty / theme ; « pts » pour le plafond est peu parlant |

Écrites par d'autres écrans : `drivers.trainer_address`, `trainer.device_name`,
`drivers.click_address`, `drivers.click_minus_address`, `drivers.hr_address`, `drivers.hr_name`
(Appareils), `rider.ftp_w` (bilan du test de FTP), `profils.dernier` (auto, écran « Qui roule ? »).

### 4.2 Lues mais absentes du menu, utiles au joueur (À FAIRE ou PRÉVU)

| Clé | Rôle | Proposition |
|---|---|---|
| `drivers.hr` | active la ceinture cardio | jamais écrite par Appareils : **O24** |
| `gravel.mode` | surface imposée au parcours | PRÉVU, U16 (fil gravel) |
| `render.biome` (prévue par U1, absente de `config.py`) | biome forcé | PRÉVU, U16 |
| `render.living` | décor vivant ou rendu de la 1.0 | **O26**, Graphisme, appliqué au lancement suivant |
| `render.visual_grade_scale` | relief exagéré, 1,0 à 3,0 | **O26**, Graphisme |
| `wind.feel` | vent ressenti par la pente ou par le champ vent du trainer | **O26**, Vent |
| `open_world.network` | monde ouvert hors ligne (cache seulement) | **O27**, Avancé |
| `open_world.cache_max_gb`, `render.theme_library_gb` | plafonds de disque | **O27**, Avancé |
| `progression.enabled` | progression et Garage coupés | **O27**, Avancé |
| `trainer.resend_s` | renvoi de la consigne (essais contre le pompage) | **O27**, Avancé, si l'essai la garde réglable |

Les clés de l'onglet Avancé ne tiennent pas dans le plafond actuel du message `settings`
(32 éléments, un datagramme) avec U16 et O26 : 25 + 2 + 3 = 30. O27 demande donc soit de découper
`settings` en parties comme `routes` (nouvelle révision du contrat IPC), soit de ne mettre en Avancé
que deux clés. Décision au §8.

### 4.3 Lues, hors menu par choix (EXPERT ou DEV)

| Section | Clés | Verdict |
|---|---|---|
| `[bike]` | `cda_m2`, `crr`, `drivetrain_efficiency` | EXPERT (modèle physique) |
| `[trainer]` | `latency_tau_s`, `grade_min_pct`, `grade_max_pct`, `power_smooth_tau_s`, `grade_rate_up_pct_per_s`, `grade_rate_down_pct_per_s`, `grade_rate_pct_per_s` (ancien), `hr_relay_freeze_s` | EXPERT |
| `[trainer]` | `trace_ftms` | DEV |
| `[gearing]` | `n_gears`, `ratio_min`, `ratio_max`, `g_base_pct`, `long_press_gears` | EXPERT |
| `[drivers]` | `click_short_max_s`, `click_long_min_s`, `click_mute_after_s`, `click_rehandshake_s`, `click_reset_locked` | EXPERT |
| `[drivers]` | `trainer`, `input` (posés par le lanceur), `click_trace_raw`, `mock_replay`, `sim_scenario` | DEV |
| `[render]` | `load_guard` | EXPERT (coupé pour les mesures) |
| `[gravel]` | `factor_compacted`, `factor_gravel`, `factor_dirt` | EXPERT |
| `[wind]` | `seed` | DEV |
| `[avatar]` | `standing_grade_pct`, `standing_power_pct` | EXPERT |
| `[rogue]` | `w_prime_j` (choisi aussi dans le menu du Cyber-Rogue), `cp_w`, `grade_rate_up_pct_per_s`, `grade_rate_down_pct_per_s` | EXPERT |
| `[open_world]` | `cache_dir`, `horizon_m`, `offer_m`, `lock_m`, `preview_m`, `recenter_m`, `prefetch_history`, `prefetch_radius_km` | EXPERT |
| `[ipc]` | `port_state`, `port_commands` | DEV |
| `[engine]` | `godot` (écrit par `scripts/install.sh`) | DEV |
| `[log]` | `latence` | DEV |

## 5. Fichiers et dossiers de `~/OpenRide/`

| Chemin | Rôle | Sans terminal ni fichier à la main ? | Verdict |
|---|---|---|---|
| `config.toml`, `Profils/<id>/profil.toml` | réglages | oui, par les menus ; une erreur de saisie bloque le lancement | O34 pour la reprise |
| `GPX/` | traces à compiler | dépôt à la main puis relance | PRÉVU (O23) |
| fiche `.toml` à côté d'une trace | nom, description, étiquettes | à la main | à ajouter à O23 (fiche remplie à l'import) |
| `Workouts/` | entraînements | créer et importer : menu ; série de départ : commande | O25 |
| `Import/`, Téléchargements, Bureau | sources de l'import ERG | menu « Importer un fichier » | OK |
| `Plans/` | plans `.toml` | plans de départ par commande, plan maison à la main ou par commande | O25, O30 |
| `plan_state.toml`, `progression.toml`, `records.json`, `profile.json`, `.profil_actif` | état du jeu | auto | OK |
| `Activities/`, `Activities/.journal/` | FIT et journaux | auto ; FIT après un arrêt brutal par commande | O34 |
| `Themes/`, `Themes/.utilisation.json` | thèmes et packs de biomes | installation par commande | O29 |
| `Sounds/<son>.ogg` | sons remplacés par le joueur | à la main | EXPERT (personnalisation facultative, décision au §8) |
| `wtf.toml` | règles du mode WTF | menu dans la PR #594 | PRÉVU |
| `powerups.toml`, `rogue_balance.toml` | équilibrage des bonus et du Cyber-Rogue | à la main | DEV (surcharges d'équilibrage) |
| `Profils/.corbeille/`, `Sauvegardes/` | profils supprimés, sauvegarde de migration | restauration à la main | O33 |
| `Cache/monde/` | cache du monde ouvert | auto, régions épinglables dans le menu | OK |
| `Logs/` | journaux | auto | OK |
| `Essais/`, `boutons_click/`, `click_recette/`, `fc_recette/`, `coupures/`, `gigue/`, `trainer_steps/`, `rapports/` | outils d'essai | outils | DEV |
| `.update.lock` | verrou de mise à jour (icône « Mettre à jour ») | auto | OK |

## 6. Constats transverses

1. **Ceinture cardio** (§1) : `pairing.CONFIG_TARGETS` n'a pas de cible pour `drivers.hr`. Il manque
   aussi « Aucune ceinture » et « Oublier cet appareil » : `pair_devices` garde la valeur actuelle
   quand on envoie `null`, donc un appareil ne se retire qu'à la main.
2. **Premier lancement** : `FIRST_RUN_INFO` (`core/src/openride_core/launcher.py`) dit « Configurez
   vos appareils : openride-core devices --save (la section Appareils du menu viendra plus tard) ».
   Seuls `GPX/` et `Workouts/` sont créés ; `Workouts/` reste vide (les entraînements livrés dans
   `core/workouts/` ne sont pas copiés), aucun plan n'est installé, le pack « cols célèbres » et les
   parcours de démonstration des biomes ne le sont pas non plus.
3. **Saisie de texte au Click** : le nom de profil a déjà une saisie lettre par lettre au Click
   (série MJ) ; la recherche du monde ouvert (`engine/scripts/world_menu_model.gd`, `type_text`) ne
   la reprend pas. Même besoin pour le QWKcode (O21) : un seul composant de saisie partagé évite une
   exception par écran.
4. **Légendes techniques** : `CHOICE_TEXTS` (`engine/scripts/settings_view_model.gd`) n'a pas
   d'entrée pour `wind.mode` ni `render.theme`.
5. **Guide d'utilisation en retard** sur la liste des réglages et encore plein de commandes :
   `plan install`, `tools.workouts install`, `theme-install`, `summary`, `history`, `recover`,
   `profil essai --vider`, et « écrivez dans config.toml » pour le décor vivant. Chaque lot ci-dessous
   retire sa commande du guide et la remplace par le chemin dans le menu.
6. **Derniers choix** : rien ne garde le parcours, l'entraînement, le bot, le fantôme, les choix du
   Cyber-Rogue ni le départ du monde ouvert d'un lancement à l'autre.
7. **Configuration invalide** : le lanceur refuse de démarrer avec une fenêtre qui cite la clé ; le
   joueur doit ouvrir le fichier. Avec des menus qui valident tout, ce cas vient surtout d'une ancienne
   édition à la main ou d'une clé dont les bornes ont changé (cas des braquets du 28 octobre).
8. **Aucun garde-fou** n'empêche aujourd'hui une nouvelle clé ou un nouvel argument d'arriver sans
   menu : c'est ce qui a laissé passer le gravel et la ceinture.

## 7. Lots proposés (rien n'est codé avant accord)

Numéros libres à la date de l'audit : O24 et suivants (O20 à O23 sont pris ou prévus), X53.

| Lot | Contenu | Priorité | Taille | Dépend de |
|---|---|---|---|---|
| **O24** | Ceinture cardio et appareils : l'appairage d'une ceinture écrit aussi `drivers.hr = "ble"` (profil en cours) ; « Aucune ceinture » remet `none` ; « Oublier cet appareil » pour le trainer, chaque boîtier du Click et la ceinture ; « Libérer le trainer » dans l'écran Appareils ; test du banc des menus qui appaire une ceinture simulée et vérifie la FC reçue | P0 | Petite | — |
| **O25** | Premier lancement sans terminal : copie des entraînements livrés et des deux plans de départ, installation du pack « cols célèbres » et des parcours de démonstration des biomes (une fois, sans écraser) ; message de bienvenue réécrit (Appareils du menu) ; même action « Installer les contenus de départ » dans Réglages pour une installation existante | P1 | Petite | — |
| **O26** | Réglages joueur manquants : Graphisme « Décor vivant » et « Relief exagéré », Vent « Ressenti du vent » ; légendes françaises de `wind.mode` et `render.theme` (et de `render.quality` si le propriétaire le veut) ; unité du plafond du vent | P1 | Petite | U16 pour l'ordre des lignes |
| **O27** | Sous-écran « Avancé » : hors ligne du monde ouvert, plafonds de disque, progression, renvoi de la consigne ; `settings` en parties si la décision 2 le demande (révision IPC suivante) | P2 | Petite à moyenne | O26 |
| **O28** | Historique dans le menu : liste des séances (date, parcours, durée, NP, TSS) avec leur bilan, cumul par semaine, historique des tests de FTP ; mêmes calculs que `history` et `summary` | P2 | Moyenne | — |
| **O29** | Thèmes et packs depuis le menu : liste des packs connus et des archives trouvées dans Téléchargements, installation avec progression et place disque, packs de parcours (peut être fusionné avec O23) | P2 | Moyenne | O23 |
| **O30** | Plan maison depuis le menu : choisir des entraînements et des jours, comme `plan import` | P3 | Petite | O25 |
| **O31** | Saisie de texte partagée au Click : composant unique (celui du nom de profil) pour la recherche du monde ouvert et le QWKcode | P1 | Petite | O21 |
| **O32** | Derniers choix mémorisés par profil : parcours, entraînement, bot, fantôme, Cyber-Rogue, départ du monde ouvert | P1 | Petite | — |
| **O33** | Profils : « Vider le profil d'essai » et « Restaurer un profil supprimé » dans Gérer un profil | P3 | Petite | — |
| **O34** | Démarrage robuste : séance interrompue d'un lancement précédent proposée au démarrage (FIT créé) ; configuration invalide : fenêtre « Remettre la valeur par défaut » (copie `.bak` gardée) | P1 | Petite | — |
| **X53** | Garde-fou : test qui échoue si une clé de `config.py` ou un argument d'`engine_args.gd` n'est ni dans un menu, ni dans une liste EXPERT ou DEV écrite dans le code, avec sa raison ; même contrôle sur les commandes citées dans le guide d'utilisation | P0 | Petite | — |

Ordre conseillé : O24 et X53 tout de suite (X53 fera échouer le test tant que U16 et O26 ne sont pas
faits, ou les listera en « à faire » avec le numéro du lot), puis O25, O32, O34, O31, O26 après U16,
puis O28, O29, O27, O30, O33.

## 8. Décisions pour le propriétaire

1. **Fichiers de personnalisation** (`Sounds/`, `powerups.toml`, `rogue_balance.toml`) : recommandé,
   les garder comme fichiers facultatifs documentés (aucun n'est nécessaire pour jouer), sans menu.
2. **Onglet Avancé** : recommandé, quatre clés seulement et découpage de `settings` en parties
   (révision IPC suivante), pour ne plus buter sur le plafond de 32 éléments.
3. **Qualité graphique** : garder « low / medium / high » (les mots des essais et des bancs) ou
   afficher « basse / moyenne / haute ». Recommandé : garder, puisque les règles de mesure les
   emploient.
