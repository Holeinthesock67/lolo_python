# Recherche – Pourquoi le boîtier gauche du Zwift Click V2 se tait

Recherche documentaire du 27 octobre 2026 : spécification publique du protocole (dépôts open source,
rétro-ingénierie) et retours d'utilisateurs (forums, issues GitHub), comparés au code d'OpenRide et
aux relevés de l'outil `boutons_click` (protocole G3). Complète `docs/DIAG_CLICK_GAUCHE.md` (lot Q6),
dont certaines affirmations sont ici vérifiées ou corrigées (§5).

Aucune donnée personnelle : pas d'adresse Bluetooth ni de nom de boîtier réel. Matériel cité :
Click V2, matériel B.0, firmware 1.0.2 puis 1.2.0.

## 1. Le constat à expliquer

| Firmware | Boîtier droit | Boîtier gauche |
| --- | --- | --- |
| 1.0.2 | 10 appuis sur 10 | touches reçues pendant environ 35 à 70 s après la connexion, puis plus rien, liaison toujours active |
| 1.2.0 (mise à jour par l'appli Zwift) | 10 appuis sur 10 | relié, aucune touche reçue, même juste après la connexion |

Résultat du test guidé : 10/17. Pendant l'essai du 25 octobre, le boîtier gauche « muet » envoyait
encore environ 22 notifications par minute, toutes sans bouton appuyé.

## 2. Réponse courte

Le comportement est **connu, publié et voulu par Zwift** : le boîtier gauche du Click V2 se
« verrouille » environ une minute après la connexion s'il n'a pas été déverrouillé par l'appli Zwift
dans les dernières 24 heures environ. La liaison reste active, le boîtier continue d'envoyer des
messages d'état, mais plus aucun message de bouton « en clair ». Quatre projets indépendants
(BikeControl, zwiftboard, OpenRadlr, qdomyos-zwift) décrivent la même chose et aucun ne sait le
déverrouiller seul : le déverrouillage passe par un défi cryptographique auquel seule l'appli Zwift
répond. Les contournements publiés sont : utiliser le boîtier droit seul (ce que fait OpenRide avec
B = « − »), redémarrer le boîtier gauche à distance avant chaque minute, ou passer par l'appli Zwift
avant chaque séance.

## 3. Ce que dit la spécification publique (rétro-ingénierie)

Il n'existe aucune documentation officielle de Zwift. Tout ce qui suit vient de dépôts open source.

### 3.1 Service et caractéristiques (déjà dans OpenRide)

Service `00000001-19ca-4651-86e5-fa29dcdd09d1`, notifications `…0002` (ASYNC), écriture `…0003`
(SYNC_RX), indications `…0004` (SYNC_TX). Identifiant constructeur Bluetooth de Zwift : `0x094A`.
Messages de boutons : octet `0x23` puis protobuf, champ 1 = tableau de bits, 0 = appuyé ; bits
LEFT 0x1, UP 0x2, RIGHT 0x4, DOWN 0x8, A 0x10, B 0x20, Y 0x40, Z 0x80, MINUS 0x100, PLUS 0x1000.
Ces valeurs sont identiques à `KEYPAD_BITS` dans `core/src/openride_core/zwift_click.py`.
Source : [zwiftboard, README](https://github.com/AntoninGuilbaud/zwiftboard) et
[internal/zwift/protocol.go](https://github.com/AntoninGuilbaud/zwiftboard/blob/HEAD/internal/zwift/protocol.go).

### 3.2 Architecture de la paire

- Le **boîtier gauche est l'« ancre » de la paire** : le droit lui recopie son état par une liaison
  radio privée, et le gauche relaie donc aussi les appuis du droit
  ([zwiftboard, section « Both pods connected »](https://github.com/AntoninGuilbaud/zwiftboard)) ;
  OpenRadlr le constate aussi (« the left half relays the right half's presses »,
  [OpenRadlr PR #13](https://github.com/Lethonium/OpenRadlr/pull/13)). C'est ce qu'OpenRide a mesuré
  le 24 octobre (`ClickPair`, déduplication à 150 ms dans `input_providers.py`).
- Dans les données constructeur des annonces BLE, le droit porte le type `0x0A`, le gauche `0x0B`
  ([OpenRadlr PR #13](https://github.com/Lethonium/OpenRadlr/pull/13)).
- Un boîtier droit seul, sans le gauche allumé, perd sa liaison environ 65 s après son dernier appui
  ([zwiftboard, dépannage](https://github.com/AntoninGuilbaud/zwiftboard)) : il faut garder les deux
  allumés même si l'on n'utilise que le droit.

### 3.3 Poignée de main, maintien, verrou

D'après le code de zwiftboard
([internal/ble/ble.go](https://github.com/AntoninGuilbaud/zwiftboard/blob/HEAD/internal/ble/ble.go),
« verified on Click V2 hardware ») :

- **Activation** : trois écritures sur SYNC_RX à 100 ms d'intervalle : `RideOn 02 03`, `00 08 00`,
  `00 08 10`. OpenRide n'écrit que `RideOn` seul.
- **Réponse** : un boîtier **déverrouillé** renvoie l'écho `RideOn` sur SYNC_TX ; un boîtier
  **verrouillé** envoie un **défi cryptographique commençant par `0xFF`**, sur ASYNC (pas sur SYNC_TX).
- **Garder un boîtier déjà déverrouillé** : répondre `ff 04 00` sur SYNC_RX à l'écho et à chaque défi
  « garde le flux de boutons » d'un boîtier déjà déverrouillé. Cela ne déverrouille pas un boîtier
  verrouillé.
- **Maintien** : `RideOn` toutes les 3 s, qui sert seulement à détecter une coupure ; il ne réveille
  rien et ne déverrouille rien.
- **Redémarrage à distance** : un octet seul `0x18` écrit sur SYNC_RX fait redémarrer le boîtier, qui
  se réannonce en quelques secondes. zwiftboard l'envoie après 55 s sans appui.

D'après OpenRadlr ([PR #13, `zwiftProtocol.js`](https://github.com/Lethonium/OpenRadlr/pull/13/files)) :

- Le gauche envoie un **message d'état** qui commence par `ff 05 00 ea 05 <longueur>`, suivi d'un
  protobuf : champ 1 = l'autre moitié de la paire, champ 2 = « mode ». Les boutons en clair arrivent
  tant que le mode vaut 0 ; **il passe à 1 environ une minute après la connexion** et les boutons
  s'arrêtent.
- Renvoyer `RideOn`, un maintien `RideOn` ou la séquence d'activation de zwiftboard **ne
  déverrouille pas** ; le défi `ff 03` « n'est résolu que par Zwift ».
- Redémarrer le gauche avec `0x18` **redonne une minute** de boutons en clair (vérifié par l'auteur
  sur une paire Click V2). Le **droit ne se verrouille jamais** mais n'envoie que ses propres boutons.

BikeControl a activé le chiffrement pour le Click V2 en mai 2026
([commit 788cd59](https://github.com/OpenBikeControl/bikecontrol/commit/788cd59)) ; le détail de la
négociation n'est pas public dans ce commit.

### 3.4 Firmware

- Zwift ne publie pas de notes détaillées pour le Click V2. D'après le fil BikeControl,
  le **1.2.0 est sorti le 16 mars 2026** avec un correctif pour les « ponts » des home-trainers Zwift
  Ready ; le développeur de BikeControl déconseille toute mise à jour non validée par lui
  ([issue #68](https://github.com/OpenBikeControl/bikecontrol/issues/68)).
- Avec le 1.2.0, des utilisateurs de QZ signalent que les événements du boîtier gauche n'arrivent
  **jamais** (« the event for the left controller never reach qz »), alors qu'il fonctionne dans
  Zwift ([qdomyos-zwift #4456](https://github.com/cagnulein/qdomyos-zwift/issues/4456)). C'est notre
  relevé du 27 octobre sous 1.2.0.
- Un utilisateur signale que la touche de regard en arrière ne marche plus après le 1.2.0
  ([forum Zwift](https://forums.zwift.com/t/zwift-click-v2-firmware-1-2-0-broken-rearview/667185)).

## 4. Retours d'utilisateurs

| Source | Ce qui est rapporté |
| --- | --- |
| [BikeControl #68](https://github.com/OpenBikeControl/bikecontrol/issues/68) (sept. 2025 → juin 2026) | Firmware 1.1.0 : boutons reçus puis plus rien après une minute, quand la LED bleue s'éteint ; la liaison BLE reste active. Corrigé « pour un temps » en connectant brièvement le Click dans l'appli Zwift. En juin 2026, le développeur écrit que le droit marche de façon fiable et que le gauche « needs a quick restart every minute (or you unlock it with Zwift like before) » ; il conseille d'utiliser le droit seul. |
| [BikeControl, TROUBLESHOOTING.md](https://github.com/OpenBikeControl/bikecontrol/blob/HEAD/TROUBLESHOOTING.md) | Méthode manuelle : ouvrir l'appli Zwift (pas Companion), se connecter (abonnement non requis), connecter le home-trainer puis le Click, attendre 10 à 30 s, fermer Zwift complètement, puis se connecter dans l'autre appli. |
| [qdomyos-zwift #5053](https://github.com/cagnulein/qdomyos-zwift/issues/5053) (sept. 2026, firmware 1.2.0) | « After a minute or so, the left device stops working while the right continues ». Résolu en gardant le Click connecté dans l'appli Zwift complète **trois minutes** ; Companion seul ne suffit pas selon le mainteneur. |
| [qdomyos-zwift #4456](https://github.com/cagnulein/qdomyos-zwift/issues/4456) (mars 2026, firmware 1.2.0) | Droit OK, gauche « connecté » mais aucun « − », alors qu'il navigue dans les menus de Zwift ; deux minutes dans Zwift n'ont pas suffi. Fermé sans solution. |
| [zwiftboard](https://github.com/AntoninGuilbaud/zwiftboard) | Choix assumé : seuls les boutons du droit sont utilisés, « no 24h controller unlock ». |
| [OpenRadlr PR #13](https://github.com/Lethonium/OpenRadlr/pull/13) | Détection du verrou par le message d'état, redémarrage `0x18` une fois par verrou, et B du droit = « − » quand le gauche est verrouillé : exactement le contournement d'OpenRide. |
| Forums Zwift ([commandes qui ne marchent pas](https://support.zwift.com/en_us/controls-not-working-on-zwift-click-BJKICSXWp.md), [Click V2 disconnecting](https://forums.zwift.com/t/zwift-click-v2-disconnecting/657878)) | Côté appli Zwift, les pannes du gauche rapportées sont surtout matérielles (pile mal tenue, coupures) ; rien sur les applis tierces, et pas de déclaration officielle sur le verrou. |

Aucun fil Reddit pertinent trouvé. Les pages des forums Zwift, de DC Rainmaker et de Zwift Insider
n'étaient pas lisibles depuis l'environnement de recherche : seuls leurs résumés de recherche ont
servi, et rien d'essentiel n'en dépend.

## 5. Comparaison avec OpenRide

| Point | OpenRide aujourd'hui | Ce que disent les sources |
| --- | --- | --- |
| Poignée de main | `RideOn` seul sur SYNC_RX (`input_providers.py`, `_connected_session`) | Activation en trois écritures ; ne change rien au verrou, mais c'est la séquence « vérifiée » |
| Réponse SYNC_TX | abonné, **contenu ignoré** | l'écho `RideOn` indique un boîtier déverrouillé : c'est le meilleur indicateur à journaliser |
| Messages `0xFF` sur ASYNC | classés « inconnu » ; visibles en hexadécimal avec `click_trace_raw` | défi cryptographique et message d'état `ff 05 00 ea 05`, dont le champ 2 dit si le gauche est verrouillé |
| `ff 04 00` | jamais envoyé | garde déverrouillé un boîtier déjà déverrouillé par Zwift |
| Reprise du lot Q6 (`click_rehandshake_s`) | renvoi `RideOn`, réabonnement, reconnexion complète | renvoyer `RideOn` ne déverrouille pas ; seul le redémarrage `0x18` redonne une minute |
| Détection « muet » | aucun appui pendant 60 s, ou débit de notifications faible (`boutons_click`) | un verrou se lit directement : mode = 1 dans le message d'état |
| Contournement | B du droit = « − » | même choix dans zwiftboard, OpenRadlr et BikeControl (« right only ») |

Corrections à `docs/DIAG_CLICK_GAUCHE.md` :

- §2 point 3 et docstring de `zwift_click.py` : le constat de BikeControl et zwiftboard est confirmé
  (sources ci-dessus) ; il ne s'agit pas d'un passage en veille de la liaison.
- §3, hypothèse 3 (CCCD, intervalle de connexion) : écartée, la liaison et les notifications
  continuent ; seul le contenu change.
- §2 : `0x15` n'est pas un vrai maintien côté protocole ; les ~22 messages par minute sans bouton
  sont très probablement les messages d'état et les défis `0xFF` du gauche verrouillé (à vérifier
  par l'essai A).

## 6. Hypothèses classées

1. **Verrou volontaire du boîtier gauche par Zwift** (très probable). Après environ une minute, ou
   dès la connexion avec le 1.2.0, le gauche passe en mode verrouillé faute d'un déverrouillage par
   l'appli Zwift dans les 24 h environ. Explique les deux relevés, la liaison qui tient, les
   messages sans bouton, et que le droit ne soit jamais touché. Le 1.2.0 semble verrouiller plus tôt
   (QZ #4456 et notre relevé) ; rien de public ne le confirme officiellement.
2. **Poignée de main incomplète d'OpenRide** (facteur secondaire). Sans `ff 04 00`, un boîtier
   déverrouillé par Zwift pourrait se reverrouiller plus vite chez nous que dans BikeControl ou
   zwiftboard. Ne peut pas, à lui seul, expliquer le 1.2.0.
3. **Connexion directe aux deux boîtiers qui gênerait la liaison privée** (peu probable).
   zwiftboard dit au contraire qu'il faut garder le gauche connecté pour que le droit tienne.
4. **Défaut matériel ou pile du gauche** (peu probable). Le gauche se connecte, envoie des messages
   et a envoyé des touches pendant ~70 s sous 1.0.2 ; un essai dans l'appli Zwift tranche.

## 7. Essais proposés (sur le PC, par le propriétaire)

Rien n'a été lancé ni modifié sur le PC. Les essais A et B se font avec le code actuel ; C et D
demandent un petit lot de code (§8).

**Essai A – lire le verrou dans la trace (10 min, code actuel).** Avec `click_trace_raw = true`, lancer
`click_recette --minutes 3` ou une séance courte, appuyer sur le gauche toutes les 20 s. Chercher dans
le journal les lignes `Click gauche ASYNC type 0xff` : un message dont l'hexadécimal commence par `ff0500ea05`
confirme l'hypothèse 1 ; noter l'heure de passage du champ 2 à 1 (octets après la longueur). Ne pas
recopier d'adresse dans le compte rendu.

**Essai B – déverrouillage par l'appli Zwift (15 min, code actuel).** Méthode manuelle de BikeControl :
appli Zwift complète (pas Companion), connecter le home-trainer puis le Click, vérifier que « − » et
les flèches répondent, **attendre trois minutes**, fermer Zwift complètement, puis lancer aussitôt
`boutons_click`. Attendu si l'hypothèse 1 est juste : 17/17, ou au moins les touches du gauche
au-delà de la minute. Refaire le lendemain sans passer par Zwift pour voir la durée du
déverrouillage. Si le gauche ne répond pas non plus dans Zwift, c'est l'hypothèse 4.

**Essai C – redémarrage `0x18` (lot de code).** Quand le gauche est verrouillé, écrire `0x18` sur
SYNC_RX et mesurer : délai de réapparition, durée de la nouvelle fenêtre de boutons, appuis perdus
pendant le redémarrage, sous firmware 1.2.0.

**Essai D – garder le déverrouillage (lot de code).** Après l'essai B, séance d'une heure avec la
séquence d'activation complète et la réponse `ff 04 00`, comparée à une séance sans.

## 8. Suite proposée

- **Code, petit lot « lecture du verrou »** : journaliser les trames SYNC_TX et décoder le message
  d'état `ff 05 00 ea 05` (verrouillé ou non, côté gauche) dans `zwift_click.py` ; remplacer la
  détection « muet » par cette lecture directe ; envoyer la séquence d'activation complète et
  `ff 04 00`. Sans risque pour le droit.
- **Option à décider ensuite** : redémarrage automatique du gauche par `0x18` (comme OpenRadlr et
  BikeControl). Avantage : flèches et « − » utilisables. Inconvénient : quelques secondes sans
  gauche chaque minute environ, et un boîtier qui redémarre en pleine séance. Le contournement
  actuel (B = « − », rien d'indispensable sur le seul gauche, spécification §7.1) reste la base.
- **Ne pas mettre à jour le firmware** au-delà du 1.2.0 sans relire ces sources.

## 9. Suivi : essai C livré (30 octobre 2026)

L'essai B (déverrouillage par l'appli Zwift) est abandonné : pas d'abonnement Zwift, et l'appli
Companion seule n'a rien changé. Le code livre à la place l'essai C, **activé par défaut depuis le 30/10/2026** (après l'essai ci-dessous) :

- `zwift_click.parse_status` lit le message d'état `ff 05 00 ea 05` du boîtier gauche ; la trace et le
  journal le classent en « état » et notent chaque changement de mode (`Click gauche : état du boîtier,
  mode 1 (verrouillé par Zwift)`). Cette lecture est active tout le temps et ne change rien au
  comportement.
- `[drivers] click_reset_locked = true` (défaut ; `false` laisse le boîtier muet) : dès que le mode passe à 1, le core écrit l'octet `0x18` sur
  SYNC_RX. Le boîtier redémarre, la liaison tombe, la reconnexion habituelle reprend (journal :
  « verrouillé par Zwift, redémarrage du boîtier (0x18) »). Un seul redémarrage par connexion.
- Risque connu : d'après zwiftboard, le droit s'appuie sur le gauche pour sa liaison ; il pourrait
  lui aussi tomber pendant le redémarrage. À observer pendant l'essai.

Essai à faire sur le PC (10 minutes) : `click_trace_raw = true` et `click_reset_locked = true`, séance
avec appuis réguliers sur le gauche toutes les 20 s. À relever : présence des lignes « état », délai
avant le mode 1, durée de la nouvelle fenêtre de boutons après chaque redémarrage, et si le droit
reste connecté.

**Résultat de l'essai (PC, 30/10/2026, firmware 1.2.0).** Un premier passage n'a rien redémarré :
`decode_protobuf_varints` décalait la lecture après le champ 1 (longueur, numéro de série) et lisait
toujours le mode 0 (corrigé par #607, tests avec les deux vraies trames). Sur 7 min 18 avec la
correction : 7 verrous, chacun 47,7 à 52,1 s après la connexion du gauche ; `0x18` écrit 6 à 187 ms
après, liaison coupée 0,3 s plus tard, reconnexion en 3,8 à 7,1 s, mode 0 relu. Le gauche manque donc
environ 4,5 s sur chaque cycle de 56 s (8 %) ; un appui fait pendant la coupure est perdu (20 « − »
reçus sur 21 bips). Le droit est resté connecté tout du long. Le redémarrage est donc activé par défaut ;
rien d'indispensable ne doit dépendre du seul boîtier gauche (le droit couvre tout, B = « − »).

Un troisième essai (4 min) a reçu les quatre flèches du gauche avant et après chacun des 4 redémarrages
(46 flèches, reconnexion en 3,8 à 8,1 s ; haut et bas changent bien la vue). Les aides à l'écran montrent
depuis le 31 octobre « − » et les flèches à côté de B (bandeau des menus : « + A → » suivant, « − B ← » précédent).
