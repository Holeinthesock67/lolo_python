# Lot P10 – Sons du vélo : vent selon la vitesse dans l'air, roue libre réaliste

## 1. Objectif

Demande du propriétaire (25 octobre) : le son du vent doit varier avec la vitesse, et on doit entendre la roue libre quand on arrête de pédaler. Les deux existent depuis E4 et L5, mais de façon simple :
- le vent monte linéairement avec la vitesse du cycliste jusqu'à 60 km/h, sans tenir compte du vent réel ;
- la roue libre se déclenche après 0,5 s à 0 W au-dessus de 5 km/h, avec un cliquetis fixe de 20 coups par seconde.

Ce lot les rend crédibles : le vent suit la **vitesse dans l'air** (vitesse du cycliste plus vent de face de P2, avec les rafales), selon une courbe proche du bruit aérodynamique réel ; la roue libre se déclenche aussi à **cadence nulle**, son cliquetis suit la vitesse de la roue et ralentit avec elle, et un « clac » d'engagement se fait entendre à la reprise du pédalage.

## 2. À lire

1. `docs/lots/00_INDEX.md`, `docs/lots/LOT_L5_modele_sonore.md`, `docs/lots/LOT_E4_osm_eau_sons.md`, `docs/lots/LOT_P4_modele_vent_engine.md`, `docs/RECETTE_E3_E4.md` (sons à vérifier).
2. Code : `engine/scripts/sound_model.gd` (`on_state`, `_target_wind_db`, `_target_wind_pitch`, roue libre), `engine/scripts/sound_player.gd` (`_synthesize_stream`), `engine/tests/unit/test_sound_model.gd`, `engine/tests/unit/test_sound_player.gd`.

## 3. Prérequis

P4 livré (vent apparent). P2 n'est pas requis : sans champ `wind`, le vent dans l'air est la vitesse du cycliste. Version 1.0 publiée.

## 4. Travail demandé

### 4.1 Vent

- Vitesse dans l'air `va = v + head_mps` (champ `wind` de `state`, 0 s'il manque), bornée à 0.
- Volume : `20 × k × log10(va / v_ref)` dB (k de 2,5 à 3, à régler), avec plancher `WIND_MIN_MOVING_DB` et plafond `WIND_MAX_DB` ; à 10 km/h dans l'air le vent est à peine audible, à 50 km/h il domine. Hauteur : de 0,8 à 1,3 selon `va`.
- Rafales : le facteur `gust` module le volume de ± 3 dB et la hauteur de ± 5 %.
- Son synthétisé : bruit filtré passe-bande dont la fréquence centrale monte avec `va` (au lieu de la sinusoïde à 120 Hz), boucle sans clic.

### 4.2 Roue libre

- Déclenchement : cadence à 0 (si le champ `cadence` est présent) **ou** puissance à 0 W, pendant 0,5 s, au-dessus de 5 km/h ; arrêt dès que la puissance dépasse 10 W ou que la cadence dépasse 20 tr/min.
- Rythme : `coups par seconde = tours de roue par seconde × points d'engagement` (roue de 2,1 m, 36 points par défaut, constantes en tête du script) ; à 36 km/h, environ 170 coups par seconde, qui ralentissent avec le cycliste. Réalisé par `pitch_scale` d'une boucle courte ou par génération de clics à la volée (`AudioStreamGenerator`), au choix, sans allocation par image.
- Volume : un peu plus fort à haute vitesse, nul sous 5 km/h.
- Reprise du pédalage : un « clac » court (moins de 80 ms), une seule fois par reprise.
- Pause : silence immédiat.

## 5. Fichiers concernés

- **Modifiés :** `engine/scripts/sound_model.gd`, `engine/scripts/sound_player.gd`, `engine/tests/unit/test_sound_model.gd`, `engine/tests/unit/test_sound_player.gd`, `engine/tests/README.md`, `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Interdits :** `main.gd`, le core, le contrat. `sound_player.gd` est partagé avec P9, P13 et P15 : fusionner l'un après l'autre.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `engine/tests/run_engine_tests.sh` passe en entier.
2. Sans vent : volume du vent strictement croissant de 5 à 60 km/h ; 30 km/h avec 15 km/h de vent de face : même volume (à 0,5 dB près) que 45 km/h sans vent ; même vitesse avec 30 km/h de vent de dos : vent quasi muet.
3. Cadence 0 et puissance 150 W (capteur de puissance qui traîne) à 30 km/h pendant 0,6 s : roue libre active ; cadence 80 tr/min : inactive.
4. Rythme : 36 km/h donne environ 171 coups par seconde (± 2 %), 18 km/h la moitié.
5. Reprise : exactement un « clac » à la reprise, aucun pendant le pédalage continu.
6. Trames de L5 sans `cadence` ni `wind` : comportement identique aux tests actuels (anciens tests conservés, sauf les valeurs de la courbe de volume, mises à jour et justifiées).
7. Synthèse de tous les sons sous le budget `sound_generation` (1 200 ms depuis le 28/10).

**Sur le vélo (le propriétaire) :** arrêter de pédaler à 35 km/h en descente, puis reprendre : cliquetis qui ralentit avec la vitesse, « clac » à la reprise ; vent qui forcit nettement avec le vent de face de P2.

## 8. Hors périmètre

- Bruit de chaîne et de dérailleur au changement de braquet, bruit du trainer, souffle du cycliste.

## 9. Livraison

Livré sur la branche `lot-p10-sons-vent`, sans toucher à `main.gd`, au core ni au contrat.

- **`sound_model.gd`** :
  - Vent : vitesse dans l'air `va = v + wind.head_mps` (bornée à 0 ; vent coupé 2 s après le dernier objet `wind`, qui arrive 2 fois par seconde). Volume `20 × 2,5 × log10(va / 60 km/h)`, entre −60 et 0 dB : −39 dB à 10 km/h, −15 dB à 30 km/h, −4 dB à 50 km/h, plafond à 60 km/h. Le plancher passe de −36 à −60 dB pour que la courbe reste strictement croissante dès 5 km/h ; c'est la seule valeur des tests L5 qui change, leurs vérifications de forme restent. Hauteur de 0,8 à 1,3, linéaire en `va` (volumes, hauteur et sons revus après la recette P16 : voir LOT_P16 § 10). La rafale (`gust`) module le volume de ± 3 dB et la hauteur de ± 5 % sur une période de 3 s.
  - Roue libre : avec un champ `cadence`, c'est la cadence qui décide (0 tr/min pendant 0,5 s : roue libre ; au-dessus de 20 tr/min : reprise), puisqu'un capteur de puissance traîne ; sans cadence, la puissance comme en L5 (0 W, reprise au-dessus de 10 W). `clicks_per_s` = tours de roue par seconde × 36 (roue de 2,1 m) : 171,4 à 36 km/h. Volume de −10 dB à 5 km/h à −4 dB à 40 km/h. `clac` vrai pour une seule évaluation à chaque reprise du pédalage pendant la roue libre (pas en pause ni sous 5 km/h).
  - Pause : vent et roue libre au silence immédiatement, sans lissage.
- **`sound_player.gd`** : le vent devient un bruit blanc filtré passe-bande (500 Hz, Q 0,8), boucle d'une seconde raccordée par un fondu enchaîné de 50 ms ; sa fréquence monte avec `pitch_scale`. La boucle de roue libre contient 100 coups par seconde et `pitch_scale` vaut `clicks_per_s / 100`. Un lecteur créé au démarrage joue le « clac » (60 ms, remplaçable par `~/OpenRide/Sounds/clac.ogg`). Synthèse de tous les sons : 186 ms ici.
- **Tests** : `test_sound_model.gd` (27 vérifications, dont 9 nouvelles), `test_sound_player.gd` (14 vérifications, dont 4 nouvelles).
- **Reste sur le vélo (le propriétaire)** : arrêter de pédaler à 35 km/h en descente puis reprendre, après le branchement par P16 ; le vent de face de P2 se ressent quand `[wind] mode` est activé.
