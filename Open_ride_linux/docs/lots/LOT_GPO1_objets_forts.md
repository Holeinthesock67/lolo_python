# Lot GPO1 – Objets du Grand Prix plus forts et plus longs, bots visibles, voies utiles

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série GP : tout effet dure, valeurs renforcées, boîtes de famille par voie, boîtes et objets des bots visibles | Python, GDScript | GP1 à GP14 | Moyenne | **Livré le 24 novembre** (PR #957) ; recette PC à faire |

Série GP (mode « Grand Prix des objets »). Plan de la série : `docs/4.0/PLAN_SERIE_GP.md`. Demande du propriétaire du 21 novembre 2026, pendant un essai du Grand Prix : « les objets ont une durée trop limitée et un effet trop faible », « quand un bot prend un objet, pas d'effet visuel », « changement de voies pas assez exploité, quasi inutile ». Proposition : `/mnt/project-files/plans/PROPOSITION_GP_OBJETS_2026-11-21.md` (dossier du projet) ; choix « Tout : valeurs, bots, voies A » sur la carte du 21 novembre.

## 1. Cause

Le coup de fouet et toutes les glissades (bidon, musettes, musette guidée, sonnette, frôlement de la super-forme, éclaboussure du nuage) étaient des impulsions d'une image (v × 1,3 ou v × 0,7) : la vitesse revenait d'elle-même en quelques secondes, l'effet n'était pas dans la liste des effets en cours, donc ni compte à rebours au HUD ni dessin sur le coureur (les dessins « glissade » et « coup de fouet » du lot GP7 ne recevaient jamais rien). Les sons des objets n'étaient joués que pour le cycliste, et rien ne se voyait quand un bot prenait une boîte ou lançait un objet. Les trois boîtes d'une rangée donnaient le même tirage : la voie ne servait qu'à éviter un objet posé.

## 2. Règle unique

- **Tout effet dure.** Plus d'impulsion : un bonus pour soi est un plancher de vitesse (`speed_floor`), un coup reçu un plafond (`cap`), chacun avec sa durée. Effets `kick` et `slip` retirés de la table commune (`powerups.py`) ; leurs clés dans `grandprix.toml` sont ignorées sans refuser le fichier (`items.RETIRED_KEYS`).
- **Table de réglage centrale** en tête de `grandprix/items.py` : `SHORT_S` = 5 s (objets courants, tous les coups reçus), `LONG_S` = 12 s (super-forme, voiture d'équipe, Furtif), `WIND_S` = 10 s (vent contraire), `KICK` 1,3, `SLIP` 0,6 (0,7 jusqu'à l'essai du 22 novembre), `STORM` 0,5, `TOW` 1,5, `WIND_MPS` 6.
- **Pas d'acharnement** : pause entre deux coups reçus = durée d'un coup (`mode.HIT_GRACE_S = SHORT_S`, 2 s avant).
- Un même effet du même objet reçu à nouveau est relancé, pas cumulé.
- **Boîtes de famille par voie** : gauche « s'aider » (objets pour soi et sonnette), centre tout le tirage, droite « attaquer » (attaques, pièges, objets contre la tête). Le tirage selon le retard reste, limité à la famille de la voie ; une boîte donne toujours un objet (famille sans objet tirable : tout le tirage). Signe écrit au-dessus de chaque boîte (les couleurs seules ne se lisaient pas, retour du propriétaire du 21 novembre) : « + BONUS », « ? SURPRISE », « ! ATTAQUE » ; la couleur renforce seulement : jaune (famille « pour soi » des maquettes GP6), blanche, rouge (famille « attaque »). Mêmes mots dans l'aide du mode (lot de #952).
- **Bots** : à moins de 150 m d'une rangée, sans objet ni roulette, un bot prend la voie « attaquer » s'il est en tête ou à moins de 5 s, « s'aider » sinon, ou reste au centre une fois sur trois ; une décision par rangée, jamais vers une voie où un objet l'attend à moins de 40 m.
- **Même retour pour tous les coureurs** : message `gp_event` (révision 1.32) à chaque boîte prise et chaque objet utilisé ; l'engine écrit au-dessus du coureur « HOP ! » ou le nom de l'objet, dans la couleur de sa famille (Label3D déjà en place, 6 au plus) ; les dessins d'effets passent pour tous puisque tout effet dure ; les sons d'objet et de coup reçu sont joués aussi pour un bot à moins de 30 m, 9 dB plus bas, au plus un toutes les 0,5 s et jamais dans les 0,8 s après un son du cycliste.

## 3. Valeurs

| Objet | Avant | Après | Gain ou perte, plat / 6 % / −4 % (avant) |
| --- | --- | --- | --- |
| Coup de fouet | v × 1,3 d'un coup | v ≥ 130 % pendant 5 s | +5,4 / +3,4 / +4,9 s (+3,9) |
| Glissade (bidon, musettes, guidée, sonnette, frôlement, éclaboussure) | v × 0,7 d'un coup | v ≤ 60 % pendant 5 s | −7,0 / −3,9 / −6,9 s (−3,9) |
| Nuage d'orage | v ≤ 50 % pendant 1,5 s, éclaboussure 10 m | v ≤ 50 % pendant 5 s, éclaboussure 15 m | −8,7 / −4,7 / −8,7 s (−6,9) |
| Super-forme | v ≥ 120 %, 8 s | v ≥ 130 %, 12 s | +7,5 / +5,5 / +7,0 s (+4,2) |
| Vent contraire | 5 m/s, 6 s | 6 m/s, 10 s | −4,2 / −2,2 / −3,7 s (−2,1) |
| Voiture d'équipe | v = 150 %, 6 s | v = 150 %, 12 s | +12,4 / +9,4 / +11,4 s (+9,4) |
| Furtif | 10 s, vol à 50 m | 12 s, vol à 100 m | — |
| Portées | musette 400 m, guidée 200 m, sonnette 5 m / 15 m | 500 m, 300 m, 8 m / 25 m | — |

Banc simulé (`tools/grandprix_sim`, 200 courses par configuration) : `docs/4.0/RAPPORT_EQUILIBRAGE_GPO1.md`, cibles du lot GP5 toutes tenues. Un premier essai à 8 m/s × 12 s de vent dépassait 35 % du temps à 11 bots (37 %) : d'où 6 m/s × 10 s.

## 3 bis. Après l'essai vélo du 22 novembre

L'essai tournait sur main (sans ce lot) ; le propriétaire a trouvé l'impact des objets toujours trop faible et n'a rien vu quand sa musette guidée a été arrêtée deux fois (onde d'une sonnette sonnée 0,02 s après le lancer, puis bidon gardé en réserve par le bot visé). Ajouts, une règle pour tous les coureurs :

- **Toute parade se voit** : objet gardé en réserve, onde de la sonnette, invincibilité. `gp_event` de type `parry` (avec `by`, le lanceur), « PARÉ ! » au-dessus du coureur qui pare, « ding » de la sonnette, ligne `parry` du journal avec `how` (`shield`, `bell`, `immune`).
- **Temps perdu écrit avec le coup** : « ZIOUF ! −7 s » (le `loss_s` de `gp_hit`, déjà envoyé, n'était pas affiché).
- **Bots humains** : sonnette après un temps de réaction tiré entre 0,6 et 1,5 s (`brain.REACT_S`) ; esquive des objets sur la voie 0,18 / 0,30 / 0,45 selon le chaos (0,30 / 0,50 / 0,75 avant).
- **Glissade plus forte** : vitesse au plus 60 % pendant 5 s (−7,0 s sur le plat) ; onde de la sonnette ramenée à 15 m.

## 4. Livraison (21 novembre 2026)

- Core : `powerups.py`, `grandprix/effects.py`, `items.py` (table de réglage, `BOX_LANES`, `lane_items`), `draw.py` (`only`), `mode.py` (`gp_event`, tirage par voie, pause = `SHORT_S`), `brain.py` (voie des boîtes).
- Contrat : révision 1.32, message `gp_event` (`docs/contracts/ipc/gp_event.schema.json`), boîtes de famille par voie ; numéro pris à la fusion au-dessus de `main` (provisionnel 1.32, `CONTRACT_REV` « 1.32 » ; 1.25 non utilisée, 1.31 prise par RZ1), renuméroté si une autre révision fusionne avant.
- Engine : `gp_scene_model.gd` (`on_event`, `box_color`, couleur des mots), `gp_scene.gd` (teinte des boîtes du MultiMesh, mots colorés), `gp_sound_model.gd` (`on_event`, `bot_hit`, `bot_sound`), `sound_player.gd` (`play_event(jingle, volume_db)`), `ipc_client.gd` (`gp_event_received`), `main.gd` (branchement).
- Tests : `test_grandprix.py` (tout effet dure, valeurs, boîtes par voie, `gp_event`), `test_grandprix_bots.py` (voie des boîtes), `test_grandprix_session.py` (`gp_event` validé par son schéma), `test_tt2_modele_bonus.py`, `engine/tests/unit/test_gp_scene.gd`.

## 5. Recette PC

Catégorie : rendu (couleur des boîtes, mots au-dessus des bots, dessins d'effets plus longs). `sim_bench` `grand_prix` et `grand_prix_onze` en low, medium et high ; captures à valider par le propriétaire : boîtes colorées par voie, « HOP ! » et nom d'objet au-dessus d'un bot, glissade dessinée sur un bot touché, compte à rebours au HUD du coup de fouet. Essai vélo de 10 min sur le Circuit des Prés.
