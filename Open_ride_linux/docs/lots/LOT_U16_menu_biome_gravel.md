# Lot U16 – Choix du biome et option « gravel » au menu

## 1. Objectif

**Version 3.0.** Permettre de forcer le biome du rendu (U-Q1) et d'activer l'option « gravel » (U-G1) depuis la section « Réglages » du menu, au Click ou au clavier, sans recompiler.

**Lot interne (menu).**

## 2. À lire

1. `docs/3.0/PLAN_SERIE_U.md` §7, `docs/SPECIFICATION_GENERALE.md` §7.1 (boutons), `docs/lots/LOT_U1_contrat_biomes.md` §4.6, `docs/lots/LOT_O3_reglages_core.md`, `docs/lots/LOT_O4_menu_reglages.md`.
2. Code : `core/src/openride_core/settings.py` (O3), `core/src/openride_core/ipc_server.py`, `engine/scripts/menu_model.gd`, `engine/scripts/settings_view.gd` (O4).

## 3. Prérequis

U1, U2 et O4 livrés ; U5 pour l'effet à l'écran.

## 4. Travail demandé

- Core : deux réglages de plus dans `settings.py` : `render.biome` (liste `auto` puis les seize biomes, libellés français du lot U0, `applies` = `now`) et `gravel.mode` (« Coupé », « Chemins réels » pour `auto`, « Chemin compact », « Gravier », « Terre » ; `applies` = `next_session`) ; `hello_ack.config` porte `biome` et `gravel` (IPC 1.6 du lot U1).
- Engine : les deux lignes dans l'écran des réglages, au Click selon le plan de boutons commun (`docs/SPECIFICATION_GENERALE.md` §7.1, sans exception : mêmes boutons que les autres réglages d'O4) ; le biome forcé s'applique tout de suite au décor de fond du menu (`biome_model.gd`).
- Fiche du parcours (O15) : part des biomes (`shares`) et part de chemins non revêtus, quand elles existent.

## 5. Fichiers concernés

- **Modifiés :** `core/src/openride_core/settings.py`, `core/src/openride_core/ipc_server.py` (`hello_ack.config`), `core/tests/test_ipc_settings.py`, `engine/scripts/menu_model.gd`, `engine/scripts/settings_view.gd`, `engine/scripts/catalog_model.gd`, `engine/tests/unit/test_menu_model.gd`, `README.md`, `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Interdits :** compilateur, contrats (déjà faits par U1).

## 6. Modifications de contrat autorisées

Aucune (U1).

## 7. Critères d'acceptation

1. Toutes les suites passent (core, compilateur, engine, bout en bout `run_e2e.sh`).
2. Au clavier puis au Click : choisir « Savane », quitter, relancer : `config.toml` contient `biome = "savanna"` et la séance suivante est en savane ; choisir « Gravier » : la séance suivante sur une trace revêtue se roule et s'affiche en gravier de bout en bout.
3. `gravel.mode` changé pendant une séance : refusé (`setting_busy`), rien d'écrit.
4. `hello_ack` sans les deux clés (core plus ancien) : l'engine reste en `auto` et sans gravel.

**Sur le PC cible (le propriétaire) :** lisibilité à 2 m, navigation au Click réel.

## 8. Hors périmètre

Choix du biome tuile par tuile, éditeur de biomes.
