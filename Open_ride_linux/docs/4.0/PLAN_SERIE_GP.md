# Plan de la série GP : mode « Grand Prix des objets »

Demande du propriétaire du 31 octobre 2026 : « un mode type Mario Kart avec des items qui ont le même effet que bananes, carapaces, étoile… ». Le mode reprend les **effets** de ces objets d'arcade, sous des objets propres à OpenRide et au vélo (bidon, musette, voiture d'équipe…), avec un style et des noms à nous. Ce document est une étude ; aucun code n'est écrit. Toute maquette sera soumise au propriétaire avant le moindre code d'affichage, et tout essai de performance se fera en `low`, `medium` **et** `high`, captures à l'appui.

Sources lues : `core/src/openride_core/physics.py` (`RiderPhysics`, `steady_speed`), `powerups.py` (T6), `draft.py` (AS1), `bots.py` (bots à profil T12, calibrage T13, `MAX_CONSTANT_BOTS = 4`), `session.py` (pente envoyée, supplément `grade_offset_pct`, rampes de 4 %/s et 8 %/s), `docs/SPECIFICATION_GENERALE.md` §7.1 (plan des boutons), `docs/4.0/PLAN_SERIE_TT.md`, `docs/5.0/PLAN_SERIE_CT.md`, `docs/5.0/CHARTE_CARTOON_CT9.md`, `docs/2.0/PLAN_SERIE_WTF.md`, plan de la série DS (PR #673), cahiers AS2, AS4 et AS6. Les gains et pertes du §3 sont calculés avec `RiderPhysics` du core (cycliste et vélo de 84 kg, CdA 0,32 m², Crr 0,004, 250 W, écart mesuré 60 s après l'effet sur un coureur identique sans effet).

---

## 1. En bref

1. **Un mode à part**, « Grand Prix des objets » (`grandprix`), lancé depuis l'accueil du menu comme le Mode WTF : le classique, ses records et sa physique honnête ne changent pas. Rien ne se lance en ligne de commande.
2. **Treize objets** (§3), chacun désactivable au menu : coup de fouet (champignon), bidon glissant (peau de banane), musettes lancée et guidée (carapaces verte et rouge), nuage d'orage (carapace bleue), super-forme (étoile), sonnette (super klaxon), vent contraire (éclair), voiture d'équipe (fusée de rattrapage), furtif (fantôme voleur), plus les versions triples.
3. **Obtention** : des rangées de **boîtes de ravitaillement** sur la route, une tous les 1,5 km par défaut ; le tirage dépend du **retard sur le premier** (le dernier reçoit les objets forts, le premier les objets de défense).
4. **Usage** : Z court lance l'objet, A court change de voie quand un objet est en vue (sinon vue suivante, exactement la règle du monde ouvert), flèches gauche et droite en raccourci. Rien de nouveau dans le plan des boutons, clavier compris.
5. **Le trainer n'est jamais secoué** : aucun objet ne touche la pente envoyée. Les effets ne changent que la vitesse virtuelle ; seul l'abri et le vent, qui existent déjà, se ressentent, avec leurs rampes et leur borne. La puissance mesurée, le journal et le FIT restent réels. **SIM seulement**, comme WTF, CT et DS.
6. **Pas de doublon** : les effets sont des lignes du **modèle unique de bonus de la 4.0** (TT2), que la Course tactique (5.0) paie en crédits et que ce mode distribue dans des boîtes. Une seule table d'effets, trois façons de les obtenir.
7. **Version proposée : 4.0**, juste après TT2 (modèle d'effets) et AS2 (voies et écart latéral).

## 2. Course

### 2.1 Format

- **Circuit** (1 à 5 tours) ou **parcours en ligne** (5 à 30 km, arrivée à la distance choisie), dans la liste habituelle des parcours. Le monde ouvert n'est pas proposé dans un premier temps (pas de distance de course fixe).
- **Départ groupé** : 2 à 4 bots tant que le core en limite le nombre à 4, jusqu'à 11 avec le peloton prévu après le lot Y18 (lot GP10). Le fantôme est exclu : il rejoue une séance passée, il ne peut ni être touché ni réagir.
- **Plateau** : composé par le core comme pour DS (profils tournants grimpeur, rouleur, sprinteur, diesel ; niveaux autour du réglage existant « Niveau des bots », `bots.level_pct` ; calibrage T13).
- **Classement** : à l'arrivée ; le bilan donne la place, les objets lancés, reçus, esquivés et le temps gagné ou perdu par objet.

### 2.2 Ce qui reste du classique

| Élément | Dans ce mode | Pourquoi |
| --- | --- | --- |
| Physique, abri (AS1, puis AS2 à AS7), vent | Identiques | Les objets s'ajoutent à la physique, ils ne la remplacent pas |
| Bonus T6 et TT | Coupés | Les boîtes les remplacent (mêmes effets, §5) |
| Segments, records, maillots | Coupés | Physique volontairement faussée par les objets ; le haut du HUD sert à l'objet |
| Journal, FIT, expérience (série V) | Comme une séance libre | Puissance et vitesse réelles |
| Difficulté (Q1) | Inchangée | Elle ne change que la pente ressentie |
| Pause (Y), coupure du trainer (#542) | Tout est figé, objets et projectiles compris | Pas de coup reçu pendant une pause |

### 2.3 Voies

Pour qu'un bidon ou une musette s'esquive, il faut une position latérale. Le mode s'appuie sur l'écart latéral `lane_m` et le placement automatique du lot AS2 : la route est découpée en **trois voies** (gauche, centre, droite) pour les objets. Le placement automatique reste actif ; le joueur peut le forcer (A court, §4), le changement de voie prend 0,6 s, et le placement automatique reprend par A long ou au bout de 20 s sans objet en vue. Les bots esquivent selon leur niveau (lot GP3).

## 3. Catalogue des objets

Tous les effets agissent sur la **vitesse virtuelle** du coureur visé. Une glissade ou une averse ne touchent jamais la résistance : le coureur relance avec ses propres watts, ce qui fait le coût réel. Après un coup reçu, 2 s sans nouveau coup (pas d'acharnement).

| Objet | Identifiant | Effet d'arcade | Ce qui se passe | Valeurs proposées | Gain ou perte : plat, 6 %, −4 % |
| --- | --- | --- | --- | --- | --- |
| Coup de fouet | `gel` | Champignon | Gel énergétique avalé : impulsion de vitesse | v × 1,3 d'un coup | + 3,9 s, + 1,9 s, + 3,4 s |
| Trois coups de fouet | `gel_x3` | Triple champignon | Trois charges, une par Z court, une par seconde au plus | idem × 3 | + 3,9 s par charge |
| Bidon glissant | `bottle` | Peau de banane | Lâché derrière soi sur sa voie ; reste 90 s ou jusqu'au premier contact | Glissade : v × 0,7 | − 3,9 s, − 1,5 s, − 3,7 s |
| Trois bidons | `bottle_x3` | Triple banane | Trois bidons, un par Z court | idem | idem |
| Musette lancée | `musette` | Carapace verte | Lancée tout droit devant sur sa voie, 15 m/s plus vite que le lanceur, 400 m au plus ; touche le premier coureur de la voie | Glissade v × 0,7 | − 3,9 s, − 1,5 s, − 3,7 s |
| Trois musettes | `musette_x3` | Triple carapace verte | Trois lancers | idem | idem |
| Musette guidée | `homing` | Carapace rouge | Suit le coureur juste devant (moins de 200 m), change de voie avec lui ; parée par un bidon ou une musette tenus en réserve (automatique), par la sonnette ou par la super-forme | Glissade v × 0,7 | idem |
| Nuage d'orage | `storm` | Carapace bleue | Vole jusqu'au premier et crève sur lui : averse de 1,5 s, plus une glissade pour ceux à moins de 10 m | Vitesse plafonnée à 50 % de la vitesse d'équilibre pendant 1,5 s | − 6,9 s, − 3,0 s, − 7,0 s |
| Super-forme | `star` | Étoile | 8 s invincible ; vitesse au moins 1,2 × la vitesse d'équilibre ; les coureurs frôlés (même voie, moins de 1,5 m) glissent ; les objets au sol sont sans effet | v ≥ 1,2 v_éq pendant 8 s | + 4,2 s, + 2,8 s, + 3,9 s |
| Sonnette | `bell` | Super klaxon | Dring ! Onde de 15 m : détruit bidons et musettes, fait glisser les coureurs à moins de 5 m ; sonnée dans la seconde avant l'averse, elle chasse le nuage d'orage | — | — |
| Vent contraire | `headwind` | Éclair | Rafale de face pour tous les coureurs devant le lanceur | + 5 m/s virtuels pendant 6 s, sans ressenti | − 2,1 s, − 1,1 s, − 1,9 s |
| Voiture d'équipe | `team_car` | Fusée de rattrapage | La voiture du directeur sportif te remorque 6 s dans son abri, invincible ; tirée seulement à plus de 15 s du premier (lot GP4, véhicule et abri d'AS6) | v = 1,5 × v_éq pendant 6 s | + 9,5 s, + 6,4 s, + 8,5 s |
| Furtif | `stealth` | Fantôme voleur | L'Échappée de TT4 (pas d'abri pour les suiveurs, bots aveugles à l'attaque, avatar semi-transparent) plus le vol de l'objet du coureur devant à moins de 50 m (lot GP4) | 10 s | Dépend de l'abri perdu par les suiveurs |

Repères d'équilibrage :

- **L'inertie rend les coups plus forts que les impulsions** : avec 250 W, une vitesse multipliée par 0,5 coûte 6,2 s sur le plat, alors qu'une puissance × 1,5 pendant 3 s ne rapporte que 0,5 s. C'est pourquoi le coup de fouet est une impulsion de vitesse (v × 1,3) et non un bonus de puissance, et que la glissade est réglée à v × 0,7 : l'un et l'autre valent environ 4 s sur le plat.
- **En montée, tout compte moitié moins** (la vitesse est basse, la relance coûte peu de distance) : la course se joue toujours aussi aux jambes dans les cols.
- Le nuage d'orage est l'objet le plus fort contre le premier (≈ 7 s) : un seul en vol sur toute la course, jamais tiré par les deux premiers.
- Les valeurs sont dans `~/OpenRide/grandprix.toml` (facteurs, durées, portées, poids du tirage), bornées par objet ; elles sont réglées au banc simulé (lot GP5).

## 4. Obtention et usage

### 4.1 Boîtes de ravitaillement

- Une **rangée de trois boîtes** (une par voie) tous les **1,5 km** par défaut (1, 1,5, 2 ou 3 km au menu), la première à 500 m du départ, jamais à moins de 200 m de l'arrivée. Sur un circuit, les rangées restent aux mêmes endroits d'un tour à l'autre.
- Passer dans une rangée donne un objet si la réserve est vide (une seule réserve ; les objets triples comptent pour un). Une boîte prise se reforme 2 s plus tard.
- **Roulette** de 2 s à l'écran, puis l'objet est en réserve.

### 4.2 Tirage selon le retard

Le tirage dépend du **retard en secondes sur le premier**, pas de la place seule (avec 2 bots, être 3e à 1 s n'a rien d'un retard). Poids proposés (en %, jeu « normal ») :

| Objet | En tête | Moins de 5 s | 5 à 15 s | Plus de 15 s |
| --- | --- | --- | --- | --- |
| Bidon, trois bidons | 40 | 20 | 5 | 0 |
| Musette, trois musettes | 20 | 25 | 20 | 10 |
| Musette guidée | 0 | 20 | 20 | 10 |
| Sonnette | 25 | 5 | 0 | 0 |
| Coup de fouet, trois coups | 15 | 20 | 25 | 20 |
| Vent contraire | 0 | 5 | 10 | 10 |
| Nuage d'orage | 0 | 0 | 10 | 10 |
| Super-forme | 0 | 5 | 10 | 15 |
| Voiture d'équipe | 0 | 0 | 0 | 20 |
| Furtif | 0 | 0 | 0 | 5 |

Un objet désactivé au menu sort du tirage et les autres poids sont remis à 100 %. Un objet inutile n'est jamais tiré (pas de musette guidée sans coureur devant, pas de vent contraire en tête), comme le tirage contextuel de TT2.

### 4.3 Boutons et clavier

Rien de nouveau dans le plan de la [spécification générale](../SPECIFICATION_GENERALE.md) §7.1 : le lot GP2 lui ajoute seulement la colonne du mode, qui reprend les familles existantes.

| Bouton | Dans ce mode | Famille du §7.1 |
| --- | --- | --- |
| Z court | Utiliser l'objet (lancer, lâcher, avaler) | Action du mode (comme le bonus du classique) |
| Z long | Repère « décrochage » au journal | Inchangé |
| A court | Voie suivante quand un objet ou une boîte est en vue à moins de 150 m, ou une musette derrière ; sinon vue suivante | Choisir, comme la branche suivante du monde ouvert |
| A long | Retour au placement automatique ; sinon vue par défaut | Valider, comme le monde ouvert |
| Flèches gauche, droite | Voie à gauche, à droite (raccourci, le boîtier gauche n'étant pas fiable) | Choisir, raccourci |
| Flèches haut, bas | Vue suivante, précédente | Inchangé |
| +, B (ou −) | Braquet | Inchangé |
| Y | Pause | Inchangé |

Le choix de voie est affiché (trois petits traits en bas du HUD) dès qu'il a un sens, ce qui en fait un « choix affiché » au sens du §7.1. Le clavier double le Click touche pour touche (Z, A, flèches), sans touche propre au mode. Les objets ne se visent pas : chaque objet a une direction fixe (le bidon derrière, la musette devant), ce qui évite un bouton de plus.

### 4.4 Accès par les menus

Tout se règle dans le menu, sans ligne de commande (lot GP9) :

- Accueil : entrée « Grand Prix des objets », visible quand le core annonce le mode.
- Écran du mode : parcours (circuit et nombre de tours, ou distance), puis les réglages, puis « Objets » (une case par objet, comme l'écran des règles du Mode WTF), puis « Lancer ».

| Réglage (section `[grandprix]` de `config.toml`) | Valeurs | Défaut |
| --- | --- | --- |
| Adversaires (`opponents`) | 2 à 4, puis 2 à 11 avec GP10 | 4 |
| Tours (`laps`) ou distance (`distance_km`) | 1 à 5 ; 5 à 30 km | 3 ; 10 km |
| Niveau des bots (`bots.level_pct`, réglage existant) | 50 à 150 % de la FTP | inchangé |
| Chaos (`chaos`) | doux, normal, fou : forces et fréquence des objets × 0,7, × 1, × 1,3 | normal |
| Écart des boîtes (`box_every_km`) | 1, 1,5, 2, 3 | 1,5 |
| Objets (`items.<id>`) | activé, désactivé | tous activés |

## 5. Recouvrement avec les autres modes

| Série | Ce qu'elle fait | Ce que GP reprend | Ce que GP ajoute |
| --- | --- | --- | --- |
| T6 et TT (4.0) | Bonus pour soi, tirés en fin de segment ou sous une arche, un modèle unique décrit par des données (TT2) | Le modèle de TT2 et ses effets : `breakaway` (Furtif), le tirage contextuel, le refus motivé | Des effets de plus dans **la même table** : impulsion (`kick`), plancher de vitesse (`speed_floor`), invincibilité (`immune`), glissade (`slip`), plafond de vitesse (`cap`), rafale (`wind`) ; une **cible** (soi, devant, premier, coureurs proches) et une **forme** (immédiat, durée, objet posé, projectile) |
| CT (5.0) | Capacités payées par les relais (crédits), effets venus de la 4.0 | Rien d'autre que la table d'effets | Les boîtes : troisième façon d'obtenir les mêmes effets (hasard en classique, crédits en CT, boîtes en GP) |
| WTF (2.0) | Gags qui déforment la physique, objets semés (Katamari), fromage qui poursuit | Charte cartoon CT9 et réserve d'objets 3D de l'engine (WTF5, WTF6, PR #672), si elle se prête au partage | Un vrai jeu de course : objets offensifs, voies, classement. Les règles WTF ne changent pas |
| DS (3.0 proposée) | Course à l'élimination, physique honnête, sans bonus | Composition du plateau par le core, passage interpolé, bilan de place | Les objets. Variante « élimination avec objets » laissée en question ouverte (§9) |
| AS | Abri, voies (AS2), abri derrière les véhicules (AS6) | `lane_m`, placement automatique, véhicule et abri de la voiture d'équipe | Le choix de voie manuel |

Pour factoriser sans exception : le lot GP1 écrit les **objets sur la route** (position `s`, voie, durée de vie, contact) dans un petit module générique du core, `route_objects.py`, que WTF pourra reprendre plus tard s'il le souhaite (pas d'obligation, pas de changement des règles WTF). Les commandes de réglage des objets prennent la forme de celles du Mode WTF (`list_wtf_rules`, `set_wtf_rule`) ; je propose de les généraliser en `list_mode_options` et `set_mode_option` (avec `mode`), les commandes WTF restant des alias pendant une révision (question 4 du §9).

Décision 4.0 « bots sans bonus » : elle vaut pour le classique, où les records doivent rester justes. Ici, sans records, les bots prennent et lancent des objets, sinon le mode n'a pas de sens.

## 6. Bots (lot GP3)

Calculé dans le core, à chaque pas :

- **Usage** : coup de fouet, super-forme, voiture d'équipe et nuage d'orage tout de suite (après un délai tiré entre 0,5 et 3 s) ; bidon lâché quand un coureur est à moins de 30 m derrière ; musette quand une cible est sur la voie à moins de 150 m ; musette guidée à moins de 200 m ; sonnette quand un projectile arrive à moins de 30 m ou que le nuage vise le bot ; vent contraire avec au moins deux coureurs devant.
- **Garde** : un bot en tête garde son bidon ou sa musette en réserve comme bouclier, tant qu'aucune boîte n'approche.
- **Esquive** : un objet sur sa voie à moins de 40 m, le bot change de voie avec une probabilité qui dépend de son niveau et du chaos (30 % en doux, 50 % en normal, 75 % en fou, plus ou moins 10 points selon le niveau du bot).
- **Pas d'élastique physique** : un bot ne ralentit jamais parce que le joueur est loin. Le rattrapage passe uniquement par le tirage selon le retard (§4.2), visible et compréhensible.
- Les attaques et relais plus fins viendront avec Y10 ; GP3 n'en dépend pas.

## 7. Trainer, ressenti et honnêteté

- **Aucun objet ne touche la pente envoyée.** Glissade, averse, vent contraire : vitesse virtuelle seulement. Le cycliste relance avec ses watts : c'est la « vraie » perte, et elle se paie en effort réel.
- **Ce qui se ressent passe par les canaux existants** : l'abri derrière la voiture d'équipe et le supplément d'abri ou de vent, qui dépendent de la vitesse virtuelle, gardent leurs rampes (4 %/s à la montée, 8 %/s à la descente) et leur borne (`wind.max_grade_offset_pct`, 4 points par défaut). Une impulsion de vitesse peut donc faire varier ce supplément de quelques dixièmes de point, en douceur ; jamais d'à-coup.
- **Vent contraire sans ressenti** (règle de la Course tactique : jamais de résistance augmentée par une pénalité).
- **ERG** : mode interdit (`bad_args` au `start`, `busy` à `set_ride_mode`), comme WTF, CT et DS : en ERG le trainer impose la puissance et la relance après un coup n'aurait plus de sens.
- **Coupure du trainer** (#540, #542) : objets, projectiles et bots figés tant que la séance est suspendue ; aucun coup reçu pendant 3 s après la reprise.
- **Lisibilité** : clignotement de 2 Hz au plus, pas de flash plein écran, couleurs doublées d'une forme (icône), comme les autres modes cartoon.
- **Records et FIT** : pas de record dans ce mode ; puissance, cadence et fréquence cardiaque réelles au journal et au FIT ; événements `gp` au journal (objet, lanceur, cible, temps perdu).

## 8. Contrat, HUD et performances

### 8.1 Contrat (lot GP2)

Révision : la première libre à la fusion de GP2 (la 1.6 est réservée à la série U, les suivantes à TT1 et à DS2 selon l'ordre des fusions). Ajouts compatibles :

- `start` : `mode` gagne `grandprix` ; avec un entraînement ERG, un fantôme ou un argument `bots` : `bad_args`.
- `state.gp`, dans chaque trame de la course :

```json
{"lap": [2, 3], "place": 3, "of": 5, "gap_s": 6.4, "held": "homing", "n": 1, "roll_s": 0.0,
 "lane": 1, "auto": true, "fx": [["star", 5.2]], "warn": ["homing", 42.0],
 "obj": [[17, "bottle", 1520.4, 2], [18, "musette", 1610.0, 1]], "boxes": [1950.0]}
```

  `obj` = objets et projectiles de 100 m derrière à 400 m devant (identifiant, sorte, `s`, voie), 12 au plus ; `fx` = effets actifs et reste en s ; `warn` = menace qui vise le joueur et sa distance. Environ 450 octets au pire. Chaque élément de `bots` gagne `item` (réserve) et `fx`. La pire trame mesurée (2 456 octets) reste sous 4 096 octets avec 11 bots ; à vérifier par `python -m openride_core.ipc_budget`.
- Message `gp_hit` : `v`, `item`, `by`, `target`, `loss_s` (perte estimée), répété 3 fois à 1 s comme `segment_result`.
- `summary.gp` : `place`, `of`, `laps` ou `distance_km`, objets lancés, reçus, esquivés, temps gagné et perdu par objet.
- Réglages des objets : voir question 4 du §9.

### 8.2 HUD et sons (maquettes GP6, puis GP7 et GP8)

Style : la **charte cartoon CT9**, partagée avec le Mode WTF, pour ne pas créer un troisième style. Les objets ont un dessin propre à OpenRide (bidon, musette en toile, voiture d'équipe avec vélos sur le toit), sans emprunt à un jeu existant.

- **Case d'objet** en haut au centre, avec la roulette de 2 s et le nombre de charges.
- **Place et tours** en haut à droite (libres puisque segments et bonus sont coupés) : « 3e / 5 · tour 2 / 3 · à 6,4 s du premier ».
- **Bande de course** à gauche : coureurs dans l'ordre, avec l'objet qu'ils tiennent.
- **Avertissements** : « Musette guidée derrière ! » avec une flèche, « Orage vers le premier » ; contour coloré de l'écran (pas de flash plein écran).
- **Choix de voie** : trois traits en bas, la voie choisie en blanc, la voie automatique en gris.
- **Sons** : roulette, lancer, glissade, averse, dring de la sonnette, klaxon de la voiture d'équipe ; famille des jingles existants (`sound_player.gd`).

### 8.3 Performances (budgets GPU : low 6 ms, medium 12 ms, high 14 ms)

- **Boîtes** : seules la prochaine rangée et la précédente existent dans la scène (six boîtes au plus, un `MultiMesh`).
- **Objets et projectiles** : 32 au plus dans le core (les plus vieux bidons disparaissent), 12 au plus dans la scène (ceux de la trame), une réserve d'instances par sorte, aucune création en course.
- **Effets** : `low` sans particules (sprites seulement), `medium` particules limitées, `high` averse et étincelles complètes.
- **Bots** : le coût est celui du lot Y18 ; avec 11 adversaires (GP10), c'est la mesure principale, repli par les distances de LOD (`BOT_LOD_M`).
- **Core** : contacts testés en O(objets × coureurs) par pas, soit 32 × 12 au pire : rien de mesurable à 50 Hz.
- Pire cas mesuré au banc : départ avec tous les bots, six boîtes et douze objets, en `low`, `medium` et `high` ; captures validées par le propriétaire avant fusion des lots d'affichage.

## 9. Lots

| Lot | Titre | Dépend de | Taille |
| --- | --- | --- | --- |
| [GP1](../lots/LOT_GP1_objets_core.md) | Core : catalogue, effets, objets sur la route, projectiles, contacts, tirage | TT2, AS2, T12, T13 | Grande |
| [GP2](../lots/LOT_GP2_seance_contrat.md) | Séance, réglages, contrat IPC et colonne du plan des boutons | GP1 | Moyenne |
| [GP3](../lots/LOT_GP3_bots_objets.md) | Bots : usage des objets, garde et esquive | GP1 | Moyenne |
| [GP4](../lots/LOT_GP4_voiture_furtif.md) | Voiture d'équipe et Furtif | GP1, AS6, TT4 | Petite |
| [GP5](../lots/LOT_GP5_equilibrage.md) | Équilibrage au banc simulé et fichier de valeurs | GP1, GP3 | Moyenne |
| [GP6](../lots/LOT_GP6_maquettes.md) | Maquettes des objets, des boîtes, du HUD et du bilan, validées par le propriétaire | GP1 | Petite |
| [GP7](../lots/LOT_GP7_objets_engine.md) | Engine : boîtes, objets, projectiles, effets et sons | GP2, GP6 | Grande |
| [GP8](../lots/LOT_GP8_hud_bilan.md) | Engine : HUD, avertissements et bilan | GP2, GP6 | Moyenne |
| [GP9](../lots/LOT_GP9_menu.md) | Menu : entrée du mode, réglages et objets désactivables | GP2 | Petite |
| [GP10](../lots/LOT_GP10_peloton_onze.md) | Jusqu'à 11 adversaires (après le peloton du lot Y18) | GP2, GP3, Y18 | Moyenne |
| [GP11](../lots/LOT_GP11_recette.md) | Recette sur le vélo (étapes de 10 min) et banc `low`, `medium`, `high` | GP3, GP5, GP7, GP8, GP9 | Petite |

Ordre : TT2, AS2, T12, T13 ──► GP1 ──► GP2, GP3, GP6 ;  GP1, GP3 ──► GP5 ;  GP1, AS6, TT4 ──► GP4 ;  GP2, GP6 ──► GP7, GP8 ;  GP2 ──► GP9 ;  GP2, GP3, Y18 ──► GP10 ;  GP3, GP5, GP7, GP8, GP9 ──► GP11.

GP1 attend TT2 (modèle d'effets de la 4.0) et AS2 (voies) : rien ne peut démarrer avant. GP6 (maquettes) peut avancer dès GP1, et même avant si le propriétaire veut voir le style tôt. Les lots GP ne touchent ni la série Q, ni les règles du Mode WTF, ni les records du classique.

## 10. Questions ouvertes (réponses par défaut appliquées en attendant)

1. **Version** : **4.0**, après TT2. L'avancer en 3.0 demanderait d'écrire le modèle d'effets de TT2 plus tôt.
2. **Nom du mode** : « Grand Prix des objets » ; noms des objets du §3 (Coup de fouet, Bidon glissant, Musette lancée, Musette guidée, Nuage d'orage, Super-forme, Sonnette, Vent contraire, Voiture d'équipe, Furtif).
3. **Bots** : ils prennent et lancent des objets dans ce mode (sans records), contrairement au classique 4.0.
4. **Commandes de réglage** : généraliser celles du Mode WTF en `list_mode_options` et `set_mode_option` (recommandé, sans exception) plutôt que d'ajouter `list_gp_items` et `set_gp_item`.
5. **Vent contraire** : sans ressenti sur le trainer (défaut, règle de la Course tactique) ; un léger ressenti borné reste possible si le propriétaire le souhaite.
6. **Format** : course simple ; une « coupe » de trois manches avec points (comme un championnat) pourrait venir plus tard.
7. **Variante avec élimination** (DS) : pas dans la série ; à reconsidérer après DS et GP.
