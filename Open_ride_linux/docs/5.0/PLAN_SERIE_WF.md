# Plan de la série WF : trainer en Wi-Fi et mesures rapides (version 5.0)

Étude du 31 octobre 2026, à la suite de la remarque du propriétaire : « le race mode en wifi aurait un intérêt […] ça permet peut-être de rafraîchir la résistance plus rapidement pour plus de réalisme ». Décision du propriétaire du même jour : **la série va en 5.0**. Rien n'est codé avant la v1.0.0 (gel des fusions hors 1.0), et les lots WF2 à WF6 ne démarrent que si la mesure WF1 les justifie (§4).

Sources lues : `core/src/openride_core/ftms_driver.py` (envoi des consignes, accusés du Control Point), `config.py` (rampe de pente, lissage), `ble_sim.py`, PR #683 (lot RC1, consigne de résistance FTMS) ; mesures de paliers du 29 et du 30 octobre sur le trainer du propriétaire.

Le modèle du trainer n'est pas nommé dans le dépôt (règle de confidentialité). Il gère les deux fonctions étudiées ici : un **mode de mesures rapides** (option de l'appli du fabricant : mesures envoyées 10 fois par seconde, déjà activée chez le propriétaire depuis le 30 octobre) et le **Direct Connect en Wi-Fi** (les messages FTMS transportés sur TCP par le réseau local, annoncés en mDNS `_wahoo-fitness-tnp._tcp`).

---

## 1. En bref

1. **Le retard ressenti vient du frein du trainer, pas de la liaison.** Le frein met environ 1 s avant de bouger, puis 1,5 à 4,6 s pour atteindre 90 % d'une nouvelle consigne (paliers du 29 octobre). Le transport BLE d'une consigne est estimé à 30 à 100 ms (intervalle de connexion BlueZ de 30 à 50 ms, écriture avec accusé), contre environ 2 à 10 ms en Wi-Fi sur un réseau calme. Le Wi-Fi gagnerait donc moins de 5 % du retard total.
2. **Le mode de mesures rapides** rend l'affichage de la puissance et de la cadence plus vif ; il ne serre pas le frein plus vite. Aucune mesure publiée ne soutient l'argument « résistance instantanée ».
3. **Les vrais leviers du réalisme sont dans le core** et relèvent de la série RC (mode résistance, #683 et suivantes) : consigne envoyée à 10 Hz au lieu de 5 Hz (`MIN_SEND_INTERVAL_S = 0,2 s`), pente anticipée d'environ le retard du frein (`latency_tau_s`, 0,8 s aujourd'hui), rampe de pente plus vive (4 %/s en montée aujourd'hui).
4. **Intérêt possible du Wi-Fi, à prouver** : libérer la radio Bluetooth du PC, qui sert aussi au Click et à la ceinture cardio.
5. **Recommandation** : d'abord mesurer (WF1). Le pilote Wi-Fi (WF2 à WF6) ne se fait que si la mesure montre un BLE lent ou encombré.

## 2. Où part le temps entre la pente et les jambes

| Étage | Valeur actuelle | Le Wi-Fi y change-t-il quelque chose ? |
| --- | --- | --- |
| Physique du core | boucle à 50 Hz | Non |
| Rampe de pente envoyée | +4 %/s en montée, −8 %/s en descente (lot Q4) | Non |
| Cadence d'envoi des consignes | 5 Hz au plus, seuil 0,1 % | Non |
| Transport d'une consigne | BLE estimé 30 à 100 ms | Oui : 2 à 10 ms, pics de 50 à 200 ms possibles sur un Wi-Fi chargé |
| Accusé « occupé » 0x80 | repris par #540 | Non (vient du trainer) |
| Frein du trainer | ~1 s, puis 90 % en 1,5 à 4,6 s, dépassement de 5 à 11 % | Non |
| Mesures remontées | cadence lue avec ~1,9 s de retard, lissage de 0,7 s dans le core | Un peu (mode rapide), le retard de cadence vient du trainer |

## 3. Lots

| Lot | Contenu | Lieu |
| --- | --- | --- |
| WF0 | Ce plan | docs |
| WF1 | Outil de mesure : notifications Indoor Bike Data par seconde (mode rapide activé puis coupé), aller-retour écriture au Control Point → accusé (moyenne, 95e centile, nombre de 0x80), essai de consigne à 10 Hz pendant 2 min ; rapport dans le journal et `log-report` | core, puis 10 min sur le vélo |
| WF2 | Transport Direct Connect : connexion TCP, trames (découverte des services et caractéristiques, lecture, écriture, notifications), reconnexion ; classe qui imite l'interface de `bleak`, pour que `ftms_driver.py` ne change pas | core |
| WF3 | Découverte mDNS (dépendance `zeroconf`), réglage `[trainer] transport` = `ble` (défaut) ou `wifi`, adresse retenue dans `config.toml` | core |
| WF4 | Trainer simulé en Direct Connect pour la CI, sur le modèle de `ble_sim.py` | core, tests |
| WF5 | Écran Appareils : choix Bluetooth ou Wi-Fi, état de la liaison ; ajouts IPC dans la révision ouverte à ce moment-là | core, engine |
| WF6 | Recette sur le PC : même séance de 10 min en BLE puis en Wi-Fi, comparaison des chiffres de WF1 | vélo |

Dépendances : WF0 ──► WF1 ──► (critère du §4) ──► WF2 ──► WF3, WF4 ──► WF5 ──► WF6.

## 4. Critère de décision après WF1

Le pilote Wi-Fi (WF2 à WF6) est lancé seulement si l'une de ces conditions est vraie :

- l'aller-retour d'une consigne en BLE dépasse environ 150 ms au 95e centile ;
- les notifications de mesures restent sous environ 4 par seconde avec le mode rapide activé ;
- les décrochages Bluetooth du Click ou de la ceinture diminuent nettement quand le trainer n'est plus en Bluetooth.

Sinon, la série s'arrête à WF1 et le réalisme passe par la série RC (§1, point 3).

## 5. Règles et risques

- **Réseau** : la règle « hors ligne » de la spécification vise Internet ; le réseau local n'en est pas. La boucle à 50 Hz n'attend jamais la liaison (R-NET-1) ; le transport tourne dans la tâche asyncio du pilote, comme le BLE.
- **Fiabilité** : des utilisateurs signalent un Direct Connect qui tombe après quelques heures sur ce trainer (doublon mDNS). WF6 doit couvrir une séance longue.
- **Un seul pilote du frein** : l'appli du fabricant reste fermée pendant la séance, comme en BLE. La mise à jour du micrologiciel reste en Bluetooth.
- **Rien ne change pour le Click et la ceinture**, qui restent en Bluetooth.
- **Performance** : aucun effet sur le rendu ; pas de mesure low, medium, high à prévoir hors WF5 (écran Appareils).

## 6. Hors de cette série

La course à plusieurs sur le réseau local a été étudiée le même jour comme option secondaire. Le multijoueur reste **toujours hors périmètre** (spécification générale, §2) : rien n'est planifié tant que le propriétaire n'a pas changé cette règle.
