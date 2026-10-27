# Lot U18 – Recette de la série U sur le PC et le vélo

## 1. Objectif

**Version 3.0.** Vérifier sur le PC cible (GTX 1060) et sur le vélo que les biomes du premier jalon et l'option « gravel » sont beaux, justes et assez rapides : un parcours par biome, performances, mémoire vidéo, ressenti du gravel.

**Lot du propriétaire (matériel).**

## 2. À lire

1. `docs/3.0/PLAN_SERIE_U.md` §7 et §9, `docs/lots/LOT_U17_integration_biomes.md`, `docs/lots/LOT_U19_parcours_demo_biomes.md`.

## 3. Prérequis

U17 livré ; U19 à U22 livrés pour la partie gravel.

## 4. Déroulé (propriétaire, avec Claude par Remote Control)

1. Compiler une trace personnelle en automatique (les traces restent sur le PC) et lire le rapport des parts de biomes.
2. Rouler 10 min sur chacun des parcours de démonstration du premier jalon (U19) en `low`, puis 5 min en `medium` et en `high`.
3. Forcer « Méditerranéen » puis « Haute montagne » au menu sur la trace personnelle.
4. Choisir « Gravier » au menu, rouler 10 min en SIM sur une trace habituelle (revêtue), puis 10 min en ERG ; puis « Chemins réels » sur un parcours de démonstration à portions non revêtues ou en monde ouvert.
5. Récupérer les journaux (`~/OpenRide/Logs/`) et les lignes `[perf-rendu]`.

## 5. Critères

1. 55 images/s ou plus en moyenne en `low`, p99 sous 25 ms, sur chaque biome du premier jalon.
2. Mémoire vidéo des textures du décor sous 1 Go en `high` (ligne de journal).
3. Aucune frontière droite visible entre biomes ; variantes régionales cohérentes.
4. Gravel en SIM : résistance nettement plus forte sur les portions non revêtues, jamais plus de 4 points de pente en supplément (vent compris) ; en ERG, puissance inchangée et vitesse plus faible.
5. Gravel coupé : aucune différence avec la 2.0.

## 6. Livrable

Un compte rendu dans la PR de recette (chiffres seulement, aucune coordonnée réelle), les captures d'écran retenues hors du dépôt, et les corrections demandées en issues.
