# Lot R6 – Run : machine à états, couloirs, deck et cartes, or, reliques, boss en trois phases

## 1. Objectif

Enchaîner une run complète du mode Cyber-Rogue, en module pur : échauffement, salles, couloirs avec choix de porte et de carte, boss en trois phases, retour au calme et bilan. Ce lot joue un **scénario** donné (suite de salles produite par R15, ou écrit à la main dans les tests) ; il ne choisit pas lui-même les salles.

## 2. À lire

1. `docs/lots/00_INDEX.md`, `docs/2.0/GDD_CYBER_ROGUE.md` §2.2, §2.6 et §2.7 (avec leurs corrections), `docs/2.0/PLAN_SERIE_R.md` §2 et §7.
2. `docs/lots/LOT_R5_combat.md`, `LOT_R3_generateur_salles.md` §4.4 (boss), `LOT_R1_contrat_ipc_rogue.md` §4.4 à §4.6 (phases, `loot`, bilan).

## 3. Prérequis

R5 livré.

## 4. Travail demandé

### 4.1 Machine à états

`WARMUP` → (`ROOM` → `CORRIDOR`) × n → `BOSS` (phases 1 à 3) → `COOLDOWN` → `RESULTS`, avec `RECOVERY` après une défaite (R5 §4.3). `RunEngine.step(dt, inputs) -> RunOutputs` : pente de l'ennemi à envoyer, verrou de braquet, objet `rogue` de `state`, messages `room` et `loot` à émettre, lignes d'événements pour le journal. `RunEngine.snapshot()` et `RunEngine.restore(snapshot)` pour la reprise après un plantage du core (R8).

- **Échauffement :** pente 0 à 2 %, rampe de 0,50 à 0,75 FTP (cible affichée) ; tirage de la **relique de départ** à la 3e minute (1 parmi 3, mêmes boutons que les cartes) ; calibrage : le joueur essaie chaque vitesse (rien n'est imposé).
- **Couloir (2 min par défaut, 0 %, zone 1 à 2) :** d'abord 1 carte parmi 3, puis le choix d'une porte parmi 2 (archétypes affichés). A court fait défiler (flèches gauche et droite en raccourci), A long valide, Z court relance le tirage des cartes (coût 15 or, +5 à chaque relance dans le même couloir) ; + et B restent les vitesses. Le deck se consulte dans l'écran de pause (Y). Sans choix au bout du couloir : pas de carte, porte de gauche.
- **Boss :** les trois salles de R3 §4.4, avec leurs transitions.
- **Retour au calme :** pente 0 %, 0,50 FTP conseillés ; coffres de fin (or converti en déblocages, R9) ; aucune perte possible.

### 4.2 Deck

- Le deck est l'ensemble des cartes gardées pendant la run ; toutes agissent en même temps, sauf les cartes actives (une seule équipée, sur Z long : la dernière prise remplace l'ancienne). Le Disjoncteur du GDD n'est plus une carte : c'est l'appui long sur B (décision R-Q8 revue).
- Pignons spéciaux : une seule carte par vitesse remplacée (la nouvelle remplace l'ancienne sur la même vitesse).
- Tous les effets sont exprimés **en points de pente** ou en multiplicateurs de jeu, et la pente envoyée reste bornée par la plage du trainer (risque 2 du plan).

### 4.3 Cartes de départ (GDD §2.6, chiffrées)

| Carte | Type | Effet chiffré |
| --- | --- | --- |
| Rouleau compresseur | Terraformeur | Les tronçons de pente > 6 % sont écrêtés à 6 % et allongés de 3 s |
| Tremplin cinétique | Terraformeur | Au fond d'une descente (pente ≤ −1 %), en vitesse ≥ 9 : +15 d'adrénaline et 5 s de dégâts ×1,5 |
| Overdrive | Pignon (remplace la 12) | Engagée : +4 points de pente envoyée et dégâts ×2 pendant 8 s, puis retour automatique en 6 ; recharge 45 s |
| Soin | Pignon (remplace la 1) | En vitesse 1 au-delà de 95 rpm : +1 bouclier par seconde (le bouclier ne se recharge pas en combat sans cette carte ; « 2 fois plus vite » du GDD n'a donc pas de base) |
| Maudit | Pignon (remplace la 10) | En vitesse 10 : dégâts ×1,35, Z sans effet |
| Shifter électronique pro | Module | Fenêtre de Perfect Shift doublée (au plus 3 s) ; +3 bouclier à chaque réussite |
| Siphon d'aspiration | Module (parade Z) | Aspiration réussie : +50 d'adrénaline |
| Inversion polaire | Carte active (Z long) | Une fois par salle : pendant 8 s, la pente de l'ennemi est remplacée par son opposé (montée de 7 % → descente de 7 %, bornée à −3 %) |

Reliques de départ (décision R-Q7) : trois cartes passives tirées dans une liste à part, gardées toute la run : bouclier max +20 ; or +25 % ; fenêtre de Perfect Shift +0,3 s.

### 4.4 Bilan

À `RESULTS`, objet `summary.rogue` du contrat (R1 §4.6). Une run finie par `end_session` avant `RESULTS` donne `result` = `abandoned`, sans perte d'or acquis ni déblocage.

## 5. Fichiers concernés

- **Créés :** `core/src/openride_core/rogue/run.py`, `core/src/openride_core/rogue/cards.py`, `core/tests/test_rogue_run.py`.
- **Modifiés :** `core/src/openride_core/rogue/balance.py`, `docs/SUIVI_AVANCEMENT.md` (une ligne).

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `(cd core && pytest -q)` passe.
2. Un scénario de test (échauffement, 2 salles, boss, retour au calme) joué par un cycliste simulé passe par toutes les phases dans l'ordre et produit un `summary.rogue` valide pour le schéma de R1.
3. Couloir sans appui : aucune carte, porte de gauche. Relance : coût 15 puis 20 or, refusée sans or suffisant.
4. Chaque carte du §4.3 a un test de son effet chiffré ; la pente envoyée ne sort jamais de −10 à +16 %.
5. `snapshot()` puis `restore()` au milieu d'une salle : la suite de la run est identique à celle d'une run non interrompue (même graine).
6. Défaite pendant le boss : le boss s'enfuit, passage au retour au calme, `boss` = `fled`.

## 8. Hors périmètre

- Composition du scénario (R15), déblocages permanents (R9), affichage (R13).
