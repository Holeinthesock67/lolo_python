# Lot MJ3 – Campagne simulée accélérée sur le profil d'essai

Série MJ, plan `docs/2.0/PLAN_SERIE_MJ.md` §4.3 et §4.4.

## 1. Objectif

Vérifier sans vélo ni PC, en quelques secondes, que l'expérience, les niveaux, les défis, les pièces, les achats et l'équipement marchent de bout en bout dans la vraie séance du core, sur le profil d'essai, et que le vrai profil n'a pas changé d'un octet.

## 2. À lire

1. `docs/2.0/PLAN_SERIE_MJ.md` §4.3, §4.4 ; `docs/lots/LOT_X40_rogue_bout_en_bout.md`.
2. Code : `tools/rogue_bout_en_bout.py` (modèle), `session.py`, `garage.py`, `coins.py`, `progression.py`, `profiles.py`.

## 3. Prérequis

MJ2.

## 4. Travail demandé

- **Outil `python -m openride_core.tools.campagne_profil [--seances N] [--graine G] [--json] [--home DOSSIER]`** : la vraie `CoreSession` tourne sans engine ni réseau au pas d'une seconde (simulateur de trainer), sur `_essai`, dans un HOME temporaire par défaut. Programme : sessions libres plates et vallonnées, une séance ERG terminée et une abandonnée, une séance trop courte, une run Cyber-Rogue ; entre les séances, commandes du Garage (`list_garage`, `buy` refusé faute de pièces, puis accepté, `equip`, `set_avatar`) ; arrêt et relance du core au milieu.
- **Contrôles** : expérience de chaque `xp_result` = recalcul de `openride-core xp` ; niveau cohérent avec le seuil ; défis débloqués une seule fois ; solde = gagnées − dépensées ; achat présent dans `profile.json` et appliqué à la physique (`loadout` de l'en-tête du journal) ; séance trop courte sans gain ; profil et solde identiques après relance ; **empreinte SHA-256** de `Profils/principal/` (ou du contexte historique) et de `config.toml` identique avant et après.
- **Garde-fou pytest** : la campagne courte tourne dans la suite ; un test d'isolation vérifie qu'une séance d'essai n'écrit rien hors de `Profils/_essai/` (hors `Logs/`).
- Sortie lisible et `--json`, code 0 ou 1, entrée dans `docs/OUTILS_DE_TEST.md`.

## 5. Fichiers concernés

- **Créés :** `core/src/openride_core/tools/campagne_profil.py`, `core/tests/test_campagne_profil.py`.
- **Modifiés :** `docs/OUTILS_DE_TEST.md`, suivi et index.
- **Interdits :** l'engine, le contrat IPC.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `python -m openride_core.tools.campagne_profil --seances 8` : code 0 en moins d'une minute dans le cloud, tous les contrôles verts.
2. Un défaut injecté dans le test (achat non débité, journal d'essai écrit dans le vrai profil) fait échouer la campagne.
3. `(cd core && pytest -q)` passe en entier.

## 8. Hors périmètre

Passage de la recette V10 sur `_essai` (MJ9).
