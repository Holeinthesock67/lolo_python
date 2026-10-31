# Lot L8 – Raccourci de bureau : fichier `.desktop`, icône et installation

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Raccourci de bureau : fichier `.desktop`, icône, script d'installation | Bash | — | Petite | **Livré le 24 octobre** (PR #71, issue #60) |

## 1. Objectif

Le lanceur unique `openride` (lot K6) existe, mais il se lance encore depuis un terminal : il manque l'icône et le fichier `.desktop` prévus par le SRS et notés « à faire » dans le suivi. Ce lot ajoute un script d'installation pour l'utilisateur (sans `sudo`), testé sans bureau.

## 2. À lire

1. `docs/lots/00_INDEX.md`, `docs/lots/LOT_K6_lanceur_unique.md` (livraison).
2. `docs/SRS_v1.1.md` §11 (arborescence), `docs/SUIVI_AVANCEMENT.md` (ligne du lanceur unique, « icône et fichier `.desktop` »).
3. Code : `core/src/openride_core/launcher.py`, `core/pyproject.toml` (point d'entrée `openride`), `scripts/openride-dev.sh`.
4. Référence externe : spécification freedesktop « Desktop Entry » (clés `Type`, `Name`, `Exec`, `Icon`, `Terminal`, `Categories`, `StartupWMClass`).

## 3. Prérequis

Aucun (K6 est livré).

## 4. Travail demandé

- `scripts/desktop/openride.desktop.in` : modèle avec `Name=OpenRide`, `Comment` en français, `Exec=@OPENRIDE@`, `Icon=openride`, `Terminal=false`, `Categories=Game;Sports;`, `StartupWMClass` égal au nom de fenêtre de Godot pour le projet (à vérifier dans `engine/project.godot` et à écrire dans le rapport).
- `scripts/desktop/openride.svg` : icône simple (roue de vélo stylisée, deux couleurs), SVG valide écrit à la main, moins de 8 Ko.
- `scripts/install-desktop.sh [--uninstall] [--prefix DOSSIER]` (défaut `~/.local/share`) :
  - trouve la commande `openride` (`command -v`, sinon `~/.local/bin/openride`, sinon message clair et code 1) et écrit son chemin absolu dans `Exec` ;
  - copie le `.desktop` dans `applications/` et l'icône dans `icons/hicolor/scalable/apps/` ;
  - lance `update-desktop-database` et `gtk-update-icon-cache` s'ils existent, sans échouer s'ils manquent ;
  - `--uninstall` retire exactement ce qui a été installé ; deux installations de suite donnent le même résultat.
- `Terminal=false` : les messages du lanceur doivent rester lisibles ; le rapport indique où ils vont (journal du core déjà écrit dans `~/run_trainer.log` ou équivalent, à vérifier dans `launcher.py`).

## 5. Fichiers concernés

- **Nouveaux :** `scripts/desktop/openride.desktop.in`, `scripts/desktop/openride.svg`, `scripts/install-desktop.sh`, `core/tests/test_desktop_entry.py`.
- **Modifiés :** `README.md` (section installation), `docs/SUIVI_AVANCEMENT.md` (ligne du lanceur).
- **Interdits :** `launcher.py` (un défaut trouvé est signalé, pas corrigé ici), fichiers hors de `Open_ride_linux/`.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `pytest -q` passe en entier dans `core/`.
2. Test : le modèle se lit par `configparser` (section `[Desktop Entry]`, clés obligatoires présentes, `Terminal=false`).
3. Test : `install-desktop.sh --prefix <tmp>` avec une fausse commande `openride` dans le `PATH` crée les deux fichiers, `Exec` est le chemin absolu de la fausse commande ; `--uninstall` laisse `<tmp>` sans fichier OpenRide ; sans `openride` dans le `PATH` ni `~/.local/bin`, code 1 et message en français.
4. Si `desktop-file-validate` est installé, il ne signale aucune erreur sur le fichier produit (test sauté proprement sinon) ; l'icône est un XML valide (`xml.etree`).
5. `shellcheck` sans avertissement sur `install-desktop.sh` s'il est installé (test sauté sinon).

## 8. Hors périmètre

- Paquet `.deb`, Flatpak ou AppImage.
- Démarrage automatique à l'ouverture de session.

## 9. Livraison (24 octobre 2026, PR #71)

- `scripts/desktop/openride.desktop.in` : modèle `.desktop` avec `StartupWMClass=OpenRide Engine` et `Terminal=false`.
- `scripts/desktop/openride.svg` : icône vectorielle deux couleurs < 8 Ko.
- `scripts/install-desktop.sh` : script d'installation utilisateur idempotent (`--uninstall`, `--prefix`).
- `core/tests/test_desktop_entry.py` : 4 tests de validation.
- Intégration continue GitHub Actions verte.
