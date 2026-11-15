# Lot EP3 – Bandeau de la consigne en direct dans le jeu

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série EP (essais physiques) : la consigne du guide `essai_physique` (EP2) s'affiche dans le bandeau du jeu, plein écran compris, lue dans `~/OpenRide/Essais/consigne_directe.json` | GDScript | EP2 | Petite | Livré le 15 novembre 2026 (PR #905) ; à voir sur le vélo au premier essai |

## 1. Objectif

Le guide parlait dans un terminal caché par le jeu en plein écran : pas de retour visuel. Principe validé le 15 novembre 2026 : chaque consigne a un retour visuel et sonore. La voix et les sons restent au guide ; le jeu affiche le texte.

## 2. Spécification

| # | Règle |
| --- | --- |
| EP3-1 | Fichier écrit par le guide (remplacement atomique) : `{"id": n, "texte": "...", "sorte": "consigne" \| "vu" \| "rappel" \| "saute" \| "fin" \| "annonce", "duree_s": 8}`. |
| EP3-2 | `engine/scripts/live_cue.gd` (sans nœud) : fichier relu au plus une fois par seconde pendant une séance en cours (tous les modes, Cyber-Rogue compris), consigne rendue quand son `id` change ; fichier illisible ou texte vide ignorés sans message d'erreur ; fichier déjà là au lancement : retenu sans être affiché. |
| EP3-3 | `main.gd` : bandeau `cue` (celui des consignes d'essai de `cue_model.gd`) pendant `duree_s`, ligne `[essai] consigne en direct` au journal ; pas de bip, le guide joue déjà le sien. Aucune commande IPC nouvelle. |

## 3. Tests

`engine/tests/unit/test_live_cue.gd`.

## Livraison

15 novembre 2026 : `live_cue.gd`, branchement dans `main.gd`, test.
