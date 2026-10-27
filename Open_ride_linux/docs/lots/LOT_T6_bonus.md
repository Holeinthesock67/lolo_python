# Lot T6 – Bonus : légèreté, aérodynamique, puissance

## 1. Objectif

Les bonus du mode classique (plan de la série T §3.3, décisions T-Q2 à T-Q4) dans un module pur du core : types et valeurs, obtention (fin de segment, arche tous les 5 km), réserve unique, activation, durée, effets sur la physique, désactivation en ERG et fichier de valeurs modifiable. Le branchement dans la séance (bouton Z, champ `powerup` de `state`) vient avec le contrat T1.

## 2. À lire

1. `docs/2.0/PLAN_SERIE_T.md` §3.3 et §6 (T-Q2, T-Q3, T-Q4).
2. Code : `core/src/openride_core/physics.py` (`PhysicsParams`, `RiderPhysics`, `steady_speed`), `core/src/openride_core/config.py` (`OPENRIDE_HOME`).

## 3. Prérequis

Aucun pour le module. Le bouton Z est déjà décodé par `zwift_click.py` mais pas encore transmis comme événement : il arrive avec la révision 1.3 du contrat, sous le nom `Z_SHORT` (spécification générale §6.1 et §7.1) ; son branchement sur le bonus vient avec T1.

## 4. Travail demandé

Nouveau module `core/src/openride_core/powerups.py` :

| Bonus (`kind`) | Effet | Durée par défaut |
| --- | --- | --- |
| `lightweight` (Légèreté) | masse totale × 0,90 | 15 s |
| `aero` (Aérodynamique) | CdA × 0,75 | 15 s |
| `power` (Puissance) | puissance prise en compte par la physique × 1,10 | 15 s |

- `load_table(path)` : valeurs par défaut ci-dessus, remplacées par `~/OpenRide/powerups.toml` s'il existe (sections `[lightweight]`, `[aero]`, `[power]` avec `factor` et `duration_s`, section `[obtain]` avec `arch_every_m` et `per_segment`). Bornes : facteur de 0,5 à 1,5, durée de 1 à 120 s, arche tous les 500 m au moins (0 la coupe) ; refus clair sinon.
- `PowerUps` : `award("segment" | "arch")` tire un bonus au hasard (graine réglable pour les tests) et le met en réserve à la place de l'ancien ; `activate(t)` (appui court sur Z) active la réserve s'il n'y a pas déjà un bonus actif ; `step(dt)` décompte la durée (appelé seulement en `RUNNING`, donc figé en pause) ; `uses` garde chaque activation pour le journal.
- Effets : `params(base)` rend les `PhysicsParams` du pas (masse ou CdA modifiés) et `power(mesurée)` la puissance prise en compte. La puissance mesurée reste celle du FIT, du journal et du bilan (risque 3 du plan) ; la résistance du trainer ne change pas (T-Q3), sauf le supplément vent et aspiration de la série P calculé avec le CdA courant (T7).
- ERG : `set_erg(True)` arrête le bonus actif, refuse obtention et activation et garde la réserve pour le retour en SIM (T-Q2).
- `ArchSchedule(every_m, length, loop)` : arches à position fixe (5 km, 10 km… avant l'arrivée), répétées à chaque tour d'une boucle ; `crossed(s_prev, s)` compte les arches franchies (positions servant aussi au rendu de T8).
- `state_dict()` : forme proposée pour le champ `powerup` de `state` (`reserve`, `active`, `remaining_s`), à fixer par T1.

## 5. Fichiers concernés

- **Nouveaux :** `core/src/openride_core/powerups.py`, `core/tests/test_powerups.py`, ce cahier.
- **Interdits :** `physics.py` (lecture seule), `session.py`, `config.py`, le contrat IPC, l'engine.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `python -m pytest -q` passe en entier dans `core/`.
2. Valeurs par défaut égales à celles du plan ; tirage uniforme sur 3 000 bonus ; une seule réserve.
3. Activation refusée sans réserve ou pendant un bonus actif ; fin du bonus à 15 s (à un pas près).
4. Effets : masse 80 → 72 kg, CdA 0,32 → 0,24, 250 → 275 W ; à 250 W, l'aéro fait gagner plus de 8 % de vitesse sur le plat et moins de 3 % à 8 % ; légèreté et puissance plus de 8 % à 8 %.
5. ERG : bonus arrêté, obtention et activation refusées, réserve gardée et utilisable au retour en SIM.
6. Arches : 4 sur 23 km, aucune sur la ligne d'arrivée, 2 par tour sur une boucle de 12 km.
7. Fichier de valeurs : lecture partielle, coupure des arches ou des bonus de segment, refus des valeurs hors bornes, des sections inconnues et d'un fichier illisible.

## 8. Hors périmètre

- Bouton Z et touche de secours, champ `powerup`, bonus au journal (T1 puis branchement).
- Supplément vent et aspiration avec le CdA courant (T7), arches en 3D (T8), HUD bonus (T9), option bonus du menu (T10).
- Les bots ne prennent pas de bonus.

## 9. Livraison (26 octobre 2026)

- Module pur et 17 tests, sans changement de `session.py` ni du contrat ; branchement avec T1. Ligne de suivi : ce cahier.
