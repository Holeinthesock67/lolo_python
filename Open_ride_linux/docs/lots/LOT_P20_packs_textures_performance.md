# Lot P20 – Packs de textures selon les performances (version 2.0)

## 1. Objectif

**Version 2.0** (demande du propriétaire, 25 octobre). Un thème peut aujourd'hui fournir des textures (lot N10 pour l'installer), mais il n'en a qu'une taille, quelle que soit la carte graphique. Ce lot permet à un pack de thème de fournir **plusieurs niveaux de textures** (par exemple 512, 1 024 et 2 048 px) et à OpenRide de choisir le bon niveau selon le préréglage de qualité et la mémoire vidéo disponible, pour garder 55 images/s ou plus sur la GTX 1060. Le choix est automatique et peut être imposé dans les réglages.

## 2. À lire

1. `docs/lots/00_INDEX.md` (paragraphe « Série P », budget de rendu), `docs/lots/LOT_N10_packs_themes.md`, `docs/lots/LOT_H7_schema_themes.md`, `docs/lots/LOT_L4_prereglages_qualite.md`, `docs/lots/LOT_O3_reglages_core.md`, `docs/contracts/world_format_v1.md` §9.
2. Code : `engine/scripts/theme_loader.gd` (repli sur la couleur unie), `engine/scripts/terrain_material.gd`, `engine/scripts/quality_presets.gd`, `engine/scripts/render_quality.gd`, `compiler/src/openride_compiler/theme.py`.

## 3. Prérequis

N10, O3 et P17 livrés. À faire pour la version 2.0, pas avant ; à réviser avec la série U de la 3.0 (`docs/3.0/PLAN_SERIE_U.md`), dont les packs de biomes reprendront ce mécanisme.

## 4. Travail demandé

- **Contrat (ajout compatible, à valider par le propriétaire) :** dans `theme.json`, une clé facultative `texture_levels` : liste ordonnée `{name, max_px, dir}` (par exemple `low` 512 px dans `textures/512/`) ; les chemins de `texture` restent relatifs et sont cherchés d'abord dans le dossier du niveau choisi, puis à la racine du thème ; un thème sans `texture_levels` se comporte comme aujourd'hui.
- **Compilateur :**
  - `theme-check` vérifie chaque niveau (taille réelle au plus `max_px`, puissance de 2, même liste de fichiers dans chaque niveau) ;
  - nouvelle sous-commande `theme-pack SOURCE --levels 512,1024,2048` : fabrique les niveaux réduits à partir des textures d'origine (Pillow si présent, sinon refus clair) et la clé `texture_levels` ;
  - `theme-list` affiche les niveaux et la taille de chacun.
- **Engine :**
  - choix du niveau : table par préréglage dans `quality_presets.gd` (`low` 512 ou 1 024, `medium` 1 024, `high` 2 048), plafonnée par une estimation de la mémoire vidéo occupée par les textures du décor (somme des tailles décompressées, mipmaps compris) sous un budget par préréglage (`low` 512 Mo, `medium` 1 Go, `high` 1,5 Go) ;
  - compression à l'import (VRAM compressée quand le moteur la permet) et mipmaps ;
  - niveau imposé par `[render] texture_level` (`auto` par défaut), écrit par les réglages de O3 et O4 ;
  - ligne de journal au chargement : niveau retenu, mémoire estimée, raison (préréglage ou budget).
- **Repli :** si le niveau choisi manque, niveau inférieur, puis couleur unie, avec un avertissement (jamais d'échec de séance).

## 5. Fichiers concernés

- **Nouveaux :** `engine/scripts/texture_levels.gd`, `engine/tests/unit/test_texture_levels.gd`.
- **Modifiés :** `docs/contracts/world/theme.schema.json` et `docs/contracts/world_format_v1.md` (§9 et journal), `compiler/src/openride_compiler/theme.py`, `compiler/src/openride_compiler/theme_packs.py`, `compiler/src/openride_compiler/cli.py`, tests du compilateur concernés, `engine/scripts/theme_loader.gd`, `engine/scripts/quality_presets.gd`, `engine/tests/unit/test_theme_loader.gd`, `core/src/openride_core/config.py` (`texture_level`), `README.md`, `CLAUDE.md`, `engine/tests/README.md`, `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Interdits :** `main.gd`, textures dans le dépôt (les packs restent hors du dépôt, sauf de petites images de test générées par les tests).

## 6. Modifications de contrat autorisées

Clé `texture_levels` du thème, telle que validée par le propriétaire ; `[render] texture_level` dans la configuration.

## 7. Critères d'acceptation

1. Tous les tests passent (`core`, `compiler`, `engine/tests/run_engine_tests.sh`).
2. `theme-pack` sur un thème de test à textures de 2 048 px produit les niveaux 512, 1 024 et 2 048, que `theme-check` accepte ; un niveau dont un fichier dépasse `max_px` est refusé.
3. Choix du niveau : `low` donne 512 ou 1 024 selon la table ; un pack dont le niveau 1 024 dépasse le budget `low` redescend à 512 ; `texture_level = "high"` impose 2 048 quel que soit le préréglage.
4. Niveau absent : repli sur le niveau inférieur, puis sur la couleur unie, avec un avertissement et sans erreur Godot.
5. Thème sans `texture_levels` : comportement et tests actuels inchangés.

**Sur le PC cible (le propriétaire) :** un même pack en `low` puis en `high` : niveau annoncé au journal, 55 images/s ou plus en `low`, aucune saccade au chargement des tuiles.

## 8. Hors périmètre

- Téléchargement des packs depuis Internet (installation locale par `theme-install` seulement), packs de biomes (série U, 3.0), streaming de textures à la volée.
