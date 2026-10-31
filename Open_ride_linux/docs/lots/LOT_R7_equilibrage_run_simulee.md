# Lot R7 – Table d'équilibrage en données et run simulée avec cyclistes types

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Table d'équilibrage en données et run simulée avec cyclistes types | Python | R6, R15 | Moyenne | **Livré le 27 octobre** (rapport : `docs/2.0/RAPPORT_EQUILIBRAGE_R7.md`), **version 2.0** |

## 1. Objectif

Sortir toutes les valeurs du jeu dans un fichier de données modifiable (décision Q4), puis jouer des runs complètes avec des cyclistes simulés pour vérifier que l'équilibrage tient ses cibles. Ce lot produit un rapport et propose des valeurs ; il ne change pas les règles.

## 2. À lire

1. `docs/lots/00_INDEX.md`, `docs/2.0/PLAN_SERIE_R.md` §2 (Q4) et §5 (risque 6).
2. `docs/lots/LOT_R2_wbal_postures.md` à `LOT_R6_run_deck_boss.md`, `LOT_R15_scenariste_run.md`.
3. Code : `core/src/openride_core/rogue/` (après R6), `core/src/openride_core/tools/session_summary.py` (NP, IF, TSS).

## 3. Prérequis

R6 livré ; R15 utile (sinon scénarios écrits à la main).

## 4. Travail demandé

### 4.1 Fichier de données

- `core/src/openride_core/rogue/balance.toml`, embarqué dans le paquet ; chaque champ de `RogueBalance` y figure avec un commentaire en français.
- Surcharge facultative par `~/OpenRide/rogue_balance.toml` (mêmes clés ; clé inconnue = erreur lisible, valeur hors bornes = erreur lisible).
- Le journal de chaque run note l'empreinte (hachage court) de la table utilisée.

### 4.2 Cyclistes types

| Profil | FTP | W' | Comportement |
| --- | --- | --- | --- |
| Débutant | 150 W | 12 kJ | Tient la cible à ± 8 %, 30 % de Perfect Shifts, les appuis sur Z une fois sur deux |
| Moyen | 250 W | 20 kJ | ± 5 %, 60 % de Perfect Shifts, les appuis sur Z trois fois sur quatre |
| Confirmé | 330 W | 25 kJ | ± 3 %, 90 % de Perfect Shifts, les appuis sur Z presque toujours |
| Fatigué | 250 W | 20 kJ | Comme Moyen, puis −15 % de puissance après 30 min |

### 4.3 Outil et cibles

- `python -m openride_core.tools.rogue_sim --objective threshold --duration 45 --runs 200` : runs simulées en temps accéléré (sans trainer ni engine), rapport texte et JSON.
- Cibles de l'équilibrage (valeurs de départ, à confirmer par le propriétaire) :

| Mesure | Cible |
| --- | --- |
| Salles gagnées par le profil Moyen | 60 à 80 % |
| Défaites par run, profil Moyen | 0 à 1 en moyenne |
| Défaites par run, profil Débutant | au plus 2 (l'équité par la FTP doit tenir) |
| Écart de salles gagnées Débutant / Confirmé | dû au jeu (boutons, timing), pas à la FTP : moins de 25 points |
| Relances de cartes par run, profil Moyen | 1 à 2 |
| IF d'une run de 45 min | endurance 0,62 à 0,72 ; seuil 0,80 à 0,88 ; VO2max 0,80 à 0,90, avec au moins 8 min au-delà de 1,10 FTP |
| Boss battu, profil Moyen | 50 à 70 % des runs |

- Le rapport donne, pour chaque cible tenue ou non, la valeur mesurée et la ou les constantes qui la font bouger le plus (essai de ±20 % sur chaque constante).

## 5. Fichiers concernés

- **Créés :** `core/src/openride_core/rogue/balance.toml`, `core/src/openride_core/tools/rogue_sim.py`, `core/tests/test_rogue_balance.py`.
- **Modifiés :** `core/src/openride_core/rogue/balance.py` (chargement), `core/pyproject.toml` (données du paquet), `README.md` (une ligne), `docs/SUIVI_AVANCEMENT.md` (une ligne).

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `(cd core && pytest -q)` passe.
2. `balance.toml` chargé donne exactement les défauts de `RogueBalance` ; une surcharge locale change la valeur ; une clé inconnue est refusée avec un message lisible.
3. 200 runs simulées de 45 min en moins de 60 s sur le PC de l'IA (pas de 1 s).
4. Rapport produit pour les trois objectifs ; les cibles non tenues sont listées avec les constantes proposées.
5. Même graine, même rapport.

## 8. Hors périmètre

- Changer les règles (R5, R6) ; un écart de règle trouvé ici est signalé.
- Équilibrage des déblocages permanents (R9).

## 9. Livraison (27 octobre 2026)

- `rogue/balance.toml` (embarqué, déclaré dans les données du paquet) : les 126 champs de `RogueBalance` avec un commentaire en français, plus les tables `calendars`, `reservoirs` et `room_profiles`. `load_balance()` lit ce fichier puis la surcharge facultative `~/OpenRide/rogue_balance.toml` ; clé inconnue, type faux, liste de mauvaise longueur ou valeur hors bornes lèvent `BalanceError` avec la clé en cause. `DEFAULT_BALANCE` reste la référence : un test vérifie que le fichier embarqué lui est identique.
- Empreinte de la table (`balance_hash`, 8 caractères) notée dans la première ligne de journal de chaque run (`rogue balance hash=...`).
- `tools/rogue_sim.py` : quatre profils (Débutant, Moyen, Confirmé, Fatigué), rapport texte et JSON (`--json`), cibles du cahier, `--sensitivity` (±20 % sur chaque constante pour les cibles manquées), `--jobs`, `--balance`. Même graine, même rapport quel que soit `--jobs`. 200 runs de 45 min : 48 s sur un cœur.
- Pour tenir ce budget, `RunEngine` garde les salles générées pour les aperçus des portes au lieu de les recalculer au départ de la salle choisie (même graine, même salle).
- Résultats et valeurs proposées : `docs/2.0/RAPPORT_EQUILIBRAGE_R7.md`. Écart de règle signalé : les PV du boss ne dépendent d'aucune constante propre (R5/R6). Aucune valeur par défaut n'est changée ici.
- Tests : `core/tests/test_rogue_balance.py`.
