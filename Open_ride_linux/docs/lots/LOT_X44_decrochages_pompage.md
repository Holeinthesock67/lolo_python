# Lot X44 – Décrochage du trainer ou fatigue, statuts FTMS, analyse du pompage

## 1. Objectif

Séance du 29 octobre : la puissance est passée de 449 W à 0 W en 2 s, et le cycliste a dit « on dirait que ça pompe ». Pour juger, il fallait lire la trace à la main, puissance et cadence ensemble, à côté de ce que le trainer annonce. Ce lot le fait automatiquement, pour le banc `trainer_steps` (lot X43) comme pour un journal de séance.

## 2. Spécification

| # | Règle |
| --- | --- |
| X44-1 | **Chute** : la puissance perd plus de 60 % en 3 s au plus, depuis au moins 150 W (médiane des 3 s d'avant). Deux chutes à moins de 10 s n'en font qu'une. |
| X44-2 | **Diagnostic**, dans cet ordre :<br>– `arret` : cadence sous 20 tr/min au bout de la chute ;<br>– `fatigue` : cadence tombée de 10 tr/min ou plus avant que la puissance passe sous la moitié de son niveau ;<br>– `trainer` : cadence restée à ± 8 tr/min de son niveau d'avant pendant toute la chute ;<br>– sinon `indetermine`.<br>Le rapport donne aussi l'avance de la baisse de cadence sur la mi-chute. |
| X44-3 | **Ce que dit le trainer** : les lignes `ftms` du journal (PR #580 : `status` 0x02, 0x03, 0x14, 0xFF…, `training_status`, `brake_loss`, `power_back`, `power_not_back`), relevées à ± 5 s de chaque chute. Le banc les reçoit du pilote (`event_sink`) et les écrit dans `events.csv` (type `ftms`). Un repère `decrochage` du cycliste à ± 10 s (lot X47) est signalé. |
| X44-4 | **Pompage**, par palier du banc ou sur toute la séance :<br>– amplitude crête à crête (5e à 95e centile) de la moyenne glissante sur 4 s, en % de la moyenne ;<br>– période dominante entre 4 et 30 s (premier maximum de l'autocorrélation au-dessus de 0,3) ;<br>– nombre de chutes à 0 W (sous 10 W) à cadence d'au moins 40 tr/min.<br>La moyenne sur 4 s efface les coups de pédale (2,4 par seconde à 73 tr/min) qu'un relevé à 1 Hz prendrait pour des vagues. |
| X44-5 | **Sorties** :<br>– `rapport.html` du banc : sections « Décrochages » et « Pompage », plus un résumé texte en fin d'essai ;<br>– outil `python -m openride_core.tools.decrochages SOURCE [--html F] [--json]`, où SOURCE est un dossier du banc ou un journal `.jsonl`. |

## 3. Fichiers

- `core/src/openride_core/tools/decrochages.py` (nouveau, fonctions pures) ;
- `tools/trainer_steps.py` (`bench_source`, `event_sink`, rapport) ;
- `core/tests/test_decrochages.py` ;
- `docs/OUTILS_DE_TEST.md`.

## 4. Critères d'acceptation

1. Cas synthétiques :
   - 449 → 0 W à 75 tr/min donne `trainer` ;
   - une cadence qui baisse 3 s avant la chute donne `fatigue` ;
   - un arrêt de pédalage donne `arret` ;
   - une chute de 33 % ou partie de moins de 150 W n'est pas une chute.
2. Une oscillation de 8 s donne une période de 8 s. Des coups de pédale à 2,4 Hz donnent moins de 10 % d'amplitude.
3. Journal de séance avec des lignes `ftms` et un repère : statuts et repère attachés à la chute.
4. Sur le PC (via le fil de fusion) : relire l'essai du 29/10 (`~/OpenRide/mesures/2026-10-29/paliers/`) et le journal de la séance.

## 5. Hors périmètre

Les lignes `ftms` elles-mêmes (PR #580, fil FTMS) et le repère `decrochage` en séance (lot X47).
