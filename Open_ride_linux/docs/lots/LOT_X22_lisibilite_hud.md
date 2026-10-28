# Lot X22 – Lisibilité du HUD à 2 m et débordements

## 1. Objectif

Le critère « lisible à 2 m » n'est vérifié qu'à l'œil. Le fil de la série T (28 octobre) ajoute un besoin : vérifier que l'encart des bots (T15) ne déborde pas quand les blocs segment et bonus sont affichés en même temps, jusqu'à la plus petite fenêtre (720 px de haut).

## 2. À lire

`engine/tests/visual_check.py` (rectangles des éléments du HUD dans `[test] screenshot`), `fake_core.py`, `engine/scripts/hud_view.gd`.

## 3. Travail demandé

- **`engine/tests/hud_lisibilite.py`** : à partir des captures et des rectangles de `visual_check.py` : hauteur des chiffres principaux (puissance, vitesse, cadence, FC, pente) ramenée à un écran de 1920×1080 (seuil : 28 px, environ 7 mm sur un écran de 24 pouces, lisible à 2 m) ; contraste texte/fond mesuré dans la capture (rapport WCAG ≥ 4,5:1 pour les valeurs, 3:1 pour les étiquettes).
- **Débordements** : aucun élément visible hors de l'écran, aucun chevauchement entre panneaux (déjà vérifié pour le HUD de base) étendu aux blocs bots, segment, bonus et vent.
- **Nouvelle scène de `visual_check`** : `bots_segment_bonus` : 4 bots à profil (maillots, jauges W′, deux voisins), un segment en cours et un bonus en réserve, en `1280×720` et `1024×600`.
- Branché dans `visual_check.py` (`--lisibilite`) et dans `run_visual_tests.sh`.

## 4. Fichiers

- **Nouveaux :** `engine/tests/hud_lisibilite.py`, `core/tests/test_hud_lisibilite.py` (contraste et hauteur sur des images fabriquées).
- **Modifiés :** `visual_check.py`, `fake_core.py`, `run_visual_tests.sh`, `docs/OUTILS_DE_TEST.md`, ce cahier, `00_INDEX.md`, `SUIVI_AVANCEMENT.md`.

## 5. Critères d'acceptation

1. Contraste : blanc sur noir 21:1, gris moyen sur gris clair en échec.
2. La scène `bots_segment_bonus` passe à 720 px ; un panneau volontairement trop grand échoue.

## 6. Hors périmètre

Changer la mise en page du HUD.
