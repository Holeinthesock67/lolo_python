# Lot N11 – Compilation des nouvelles traces GPX au lancement d'OpenRide

## 1. Objectif

Déposer un GPX dans `~/OpenRide/GPX/` puis cliquer sur l'icône doit suffire pour rouler dessus. Aujourd'hui il faut lancer `openride-compiler build-all` dans un terminal. Ce lot fait compiler par le lanceur `openride` les traces nouvelles ou modifiées avant de démarrer la séance, avec un retour visible sans terminal et sans bloquer indéfiniment. C'est la réponse proposée (lot N1 §4.6, question 3) à la « compilation d'un GPX depuis le menu », reportée.

## 2. À lire

1. `docs/lots/00_INDEX.md`, `docs/SRS_v1.1.md` §7 (compilateur, « à compiler ») et §11 (arborescence).
2. `docs/lots/LOT_I2_catalogue_parcours.md` (`list`, `build-all`), `docs/lots/LOT_K6_lanceur_unique.md`, `docs/lots/LOT_M8_journal_lanceur.md`, `docs/lots/LOT_L8_raccourci_bureau.md`.
3. Code : `core/src/openride_core/launcher.py`, `core/src/openride_core/catalog.py` (statuts `to_compile`, `outdated`), `compiler/src/openride_compiler/cli.py` (`build-all`, `--dry-run`).

## 3. Prérequis

Lot M8 (PR #96) fusionné : il modifie `launcher.py` et crée le journal du lanceur. Indépendant d'E3/E4 et de l'engine.

## 4. Travail demandé

- Au lancement, avant le core : `catalog.list_routes()` ; s'il y a des traces `to_compile` ou `outdated`, appel de `openride-compiler build-all` (sous-processus, sortie dans le journal du lanceur).
- Délai maximal configurable (`--compile-timeout`, défaut 300 s) ; au-delà, compilation arrêtée proprement, OpenRide démarre avec les parcours déjà prêts.
- Retour visible sans terminal : `notify-send` s'il existe (« Compilation de 2 traces… », puis « 2 parcours prêts » ou « 1 trace en erreur, voir le journal »), sinon journal seul. Fonction de notification injectable pour les tests.
- Compilateur absent (paquet non installé) : message clair, démarrage normal.
- `--no-compile` pour sauter l'étape ; `--compile-only` pour compiler puis quitter.
- Le réseau est autorisé (tuiles d'altitude, OSM, comme `build-all`) ; sans réseau, une trace en échec n'empêche pas de démarrer.

## 5. Fichiers concernés

- **Modifiés :** `core/src/openride_core/launcher.py`, `core/tests/test_launcher.py`, `README.md` et `CLAUDE.md` (options citées), `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Nouveaux :** `core/src/openride_core/launch_compile.py` (au choix, si `launcher.py` grossit trop), `core/tests/test_launch_compile.py`.
- **Interdits :** le compilateur (on l'appelle, on ne le modifie pas), `catalog.py` (lecture seule), l'engine.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `pytest -q` passe en entier dans `core/` et dans `compiler/`.
2. Dossier GPX temporaire avec 2 traces nouvelles et 1 déjà compilée : `build-all` appelé une fois, deux notifications (début, fin), core démarré ensuite.
3. Aucune trace à compiler : ni appel au compilateur ni notification.
4. Compilateur simulé qui ne rend pas la main : arrêt au bout du délai (réduit à 2 s dans le test), démarrage du core quand même, ligne d'alerte dans le journal.
5. Compilateur absent : message clair, core démarré.
6. `--no-compile` et `--compile-only` se comportent comme décrit.

**Sur le PC cible (Laurent) :** déposer un GPX, cliquer sur l'icône, vérifier la notification et rouler sur le parcours.

## 8. Hors périmètre

- Compilation depuis le menu de l'engine (commande IPC, reportée).
- Surveillance du dossier pendant que l'application tourne.
