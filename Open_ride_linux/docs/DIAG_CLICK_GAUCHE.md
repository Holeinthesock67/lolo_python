# Diagnostic – Boîtier gauche du Zwift Click muet après la connexion

**Statut au 31 octobre 2026 : réglé.** Le boîtier gauche est redémarré quand Zwift le verrouille (`[drivers] click_reset_locked`, vrai par défaut, docs/RECHERCHE_CLICK_GAUCHE.md §9) ; − et les quatre flèches sont reçus (essais sur le PC du 30 octobre, firmware 1.2.0). B du boîtier droit n'est plus un contournement : il double « − » pendant les environ 4 s de chaque redémarrage. Ce document garde l'historique du diagnostic.

## 1. Contexte et constat (essai du 25 octobre 2026)

Lors de la séance d'essai du 25 octobre 2026 :
- Les deux boîtiers du **Zwift Click V2** se sont connectés avec succès en BLE et sont restés connectés pendant toute la séance (aucun décrochage intempestif de la liaison radio).
- Cependant, le boîtier gauche (« − ») a cessé de transmettre les appuis physiques environ 5 secondes après sa connexion initiale.
- Par la suite, le boîtier gauche a continué à émettre environ **22 notifications par minute**, mais aucune d'entre elles ne contenait d'état de bouton appuyé.
- Tous les passages de vitesse vers le bas (« − ») ont été assurés grâce au bouton **B** du boîtier droit (contournement mis en place lors des travaux précédents).

Ce comportement est documenté dans la littérature libre sur le protocole Zwift Click et Zwift Play. Ce rapport synthétise l'état de l'art public, formule les hypothèses explicatives et définit le protocole d'essai sur le matériel.

---

## 2. État de l'art public et documentation du protocole

Plusieurs projets open-source ont analysé et rétro-ingénié le protocole propriétaire de Zwift pour les périphériques Zwift Click et Zwift Play :

1. **jat255 / zwift_click_handling** :
   - Mise en évidence de l'architecture GATT propriétaire :
     - Service : `00000001-19ca-4651-86e5-fa29dcdd09d1`
     - Caractéristique de notification asynchrone (`ZWIFT_ASYNC`) : `00000002-19ca-4651-86e5-fa29dcdd09d1`
     - Caractéristique d'écriture (`ZWIFT_SYNC_RX`) : `00000003-19ca-4651-86e5-fa29dcdd09d1`
     - Caractéristique de réponse (`ZWIFT_SYNC_TX`) : `00000004-19ca-4651-86e5-fa29dcdd09d1`
   - Décodage du handshake initial non chiffré par écriture de `b"RideOn"` sur `SYNC_RX` et réception de la réponse sur `SYNC_TX`.

2. **ajchellew / zwiftplay** :
   - Documentation de la structure des paquets asynchrones : préfixe d'un octet de type (`0x37` pour les premières versions, `0x23` pour les versions récentes à tableau de bits, `0x19` pour le niveau de batterie, `0x15` pour les paquets de maintien / keepalive).
   - Format Protobuf simplifié pour les champs varints.

3. **BikeControl** et **zwiftboard** :
   - Constat explicite d'un bridage temporel (lockout / mute) du boîtier gauche sur le Zwift Click V2 : en l'absence de négociation périodique ou si le boîtier n'a pas été appairé récemment avec l'application Zwift officielle, le boîtier gauche désactive la transmission de ses touches (touches fléchées et bouton « − ») après environ 1 minute ou dès le passage en mode veille.
   - La liaison Bluetooth reste active, le périphérique envoie des pings périodiques à basse fréquence (~0,3 à 0,5 Hz, soit environ 20–25 notifications par minute), mais les changements d'état du clavier ne sont plus signalés dans le bitmask `0x23`.

---

## 3. Hypothèses techniques

À partir des relevés et du code d'OpenRide Linux :

### Hypothèse 1 : Bridage micrologiciel (firmware lockdown)
Le micrologiciel interne du boîtier gauche exige un déverrouillage cryptographique ou une commande de handshake spécifique que seule l'application propriétaire Zwift émet (ou conserve un état déverrouillé pendant 24 heures après synchronisation avec l'application officielle). Passé ce délai ou sans séquence de déverrouillage complète, le boîtier bascule en mode de veille fonctionnelle partielle : la liaison BLE est maintenue par des trames de maintien (`0x15` ou `0x23` neutre), mais les entrées utilisateur sont ignorées pour décourager les logiciels tiers non certifiés.

### Hypothèse 2 : Nécessité d'un acquittement ou rafraîchissement d'état
Le boîtier gauche attend peut-être un acquittement sur `SYNC_RX` ou une notification sur la caractéristique `00000006-19ca-4651-86e5-fa29dcdd09d1` (`ZWIFT_UNKNOWN_6`). L'absence d'échange sur ce canal après les premières secondes pourrait amener le boîtier à considérer que la session applicative n'a pas été validée.

### Hypothèse 3 : Désynchronisation de la souscription aux notifications BLE
Le contrôleur BLE du boîtier pourrait cesser d'émettre les notifications d'interruption clavier suite à un problème de configuration CCCD (Client Characteristic Configuration Descriptor) ou de paramètre de connexion de l'intervalle de connexion BLE (Connection Interval).

---

## 4. Outils et mécanismes mis en place (Lot Q6)

Pour poser le diagnostic définitif sur le matériel réel, les mécanismes suivants ont été intégrés dans `openride_core` :

1. **Trace brute configurable (`[drivers] click_trace_raw = true`)** :
   - Journalisation détaillée de chaque notification avec horodatage, identification du boîtier (`gauche`, `droit`, `inconnu`), caractéristique UUID, type d'opcode en hexadécimal et classification textuelle.
   - Agrégation avec limitation de débit (au plus une ligne toutes les 2 secondes pour les messages répétés sans bouton) pour éviter la saturation du journal à 10 Hz tout en préservant le décompte exact.
   - Les appuis réels sur les boutons sont journalisés immédiatement sans aucun regroupement.

2. **Classement automatique des messages (`zwift_click.classify_message`)** :
   - `boutons` : opcodes `0x23` (clavier récent), `0x37` (notification historique), `0x07` (contrôleur Play).
   - `batterie` : opcode `0x19`.
   - `maintien` : opcode `0x15` (message vide / keepalive).
   - `inconnu` : tout autre opcode non référencé.
   - Décompte cumulé consultable à la coupure ou dans le résumé périodique.

3. **Détection du statut « muet » (`click_mute_after_s`, défaut 60 s)** :
   - Émission d'un avertissement unique au journal si un boîtier reste connecté et émet des notifications sans aucun appui pendant le délai configuré :
     `Click gauche : connecté mais muet depuis 60 s`

4. **Procédure de reprise automatique échelonnée (`click_rehandshake_s`)** :
   - Désactivée par défaut (`0.0`). Si configurée (ex. `30` s) :
     - Étape 1/3 : renvoi de la commande `b"RideOn"` sur `SYNC_RX`.
     - Étape 2/3 : désabonnement puis réabonnement à `ASYNC`.
     - Étape 3/3 : déconnexion logicielle puis reconnexion BLE complète.
     - En cas d'échec persistant, arrêt définitif des tentatives pour éviter toute boucle de reconnexion tant qu'aucun appui n'a été reçu.

5. **Outil d'analyse hors-ligne (`openride-ble-diag trace <fichier.log>`)** :
   - Analyse d'un journal contenant des traces brutes pour extraire les fréquences et la répartition en pourcentages des différents types de trames.

---

## 5. Protocole d'essais à réaliser sur le matériel cible (propriétaire)

> [!IMPORTANT]
> Ne jamais consigner d'adresses Bluetooth réelles dans les retours d'essais ou les journaux partagés (utiliser des adresses masquées ou fictives de type `AA:BB:CC:...`).

### Essai 1 : Capture de la trace brute (10 minutes)
1. Dans `~/OpenRide/config.toml`, renseigner :
   ```toml
   [drivers]
   click_trace_raw = true
   click_mute_after_s = 60
   click_rehandshake_s = 0
   ```
2. Lancer une séance d'essai de 10 minutes :
   `scripts/openride-dev.sh --trainer ftms --input click --autostart`
3. Actionner le boîtier gauche (bouton « − » et flèches) au début puis régulièrement.
4. À la fin de la séance, exécuter l'analyse de trace :
   `python -m openride_core.tools.ble_diag trace ~/run_trainer.log`
5. Noter les opcodes réels renvoyés par le boîtier gauche (notamment le détail hexadécimal des ~22 notifications/min).

### Essai 2 : Test de la reprise automatique échelonnée (10 minutes)
1. Dans `~/OpenRide/config.toml`, configurer la reprise :
   ```toml
   [drivers]
   click_trace_raw = true
   click_mute_after_s = 60
   click_rehandshake_s = 30
   ```
2. Lancer la séance et observer le journal :
   - Constater le déclenchement de la détection après 60 s d'inactivité bouton.
   - Observer les 3 étapes de reprise (renvoi `RideOn`, réabonnement, reconnexion).
   - Constater si l'une des étapes restaure les appuis du boîtier gauche, ou si le boîtier reste muet.

### Essai 3 : Test de l'hypothèse de déblocage par l'application Zwift (24 h)
1. Connecter les boîtiers Click à l'application officielle Zwift ou Zwift Companion sur smartphone.
2. Vérifier que les boutons répondent dans l'application officielle.
3. Fermer l'application officielle et couper le Bluetooth du smartphone.
4. Lancer immédiatement une séance OpenRide et vérifier si le boîtier gauche reste actif pendant plus de 5 secondes.

## 6. Relevés du test guidé des boutons (27 octobre 2026)

Outil `python -m openride_core.tools.boutons_click` (protocole G3), mêmes boîtiers, matériel B.0 :

| Firmware | Boîtier droit | Boîtier gauche |
| --- | --- | --- |
| 1.0.2 (avant mise à jour) | 10 appuis sur 10 | touches reçues jusqu'à environ 70 s après la connexion, puis plus rien ; flèches demandées trop tard, jamais reçues |
| 1.2.0 (après mise à jour par l'appli Zwift) | 10 appuis sur 10 | relié, mais aucune touche reçue, même juste après la connexion |

La mise à jour ne débloque pas le boîtier gauche. Reste à savoir s'il répond dans l'appli Zwift (essai 3) et s'il envoie encore des messages sans touche (recette `click_recette`, qui compte les notifications de chaque boîtier). Le contournement reste B du boîtier droit pour « − » ; le plan des boutons (spécification générale §7.1) ne met rien d'indispensable sur le seul boîtier gauche.
