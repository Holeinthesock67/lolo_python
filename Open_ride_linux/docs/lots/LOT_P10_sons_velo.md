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
7. Synthèse de tous les sons sous 500 ms.

**Sur le vélo (le propriétaire) :** arrêter de pédaler à 35 km/h en descente, puis reprendre : cliquetis qui ralentit avec la vitesse, « clac » à la reprise ; vent qui forcit nettement avec le vent de face de P2.

## 8. Hors périmètre

- Bruit de chaîne et de dérailleur au changement de braquet, bruit du trainer, souffle du cycliste.
