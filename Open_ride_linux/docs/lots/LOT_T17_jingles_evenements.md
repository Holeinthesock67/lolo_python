# Lot T17 – Engine : jingles des événements du parcours

## 1. Objectif

Marquer par un court jingle les moments forts d'une séance en mode classique : le sommet d'une montée, la fin d'un sprint, le passage sous une arche de bonus et la fin de la séance (demande du propriétaire du 27 octobre). Les sons sont synthétisés par l'engine, comme le vent et les bips ERG, et remplaçables par un fichier OGG.

## 2. À lire

1. `docs/2.0/PLAN_SERIE_T.md` §3.1 et §3.3.
2. `docs/contracts/ipc_v1.md` révision 1.4 : message `segment_result` (champs `kind`, `pr`), champ `powerup`, `session_state`.
3. Code : `engine/scripts/sound_player.gd`, `segment_markers_model.gd` (positions des arches), `segment_hud_model.gd` (doublons de `segment_result`), `main.gd`.

## 3. Prérequis

T8 et T9 (codés) ; T7 pour les vraies trames.

## 4. Travail demandé

- **Modèle sans affichage** `engine/scripts/event_sounds_model.gd`, testé par `engine/tests/unit/test_event_sounds_model.gd` :
  - `segment_result` nouveau (doublons déjà écartés par `segment_hud_model.on_result`) : `kind` « climb » donne `jingle_summit` (la fin d'une montée est son sommet), « sprint » donne `jingle_sprint` ; avec `pr` vrai, variante `_pr` ;
  - arche franchie par `s` cumulé, même règle que `ArchSchedule.crossed` du core, en `RUNNING` avec le champ `powerup` seulement (arches affichées, T8) ; un saut de plus de 100 m (reprise après coupure) ne compte pas ;
  - fin de séance au passage de `RUNNING` ou `PAUSED` à `FINISHED`, en SIM comme en ERG.
- **Synthèse et lecture** dans `sound_player.gd` : un flux non bouclé par jingle, lu sur un lecteur non spatialisé du bus « Events » (`AudioMix.bus(AudioMix.EVENTS)`, réglage « Volume bips et événements »), trois voix au plus ; `~/OpenRide/Sounds/<nom>.ogg` remplace le son généré.

## 5. Fichiers concernés

- **Nouveaux :** `engine/scripts/event_sounds_model.gd`, son test.
- **Modifiés :** `sound_player.gd`, `main.gd`, documentation (index, plan T, recette T11, guide, README).
- **Interdits :** le core, le contrat.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. Tests Godot sans écran verts, dont le nouveau test (segments et records, arches sur parcours ouvert et en boucle, vecteurs partagés avec le core, saut ignoré, fin de séance, synthèse sans écrêtage).
2. À la recette T11 : chaque jingle s'entend par-dessus le vent à 30 km/h, sans gêner, et une seule fois par événement.

## 8. Hors périmètre

- Bruitages du mode Cyber-Rogue (série R, lot R18), qui reprendront la même palette ; réglage du volume par catégorie (audio_mix.gd, docs/AUDIO.md).

## 9. Livraison (27 octobre 2026, code ; validation sur le PC)

- Six jingles (`EventSoundsModel.JINGLES`, notes de la gamme de do majeur entre 523 et 2 093 Hz, timbres « note douce » et « cloche ») :
  - `jingle_summit` : do, mi, sol montants et coup de cloche (1,5 s) ; `jingle_summit_pr` : une note de plus et la cloche une octave plus haut ;
  - `jingle_sprint` : sol, do vifs (0,4 s) ; `jingle_sprint_pr` : avec un do aigu en plus ;
  - `jingle_arch` : arpège de cloches scintillant (0,65 s) ;
  - `jingle_finish` : trois sol puis accord de do tenu (1,85 s).
- `main.gd` joue le jingle d'un `segment_result` nouveau et ceux que rend `on_state` pour chaque trame, et note `event_sound kind=…` dans le journal de test.
- Choix faits :
  - aucun champ IPC nouveau : sommet et sprint viennent de `segment_result`, l'arche des positions déjà calculées par T8 ;
  - plusieurs arches dans une même trame donnent un seul jingle ;
  - niveau −6 dB sur le bus « Events » d'audio_mix.gd, réglé par « Volume bips et événements » des Réglages.
- Tests : `engine/tests/unit/test_event_sounds_model.gd`, à lancer sur le PC ou par la CI (Godot n'a pas pu être lancé dans l'environnement cloud).

## 10. Jingles des portiques (29 octobre 2026)

- Deux jingles de plus : `jingle_start` (départ : do, do brefs puis quinte, 0,5 s) au passage de `READY` à `RUNNING` quand le parcours a ses portiques (pas le monde ouvert) et au franchissement du portique de départ d'un sprint ou d'une montée ; `jingle_lap` (« ding-dong » de deux cloches, 0,96 s) à chaque passage de la ligne d'une boucle. Arrivées inchangées : fin de sprint `jingle_sprint`, sommet `jingle_summit`, arrivée du parcours ou fin d'entraînement `jingle_finish`.
- Positions des portiques sonores : `segment_markers_model.gate_jingles(marks)`, mêmes règles que les arches (sauts de plus de 100 m ignorés, cumul sur une boucle) mais sans le champ `powerup` (ERG compris) ; jamais en mode Rogue ; un seul jingle par trame (portique avant arche).
- Démarrage : les jingles ne sont plus synthétisés au démarrage mais un par image ensuite (ou tout de suite s'il en faut un avant) ; la génération des sons du démarrage (budget `sound_generation`, 1 200 ms) y gagne environ 0,2 s malgré les deux jingles ajoutés.
- Écoute : fichiers WAV des six jingles dans les fichiers du projet (`audio-jingles-portiques/`). Tests : `engine/tests/unit/test_event_sounds_model.gd` (départ, portiques, boucle, monde ouvert, Rogue, un jingle par trame, jingles tous différents).
