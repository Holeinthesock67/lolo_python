# Lot O18 – ERG dans une session libre : bascule et cadence verrouillée

## 1. Objectif

Demande du propriétaire du 28 octobre : pendant une session libre (SIM), pouvoir passer en ERG depuis le menu, puis revenir en SIM ; et un ERG particulier où la cadence est verrouillée dans une plage de ± 15 % autour d'une cadence cible, le logiciel adaptant la puissance pour y rester.

## 2. Spécification (validée par le propriétaire le 28 octobre)

| # | Règle |
| --- | --- |
| O18-1 | L'écran de pause d'une session libre (ni entraînement ERG, ni run Cyber-Rogue ; parcours ou monde ouvert) porte la ligne « Mode : SIM / ERG / ERG cadence ». Elle se modifie en place comme la difficulté : ± ou flèches changent le choix, A long applique, Y annule. |
| O18-2 | En ERG, la ligne « Puissance cible » (50 à 1 000 W, pas de 5 W) ; en ERG cadence, la ligne « Cadence cible » (50 à 120 tr/min, pas de 1). Une nouvelle valeur remet le biais à 100 %. |
| O18-3 | ERG libre : cible de départ = puissance des 3 dernières secondes avant la pause, arrondie à 5 W (60 % de la FTP sans mesure). En roulant, ± court = intensité ± 2 %, long ± 10 %, bornée à 80–120 %, comme un entraînement. |
| O18-4 | ERG cadence : cadence cible de départ = cadence mesurée avant la pause, arrondie à 5 (85 tr/min sous 50). Plage = cible ± 15 % (fixe, pas de réglage). Cadence lissée sur 2 s. Au-dessus de la plage la puissance monte, au-dessous elle baisse, de 1,5 W/s par tr/min d'écart, au plus 10 W/s, entre 50 W et 150 % de la FTP ; dans la plage, elle ne bouge pas. Puissance de départ : la cible ERG en cours, sinon comme O18-3. |
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
3. ERG cadence simulé : cadence au-dessus de la plage, la cible monte ; au-dessous, elle baisse ; dans la plage, elle ne bouge pas ; bornes respectées.
4. Essai sur le vélo (10 min) : bascule au Click, au clavier et à la souris depuis la pause, ressenti de la cadence verrouillée.

## 6. Hors périmètre

Basculer pendant un entraînement structuré ou une run ; réglage de la largeur de plage (refusé par le propriétaire le 28 octobre).
