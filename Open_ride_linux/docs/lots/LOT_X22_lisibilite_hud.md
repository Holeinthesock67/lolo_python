# Lot X22 – Lisibilité du HUD à 2 m et débordements

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série X (outils de test) : Lisibilité du HUD à 2 m (hauteur, contraste) et débordements (4 bots à 720 px) | Python | — | Petite | **Livré le 28 octobre** (branche `claude/project-thread-818r6t-x22`) ; issue #220 |

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

## 7. Livraison

Livré le 28 octobre (branche `claude/project-thread-818r6t-x22`).

- `engine/tests/hud_lisibilite.py` : contraste WCAG mesuré dans la capture (fond : luminance médiane du rectangle ; texte : le 2 % le plus éloigné du fond), hauteur des lignes de texte ramenée à 1080 lignes, panneaux dans l'écran et sans chevauchement. Les valeurs sans chiffre (« -- ») ne sont pas mesurées.
- `visual_check.py --lisibilite` : hauteur et contraste sur chaque capture ; `check_layout` vérifie toujours les panneaux (colonnes gauche et droite, bandeau central, vent, abri, blocs segment et bonus, encart des bots, profil). `run_visual_tests.sh` passe `--lisibilite` ; `run_engine_tests.sh` (CI) ne la passe pas, pour ne pas bloquer les PR sur les constats ci-dessous.
- Scène `bots_segment_bonus` : 4 bots à profil (`profile`, `cp_w`, `mass_kg`, `wbal_pct`, `jersey`), voisins `bot_ahead`/`bot_behind`, segment en cours, bonus en réserve.
- `main.gd` : la capture donne aussi les panneaux gauche et droit, le profil, le bloc bonus, les textes des blocs segment et bonus et les libellés des métriques (`set_meta("caption")` dans `hud_view.gd`).
- `core/tests/test_hud_lisibilite.py` (5 tests) : blanc sur noir 21:1, gris moyen sur gris clair en échec, hauteur ramenée à 1080 lignes, encart volontairement trop grand en échec (hors écran et sur le profil).
- Essai au cloud (Xvfb, 1280×720 et 1024×600, `low`) : chiffres principaux à 52 px pour 1080 lignes, contraste des valeurs blanches 10:1, aucun débordement. Constats, à trancher par le fil du HUD (hors périmètre ici) :
  - la valeur de la pente, colorée selon la classe de pente avec une transparence de 0,85, n'a que 3,0:1 (plat) à 4,1:1 (4 %) sur le fond du panneau (seuil 4,5:1) ;
  - le nom d'un bot à puissance constante (orange) tombe à 2,9:1 en 1024×600 au-dessus d'un ciel clair ;
  - à 720 lignes, avec les blocs segment et bonus, l'encart des bots ne garde que les deux voisins : aucune ligne de bot (maillot, W′) ni porteurs des maillots. C'est la priorité prévue par T15 ; la scène note le nombre de lignes affichées sans seuil.

## 8. Corrections du HUD (28 octobre, suite)

Les trois constats ci-dessus sont corrigés (branche `claude/project-thread-m4q7p0`), mesurés avec `visual_check.py --lisibilite` au cloud (Xvfb, `low`), avant et après, sur toutes les captures :

| Mesure | Seuil | Avant | Après |
|---|---|---|---|
| Contraste de la pente, 1280×720 | 4,5:1 | 2,7 à 4,7:1 | 5,3 à 7,3:1 |
| Contraste de la pente, 1024×600 | 4,5:1 | 2,7 à 4,7:1 | 5,2 à 7,3:1 |
| Nom de bot le plus faible, 1280×720 | 3:1 | 3,5:1 | 4,6:1 |
| Nom de bot le plus faible, 1024×600 | 3:1 | 2,8:1 | 4,0:1 |
| Encart des bots à 720 lignes, segment et bonus affichés | — | 2 voisins seuls | 2 voisins avec maillot, FTP et W′, et ligne des maillots |

- **Pente** : `hud_view.gd` sépare les teintes des barres du profil (`GRADE_COLORS`, inchangées) des teintes de texte (`GRADE_TEXT_COLORS`, mêmes teintes éclaircies et opaques), prises aussi par les carrefours (`junction_view.gd`).
- **Noms des bots** : orange des bots à puissance constante éclairci (`bots_view_model.gd`).
- **Encart des bots** : voisins marqués sur leur propre ligne, blocs segment et bonus à la hauteur de leur contenu ; détail dans la révision du cahier T15. La scène `bots_segment_bonus` exige maintenant les deux voisins avec leur ligne complète et la ligne des maillots ; `test_bot_hud_model.gd` vérifie la même chose en 720 lignes.

