# Lot N10 – Packs de thèmes : liste et installation (`theme-list`, `theme-install`)

## 1. Objectif

Les thèmes sont des dossiers `~/OpenRide/Themes/<nom>/` (SRS §10) que l'on crée aujourd'hui à la main, puis qu'on vérifie par `openride-compiler theme-check`. Ce lot ajoute de quoi lister les thèmes installés et installer un pack de textures depuis un dossier ou une archive `.zip`, avec contrôle complet avant copie. C'est la partie outillage de l'item « Thèmes avec packs de textures » du suivi.

## 2. À lire

1. `docs/lots/00_INDEX.md`, `docs/SRS_v1.1.md` §10 et §11 (arborescence), `docs/contracts/world_format_v1.md` (section Thèmes), `docs/contracts/world/theme.schema.json`.
2. `docs/lots/LOT_H7_schema_themes.md`, `docs/ESSAI_GRAPHIQUE_E2.md` (thème d'essai `essai_textures`).
3. Code : `compiler/src/openride_compiler/theme.py` (`check_theme`, `read_image_dimensions`), `compiler/src/openride_compiler/cli.py`, `engine/tests/make_texture_theme.py` (exemple de pack), `engine/scripts/theme_loader.gd` (lecture seule : où l'engine cherche les thèmes).

## 3. Prérequis

Lot M7 (PR #95) fusionné le 24 octobre : partir de `main` à jour (il a modifié `cli.py`). Indépendant d'E3/E4 et de l'engine.

## 4. Travail demandé

- `openride-compiler theme-list [--themes-dir D] [--json]` : une ligne par thème : nom, état (`ok`, `avertissements`, `erreurs` d'après `check_theme`), textures présentes, taille totale ; le thème intégré `default` est toujours listé (« intégré »). Le thème choisi dans `config.toml` (`[render] theme`) est marqué.
- `openride-compiler theme-install SOURCE [--name NOM] [--force] [--themes-dir D]` :
  - `SOURCE` : dossier ou `.zip` (bibliothèque standard `zipfile`) ; archive à un seul dossier racine acceptée ;
  - refus des chemins absolus ou contenant `..` dans l'archive, des liens symboliques, et d'une archive de plus de 500 Mo décompressée ;
  - `check_theme` sur une copie temporaire **avant** l'installation : erreurs, refus ; avertissements affichés ;
  - nom tiré de `theme.json` (`name`) ou du dossier, normalisé (`a-z0-9-`) ; thème existant : refus sans `--force` ; installation atomique (dossier temporaire puis renommage) ;
  - en fin de sortie, la ligne à mettre dans `config.toml` (`theme = "NOM"`), sans l'écrire.
- Aucun réseau.

## 5. Fichiers concernés

- **Nouveaux :** `compiler/src/openride_compiler/theme_packs.py`, `compiler/tests/test_theme_packs.py`.
- **Modifiés :** `compiler/src/openride_compiler/cli.py` (deux sous-commandes), `README.md` et `CLAUDE.md` (commandes citées), `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Interdits :** `theme.py` (lecture seule), `theme.schema.json`, l'engine.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `pytest -q` passe en entier dans `compiler/` et dans `core/` (cohérence des commandes citées).
2. Pack produit par `engine/tests/make_texture_theme.py`, zippé : installé, puis listé `ok`.
3. Archive avec `../evil.txt`, avec un lien symbolique, ou dépassant la taille : refus, rien écrit dans le dossier des thèmes.
4. Pack dont `theme.json` est invalide : refus avec l'erreur de `check_theme`, rien écrit.
5. Réinstallation sans `--force` : refus ; avec `--force` : remplacé ; une installation interrompue (exception simulée) ne laisse ni dossier partiel ni ancien thème cassé.
6. `theme-list --json` : sortie validée par un schéma écrit dans le test.

**Sur le PC cible (le propriétaire) :** installer un vrai pack de textures et l'essayer avec `GODOT_ARGS` selon `docs/ESSAI_GRAPHIQUE_E2.md`.

## 8. Hors périmètre

- Choix du thème depuis le menu de l'engine.
- Téléchargement de packs en ligne.

## 9. Livraison (25 octobre 2026, PR #164)

- Code et tests fusionnés sur `main` par la PR #164 (issue #107 fermée) ; détail dans la description de la PR et dans `docs/SUIVI_AVANCEMENT.md`.
