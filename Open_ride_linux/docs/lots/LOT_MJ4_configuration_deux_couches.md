# Lot MJ4 – Configuration à deux couches (machine et joueur)

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
