# Lot R9 – Progression permanente du mode Cyber-Rogue : châssis à bonus de jeu, statistiques de runs, vies

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Progression permanente : châssis à bonus de jeu, statistiques de runs, vies | Python | R6, V2, V3b, V4 | Petite | **Livré le 27 octobre**, **version 2.0** |

## 1. Objectif

Ce qui reste d'une run à l'autre : des **châssis** débloqués aux coffres de fin, qui donnent des bonus de jeu (décision Q7), les statistiques des runs, et des **vies** achetées avec les pièces de la série V (une vie évite la dégradation du butin après une défaite). Le tout passe par le système de déblocage commun de la série V.

## 2. À lire

1. `docs/lots/00_INDEX.md`, `docs/2.0/PLAN_SERIE_R.md` §2 (Q7), `docs/2.0/PLAN_SERIE_V.md` (§1, §2.1 bis, lots V2, V3b et V4).
2. `docs/lots/LOT_R6_run_deck_boss.md` (coffres, bilan), `LOT_R5_combat.md` §4.3 (défaite).

## 3. Prérequis

R6, V2, V3b et V4 livrés.

## 4. Travail demandé

### 4.1 Châssis

- Un châssis est choisi avant la run (menu R13) ; un seul à la fois.
- Effets **bornés** : aucun bonus de plus de 10 % sur une valeur du jeu, aucun effet sur la pente envoyée au trainer ni sur la puissance demandée (équité par la FTP).
- Catalogue de départ en données (fichier de la série V) :

| Châssis | Déblocage | Bonus |
| --- | --- | --- |
| Standard | D'office | Aucun |
| Blindé | 1re victoire contre le boss | Bouclier max +10 |
| Conducteur | 50 Perfect Shifts au total | Fenêtre de Perfect Shift +0,15 s |
| Collecteur | 500 or cumulés | Or +10 % |
| Survolté | 3 runs VO2max terminées | Adrénaline de départ 20 |
| Endurant | 3 runs endurance terminées | Surchauffe à 0,78 FTP au lieu de 0,75 |

### 4.2 Coffres de fin et vies

- Coffres du retour au calme : l'or de la run est converti en pièces de la série V (taux en données, défaut 1 pièce pour 10 or), plus les gains fixes du plan V (10 à 50 pièces selon le boss).
- **Vie :** achetée avec des pièces (prix en données, défaut 30), au plus 3 en réserve. Après une défaite, une vie est utilisée **automatiquement** : pas de perte d'or ni de butin, mais la récupération forcée de 60 s reste (sécurité). Le menu de départ dit combien de vies sont en réserve.

### 4.3 Statistiques

- Par objectif et par durée : runs jouées, terminées, abandonnées ; salles gagnées ; boss battus ; meilleur or ; Perfect Shifts ; carte la plus prise.
- Recalculables depuis le journal (lignes `rogue` de R8), comme l'expérience de la série V : rien ne se perd si le profil est effacé, sauf les pièces dépensées.
- Stockées dans le profil local de la série V (V4), sous `~/OpenRide/`.

## 5. Fichiers concernés

- **Créés :** `core/src/openride_core/rogue/progress.py`, `core/tests/test_rogue_progress.py`.
- **Modifiés :** fichier de données de la série V (châssis, prix des vies), `core/src/openride_core/rogue/run.py` (châssis appliqué au départ, vie utilisée à la défaite), `docs/SUIVI_AVANCEMENT.md` (une ligne).

## 6. Modifications de contrat autorisées

Ajout compatible à la révision 1.4 (lot T1) : `hello_ack.config.rogue` gagne `chassis` (débloqués, choisi) et `lives` ; `start_run` gagne l'argument facultatif `chassis`.

## 7. Critères d'acceptation

1. `(cd core && pytest -q)` passe.
2. Chaque châssis : déblocage à sa condition (test sur un journal fabriqué), bonus appliqué, borne de 10 % vérifiée.
3. Défaite avec une vie : or et butin gardés, vie retirée ; sans vie : règle de R5.
4. Statistiques recalculées depuis le journal égales aux statistiques tenues au fil des runs.
5. Aucun châssis ne change `grade_sent` ni la puissance cible.

## 8. Hors périmètre

- Garage et achats d'équipement (série V), affichage des châssis (R13).

## 9. Livraison (27 octobre 2026)

- `rogue/progress.py` : catalogue `[[chassis]]` lu dans `data/progression.toml` (surcharge `~/OpenRide/progression.toml`), vérifié (`ChassisError`), `apply_chassis` (ajoute les bonus à une copie de `RogueBalance`), `run_event` (ligne `rogue_run` du journal : celle que lisent déjà l'expérience et les pièces), `RogueStats` (par objectif et durée : runs, terminées, abandonnées, salles gagnées, boss battus, meilleur or, Perfect Shifts ; carte la plus prise), `rogue_stats(progress)`, `unlocked`, `choose_chassis`, `config_block`.
- **Bornes :** seules cinq constantes sont permises (bouclier maximal, fenêtre de Perfect Shift, or gagné, adrénaline de départ, seuil de surchauffe) : la pente envoyée et la puissance demandée ne peuvent donc pas bouger (testé). Chaque bonus est vérifié à au plus 10 % de la valeur du jeu (Blindé 10 %, Conducteur 10 %, Collecteur 10 %, Endurant 4 %). **Écart au cahier :** l'adrénaline de départ du Survolté (20) a une base nulle, donc un plafond absolu de 20 au lieu des 10 %.
- `RogueBalance` gagne `gold_mult` et `adrenaline_start` (neutres) ; `RunEngine(..., lives=n)` : une défaite avec une vie en réserve ne coûte pas les 25 % d'or de la run (la récupération de 60 s reste, et le boss n'en consomme pas) ; `lives_used` et la ligne de journal `rogue life_used` le disent à la session (R8), qui retire la vie du profil (`coins.use_life`).
- Pièces (`coins.py`, `progression.toml`) : `rogue_gold_per_coin` = 10 (l'or de la run, ligne `rogue_run.gold`), `max_lives` = 3 ; `buy_life` refuse au-delà (code `item_locked`).
- Contrat 1.4 (ajout compatible) : `hello_ack.config.rogue.chassis` (`unlocked`, `selected`) et `lives`, argument facultatif `chassis` de `start_run` (`run_invalid` si inconnu, `item_locked` si non débloqué) ; schéma, `ipc_v1.md` et test de contrat mis à jour.
- Statistiques non stockées : elles se recalculent depuis les journaux (même ligne que l'expérience), donc effacer le profil ne les perd pas ; seules les pièces dépensées restent dans le profil de V4.
- Tests : `core/tests/test_rogue_progress.py`.

