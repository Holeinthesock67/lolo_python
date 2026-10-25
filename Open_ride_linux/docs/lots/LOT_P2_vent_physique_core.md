# Lot P2 – Vent physique côté core

## 1. Objectif

La formule de la SRS §5 contient déjà le vent (`wind_mps` de `physics.py`), mais il vaut toujours 0. Ce lot calcule dans le core un vent réglable (calme, fixe ou en rafales), le projette sur le cap de la route, l'applique à la vitesse virtuelle et, en SIM, à la résistance ressentie. Il publie le champ `wind` de la trame `state` (contrat v1.2 du lot P1), que l'engine utilise pour l'indicateur du HUD et l'animation du décor.

## 2. À lire

1. `docs/lots/00_INDEX.md`, `docs/lots/LOT_P1_contrat_vent_decor.md` (§4.1 et §4.3 tels que validés), `docs/contracts/ipc_v1.md` §3.
2. `docs/SRS_v1.1.md` §4.1, §5, §11.
3. Code : `core/src/openride_core/physics.py`, `core/src/openride_core/route.py` (`RouteSample.heading_deg`), `core/src/openride_core/session.py` (envoi de la pente, limitation de variation, ERG), `core/src/openride_core/config.py`, `core/src/openride_core/ftms.py`, `core/src/openride_core/recorder.py`.

## 3. Prérequis

P1 livré (contrat v1.2 et `[wind]` validés). Version 1.0 publiée.

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
- Trame `state` : champ `wind` du contrat v1.2 quand `mode` n'est pas `"off"`.
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
6. Trame `state` valide pour le schéma v1.2, avec et sans `wind` ; taille de la trame la plus chargée sous 1 400 octets.
7. Configuration invalide (`speed_kmh = -3`, `mode = "tempête"`) : `ConfigError` avec la clé fautive.

**Sur le vélo (le propriétaire) :** vent de face de 25 km/h en SIM avec `feel = "grade"`, puis `"ftms"` : la résistance doit monter de façon perceptible et progressive, sans à-coup.

## 8. Hors périmètre

- Indicateur du HUD et animation du décor (P4, P5, P16).
- Aspiration derrière les bots (P3).
- Vent de travers, effet sur la stabilité, vent abrité par les forêts ou le relief.
