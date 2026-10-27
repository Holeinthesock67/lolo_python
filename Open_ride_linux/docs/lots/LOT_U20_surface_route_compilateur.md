# Lot U20 – Option « gravel » : surface de la route au compilateur et chemins de terre au monde ouvert

## 1. Objectif

**Version 3.0.** Donner à chaque point de la route sa surface (`paved`, `compacted`, `gravel`, `dirt`) d'après OSM, pour les traces compilées comme pour le monde ouvert, et ouvrir au monde ouvert les chemins de terre et les pistes forestières quand l'option « gravel » est active (U-G1, question W-Q2 du monde ouvert).

## 2. À lire

1. `docs/3.0/PLAN_SERIE_U.md` §7 (U-G1, U-G2) et §10, `docs/lots/LOT_U1_contrat_biomes.md` §4.4 et §4.6, `docs/2.0/PLAN_SERIE_W.md` (W-Q2), `docs/lots/LOT_W4_graphe_routier.md`, `docs/lots/LOT_W6_navigateur.md`.
2. Code : `compiler/src/openride_compiler/osm.py`, `osm_layers.py`, `pipeline.py`, `writer.py`, `route_stats.py`, `worldgen/graph.py` (W4), `worldgen/navigator.py` (W6).

## 3. Prérequis

U1 livré ; W4 et W6 livrés pour la partie monde ouvert.

## 4. Travail demandé

- **Traces compilées :** requête Overpass des voies (`highway=*`) dans un couloir de 15 m autour de la trace ; pour chaque point, la voie la plus proche dont le cap concorde (écart de moins de 30°) ; surface tirée de `surface` (`asphalt`, `concrete`, `paving_stones` → `paved` ; `compacted`, `fine_gravel` → `compacted` ; `gravel`, `pebblestone` → `gravel` ; `dirt`, `ground`, `earth`, `grass`, `mud`, `sand` → `dirt`), sinon de `tracktype` (`grade1` → `paved`, `grade2` → `compacted`, `grade3` → `gravel`, `grade4` et `grade5` → `dirt`), sinon `highway=track` → `gravel`, sinon `paved` ; lissage : portion de moins de 50 m rattachée à ses voisines.
- Colonne `surface` dans `route.json` seulement si au moins un point n'est pas `paved` ; `route.surface_source` et parts de surface dans `stats` (`route_stats.py`, copie exacte dans le core à garder synchronisée).
- **Monde ouvert :** classe `g` dans le graphe (voies non revêtues, hors `access` ou `bicycle` à `no` ou `private`), écartée par le navigateur sauf si `[gravel] enabled` ; colonne `surface` dans les profils d'arête et les parties de route.
- Option `--no-surface` pour garder l'ancien comportement.

## 5. Fichiers concernés

- **Nouveaux :** `compiler/src/openride_compiler/surface.py`, `compiler/tests/test_surface.py`.
- **Modifiés :** `compiler/src/openride_compiler/pipeline.py`, `writer.py`, `route_stats.py`, `cli.py`, `worldgen/graph.py`, `worldgen/navigator.py`, `worldgen/edge_profile.py`, leurs tests, `core/src/openride_core/route_stats.py` (copie exacte), `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Interdits :** engine, physique du core (U21), contrats.

## 6. Modifications de contrat autorisées

Aucune (U1).

## 7. Critères d'acceptation

1. `pytest` passe dans `compiler/` et `core/`, réseau coupé.
2. Trace de test le long d'une voie `surface=gravel` sur 2 km : 2 km en `gravel` à 20 m près ; voie parallèle à 12 m mais perpendiculaire en cap : ignorée.
3. Trace entièrement sur `asphalt` : pas de colonne `surface`, fichier identique à aujourd'hui.
4. Portion `dirt` de 30 m isolée : rattachée à ses voisines.
5. Navigateur, `gravel` coupé : aucune arête `g` choisie ; activé : une arête `g` plus courte est préférée comme une autre.
6. `route_stats.py` du compilateur et du core identiques (test existant de copie exacte).

## 8. Hors périmètre

Physique (U21), rendu (U22), surface devinée par l'imagerie.
