# Lot EP1 – Séance verrouillée au lancement (essais physiques)

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série EP (essais physiques) : `run --autostart --seance FICHIER` joue au lancement une liste de commandes du menu (parcours, bots, mode, épreuve de piste, run Cyber-Rogue) ; toute séance d'essai part verrouillée, sans menu ni réglage repris de la partie d'avant | Python | J1 | Petite | Livré le 15 novembre 2026 (PR à venir) |

## 1. Objectif

Essais du 15 novembre 2026 sur le vélo : le guide des séances donnait ses consignes à l'horloge et laissait choisir le parcours au menu. Les séances partaient en retard (menus, chargements, échauffement du Cyber-Rogue) ou sur un autre terrain (cinq bots de la partie d'avant sur l'Alpe d'Huez, Grand Prix lancé sur l'Alpe d'Huez). Principe validé par le propriétaire le 15 novembre : chaque essai annonce ce qu'il teste, part sur un terrain imposé qui permet ce test, et ses consignes suivent les événements du jeu lus au journal. Ce lot pose la première brique : lancer **toute** séance sans menu, par un seul chemin.

## 2. Spécification

| # | Règle |
| --- | --- |
| EP1-1 | `seance_file.py` : une séance verrouillée est une liste de commandes IPC du menu (`select_route`, `select_workout`, `start_run`, `set_wtf_rule`, `set_mode_option`, `start`), qui finit par un seul `start`. Fichier JSON `{"id", "but", "commandes": [{"cmd", "args"}]}` ; `id` et `but` sont pour le guide, le core ne lit que `commandes`. |
| EP1-2 | `run --autostart --seance FICHIER` joue ces commandes dans l'ordre, comme les menus de l'engine. `--route`, `--workout` et `--mode` donnent la liste courte (`seance_file.from_options`) et passent par le même chemin ; `--seance` les exclut et demande `--autostart` (code 2). |
| EP1-3 | Parcours et entraînements de la liste sont vérifiés avant d'ouvrir les ports (comme J1). Ensuite, la première erreur renvoyée par le core sur une commande, ou un `start` qui ne fait pas partir la séance, arrête le core (`AutostartError`, code 1, message au journal) : aucune séance ne part à moitié réglée. |
| EP1-4 | `start` de la fiche porte ses bots (`"bots": []` pour aucun) : les bots de la ligne de commande ou de la partie d'avant ne sont pas repris. |

## 3. Tests

`core/tests/test_seance_verrouillee.py` : liste courte, listes refusées, lecture du fichier, séance libre sans bots, élimination au vélodrome, run Cyber-Rogue, épreuve de piste hors vélodrome refusée et core arrêté, parcours inconnu refusé avant les ports, options exclusives de la ligne de commande.

## 4. Suite de la série

- EP2 : guide des essais à étapes déclenchées par le journal (départ réel, phase et salle du Cyber-Rogue, boîtes et objets du Grand Prix, tours et éliminations au vélodrome), fiches réécrites, fin à 10 min de pédalage.
- EP3 : bandeau de consigne envoyé par le guide et affiché dans le jeu (révision IPC à réserver).

## Livraison

15 novembre 2026 : `seance_file.py`, option `--seance` de `openride-core run` (aussi par le lanceur `openride`), tests.
