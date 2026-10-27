# Lot P2 – Vent physique côté core

## 1. Objectif

La formule de la SRS §5 contient déjà le vent (`wind_mps` de `physics.py`), mais il vaut toujours 0. Ce lot calcule dans le core un vent réglable (calme, fixe ou en rafales), le projette sur le cap de la route, l'applique à la vitesse virtuelle et, en SIM, à la résistance ressentie. Il publie le champ `wind` de la trame `state` (contrat v1.2 du lot P1), que l'engine utilise pour l'indicateur du HUD et l'animation du décor.

## 2. À lire

1. `docs/lots/00_INDEX.md`, `docs/lots/LOT_P1_contrat_vent_decor.md` (§4.1 et §4.3 tels que validés), `docs/contracts/ipc_v1.md` §3.
2. `docs/SRS_v1.1.md` §4.1, §5, §11.
3. Code : `core/src/openride_core/physics.py`, `core/src/openride_core/route.py` (`RouteSample.heading_deg`), `core/src/openride_core/session.py` (envoi de la pente, limitation de variation, ERG), `core/src/openride_core/config.py`, `core/src/openride_core/ftms.py`, `core/src/openride_core/recorder.py`.

## 3. Prérequis

P1 livré (contrat révision 1.3 et `[wind]` validés). Version 1.0 publiée.

## 4. Travail demandé

- Nouveau module pur `wind.py` (sans entrée-sortie) :
  - `WindModel(cfg, seed)` : vent de base (`speed_kmh`, `from_deg`) et rafales déterministes (somme de deux ou trois sinusoïdes de périodes 20 à 90 s, phases tirées de `seed`), amplitude `gust_pct` ; direction qui oscille de ± 15° au plus en mode `gusty` ;
  - `sample(t_s) -> WindSample(speed_mps, from_deg, gust)` ;
  - `head_component(sample, heading_deg) -> float` : composante de face (cos de l'écart entre la direction d'où vient le vent et le cap de la route), positive de face.
- Physique : `PhysicsParams.wind_mps` reçoit `head_mps` à chaque pas de 50 Hz (ou un paramètre de `step`, au choix, sans changer le cas de référence de la SRS §5).
- Ressenti en SIM, selon `[wind] feel` :
  - `"grade"` : supplément de pente `100 × ΔF / (m g)`, où `ΔF` est l'écart de force aérodynamique dû au vent (et à l'aspiration, voir P3), calculé à chaque pas avec les `PhysicsParams` courants (`cda_m2`, masse) et non avec des constantes lues dans la configuration : un bonus temporaire qui modifie `cda_m2` ou la masse (série T de la 2.0) réduit alors aussi ce supplément, sans deuxième voie, borné par `max_grade_offset_pct`, ajouté **avant** la limitation de variation et les bornes −10 % / +16 % existantes ;
  - `"ftms"` : `head_mps` passé dans le champ vent de la commande 0x11, pente inchangée.
- ERG : vitesse virtuelle seulement, aucune incidence sur la commande au trainer.
- Pause : vent figé (comme le chronomètre).
- Trame `state` : champ `wind` du contrat (révision 1.3), 2 fois par seconde, quand `mode` n'est pas `"off"` ; la physique utilise le vent exact à chaque pas de 50 Hz.
- `max_grade_offset_pct` réglable dans la section « Réglages » du menu : clé ajoutée aux réglages écrits par le core (même mécanisme qu'O3) ; l'écran lui-même vient avec P16.
- Journal : `head_mps` et le supplément de pente ajoutés en champs facultatifs de l'enregistrement à 1 Hz (le format reste lisible par `openride-core summary` et `history`).
- `config.py` : section `[wind]` validée (types et bornes, `ConfigError` lisible) ; SRS §11 mise à jour.

## 5. Fichiers concernés

- **Nouveaux :** `core/src/openride_core/wind.py`, `core/tests/test_wind.py`.
- **Modifiés :** `core/src/openride_core/physics.py`, `core/src/openride_core/session.py`, `core/src/openride_core/config.py`, `core/src/openride_core/recorder.py`, `core/tests/test_physics.py` ou un nouveau test, `docs/SRS_v1.1.md` (§11), `CLAUDE.md` (module `wind.py` dans l'architecture), `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Interdits :** l'engine, le contrat (déjà fait par P1), `ftms_driver.py` hors de l'appel existant à la commande 0x11.

## 6. Modifications de contrat autorisées

Aucune (P1 les a faites).

## 7. Critères d'acceptation

1. `(cd core && pytest -q)` passe en entier ; le cas de référence de la SRS §5 (250 W à plat, environ 10,2 m/s) est inchangé avec `mode = "off"`.
2. 250 W à plat, vent de face de 20 km/h : vitesse stabilisée nettement plus basse qu'à l'arrêt du vent, égale au calcul de `steady_speed` avec `wind_mps` à 1 % près ; vent de dos : plus haute.
3. Vent du nord, route plein nord puis plein sud puis plein est : `head_mps` positif, négatif, nul (à 0,01 près).
4. Même `seed`, même suite de vents (déterminisme) ; `gust_pct = 0` : vent constant.
5. `feel = "grade"` : supplément de pente borné par `max_grade_offset_pct`, nul en ERG et à `mode = "off"`, cohérent avec `ΔF / (m g)` à 0,05 point près ; `feel = "ftms"` : champ vent de la commande 0x11 égal à `head_mps` (doublure `MockDriver`).
6. Trame `state` valide pour le schéma de la révision 1.3, avec et sans `wind` ; taille de la trame la plus chargée sous 1 400 octets.
7. Configuration invalide (`speed_kmh = -3`, `mode = "tempête"`) : `ConfigError` avec la clé fautive.

**Sur le vélo (le propriétaire) :** vent de face de 25 km/h en SIM avec `feel = "grade"`, puis `"ftms"` : la résistance doit monter de façon perceptible et progressive, sans à-coup.

## 8. Hors périmètre

- Indicateur du HUD et animation du décor (P4, P5, P16).
- Aspiration derrière les bots (P3).
- Vent de travers, effet sur la stabilité, vent abrité par les forêts ou le relief.

## 9. Livraison (26 octobre 2026)

Livré sur la branche `lot-p2-vent-physique-core`, au-dessus de P1.

- **`wind.py`** (module pur) : `WindModel` (modes `off`, `fixed`, `gusty`, `theme` ; rafales par trois sinusoïdes de 23, 47 et 89 s dont les phases viennent de `seed`, direction qui oscille de ± 15° au plus à 100 % de rafales), `head_component`, `aero_force_delta`, `grade_offset_pct` (100 · ΔF / (m g) avec les `PhysicsParams` courants, borné) et `wind_frame` (arrondis du contrat).
- **Session** : à chaque pas de 50 Hz, le vent du temps de séance (figé en pause) est projeté sur le cap de la route et donné à `PhysicsParams.wind_mps`. Les bots à puissance constante reçoivent le vent à leur propre position (chaque bot garde désormais sa copie des paramètres, au lieu d'un objet partagé). En SIM avec `feel = "grade"`, le supplément de pente s'ajoute à la pente du braquet **avant** la limitation de variation et les bornes du trainer ; avec `feel = "ftms"`, `head_mps` part dans le champ vent de la commande 0x11 (`set_wind` des pilotes FTMS et mock) et la pente ne change pas. En ERG, ni la cible ni la commande ne changent.
- **Trame `state`** : `wind` une trame sur quinze ; quand cette trame porte `devices`, `wind` part dans la suivante.
- **Journal** : `head_mps` et `wind_grade_pct` en champs facultatifs des relevés à 1 Hz (`null` vent coupé).
- **Configuration** : section `[wind]` dans `config.py` (types, bornes et choix contrôlés), dans l'exemple de la SRS §11. En mode `theme`, le core lit la clé `wind` de `~/OpenRide/Themes/<thème>/theme.json`, sinon du thème par défaut du dépôt.
- **Menu :** la clé `max_grade_offset_pct` est lue par le core ; son curseur dans « Réglages » viendra avec l'écran des réglages (O3/O4) et P16, puisque `config_edit.py` n'écrit encore que des textes.
- **Tests** : `core/tests/test_wind.py` (18 tests, plus 10 cas de bornes et de choix ajoutés d'office aux tests de configuration : cas de référence inchangé, vent de face et de dos à 20 km/h contre `steady_speed` à 1 %, projection nord, sud, est, déterminisme, supplément borné et cohérent avec ΔF, ressenti FTMS, ERG, pause, trames avec et sans `wind` sous 1 400 octets, journal, configuration invalide, vent du thème).
- **Reste sur le vélo (le propriétaire)** : vent de face de 25 km/h en SIM avec `feel = "grade"`, puis `"ftms"` : résistance perceptible et progressive, sans à-coup.
- **Journal sans vent inchangé** : `head_mps` et `wind_grade_pct` ne sont écrits que s'ils ont une valeur (`journal.record_line`). Sans cela, le test d'endurance de 3 h (`test_endurance_memory_stability`, seuil de 8 Mo) dépassait son seuil sous Python 3.11 (9,3 Mo) avec deux clés vides de plus par relevé.
