# Lot R15 – Scénariste de run : composer échauffement, salles, couloirs et boss à partir de l'objectif et de la durée

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Scénariste de run : calendrier et salles composés à partir de l'objectif et de la durée | Python | R3, R6 | Petite | **Livré le 27 octobre** (module pur ; branché par R8), **version 2.0** |

## 1. Objectif

Décision Q6 : le joueur choisit dans le menu une durée et un objectif (endurance, seuil, VO2max) ; le jeu compose le scénario de la run à partir de ces deux paramètres. Ce lot écrit ce scénariste, en module pur, et corrige le calendrier de 45 min du GDD, qui ne tenait pas (quatre salles de 5 min et quatre couloirs de 2 min font 28 min, pour une fenêtre de 22 min).

## 2. À lire

1. `docs/lots/00_INDEX.md`, `docs/2.0/GDD_CYBER_ROGUE.md` §1.2 et §2.7 (avec leurs corrections), `docs/2.0/PLAN_SERIE_R.md` §2 (Q3, Q6) et §7.
2. `docs/lots/LOT_R3_generateur_salles.md` (variantes par objectif), `LOT_R6_run_deck_boss.md` (machine à états).

## 3. Prérequis

R3 et R6 livrés (R6 peut être fait en parallèle avec une interface convenue : liste d'étapes).

## 4. Travail demandé

### 4.1 Interface

`compose_run(objective, duration_min, seed, rider, balance) -> Scenario` : liste ordonnée d'étapes `{kind: warmup | room | corridor | boss | cooldown, nominal_s, archetype, variant}` ; les salles sont tirées au fil de la run, aux portes (deux archétypes proposés par couloir), dans le réservoir de l'objectif.

### 4.2 Calendriers (valeurs de départ)

| Durée | Échauffement | Salles × (combat + couloir) | Boss | Retour au calme |
| --- | --- | --- | --- | --- |
| 30 min | 6 min | 2 × (4 + 2) = 12 min | 7 min (2 + 3 + 1 min, et 1 min de transitions) | 5 min |
| 45 min | 8 min | 4 × (3,5 + 2) = 22 min | 10 min (3 + 4 + 1,5 min, et 1,5 min de transitions) | 5 min |
| 60 min | 10 min | 6 × (3,5 + 2) = 33 min | 10 min | 7 min |
| 90 min | 10 min | 10 × (4 + 2) = 60 min | 12 min (4 + 5 + 1,5 min, et 1,5 min de transitions) | 8 min |

- Salles de 3 à 5 min (GDD §2.5) ; la durée de chaque salle est tirée dans cette plage autour de la moyenne du tableau, la somme restant celle du tableau.
- Le dernier couloir avant le boss n'offre pas de porte (seulement une carte).

### 4.3 Réservoir d'archétypes par objectif

| Objectif | Archétypes et variantes | Règles |
| --- | --- | --- |
| Endurance | Diesel, Grimpeur et Saboteur en variante endurance | Surchauffe active (Q3) ; boss en variante endurance |
| Seuil | Diesel, Grimpeur et Saboteur en variante seuil ; Sprinteur au plus une fois | — |
| VO2max | Puncheur, Sprinteur et Grimpeur en variante VO2max | Au plus deux salles VO2max de suite sans couloir de 2 min complet |

- Jamais trois fois de suite le même archétype ; les deux portes d'un couloir proposent deux archétypes différents.

### 4.4 Joueur en retard

Les salles sont en distance (R3) : un joueur sous la cible met plus longtemps. Après chaque salle, le scénariste recalcule la fin prévue ; si elle dépasse la durée choisie de plus de 2 min, il raccourcit les couloirs suivants (jusqu'à 60 s), puis retire une salle avant le boss. Le boss et le retour au calme ne sont jamais retirés (décision R-Q2 du 26 octobre).

**Salle retirée = échec signalé** (ajout du propriétaire) : malus de 10 or (sans passer sous 0), salle comptée « manquée » (`rooms_skipped` du bilan), événement `room_skipped` pour l'animation et le son de l'engine (R11, R12), ligne `rogue` au journal. Un couloir raccourci n'est pas un échec.

Critère supplémentaire : le joueur simulé 10 % sous la cible du critère 4 qui perd une salle voit `room_skipped` une seule fois par salle retirée et l'or baisser de 10.

## 5. Fichiers concernés

- **Créés :** `core/src/openride_core/rogue/scenario.py`, `core/tests/test_rogue_scenario.py`.
- **Modifiés :** `core/src/openride_core/rogue/balance.py` (calendriers et réservoirs), `docs/SUIVI_AVANCEMENT.md` (une ligne).

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `(cd core && pytest -q)` passe.
2. Pour chaque durée et chaque objectif, 100 graines : somme des durées nominales égale à la durée choisie à ± 30 s.
3. Réservoirs respectés (aucune salle VO2max en endurance), jamais trois fois le même archétype.
4. Joueur simulé 10 % sous la cible sur une run de 45 min : fin à 47 min au plus, boss joué.
5. Même graine, même scénario.

## 8. Hors périmètre

- Plans d'entraînement sur plusieurs semaines (lot O11), choix libre des salles.

## 9. Livraison (27 octobre 2026)

- `rogue/scenario.py` (`compose_run`, `adapt_after_room`) ; calendriers, réservoirs et marges dans `RogueBalance` ; le moteur de run (R6) appelle `adapt_after_room` à la fin de chaque salle (`room_skipped`, malus de 10 or, `rooms_skipped`). Tests : `core/tests/test_rogue_scenario.py`.
- **Forme du scénario :** celle de R6 (`Scenario` de `Step`) : l'échauffement, la première salle, un couloir à deux portes par salle suivante (les deux salles proposées ont la même durée), un dernier couloir sans porte, les trois phases du boss (durées réparties selon le poids 3 / 4 / 1,5 min, transitions de 30 s comprises) et le retour au calme. Les salles ne sont pas tirées au fil de la run mais composées d'avance : un tirage à l'avance permet de vérifier la règle des trois archétypes sur tous les chemins.
- **Règle des trois archétypes :** les trois archétypes du réservoir tournent d'un couloir à l'autre (deux couples consécutifs partagent un seul archétype, trois n'en partagent aucun), donc aucun chemin ne joue trois fois le même archétype de suite, quelles que soient les portes (vérifié sur tous les chemins). En seuil, le Sprinteur remplace une porte d'un seul couloir, donc au plus une fois sur tout chemin. En VO2max, chaque salle est suivie d'un couloir complet de 2 min tant que le joueur n'est pas en retard ; le raccourcissement des couloirs (60 s au plus bas) vient après, comme le demande le §4.4.
- **Joueur en retard :** après chaque salle, la fin prévue est recalculée avec le ralentissement observé (temps écoulé divisé par le temps nominal joué) appliqué aux salles et au boss restants ; au-delà de 2 min de retard, les couloirs suivants passent à 60 s, puis le dernier couloir à portes et sa salle sont retirés tant que le retard dépasse la marge. Le boss et le retour au calme restent. Un joueur à 90 % de la cible finit une run de 45 min avant 47 min (dans l'essai, il gagne les salles puis le boss s'enfuit sur défaite à la 40e minute).
