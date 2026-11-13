# Lot W19 – Arrivée en destination et en boucle du monde ouvert

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Arrivée en destination et en boucle du monde ouvert : la séance se termine au but | Python | W6, W8, W9, W14 | Petite | En revue (13 novembre) |

## 1. Objectif

Demande du propriétaire du 13 novembre (« fais des lots pour compléter les incohérences et manques » du monde ouvert). En monde ouvert, les navigations **Destination** et **Boucle** n'avaient pas d'arrivée : une fois la cible atteinte, ou le départ retrouvé, le navigateur repartait en balade et la séance continuait jusqu'à « Terminer ». Ce lot donne à ces deux navigations une vraie ligne d'arrivée, comme un parcours.

## 2. À lire

1. `docs/2.0/PLAN_SERIE_W.md`, `docs/contracts/worldgen_v1.md` §4 et §5.
2. Code : `compiler/src/openride_compiler/worldgen/navigator.py` (`Choice.arrived`), `worldgen/process.py` (`_extend`, `choose`, `_publish`), `core/src/openride_core/open_world.py`, `session.py` (arrivée), `open_world_save.py` (W14).

## 3. Travail fait

- **Navigateur :** en destination, le nœud du graphe le plus proche de la cible (à moins de 300 m d'elle) compte aussi pour l'arrivée ; avant, une cible au milieu d'une longue route, à plus de 200 m de tout carrefour, n'était jamais « atteinte » et le navigateur tournait autour.
- **Générateur :** la première étape au bout de laquelle le navigateur annonce `arrived` (hors balade) devient l'arrivée. `finish_m` est le point de la route engagée le plus proche de la cible (ou du départ en boucle), sur cette étape ou la suivante. Il part dans chaque `revision` (champ facultatif ajouté au contrat). Un choix de branche qui quitte la route de l'arrivée l'efface jusqu'à ce que le navigateur la repose. La route continue d'être prolongée au-delà de l'arrivée : la séance n'est jamais mise en pause juste avant la ligne.
- **Core :** `OpenWorld.finish_s` (arrivée en distance de séance) ; la séance se termine (`FINISHED`, bilan, balade enregistrée en GPX par W14) quand le cycliste l'atteint. Générateur relancé après une panne : une destination garde sa cible ; une boucle continue en balade, sans arrivée (son compte de kilomètres repartirait de zéro).
- **Guide :** §4 bis, point 3.

## 4. Fichiers concernés

`compiler/src/openride_compiler/worldgen/navigator.py`, `worldgen/process.py`, `compiler/tests/test_worldgen_process.py`, `core/src/openride_core/open_world.py`, `session.py`, `core/tests/data/stub_worldgen.py` (`--dest-m`), `core/tests/test_open_world_session.py`, `docs/contracts/worldgen_v1.md`, `docs/GUIDE_UTILISATION.md`, `docs/SUIVI_AVANCEMENT.md`.

## 5. Modifications de contrat

`worldgen_v1.md` : champ facultatif `finish_m` du message `revision` (ajout compatible, ligne au journal). Aucune modification de l'IPC ni du format `.world`.

## 6. Critères d'acceptation

1. `pytest` passe dans `core/` et `compiler/`.
2. Générateur réel sur une grille de routes : pas d'arrivée en balade ; destination au milieu d'une route à 250 m des carrefours : arrivée à moins de 15 m de la cible ; boucle de 8 km : arrivée à moins de 15 m du départ.
3. Séance avec la doublure : la boucle de 2 km se termine à 2 km et enregistre la balade ; la destination se termine au point annoncé ; la balade n'a jamais d'arrivée ; après une relance du générateur, la destination garde son arrivée.
4. Recette PC (avec W16) : une boucle de 10 km près de Sarre-Union se termine au départ, avec le bilan.

## 7. Hors périmètre

Distance restante jusqu'à l'arrivée affichée au HUD (demanderait un champ de l'objet `open_world` de l'IPC, donc une révision) ; la boucle reprise après une panne du générateur.

## Livraison

Branche `claude/project-thread-49nsz6`, PR #873 (13 novembre).
