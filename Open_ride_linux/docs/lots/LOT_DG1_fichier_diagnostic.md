# Lot DG1 – Fichier de diagnostic sans donnée privée

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| « Réglages › Diagnostic » : un fichier `.zip` à joindre à un signalement, sans donnée privée, rien n'est envoyé | Python, GDScript | — | Petite | **Livré le 26 novembre** (PR #1004) |

## 1. Objectif

Recommandation M14 de l'audit du 22 novembre (`statut/AUDIT_COHERENCE_QUALITE_2026-11-22.md`), lancée par le propriétaire le 22 novembre (« Étalonnage et diagnostic »). Après l'installateur J9, le jeu ne se lance plus depuis le dépôt : il faut un geste simple pour réunir de quoi comprendre un problème.

## 2. Travail fait

- **Core** (`diagnostic.py`) : archive `openride_diagnostic_AAAA-MM-JJ_HH-MM-SS.zip` avec `LISEZMOI.txt`, `diagnostic.json` (versions du core, de l'engine, de Python, du système et de bleak, carte graphique, qualité, état de la séance, état des capteurs sans nom ni adresse, réglages effectifs) et `journaux/` (deux derniers journaux du lanceur : avertissements et erreurs, puis les dernières lignes).
- **Masquage** (`Masker`), appliqué à tout le texte avant l'écriture : compte, nom complet et machine ; noms et identifiants des profils ; noms et adresses des appareils de la configuration ; toute adresse Bluetooth (même repère `<appareil-N>` pour une même adresse, aussi sous la forme `dev_AA_BB_…` de BlueZ) et tout UUID hors norme Bluetooth ; numéro de série, modèle, fabricant ; poids, FTP et puissance critique ; positions GPS ; réseaux Wi-Fi ; adresses IP ; courriels ; dossier personnel écrit `~`. Section `[rider]` entièrement masquée.
- **Dossier choisi** : Téléchargements, Bureau (suivant `~/.config/user-dirs.dirs`, noms français ou anglais) ou `~/OpenRide/Diagnostics/`. Rien n'est envoyé.
- **Contrat IPC révision 1.37** (numéro pris à la fusion) : commande `create_diagnostic`, message `diagnostic` (`docs/contracts/ipc/diagnostic.schema.json`). Écriture hors de la boucle à 50 Hz.
- **Ligne de commande** : `openride-core diagnostic [--dest telechargements|bureau|openride]`.
- **Engine** (`diagnostic_view_model.gd`, `menu_flow.gd`) : ligne « Diagnostic : créer un fichier pour signaler un problème » dans « Réglages », écran à trois lignes « Enregistrer dans… », carte en mots (objectif, contenu, masqué, rien n'est envoyé, bouton), chemin et taille du fichier sur la ligne d'état.

## 3. Tests

- `core/tests/test_diagnostic.py` : archive écrite avec des valeurs privées fictives dans la configuration, les appareils, les profils et le journal ; aucune n'en ressort, ce qui sert au diagnostic reste lisible ; dossiers choisis ; commande IPC et schéma.
- `engine/tests/unit/test_diagnostic_view_model.gd` : modèle et déroulé du menu.
- Banc des menus, scénario `diagnostic` : captures low, medium et high.

## Livraison

Branche `claude/project-thread-4vofwp`. PR de menus : banc PC medium seul suffit (captures low/medium/high faites dans le cloud).
