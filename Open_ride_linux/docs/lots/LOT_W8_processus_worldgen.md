# Lot W8 – Processus `openride-worldgen` : horizon de 3 km, branches, préchargement, hors ligne

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Processus `openride-worldgen` : horizon de 3 km, amorces de branches, relief en avance, hors ligne | Python | W6, W7 | Grande | Livré le 27 octobre (PR #313) |

## 1. Objectif

Assembler graphe, navigateur, profils et carrés dans un processus séparé, piloté par le core selon le dialogue de W1 (`docs/contracts/worldgen_v1.md`) : il prépare la zone de départ, tient au moins 3 km de route engagée devant le cycliste, calcule les amorces de branches, télécharge le relief en avance et se comporte proprement sans réseau.

## 2. À lire

1. `docs/2.0/PLAN_SERIE_W.md` §3.2, §3.5, §3.6 et §5, `LOT_W1_contrat_monde_vivant.md` en entier, `docs/contracts/worldgen_v1.md`.
2. Code : `worldgen/store.py`, `region.py`, `graph.py`, `edge_profile.py`, `navigator.py`, `squares.py` ; `compiler/src/openride_compiler/cache.py`.

## 3. Prérequis

W6 et W7 livrés (donc W2 à W5). W13 n'est pas requis : sans tuiles vectorielles, seules les régions converties (W3) sont jouables.

## 4. Travail demandé

Module `worldgen/process.py`, point d'entrée `openride-worldgen` (dans `compiler/pyproject.toml`) :

- **Boucle :** lecture des lignes JSON de l'entrée standard dans un fil, file d'événements, réponses sur la sortie standard (une ligne, `flush`), journal en français sur la sortie d'erreur. Aucun calcul dans le fil de lecture.
- **`open` :**
  1. origine de séance sur la grille de 5 km (W1 §4.2), création de `seances/<id>.world/` (manifeste `live`) ;
  2. données : base de la région qui contient le départ si elle existe, sinon tuiles vectorielles (W13, si présent et `network` vrai), sinon erreur `world_unavailable` ;
  3. relief : tuile(s) du départ téléchargées avant `ready` ; `status` régulier (octets, carrés) ;
  4. point de départ accroché à l'arête admise la plus proche (moins de 200 m, sinon `world_unavailable`), sens donné par `heading_deg` ;
  5. génération des carrés à moins de 1 500 m de la route engagée et des tuiles lointaines à moins de 12 km, puis `status ready` et première `revision`.
- **Horizon :** à chaque `progress`, si `length_m − s_m < horizon_m`, prolonger la route sur la branche par défaut du navigateur, profil par W5, parties de 1 km écrites (W1 §4.2) ; carrés demandés à `SquareQueue` par ordre de distance.
- **Carrefours :** pour chaque carrefour à moins de `horizon_m`, `junctions.json` avec les amorces de 500 m de chaque branche, calculées **avant** que le carrefour soit à moins de `offer_m` (300 m) ; `choose` avant `lock_s_m` : remplacer la route après le carrefour par la branche choisie (amorce déjà prête), `changed_from_part` mis à jour, prolonger ensuite ; après `lock_s_m` : `error branch_locked`.
- **Relief en avance :** téléchargement de la tuile de relief voisine dès que la route engagée passe à moins de 10 km de son bord (plan §3.2), en tâche de fond, sans bloquer l'horizon.
- **Hors ligne :** le navigateur ne propose et n'engage que des arêtes dont le relief et les carrés sont disponibles ; si aucune branche n'en a, demi-tour proposé par défaut ; `status offline` ; plus de route du tout : `status missing` (le core met en pause, W9). La séance ne s'arrête jamais pour attendre un téléchargement.
- **Cache :** `touch` de tout ce qui sert, liens des carrés dans la séance (`link_into`), `evict()` au plus une fois par minute hors des carrés de la séance.
- **`close` :** fin des tâches en cours (au plus 5 s), index du cache à jour, `closed`.
- **Simulation :** option `--fake-clock` et `--no-network` pour les tests de bout en bout sans réseau avec la base et le relief synthétiques de W15 si présent, sinon ceux du test.

## 5. Fichiers concernés

- **Nouveaux :** `compiler/src/openride_compiler/worldgen/process.py`, `compiler/tests/test_worldgen_process.py`.
- **Modifiés :** `compiler/pyproject.toml` (point d'entrée), `docs/SUIVI_AVANCEMENT.md`.

## 6. Modifications de contrat autorisées

Aucune (W1 les a faites).

## 7. Critères d'acceptation

1. `pytest` passe dans `compiler/` sans réseau.
2. Processus lancé par le test, `open` sur une base synthétique en grille : `ready` puis `revision` ; `route/part_0.json` et `live.json` valides pour leurs schémas ; `length_m ≥ 3 000`.
3. `progress` simulé de 0 à 20 km à 60 km/h en temps accéléré : à tout instant `length_m − s_m ≥ 3 000` ; chaque carrefour publié avec ses amorces au moins 300 m avant ; parties écrites atomiquement (lecteur concurrent du test : jamais de JSON partiel).
4. `choose` à 100 m du carrefour : route remplacée, `changed_from_part` correct, nouvelle branche prolongée à 3 km dans la seconde ; à 20 m : `branch_locked`.
5. Réseau coupé (`--no-network`) hors de la zone en cache : `status offline`, aucune branche hors cache engagée, demi-tour proposé à la limite.
6. Deuxième séance au même endroit : aucun téléchargement et aucun carré recalculé (compteurs).
7. Mémoire du processus mesurée pendant le test de 20 km et affichée.

**Sur le PC (le propriétaire) :** avec W9, voir W16.

## 8. Hors périmètre

Côté core (W9), côté engine (W10 à W12), tuiles vectorielles (W13).

## Livraison

PR #313, fusionnée le 27 octobre 2026. Statut remis à jour par la passe documentaire du 1er novembre, d'après les PR fusionnées ; statut précédent : « Oui, après W7 (issue #263) ».
