# Lot R22 – Lisibilité du Cyber-Rogue

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Lisibilité du Cyber-Rogue : HUD hors du centre, consignes et boutons, raison des refus de Z, verdict des arches, légendes, zone Z au sol, couloir en deux temps, décor latéral, 3 vues, ambiance coupée (contrat révision 1.15) | Python, GDScript | R11, R13, R17, R21 | Moyenne | En revue le 12 novembre, **version 2.0** |

## 1. Objectif

Essai sur le vélo du 11 novembre : le Cyber-Rogue « fonctionne, graphismes OK, mais sans explication du gameplay et des attendus l'expérience est mauvaise » (note 3/5). Demande du propriétaire : **gameplay lisible et expérience fluide**. Ne jamais laisser le joueur dans le flou : phase, temps restant, prochaine étape, quoi faire et avec quel bouton ; tout appui a une réponse visible, y compris la raison d'un refus.

Maquettes validées par le propriétaire le 12 novembre (`rogue-r22/maquettes/` des fichiers du projet, générées par `gen.py`). Choix du propriétaire le même jour : 3 vues sur les flèches haut et bas.

## 2. Travail fait

### 2.1 Core (contrat révision 1.15, ajouts compatibles)

Champs facultatifs de l'objet `rogue` de `state` (`run.py`) :

- `phase_left_s` : secondes avant la fin de l'échauffement, du couloir, de la récupération ou du retour au calme ;
- `next` : au plus deux étapes à venir (`relic`, `room`, `corridor`, `boss`, `cooldown`, `results`), avec le temps avant chacune (estimé au temps nominal en salle) et l'archétype ;
- `loot_stage` : temps du choix en cours, `card` puis `door` ;
- `target_pct` : consigne de puissance en % de FTP (`{lo, hi}`) ;
- `firewall_gap_s` : avance sur le Firewall en secondes, à la vitesse du joueur ;
- `z_reason` et l'événement `z_refused` : raison d'un Z court refusé (`adrenaline`, `overheat`, `no_target`, `no_charge`, `no_roc_charge`, `no_surge`, `no_hack`, `cursed`, `recovery`, `gold`) ;
- `shift_miss` et l'événement `shift_missed` : arche de Perfect Shift ratée, 1,5 s après sa fenêtre : `early`, `late`, `wrong_way` ou `none`, avec l'écart en secondes.

Les règles du jeu ne changent pas : le core dit seulement ce qu'il décidait déjà en silence (`combat.py`, `run.py`).

### 2.2 Engine

- `rogue_guide_model.gd` (nouveau, pur) : textes du panneau d'état, du Firewall ou de la consigne, de la consigne du bas et des boutons utiles, retours des appuis, légendes au premier passage (gardées dans `user://rogue_legendes_vues.json`, hors mode test).
- `rogue_hud_view.gd` : l'hologramme du centre et les arcs au sol laissent la place au panneau d'état en haut à gauche, au Firewall en haut à droite, à la consigne et aux boutons en bas, aux retours au centre haut et à la légende à droite.
- `marker_guides.gd` (nouveau) : étiquette flottante de chaque objet, zone où Z est accepté (bande au sol dont la longueur suit la vitesse, exactement la fenêtre du core : ± 0,5 s, ± 0,75 s pour un rocher, au moins ± 3 m), portique des arches avec le signe + ou − géant et un anneau d'approche qui se resserre.
- `rogue_corridor_view.gd` : bandeau « 1. Choisis une carte » puis « 2. Choisis ta porte » avec le temps restant, groupe inactif estompé, une seule porte quand les deux mènent au boss, relance des cartes lisible au-dessus des boutons.
- `rogue_side_decor.gd` (nouveau) : pylônes, blocs de données et anneaux le long des deux bords, en quatre MultiMesh ; écart de 26, 18 et 12 m en low, medium et high ; bande plate qui suit le joueur hors salle, au motif périodique (pas de saut au recalage).
- `rogue_scene.gd` : 3 vues (derrière, haute, proche) ; `main.gd` les relie aux flèches haut et bas en run (A reste au core pour les cartes et les portes).
- `living_world.gd`, `main.gd` : les fonds d'ambiance du parcours (grillons) se taisent pendant la run ; ils gardaient le volume de la dernière image du menu.
- Sons : `rogue_refused` (Z refusé) et `rogue_shift_missed` (arche ratée).
- Bandeau des commandes du mode : A pour choisir, A long pour valider.

## 3. Tests

- `core/tests/test_rogue_r22_lisibilite.py` : chaque raison de refus, durée d'une trame, verdicts des arches (tôt, tard, mauvais sens, aucun), temps restant, étapes à venir, temps du couloir, consigne, avance en secondes, schéma.
- `engine/tests/unit/test_rogue_guide_model.gd` : textes du guide, retours, légendes une seule fois et relues, étiquettes, zone Z à la taille de la fenêtre, anneau d'approche, bandeau du couloir, décor (densité, motif périodique, relief).
- `test_rogue_hud_model.gd`, `test_rogue_host.gd`, `test_rogue_sound_synth.gd`, `test_rogue_sound_model.gd`, `test_rogue_combat.py`, `test_contract_ipc.py` mis à jour.

## 4. Reste au propriétaire

- Captures low, medium et high sur le PC (galerie `engine/tests/rogue_galerie.py`), budgets GPU 8 / 13 / 16 ms à vérifier avec le décor latéral.
- Ressenti sur le vélo (10 min).
- Question ouverte : équilibrage de l'adrénaline (aujourd'hui 0,5 par seconde à la cible, 100 s pour une frappe Z).

## Livraison

En revue le 12 novembre.
