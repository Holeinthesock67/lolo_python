# Lot MJ5 – Migration du profil actuel

Série MJ, plan `docs/2.0/PLAN_SERIE_MJ.md` §5 et §10 (réponse 4).

## 1. Objectif

Au premier lancement de la version avec profils, le joueur actuel devient `Profils/principal/` sans rien perdre ; les séances simulées et rejouées partent dans `_essai`.

## 2. À lire

Plan §5 ; lots X39 (`xp --compare`), MJ1, MJ2, MJ4 ; code `records.py` (recalcul depuis les journaux).

## 3. Prérequis

MJ2, MJ4.

## 4. Travail demandé

1. Sauvegarde `~/OpenRide/Sauvegardes/avant_profils_AAAAMMJJ.tar.gz` (`config.toml`, `profile.json`, `records.json`, `plan_state.toml`, `Activities/`).
2. `Profils/principal/profil.toml` reçoit les clés joueur de `config.toml` ; nom « Cycliste 1 ».
3. Déplacement (`os.replace`) de `profile.json`, `plan_state.toml` ; chaque séance selon la `source` de son journal : `live` et FIT sans journal → `principal`, `simulated` et `replay` → `_essai` ; `records.json` de `principal` recalculé depuis ses journaux réels ; caches invalidés.
4. Clés passées au profil retirées de `config.toml` par `config_edit` (commentaire indiquant où elles sont).
5. Contrôle `xp --save` / `--compare` : toute différence annule la migration et remet les fichiers.
6. Étapes notées dans `Profils/.migration` : reprise sûre après une coupure.

## 5. Fichiers concernés

Nouveau `core/src/openride_core/migration_profils.py`, `launcher.py` (appel au démarrage), tests ; interdits : l'engine, le contrat.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. Dossier factice avec séances `live`, `simulated`, `replay` et FIT sans journal : rangement attendu, progression de `principal` identique (X39).
2. Coupure simulée à chaque étape : la reprise aboutit au même résultat.
3. Seconde exécution : rien ne change.

**Sur le PC (propriétaire, via la file des mesures PC) :** migration réelle dans MJ10, sauvegarde d'abord.

## 8. Hors périmètre

Retour à une version antérieure (la sauvegarde le permet à la main).
