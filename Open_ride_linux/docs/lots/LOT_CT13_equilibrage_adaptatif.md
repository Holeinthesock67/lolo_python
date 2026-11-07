# Lot CT13 – Journal des courses, classement Elo et équilibrage adaptatif

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série CT : journal des courses tactiques, classement Elo et niveau des bots adaptatif | Python | CT0, CT3, MJ1 | Moyenne | Prêt (version 5.0, idées du propriétaire du 7 novembre) |

Série CT (version 5.0, mode « Course tactique »). Plan de la série : `docs/5.0/PLAN_SERIE_CT.md`. Idées du propriétaire du 7 novembre : « un log pour enregistrer les résultats et équilibrer automatiquement au cours des batteries, par rapport à la FTP et au nombre de victoires du joueur », puis « une sorte de classement Elo pour donner des points aux joueurs et aux bots et servir de base à l'équilibrage » (accord du 7 novembre sur les deux précautions du §4).

## 1. Objectif

Les valeurs de `tactical/balance.toml` ont été réglées en simulation (CT0). Ce lot s'occupe des vraies courses : il note le résultat de chaque course tactique et ajuste le niveau des bots du joueur pour que ses courses restent disputées. Le joueur ne doit gagner ni toujours, ni jamais.

## 2. À lire

1. `docs/5.0/RAPPORT_EQUILIBRAGE_CT0.md`, `core/src/openride_core/tools/tactical_sim.py` (calibrage, `shares`, `score`).
2. Code : `bots.py` (`calibrate_bots`, `level_pct`), `settings.py` (`bots.level_pct`), `profiles.py` (MJ1 : dossier du profil), `records.py`, `journal.py`.

## 3. Prérequis

CT0 fusionné ; CT3 (cerveau des bots) livré ; profils de joueur (MJ1).

## 4. Travail demandé

- **Journal des courses** `tactical_results.jsonl` dans le dossier du profil (une ligne par course terminée) : date, circuit, FTP et CP/W′ du moment, niveau des bots, Elo de chacun avant et après, rang, écart au vainqueur, profil du vainqueur, Burnouts, catapultes, capacités, empreinte de la table (`balance_hash`). Les séances simulées vont dans le profil d'essai (`_essai`, MJ2), jamais dans le vrai profil.
- **Classement Elo** (`tactical/elo.py` du lot CT0, sans copie) : chaque course compte comme des duels par paires entre tous les coureurs ; le joueur a son Elo dans son profil (départ 1 500), chaque bot a le sien, par profil et par niveau. K plus fort pendant les 10 premières courses du joueur (40), puis 24 : le classement converge vite sans sauter ensuite. Le bilan affiche l'Elo et son évolution (« Elo 1 532 (+14) », affichage par CT11).
- **Deux chiffres séparés** (précaution 1) : l'Elo mesure le joueur et n'est jamais corrigé par l'équilibrage ; le niveau des bots est choisi d'après lui. Si les bots s'adaptaient pour que le joueur gagne toujours autant, son Elo stagnerait et ne mesurerait plus rien.
- **La FTP règle la force, l'Elo règle la tactique** (précaution 2) : les bots restent calibrés sur la FTP du profil (comme aujourd'hui), donc une FTP plus haute après un test de rampe (O10) ne fait pas monter l'Elo à elle seule. L'Elo, lui, choisit le niveau tactique des bots : taux d'erreur (`bot_error_pct`), seuil pour suivre une attaque, agressivité des attaques, et un petit écart de niveau autour de `bots.level_pct` (± 5 % au plus).
- **Niveau adaptatif** : réglage « Niveau des bots : fixe / adaptatif » (défaut adaptatif dans la Course tactique seulement). Les adversaires sont choisis pour que la chance de victoire prévue par l'Elo soit d'environ une sur quatre ou cinq (20 à 30 %) ; changement entre deux courses seulement, jamais plus de 5 % de niveau d'une course à l'autre, pour que le joueur ne sente pas d'élastique.
- **Lot de courses** (« batterie ») : `tactical_sim --journal FICHIER` rejoue un journal (circuits, FTP, niveaux) avec le cycliste virtuel, pour vérifier que l'Elo et le niveau convergent en 10 à 15 courses et ne font pas de va-et-vient. Le rapport CT0 donne déjà l'Elo de chaque profil et de chaque stratégie : un profil équilibré reste près de 1 500.
- **Jamais sur la résistance** : seule la force des bots change ; la pente envoyée au trainer reste la même.

## 5. Fichiers concernés

- **Nouveaux :** `core/src/openride_core/tactical/adaptatif.py`, `core/tests/test_tactical_adaptatif.py`.
- **Modifiés :** `tools/tactical_sim.py`, `settings.py`, `config.py`, `tactical/balance.toml` (pas de hausse, de baisse, fenêtre, plafond par course), ce cahier, `SUIVI_AVANCEMENT.md`.
- **Interdits :** l'engine (le réglage passe par `settings`), `physics.py`.

## 6. Modifications de contrat autorisées

Aucune : le réglage passe par le message `settings` (révision 1.3). L'affichage du niveau dans le bilan relève de CT11.

## 7. Critères d'acceptation

1. `pytest -q` passe.
2. En rejouant 30 courses avec un cycliste virtuel plus habile (stratégie « mixte ») que la moyenne, son Elo monte, le niveau tactique des bots aussi, et ses victoires reviennent entre 20 et 30 % sur les 10 dernières.
3. Même chose avec un cycliste moins habile (« échappée ») : Elo et niveau baissent.
3 bis. Une FTP relevée de 10 % entre deux courses ne change pas l'Elo à elle seule (bots recalibrés sur la nouvelle FTP).
4. Le niveau ne bouge jamais de plus de 5 % d'une course à l'autre, ni en cours de course.
5. Le journal d'une séance simulée n'apparaît pas dans le vrai profil.

## 8. Hors périmètre

Classement en ligne entre joueurs ; ajustement des règles du mode (catapulte, crédits) selon le joueur : la table reste la même pour tous, seul le niveau des bots s'adapte.
