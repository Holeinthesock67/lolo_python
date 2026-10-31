# Lot MJ4 – Configuration à deux couches (machine et joueur)

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série MJ : configuration à deux couches `config.toml` + `profil.toml`, portée de chaque réglage | Python | MJ1 | Moyenne | **Livré le 30 octobre** (branche `claude/project-thread-grv91v-mj4b`) |

Série MJ, plan `docs/2.0/PLAN_SERIE_MJ.md` §2.2 et §10 (réponse 1).

## 1. Objectif

Les réglages du joueur (FTP, poids, FC max, poids du vélo, difficulté, braquet de départ, bonus, niveau des bots, vent, vue de caméra, courbes, ceinture cardio) vivent dans `Profils/<id>/profil.toml` ; ceux de la machine restent dans `config.toml`.

## 2. À lire

Plan §2.2 ; code `config.py`, `config_edit.py`, `settings.py`, `profiles.py`.

## 3. Prérequis

MJ1 (et MJ2 pour le format de `profil.toml`).

## 4. Travail demandé

- Configuration effective = défauts ← `config.toml` ← `profil.toml`, par le même `config.load()` (mêmes bornes, mêmes messages).
- Table unique `PROFILE_KEYS` dans `config.py` (pas de suite de `if`) ; FC max (PR #561) comprise.
- Chaque réglage du menu porte sa portée dans `settings.py` (`scope = "profil"` ou `"machine"`) ; `set_setting` et `openride-core settings set` écrivent dans le bon fichier avec `config_edit` (commentaires gardés, `.bak`).
- Une clé joueur encore présente dans `config.toml` reste lue ; le profil l'emporte.

## 5. Fichiers concernés

`config.py`, `settings.py`, `config_edit.py`, `profiles.py`, tests ; interdits : l'engine, le contrat.

## 6. Modifications de contrat autorisées

Aucune : l'engine ne voit pas la répartition.

## 7. Critères d'acceptation

1. FTP réglée au menu sur un profil : écrite dans son `profil.toml`, `config.toml` inchangé ; l'autre profil garde sa FTP.
2. Qualité graphique réglée : `config.toml` seul.
3. Matrice X42 et persistance X37 vertes ; `(cd core && pytest -q)` passe.

## 8. Hors périmètre

Migration des clés existantes (MJ5).

## Livraison

Livré le 30 octobre 2026 (branche `claude/project-thread-grv91v-mj4b`, PR #614).

- `config.py` : table `PROFILE_KEYS` (FTP, poids, FC max, poids du vélo, difficulté, braquet de départ, bonus, niveau des bots, vent, vue de caméra, courbes, ceinture cardio), `profile_overlay` (clés machine de `profil.toml` signalées et ignorées, section `[profil]` laissée à `profiles.py`), `from_layers`, `load(path, profile_path)` : `profil.toml` du profil en cours par défaut, aucun en contexte historique ; mêmes bornes et messages, le message cite les deux fichiers.
- `config_edit.update_layers` : chaque clé dans son fichier, configuration effective validée avant toute écriture, copie `.bak` et remplacement atomique de chaque fichier changé.
- `settings.py` : `Setting.scope` (« profil » ou « machine », tiré de `PROFILE_KEYS`), `apply` passe par `update_layers` ; même chemin pour `set_setting`, `openride-core settings set`, la FTP d'un test (`ftp_test.py`) et la ceinture appairée (`pairing.save`).
- Tests : `core/tests/test_config_couches.py` (FTP d'un profil sans toucher `config.toml` ni l'autre profil, qualité dans `config.toml` seul, contexte historique inchangé, clé joueur restée dans `config.toml` lue et dominée par le profil, clé machine ignorée dans `profil.toml`, valeur refusée sans écriture, ceinture appairée dans le profil).
