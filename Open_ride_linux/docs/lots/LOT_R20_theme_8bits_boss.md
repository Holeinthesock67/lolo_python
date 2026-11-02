# Lot R20 – Thème 8 bits du boss

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Thème 8 bits du boss : couche `chip` (onde carrée, triangle, bruit) jouée seule pendant le boss | GDScript | R18, X51 | Petite | Livré le 30 octobre (PR #632), **version 2.0** |

## 1. Objectif

Demande du propriétaire du 30 octobre : une musique « genre 8 bits » pendant le combat contre le boss. Pendant le boss, le mode joue un thème original façon console 8 bits à la place des trois couches de R18. Le propriétaire l'a validé à l'écoute le 30 octobre.

## 2. À lire

`docs/lots/LOT_R18_bruitages_rogue.md` (§4.3 musique, principe « doux d'abord »), `engine/scripts/rogue/rogue_sound_synth.gd`, `rogue_sound_model.gd`, et le lot X51 (`test_rogue_sound_levels.gd`, page d'écoute).

## 3. Travail demandé

- **Nouvelle couche `chip`** dans `MUSIC_LAYERS`. Elle garde le tempo (96 bpm), la grille d'accords et la boucle de 8 mesures (20 s) des autres couches. Elle comprend :
  - une mélodie en onde carrée, par double-croches (`CHIP_MOTIFS`, rapport cyclique 25 % puis 50 %, volume en paliers de 1/16) ;
  - une basse en onde triangle par croches ;
  - une batterie de bruit (grosse caisse, caisse claire, charleston) ;
  - une compression douce (`CHIP_DRIVE`), pour que le thème tienne le niveau des autres phases.
- **`MUSIC_BY_PHASE`** : au boss, le thème 8 bits joue seul. Les autres phases ne changent pas. Le fondu de 2 s entre phases est gardé.
- La page d'écoute (`rogue_ecoute.py`) et `rogue_sound_export.gd` mêlent les couches avec les poids de chaque phase.

## 4. Critères d'acceptation

1. `test_rogue_sound_synth.gd` : quatre couches de 20 s, crête sous −3 dBFS, mémoire sous 8 Mo.
2. `test_rogue_sound_model.gd` : au boss, le thème 8 bits seul ; au retour au calme, la basse revient.
3. `test_rogue_sound_levels.gd` : la musique de chaque phase reste sous le vent à 60 km/h, et le thème garde moins de 10 % de son énergie au-dessus de 4 kHz. Mesures du 30 octobre : boss −36,2 dB, salle −35,2 dB, aigus 1 %.
4. Écoute du propriétaire : validée le 30 octobre.

## 5. Fichiers

Modifiés : `engine/scripts/rogue/rogue_sound_synth.gd`, `rogue_sound_model.gd`, `engine/tests/unit/test_rogue_sound_synth.gd`, `test_rogue_sound_model.gd`, `test_rogue_sound_levels.gd`, `engine/tests/rogue_sound_export.gd`, `rogue_ecoute.py`, `docs/lots/00_INDEX.md`, `docs/SUIVI_AVANCEMENT.md`.

## Livraison

PR #632, fusionnée le 30 octobre 2026. Statut remis à jour par la passe documentaire du 1er novembre, d'après les PR fusionnées ; statut précédent : « Non : interne ; demande et écoute validée du 30 octobre, **version 2.0** ».
