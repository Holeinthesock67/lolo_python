# Lot J9 – Installeur en un seul fichier

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Installation simple sur Linux : un seul fichier exécutable si possible, sinon une archive et une notice courte ; en tout dernier | Bash + Python | J4, O37 | Moyenne | Prêt (version 5.0, dernier lot du projet) |

Demande du propriétaire du 31 octobre 2026 : en fin de projet, prévoir un moyen simple d'installer le jeu sur Linux, idéalement un seul exécutable, et une notice si ce n'est pas un fichier unique. Le 5 novembre : les mondes demo (O37) passent avant. Cahier rédigé le 8 novembre (aucun n'existait).

## 1. Objectif

Installer OpenRide sur un PC Linux neuf sans cloner le dépôt ni taper plus d'une commande.

## 2. À lire

`scripts/install.sh` (lot N14 : venv, liens `openride` et `openride-core`, `config.toml`, Godot 4.7, entrées de bureau) ; `scripts/install-desktop.sh`, `scripts/update.sh`, `scripts/recette_install.py` ; `docs/lots/LOT_J4_paquetage_autonome.md` (ressources embarquées, prérequis) ; `docs/GUIDE_UTILISATION.md`.

## 3. Travail demandé

- **Étude courte** (une page, choix du propriétaire avant le code) : AppImage contenant Python, le core, le compilateur, l'engine exporté et Godot, contre archive `.tar.gz` plus `install.sh`. Critères : taille, mise à jour, droits Bluetooth (BlueZ, groupe), dépendances système.
- **Engine exporté** (modèle d'export Godot Linux) au lieu de Godot installé à part.
- **Paquet :** core et compilateur avec leurs ressources embarquées (J4) ; mondes demo d'O37 ; aucun fichier personnel (règle de confidentialité, invariant A8).
- **Premier lancement :** création de `~/OpenRide/` et des contenus de départ (O25), message d'aide si le Bluetooth manque.
- **Mise à jour** par le même fichier ; désinstallation documentée.
- **Notice** `docs/INSTALLATION.md` si le choix n'est pas un fichier unique.

## 4. Critères d'acceptation

1. `recette_install.py` vert sur une machine propre (conteneur ou utilisateur neuf).
2. Installation, appairage et une séance de 10 min sur le PC cible, lancées depuis l'icône, sans terminal.
3. Aucune donnée personnelle dans le paquet (`scripts/privacy`).

## 5. Fichiers touchés

`scripts/`, fichier d'export de l'engine, `docs/INSTALLATION.md`, `docs/GUIDE_UTILISATION.md`, `README.md`.
