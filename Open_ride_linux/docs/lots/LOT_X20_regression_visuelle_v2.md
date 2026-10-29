# Lot X20 – Non-régression visuelle, version 2

## 1. Objectif

`visual_check.py` compare des images pixel à pixel sous Xvfb, en `1280×720` `low` seulement dans `run_engine_tests.sh`, sans images de référence ; les captures « caméra par défaut » et « mouvement » sont prises à des instants qui varient d'un passage à l'autre, ce qui rend la comparaison de deux branches impossible. Propositions des fils (28 octobre) : vue fixe déterministe par préréglage (Y13), captures `1024×600` et `1920×1080` des menus avec références (menus), décor coupé (`living=false`) comparé aux images de la 1.0 (décor vivant), capture juste après la bascule de caméra sans trou sous l'horizon (S1).

## 2. Répartition

Les vitrines des biomes et des sols (`--compare REF`, exposition, coutures) sont faites par la série U ; le comparateur de base `compare_captures.py` par S1 ; ce lot les réutilise.

## 3. À lire

`engine/tests/visual_check.py`, `run_visual_tests.sh`, `run_engine_tests.sh`, `fake_core.py`, `compare_captures.py` (PR #465).

## 4. Travail demandé

- **Écart perceptuel** : `engine/tests/image_diff.py` (bibliothèque standard + zlib) : SSIM par blocs sur la luminance, masques par scène (rectangles des chiffres du HUD, ciel animé) ; score et carte des écarts en PNG.
- **Scène figée** : `visual_check.py --fige` : le faux core envoie une position, une heure de séance et une météo fixes ; l'engine reçoit `_test` `freeze` (décor vivant, nuages, herbe arrêtés à un temps donné) ; deux passages de suite donnent la même image (SSIM ≥ 0,995).
- **Références séparées** : `--golden DOSSIER` par moteur (`xvfb` ou `natif`) et par préréglage : `DOSSIER/<moteur>/<préréglage>/<scène>.png` ; `--update-golden SCÈNE` met à jour une seule scène ; références Xvfb `low` en vignettes 640×360 dans le dépôt (`engine/tests/golden/xvfb/low/`), références natives sur le PC (`~/OpenRide/visual_golden/`).
- **Nouvelles scènes** : menus (accueil, réglages, pause, bilan) en `1024×600` et `1920×1080` ; `living=false` ; bascule de caméra (capture 0,1 s après, prédicat « pas de ciel sous l'horizon »).
- **CI** : `run_engine_tests.sh` compare les scènes figées aux vignettes du dépôt (seuil SSIM 0,97).

## 5. Fichiers

- **Nouveaux :** `engine/tests/image_diff.py`, `engine/tests/golden/xvfb/low/*.png`, `core/tests/test_image_diff.py`.
- **Modifiés :** `visual_check.py`, `fake_core.py`, `engine/scripts/main.gd` (message `freeze`), `living_decor.gd` (temps figé), `run_engine_tests.sh`, `run_visual_tests.sh`, `docs/OUTILS_DE_TEST.md`, `engine/tests/README.md`, ce cahier, `00_INDEX.md`, `SUIVI_AVANCEMENT.md`.

## 6. Critères d'acceptation

1. SSIM testé : images identiques 1,0 ; bruit léger > 0,98 ; objet déplacé < 0,95 ; masque qui ignore une zone.
2. Deux passages de `visual_check.py --fige` donnent des images identiques au seuil près.
3. Une modification volontaire du ciel fait échouer la comparaison et produit la carte des écarts.

## 7. Hors périmètre

Les vitrines par biome (série U), le banc visuel du Cyber-Rogue (série R).

## 8. Réalisation (28 octobre)

- **`engine/tests/image_diff.py`** : PNG (déplacés de `visual_check.py`), réduction par moyenne et vignettes de 640 pixels de large, SSIM par blocs de 8 × 8 sur la luminance avec masques, carte des écarts (blocs en rouge, masques en bleu), ligne de commande (codes 0, 1, 2).
- **Scène figée** : message `_test` `freeze` (`main.gd`) ; `anim_clock.gd` (PR #503, sur laquelle ce lot s'appuie) figé à l'instant T, `wind_model.settle(T)` (vent posé sur ses cibles, phase calculée depuis 0), `sky_clouds.place(T)`, `living_world.freeze(T)` ; le décor vivant est ensuite appelé au même instant avec un pas nul. `visual_check.py --fige [T]` envoie `freeze` avant toute trame. Mesuré sous Xvfb : deux passages donnent des images identiques (SSIM 1,0000 sur `vue_fixe`, `attente`, `erreur`, `menu_accueil`, `bilan`, `pente_4pct` ; 0,9995 et 0,9998 sur `pente_0pct` et `pause`), et la capture `vue_fixe_figee`, 2 s après `vue_fixe`, est identique hors chronomètre et aide des commandes (SSIM 1,0).
- **Références** : `--golden DOSSIER` range `DOSSIER/<xvfb|natif>/<préréglage>/<scène>.png` (`<préréglage>_sans_vivant` avec `--decor-vivant off`) ; `--update-golden[=SCÈNES]` ; verdict sur la SSIM (seuil 0,97), éléments du HUD dépendants de l'instant masqués (état, distance, temps, courbes, bots), écart moyen gardé comme information. Vignettes Xvfb `low` dans `engine/tests/golden/xvfb/low/` (8 scènes, 1 Mo).
- **Bascule de caméra** : capture 0,1 s après l'appui, prédicat « pas de ciel sous l'horizon » (bleu franc du ciel dans le tiers bas, au plus 2 %).
- **Décor coupé** : `--decor-vivant off` lance l'engine avec `--living=off` (rendu de la 1.0), références à part.
- **CI** : `run_engine_tests.sh` passe `--fige` et, en `1280x720:low`, compare aux vignettes du dépôt.
- Tests : `core/tests/test_image_diff.py` (6 tests : identique, bruit léger, objet déplacé, masque, vignette et format, PNG et carte, ligne de commande, ciel modifié sur une vignette du dépôt) ; `engine/tests/unit/test_scene_freeze.gd` (9 vérifications).
- Reste : les menus en `1024×600` et `1920×1080` ont leurs scènes (`menu_accueil`, `bilan`) dans la matrice complète de `run_visual_tests.sh`, avec des références natives à créer sur le PC (`run_visual_tests.sh --native --update-golden`) ; les écrans Réglages et Pause comme scènes de référence attendent le banc des menus.
