# Lot J3 – Configuration validée et erreurs lisibles

## 1. Objectif

`config.py` convertit chaque valeur de `~/OpenRide/config.toml` vers le type par défaut, sans contrôle (audit J, constat J-F1) :
- `ftp_w = "abc"` ou une erreur de syntaxe TOML donnent une trace Python au démarrage du core ;
- des valeurs absurdes passent sans avertissement (`start_gear = 40` pour 24 vitesses, `ftp_w = 0`, `drivers.trainer = "ftmss"`, port hors de 1 à 65 535) ;
- une clé inconnue (faute de frappe : `ftp = 260`) est ignorée sans le dire ;
- `openride-core run --gear 0` est ignoré en silence (`if args.gear:`).

Ce lot rend la lecture stricte sur les types et les bornes, et tolérante sur l'absence de clés.

## 2. À lire

1. `docs/lots/00_INDEX.md`.
2. `docs/SRS_v1.1.md` §11 (exemple de `config.toml`, valeurs par défaut).
3. Code : `core/src/openride_core/config.py`, `core/src/openride_core/__main__.py`, `core/src/openride_core/gearing.py` ; tests `core/tests/test_gearing_config.py`, `core/tests/test_docs_coherence.py` (contrôle 1, SRS §11).

## 3. Prérequis

**Après J1** (les deux lots modifient `__main__.py`). Partir de `main` à jour, J1 fusionné.

## 4. Travail demandé

- `ConfigError(Exception)` dans `config.py`, avec un message en français qui cite le fichier, la section et la clé (« config.toml, [rider] ftp_w : nombre attendu, reçu "abc" »).
- `load()` lève `ConfigError` pour : TOML invalide (avec la ligne), type incompatible, valeur hors bornes. Bornes minimales à appliquer (les documenter dans `config.py`) :
  - `rider.ftp_w` de 50 à 600 ; masses de 20 à 200 kg (cycliste) et de 3 à 30 kg (vélo) ;
  - `gearing.start_gear` de 1 à `n_gears` ; `n_gears` de 2 à 40 ; `ratio_min` < `ratio_max` ;
  - `trainer.difficulty_pct` de 0 à 100 ; `grade_min_pct` < `grade_max_pct` ;
  - `ipc.port_state` et `ipc.port_commands` de 1 024 à 65 535 et différents ;
  - `drivers.trainer` dans {`mock`, `ftms`}, `drivers.input` dans {`click`, `keyboard`, `none`}, `render.quality` dans {`low`, `medium`, `high`} ;
  - un booléen TOML n'est pas accepté pour un nombre.
- Clé ou section inconnue : avertissement au journal (`log.warning`), pas d'erreur.
- `openride-core run` : une `ConfigError` affiche le message sur la sortie d'erreur et renvoie 1, sans trace. `--gear 0` ou `--gear 99` : erreur `argparse` (code 2).
- `from_dict` garde son comportement pour les tests existants (valeurs valides).

## 5. Fichiers concernés

- **Nouveau :** `core/tests/test_config_validation.py`.
- **Modifiés :** `core/src/openride_core/config.py`, `core/src/openride_core/__main__.py`, `docs/SUIVI_AVANCEMENT.md` (une ligne). `docs/SRS_v1.1.md` §11 seulement pour y ajouter une phrase sur les bornes (pas de changement de valeur par défaut).

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `cd core && pytest -q` passe en entier, `test_docs_coherence.py` compris.
2. Tests paramétrés : chaque borne du §4 a un cas juste en dessous et un cas juste au-dessus ; chaque cas invalide lève `ConfigError` dont le message contient la section et la clé.
3. TOML invalide : le message contient le numéro de ligne.
4. Clé inconnue : `caplog` contient un avertissement qui la nomme ; la configuration est chargée.
5. `main(["run", "--config", <fichier invalide>, ...])` renvoie 1 sans exception (capturer `stderr`).
6. Le `config.toml` d'exemple de la SRS §11 se charge sans erreur ni avertissement.

## 8. Hors périmètre

- Écriture ou migration automatique de `config.toml`.
- Menu de réglages (lot G).

## 9. Livraison (23 octobre 2026, fait directement à la demande du propriétaire, sans sous-traitance)

- `config.py` : `ConfigError`, conversion stricte des types (un booléen n'est jamais un nombre ; un entier écrit `20.0` est accepté), bornes `BOUNDS` et choix `CHOICES` documentés dans le code, cohérences (`start_gear` ≤ `n_gears`, `ratio_min` < `ratio_max`, `grade_min_pct` < `grade_max_pct`, ports différents), avertissement pour une clé ou une section inconnue, TOML invalide signalé avec sa ligne.
- `__main__.py` : configuration invalide → message sur la sortie d'erreur et code 1 ; `--gear` hors de 1 à `n_gears` → code 2 (contrôle fait après la lecture de la configuration, car `n_gears` en dépend). `tools/workouts.py check` : message et code 1 au lieu d'une trace.
- Tests : `core/tests/test_config_validation.py` (bornes paramétrées, choix, types, ligne TOML, clé inconnue, exemple de la SRS §11 sans avertissement, codes de sortie).
- Bornes ajoutées au-delà du cahier : `bike.cda_m2`, `bike.crr`, `drivetrain_efficiency`, constantes de temps du trainer, `g_base_pct`, `long_press_gears` et seuils du Click.
