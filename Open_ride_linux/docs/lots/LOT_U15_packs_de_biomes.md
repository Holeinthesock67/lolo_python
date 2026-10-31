# Lot U15 – Packs de biomes : thème 2.0 par défaut et pack de textures libres téléchargeable

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Packs de biomes : thème 2.0 par défaut en couleurs unies, `theme-install` depuis une adresse, bibliothèque de 5 Go | Python + JSON | U1, N10, P20 | Moyenne | Oui, après U1, **version 3.0** (issue #345) ; thème par défaut 2.0 à seize biomes livré le 28 octobre, reste `theme-install` depuis une adresse et la bibliothèque |

## 1. Objectif

**Version 3.0.** Fournir le thème 2.0 par défaut, en couleurs unies, qui décrit les seize biomes, et permettre d'installer depuis Internet des packs de textures CC0 par `theme-install`, rangés dans une bibliothèque locale plafonnée à 5 Go (U-Q3).

## 2. À lire

1. `docs/3.0/PLAN_SERIE_U.md` §7 (U-Q3), `docs/lots/LOT_U1_contrat_biomes.md` §4.5, `docs/lots/LOT_N10_packs_themes.md`, `docs/lots/LOT_P20_packs_textures_performance.md` (niveaux, provenance, méthode Gemini).
2. Code : `compiler/src/openride_compiler/theme.py`, `compiler/src/openride_compiler/theme_packs.py`, `compiler/src/openride_compiler/cli.py`, `engine/themes/default/theme.json`.

## 3. Prérequis

U1 et N10 livrés ; P20 livré.

## 4. Travail demandé

- **Thème par défaut 2.0** (`engine/themes/default/theme.json`) : les seize biomes en couleurs unies (aucune image), espèces, sons, faune, calendriers et variantes ; le biome `temperate_grassland` reprend exactement les valeurs du thème 1.x actuel.
- **Installation depuis une adresse :** `theme-install URL` (HTTPS seulement, archive `.zip`), téléchargement dans un dossier temporaire, contrôle complet par `theme-check` (schéma 2.0, niveaux, provenance) avant copie ; refus clair sans réseau ; jamais pendant une séance (compilateur seulement).
- **Bibliothèque :** chaque pack installé reste dans `~/OpenRide/Themes/` avec une date de dernière utilisation (écrite par le lanceur au démarrage d'une séance) ; au-delà de 5 Go (`[render] theme_library_gb`), `theme-install` retire le pack utilisé le moins récemment, jamais le thème choisi ni le thème par défaut ; `theme-list` affiche taille et dernière utilisation.
- **Recette d'un pack CC0 :** fichier `docs/3.0/PACK_BIOMES_CC0.md` qui liste, pour chaque sol du premier jalon, la texture ambientCG ou Poly Haven conseillée (nom et adresse de la page, licence CC0), et la commande `theme-pack` pour fabriquer les niveaux ; le pack lui-même reste hors du dépôt.

## 5. Fichiers concernés

- **Nouveaux :** `docs/3.0/PACK_BIOMES_CC0.md`, `compiler/tests/test_theme_library.py`.
- **Modifiés :** `engine/themes/default/theme.json`, `compiler/src/openride_compiler/theme.py`, `theme_packs.py`, `cli.py`, `compiler/tests/test_theme_packs.py`, `core/src/openride_core/launcher.py` (date d'utilisation), `core/src/openride_core/config.py` (`theme_library_gb`), `README.md`, `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Interdits :** textures ou images dans le dépôt (sauf petites images générées par les tests), engine hors du thème par défaut.

## 6. Modifications de contrat autorisées

`[render] theme_library_gb` (5 par défaut, bornes 1 à 50) dans la configuration.

## 7. Critères d'acceptation

1. Tous les tests passent (`core`, `compiler`, `engine/tests/run_engine_tests.sh`).
2. `theme-check engine/themes/default` accepte le thème 2.0 ; un engine qui ne lit que le 1.x (tests existants) affiche le même décor qu'aujourd'hui.
3. `theme-install` d'une archive servie par un petit serveur HTTPS de test : installé ; archive invalide : refusée, rien de copié.
4. Bibliothèque de test à 5,2 Go : le pack le moins récemment utilisé est retiré, jamais le thème choisi.
5. Aucun accès réseau dans les tests hors du serveur local de test.

## 8. Hors périmètre

Hébergement d'un pack officiel, mise à jour automatique des packs.
