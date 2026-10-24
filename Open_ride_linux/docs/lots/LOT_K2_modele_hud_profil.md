# Lot K2 – Modèle de vue du HUD et profil d'altitude (sans affichage)

## 1. Objectif

Préparer le HUD final du lot E3 (SRS §13) sans toucher au rendu : toute la logique (valeurs affichées, unités, lissage, profil d'altitude devant le cycliste, prochaine montée) dans un script GDScript pur, testé sans écran, comme `erg_view_model.gd` (lot I6). E3 n'aura plus qu'à dessiner ce que ce modèle calcule.

## 2. À lire

1. `docs/lots/00_INDEX.md`, `docs/lots/LOT_I6_logique_erg_godot.md` (même démarche).
2. `docs/SRS_v1.1.md` §13 (HUD) et §4 (pente), `docs/contracts/ipc_v1.md` §3 (trame `state`).
3. Code : `engine/scripts/route_data.gd` (`sample`, `sample_point`, `wrap_s`, `length_m`), `engine/scripts/erg_view_model.gd`, `engine/scripts/main.gd` (HUD actuel, lecture seule).

## 3. Prérequis

Lot K1 livré (le test se dépose dans `engine/tests/unit/`).

## 4. Travail demandé

Nouveau `engine/scripts/hud_view_model.gd` (`extends RefCounted`, sans `class_name`, chargé par `preload`), qui ne crée aucun nœud :

- `on_state(state: Dictionary, now_s: float)` puis `evaluate(now_s: float) -> Dictionary`, avec au moins :
  - `power_text` (moyenne 3 s, `power_3s`), `speed_text` (km/h, une décimale), `cadence_text`, `hr_text` (« — » si `hr` est nul), `gear_text` (« 12/24 »), `grade_text` (pente réelle, signe et une décimale), `distance_text` (km, deux décimales ; distance parcourue sur une boucle comprise), `elapsed_text` (`t` en h:mm:ss) ;
  - les champs bruts correspondants, pour les tests.
- `profile(route, s: float, behind_m := 500.0, ahead_m := 4500.0, columns := 120) -> Dictionary` :
  - `points` : `columns` couples (distance relative en m, altitude en m) échantillonnés régulièrement sur la fenêtre, en tenant compte des boucles (`wrap_s`) et des parcours ouverts (fenêtre tronquée aux extrémités, sans valeur inventée) ;
  - `marker_index` : colonne de la position courante ; `alt_min`, `alt_max` (marge de 5 % pour le dessin) ;
  - `grade_class` par colonne : `flat` (< 2 %), `climb` (2 à 6 %), `steep` (6 à 10 %), `wall` (> 10 %), `descent` (< −2 %) ; seuils en constantes en tête du fichier.
- `next_climb(route, s: float, min_length_m := 300.0, min_grade_pct := 3.0) -> Dictionary` : début (distance depuis `s`), longueur, pente moyenne et dénivelé de la prochaine montée qui dépasse les deux seuils ; `{}` s'il n'y en a pas avant la fin (parcours ouvert) ou dans un tour (boucle).

## 5. Fichiers concernés

- **Nouveaux :** `engine/scripts/hud_view_model.gd`, `engine/tests/unit/test_hud_view_model.gd`.
- **Modifiés :** `engine/tests/README.md` (une ligne), `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Interdits :** `main.gd`, `ipc_client.gd`, scripts de rendu d'E1.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `engine/tests/run_engine_tests.sh` passe en entier, sans erreur ni avertissement Godot.
2. Textes : tableau de cas (au moins 15) avec les valeurs limites (0, nul, négatif, `NaN`, très grand) ; aucun texte vide, aucune exception.
3. Profil sur `res://demo/demo.world` (ou un `.world` synthétique produit dans `user://`) : à `s` = 0, au milieu et à 50 m de la fin, les altitudes du profil égalent `route.sample` aux mêmes distances à 1 cm ; la fenêtre est tronquée aux extrémités d'un parcours ouvert ; sur une boucle, la fenêtre traverse la ligne d'arrivée sans saut.
4. `next_climb` sur un parcours synthétique (plat, puis 800 m à 7 %, puis plat) : début, longueur à ± 20 m, pente moyenne à ± 0,3 point.
5. `profile` sur 120 colonnes : moins de 2 ms en moyenne sur 100 appels (mesure affichée).

## 8. Hors périmètre

- Dessin du HUD et du profil (E3, interne : contrôle visuel).
- Bandeau ERG (déjà dans `erg_view_model.gd`, affichage F2).

## 9. Livraison (24 octobre 2026, PR #39)

- `engine/scripts/hud_view_model.gd` et `engine/tests/unit/test_hud_view_model.gd` (60 vérifications, découvert par K1).
- **Écarts assumés :** si `s` est déjà dans une montée, `next_climb` renvoie ce qu'il en reste (`in_progress` vrai) ; une montée commence à 2 % sur 10 m et finit au premier replat de plus de 50 m. Altitude et pente sont lues par l'interpolation linéaire de `route_data.sample()`, sans calcul de position.
- Mesure : `profile` sur 120 colonnes en 0,35 ms environ (seuil 2 ms).
