# Lot M9 – Petite dette des vérifications du 24 octobre (R3 et S2)

## 1. Objectif

La vérification du 24 octobre (`docs/VERIFICATION_2026-10-24.md`) a laissé deux constats ouverts « à traiter au fil de l'eau ». Aucun ne touche une séance aujourd'hui, mais chacun peut piéger un futur appelant ou une installation. Ce lot les ferme, avec un test chacun.

## 2. À lire

1. `docs/lots/00_INDEX.md`, `docs/VERIFICATION_2026-10-24.md` §4 (S2), §5 (R3) et §7 (suivi), `docs/REVUE_CODE_2026-10-24.md` (tableau de suivi).
2. Code : `core/src/openride_core/workout.py` (`ErgController.__init__`, `step`), `compiler/pyproject.toml` (extra `dev`), `CLAUDE.md` (installation des environnements de test).

## 3. Prérequis

Aucun. M4 lit `workout.py` sans le modifier ; M7 modifie `compiler/pyproject.toml` (section `dependencies`, pas l'extra `dev`) : fusionner l'un après l'autre.

## 4. Travail demandé

- **R3.** `ErgController.step(dt)` : un `dt` négatif, infini ou NaN lève `ValueError` (message en français) ; `dt == 0` reste accepté. Le constructeur refuse une FTP ≤ 0 ou non finie (`ValueError`). Vérifier que la session ne peut pas produire ces valeurs (horloge monotone, FTP bornée par la configuration) et le noter dans une docstring.
- **S2.** `pip install -e "compiler[dev]"` seul doit donner une suite de tests du compilateur qui passe ou qui saute proprement :
  - soit l'extra `dev` du compilateur déclare `openride-core` par chemin local, si `pip` et la CI l'acceptent sans réseau supplémentaire ;
  - soit les tests du compilateur qui importent `openride_core` utilisent `pytest.importorskip("openride_core")` avec une raison claire, et un test vérifie que la CI les exécute bien (variable d'environnement `CI` : un saut y est une erreur).
  - Le rapport dit laquelle des deux voies a été choisie et pourquoi.
- Mettre à jour le suivi des constats : R3 et S2 « Corrigés (lot M9) ».

## 5. Fichiers concernés

- **Modifiés :** `core/src/openride_core/workout.py`, `core/tests/test_workout.py`, `compiler/pyproject.toml` (extra `dev`) ou les tests du compilateur qui importent `openride_core`, `CLAUDE.md` (si l'installation change), `docs/VERIFICATION_2026-10-24.md` et `docs/REVUE_CODE_2026-10-24.md` (lignes de suivi), `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Interdits :** `session.py`, `.github/workflows/` (lot J5 ouvert).

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `pytest -q` passe en entier dans `core/` et `compiler/`.
2. `ErgController(w, 200).step(-10)`, `step(float("nan"))` et `ErgController(w, 0)` lèvent `ValueError` ; les tests ERG existants passent sans modification.
3. Dans un environnement neuf avec seulement `pip install -e "compiler[dev]"` (vérifié dans le rapport, commande et sortie à l'appui) : aucune erreur d'import à la collecte.
4. Avec les deux paquets installés (cas de la CI), aucun test du compilateur n'est sauté.

## 8. Hors périmètre

- C5 (dossier de l'engine déduit de l'emplacement du paquet) : lot J4, issue #50.
- R4 (pente NaN) : déjà corrigé par la PR #62.
