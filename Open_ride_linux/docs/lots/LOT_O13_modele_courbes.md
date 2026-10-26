# Lot O13 – Courbes de la séance façon GoldenCheetah : modèle sans affichage

## 1. Objectif

En mode entraînement, GoldenCheetah montre le profil des watts cibles de toute la séance et, par-dessus, les courbes de la puissance, de la fréquence cardiaque et de la cadence, qui se dessinent au fur et à mesure. Le propriétaire veut la même vue dans OpenRide. Ce lot écrit le **modèle** de ce graphique, sans affichage et testé sans écran : séries échantillonnées, échelles, géométrie des courbes et du profil. Le dessin dans la scène est le lot O14.

## 2. À lire

1. `docs/lots/00_INDEX.md`, `docs/contracts/ipc_v1.md` (trame `state`, objet `erg`, élément de `workouts` avec `profile`, `hello_ack.config.ftp_w`), `docs/lots/LOT_I6_logique_erg_godot.md`, `docs/lots/LOT_K2_modele_hud_profil.md` (forme des modèles de vue).
2. Code : `engine/scripts/erg_view_model.gd` (`profile_bars`), `engine/scripts/hud_view_model.gd`, `engine/tests/unit/test_erg_view_model.gd` ou `engine/tests/test_erg_view_model.gd`, `engine/tests/fake_core.py` (`--erg-workout`).

## 3. Prérequis

K1 (livré). N3 recommandé (liste des entraînements avec `profile` côté engine) : sans lui, le test fournit le profil directement.

## 4. Travail demandé

Nouveau `engine/scripts/workout_chart_model.gd` (classe sans nœud, comme les autres modèles) :

- **Entrées :** `set_workout(profile, ftp_w, duration_s)` (triplets du contrat ; `null` = roue libre ; mode watts absolus prévu pour les `.erg` du lot O9 : `set_workout_w(profile_w, duration_s)`) ; `push(t_s, power_w, hr_bpm, cadence_rpm, target_w)` appelé à chaque trame `state` (30 Hz) ; `reset()`.
- **Échantillonnage :** une valeur par seconde de séance (moyenne des trames de la seconde) ; valeurs absentes (`null`, FC à 0) gardées comme trous, pas comme zéro ; pause : le temps de séance n'avance pas, aucune valeur ajoutée.
- **Lissage d'affichage** au choix : brut, 3 s, 10 s (moyenne glissante), sans toucher aux valeurs brutes.
- **Fenêtre :** séance entière (entraînement) ou 10 dernières minutes (parcours libre, sans profil) ; au-delà de 3 600 points, regroupement par 2, 4… pour rester sous 1 800 points dessinés.
- **Échelles :** watts de 0 à max(1,5 × FTP, cible max × 1,1, puissance max × 1,05) arrondi à 50 W ; FC de 60 à max(190, FC max) ; cadence de 0 à 140 tr/min ; graduations « jolies ».
- **Géométrie** pour une taille `(w, h)` donnée : polygone du profil cible (zones de Coggan, mêmes seuils que `profile_bars` et `openride-core summary`), polylignes des trois courbes avec leurs trous, curseur du temps courant, et valeurs courantes (dernière seconde) pour la légende ; tout en coordonnées locales, sans dépendre d'un nœud.
- **Coût :** `push` en O(1) ; recalcul de la géométrie au plus une fois par seconde.

## 5. Fichiers concernés

- **Nouveaux :** `engine/scripts/workout_chart_model.gd`, `engine/tests/unit/test_workout_chart_model.gd`.
- **Modifiés :** `engine/tests/fake_core.py` seulement si une option manque pour un test de bout en bout (à signaler, N3 étant seul à le modifier dans la série N), `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Interdits :** `main.gd`, le HUD, `ipc_client.gd`, le core, le contrat.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `engine/tests/run_engine_tests.sh` passe, avec `UNIT=test_workout_chart_model`.
2. 90 trames à 30 Hz : 3 points, chacun moyenne de sa seconde ; FC à 0 et cadence `null` donnent des trous.
3. Pause de 20 s : aucun point ajouté, curseur figé.
4. Profil `sweet_spot_3x10` à FTP 250 W : polygone avec les bonnes marches et rampes, couleurs de zone justes, échelle des watts à 400 W.
5. 2 h de séance simulée : au plus 1 800 points par courbe, géométrie en moins de 5 ms (mesuré dans le test).
6. Lissage 10 s : valeurs attendues sur une marche de 100 à 300 W.

## 8. Hors périmètre

- Dessin dans la scène (O14) ; graphique du bilan après la séance (peut réutiliser ce modèle plus tard).

## 9. Livraison

Livré le 26 octobre 2026 (issue #156), thread « Développer les lots O restants ». Écrit sans Godot dans le conteneur cloud : `UNIT=test_workout_chart_model engine/tests/run_engine_tests.sh` reste à lancer sur le PC.

- `engine/scripts/workout_chart_model.gd` (RefCounted, sans nœud) : `set_workout(profile, ftp_w, duration_s)`, `set_workout_w(profile_w, duration_s)` (watts absolus, zones avec `set_ftp`), `clear_workout`, `push(t_s, power_w, hr_bpm, cadence_rpm, target_w)`, `reset`, `set_smoothing(0|3|10)`, `values`, `smoothed`, `current_values`, `scales`, `nice_ticks`, `time_window`, `group_factor`, `geometry(w, h)`.
- Pause : le modèle ne reçoit pas d'indicateur ; une trame dont `t_s` n'avance pas est ignorée (temps de séance figé), ce qui couvre la pause sans toucher au contrat.
- Zones : seuils et couleurs repris de `erg_view.gd` (`ZONE_HIGH_PCT`, `ZONE_COLORS`, `FREERIDE_COLOR`), eux-mêmes alignés sur `session_summary.ZONES`. Les rampes sont coupées aux seuils de zone : chaque morceau a la couleur de sa zone (échauffement de `sweet_spot_3x10` : Z1 jusqu'à 137,5 W, puis Z2).
- Géométrie : `profile` (polygones, `t0`, `t1`, `zone`, `color`), `curves.power|hr|cadence` (polylignes coupées aux trous), `cursor_x`, `current`, `scales`, `window`, `group` ; recalculée seulement quand le nombre de secondes, la taille, le lissage ou le profil changent.
- Les séries brutes sont gardées dans des `Array` (un `PackedFloat32Array` rangé dans un `Dictionary` serait copié à chaque ajout).
- Tests : `engine/tests/unit/test_workout_chart_model.gd` (critères 2 à 6, fenêtre du parcours libre, graduations).
