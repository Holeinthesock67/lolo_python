# Lot O18 – ERG dans une session libre : bascule et cadence verrouillée

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| ERG dans une session libre : bascule SIM, ERG libre et ERG à cadence verrouillée (± 10 %, ± 15 % avant le 1er novembre) depuis l'écran de pause | Python + GDScript | O17 (livré) | Moyenne | **Livré le 29 octobre** (PR #550, demande du propriétaire du 28 octobre), essai sur le vélo à faire |

## 1. Objectif

Demande du propriétaire du 28 octobre : pendant une session libre (SIM), pouvoir passer en ERG depuis le menu, puis revenir en SIM ; et un ERG particulier où la cadence est verrouillée dans une plage de ± 15 % autour d'une cadence cible, le logiciel adaptant la puissance pour y rester.

## 2. Spécification (validée par le propriétaire le 28 octobre)

| # | Règle |
| --- | --- |
| O18-1 | L'écran de pause d'une session libre (ni entraînement ERG, ni run Cyber-Rogue ; parcours ou monde ouvert) porte la ligne « Mode : SIM / ERG / ERG cadence ». Elle se modifie en place comme la difficulté : ± ou flèches changent le choix, A long applique, Y annule. |
| O18-2 | En ERG, la ligne « Puissance cible » (50 à 1 000 W, pas de 5 W) ; en ERG cadence, la ligne « Cadence cible » (50 à 120 tr/min, pas de 1). Une nouvelle valeur remet le biais à 100 %. |
| O18-3 | ERG libre : cible de départ = puissance des 3 dernières secondes avant la pause, arrondie à 5 W (60 % de la FTP sans mesure). En roulant, ± court = intensité ± 2 %, long ± 10 %, bornée à 80–120 %, comme un entraînement. |
| O18-4 | ERG cadence : cadence cible de départ = cadence mesurée avant la pause, arrondie à 5 (85 tr/min sous 50). Plage = cible ± 10 % (fixe, pas de réglage ; ± 15 % jusqu'à l'essai du 1er novembre). Cadence lissée sur 2 s. Au-dessus de la plage la puissance monte, au-dessous elle baisse, de 1,5 W/s par tr/min d'écart, au plus 10 W/s, entre 50 W et 150 % de la FTP ; dans la plage, elle ne baisse pas. Correctif du 1er novembre (§8) : à l'enclenchement et à chaque reprise, puissance figée tant que la cadence n'est pas revenue dans la plage (au plus 15 s) ; dans la plage, à la cadence cible ou au-dessus, la puissance remonte de 2 W/s vers la puissance de référence (la plus haute atteinte depuis l'enclenchement). Puissance de départ : la cible ERG en cours, sinon comme O18-3. |
| O18-5 | En ERG cadence, ± court change la cadence cible de 2 % (long 10 %), par le même biais borné à 80–120 % de la cadence choisie. |
| O18-6 | Retour en SIM : la pente repart de 0 % avec la limitation de variation habituelle ; le braquet est celui d'avant. |
| O18-7 | Z garde son rôle de la session libre (bonus de la série T) : l'ERG libre n'a pas de blocs. Y reste la pause. |
| O18-8 | HUD : le bandeau ERG montre « ERG libre » ou « ERG cadence », la cible, et en cadence la plage et l'état (dans la plage, trop vite, trop lent) ; pas d'histogramme ni de temps restant. Le braquet est masqué comme en ERG. |
| O18-9 | Journal : lignes `record` en mode `ERG` avec `target_w`, et champs facultatifs `erg_kind` (`free`, `cadence`) et `cadence_target_rpm` ; une reprise après un plantage du core (N8) retrouve le mode, la cible et la cadence. |

## 3. Contrat

Révision 1.5 (ajout compatible) : commande `set_ride_mode`, champs facultatifs `kind`, `cadence_target_rpm`, `cadence_low_rpm`, `cadence_high_rpm`, `cadence_zone` de l'objet `erg` (`docs/contracts/ipc_v1.md` §3 et §4).

## 4. Fichiers

- Core : `free_erg.py` (nouveau, module pur), `session.py` (`set_ride_mode`, pas ERG, Z, journal, reprise), `workout.py` (`kind`), `journal.py`, `resume.py`.
- Engine : `menu_model.gd` (lignes de la pause), `menu_flow.gd`, `settings_view_model.gd` (modifications de la pause), `erg_view_model.gd` et `erg_view.gd` (bandeau), `hud_view_model.gd`.
- Tests : `core/tests/test_free_erg.py`, `engine/tests/unit/test_free_erg_menu.gd`, `engine/tests/test_erg_view_model.gd`.

## 5. Critères d'acceptation

1. `pytest -q` passe dans `core/` ; `run_engine_tests.sh` passe sur le PC.
2. Séance simulée (Bluetooth simulé) : SIM → ERG libre → cible envoyée au trainer, braquet ignoré ; ± change le biais ; retour SIM : pente de nouveau envoyée.
3. ERG cadence simulé : cadence au-dessus de la plage, la cible monte ; au-dessous, elle baisse ; dans la plage, elle ne baisse pas ; bornes respectées ; la reprise depuis la pause ne fait pas chuter la cible et la cible remonte quand la cadence revient (§8).
4. Essai sur le vélo (10 min) : bascule au Click, au clavier et à la souris depuis la pause, ressenti de la cadence verrouillée.

## 6. Hors périmètre

Basculer pendant un entraînement structuré ou une run ; réglage de la largeur de plage (refusé par le propriétaire le 28 octobre).

## 7. Livraison

Livré le 29 octobre (PR #550, branche `claude/project-thread-ay70fd`).

- Core : `free_erg.py` (`FreeErg`, `CadenceLock`), commande `set_ride_mode` dans `session.py`, ERG libre gardé au journal et à la reprise après un plantage du core.
- Engine : lignes Mode, Puissance cible et Cadence cible de l'écran de pause, bandeau ERG (« dans la plage », sous ou au-dessus).
- Contrat : révision 1.5 (`set_ride_mode`, `erg.kind`, champs `cadence_*`), exemples et séquence au §7 de `docs/contracts/ipc_v1.md`.
- Tests : `core/tests/test_free_erg.py` (10 tests : valeurs de départ, biais, plage et sens de la cadence verrouillée, bornes et vitesse, absence d'oscillation avec un cycliste qui réagit, bascule SIM → ERG → cadence → SIM dans la séance, refus `busy` et `bad_args`, journal et reprise, trainer du Bluetooth simulé qui suit la cadence verrouillée), `engine/tests/unit/test_free_erg_menu.gd`, scénario `erg_libre` du banc des menus (trois voies).
- Reste : critère 4, l'essai sur le vélo (10 min : bascule au Click, au clavier et à la souris, ressenti de la plage de 15 %, 10 % à revoir après l'essai). Fait le 1er novembre : ± 10 % retenu, correctif de la reprise (§8).

## 8. Correctif après l'essai sur le vélo du 1er novembre

Constat de l'essai (deux passes, bilan sur le PC) : à la reprise depuis la pause, la cadence lue vaut 0 pendant que le cycliste relance ; la cadence lissée restait sous la plage plusieurs secondes et la puissance cible perdait environ 95 W en 10 s. Comme la puissance ne bougeait plus dans la plage, elle restait ensuite au plancher de 50 W, même une minute à 88 tr/min. Les deux passes finissaient à 50 W.

Correctif dans `free_erg.CadenceLock`, sans changement du contrat IPC :

- Reprise : à l'enclenchement (le mode se choisit depuis la pause) et à chaque passage de la pause à la reprise, le lissage de la cadence repart de zéro et la puissance reste figée tant que la cadence lissée n'a pas atteint la plage (`RESUME_GRACE_S` = 15 s au plus). Un cycliste qui ne repart pas voit ensuite la puissance baisser comme avant, jusqu'au plancher de 50 W.
- Remontée : la puissance de référence est la plus haute atteinte depuis l'enclenchement (puissance de départ, ou plus si la cadence trop rapide l'a fait monter). Dans la plage, cadence à la cible ou au-dessus, la puissance remonte de `RECOVER_W_PER_S` = 2 W/s vers cette référence, sans la dépasser. Sous la cible, elle ne bouge pas : un cycliste fatigué qui ralentit arrête la remontée, ce qui évite le pompage.

Tests (sans vélo) : `core/tests/test_free_erg.py` (reprise après une et plusieurs pauses, enclenchement depuis la pause, baisse après le délai sans pédalage, remontée vers la référence, remontée qui se stabilise avec un cycliste qui réagit) et `core/tests/test_recettes_velo_auto.py` (`test_7ae_bis_resume_in_cadence_lock_keeps_the_power`) (rejeu de l'essai dans la séance : ERG cadence choisi en pause, deux reprises depuis 0 tr/min, une minute à 88 tr/min, la consigne envoyée au trainer ne chute pas). Les six tests échouent sur le code d'avant le correctif.

Plage de cadence : notes du propriétaire après l'essai, ± 10 % = 5/5, ± 15 % = 4/5. Le propriétaire a choisi ± 10 % le 1er novembre (carte de décision) : `CADENCE_BAND_PCT` = 10, commit séparé du même PR.

