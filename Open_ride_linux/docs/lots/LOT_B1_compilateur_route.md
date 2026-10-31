# Lot B1 – Compilateur : GPX vers `.world` (couche route)

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Compilateur : GPX vers `.world` (couche route) | Python | Aucune (A, livré, sert à la vérification croisée) | Moyenne | **Livré le 23 octobre** (fusionné ; 53 tests revérifiés le 23 octobre) |

## 1. Objectif

Créer le programme `openride-compiler`, qui transforme une trace GPX en dossier `.world` contenant le manifeste et la couche route. Le terrain fera l'objet du lot B2.

Ce lot correspond à la première moitié du sprint 2 de la SRS.

## 2. À lire

1. `docs/lots/00_INDEX.md` (règles communes).
2. `docs/SRS_v1.1.md` §7 (compilateur) et §11 (arborescence).
3. `docs/contracts/world_format_v1.md` §2, §3, §4, §10 et §11.
4. Lot A (livré) : `core/src/openride_core/route.py` (`load_world`) et `docs/contracts/world/*.schema.json`, pour la vérification croisée du critère 8. La projection des parcours compilés est `utm` ; `local_equirectangular` est réservée aux parcours synthétiques.

## 3. Travail demandé

### 3.1 Paquet

- Nouveau dossier `compiler/`, à côté de `core/` :
  - `compiler/pyproject.toml` : paquet `openride-compiler`, script `openride-compiler = openride_compiler.cli:main`, Python ≥ 3.11 ;
  - code dans `compiler/src/openride_compiler/`, tests dans `compiler/tests/`.
- **Dépendances autorisées :** `numpy`, `scipy` (filtre de Savitzky-Golay), `pyproj` (projection UTM). Le GPX se lit avec `xml.etree.ElementTree`, sans bibliothèque GPX.
- **Dépendances de test :** `pytest` et `jsonschema`.
- Le compilateur ne dépend pas du paquet `openride-core`. Si les deux partagent une constante, elle est recopiée et un test garde les deux copies identiques.

### 3.2 Chaîne de traitement

1. **Lecture du GPX** (1.0 et 1.1).
   - Prendre tous les `trkpt` de tous les `trkseg` de tous les `trk`, dans l'ordre. À défaut, prendre les `rtept`.
   - Garder latitude, longitude et altitude (`ele`) si elle est présente.
   - Ignorer les espaces de noms et extensions inconnus.
2. **Nettoyage.**
   - Supprimer les points à moins de 1 m (en horizontal) du dernier point gardé : doublons et arrêts.
   - Une trace de moins de 500 m après nettoyage est refusée, avec le message d'erreur `trace trop courte (… m < 500 m)`.
3. **Projection.**
   - UTM de la zone du premier point, WGS84, via `pyproj`.
   - Translation pour que le premier point soit en `(x, z) = (0, 0)`, avec `x` vers l'est et `z` vers le sud (`z = −(nord − nord_0)`).
   - La zone est notée au format du manifeste (`32T` : numéro et bande de latitude).
4. **Type de parcours.**
   - Si le dernier point est à moins de 50 m du premier, le parcours est une `loop` : on ajoute le premier point à la fin pour fermer la trace.
   - L'option `--out-and-back` concatène la trace et son inverse ; le type vaut alors `out_and_back`.
5. **Ré-échantillonnage.**
   - Un point tous les 10 m de distance horizontale cumulée, le long de la polyligne projetée, avec interpolation linéaire de `x`, `z` et de l'altitude brute.
   - Le dernier point est placé à `length_m`, exactement à la fin de la trace.
   - `n = ⌊length_m / 10⌋ + 1`, plus 1 si un reste existe.
6. **Altitude.**
   - Si toute la trace a une altitude : lissage de Savitzky-Golay (fenêtre 11, ordre 2, `mode="interp"`) sur les points ré-échantillonnés, ce qui donne `alt_m`. L'altitude avant lissage est écrite dans `alt_raw_m`.
   - Pour une boucle, l'altitude du dernier point est forcée égale à celle du premier, après lissage.
   - Si l'altitude manque, entièrement ou en partie : erreur `altitude absente : la source MNT arrive avec le lot B2`. Le lot B2 remplacera cette erreur par la lecture du MNT.
7. **Pente.**
   - Différences centrées sur 20 m : `grade_i = 100 × (alt_{i+1} − alt_{i−1}) / (s_{i+1} − s_{i−1})`. Aux extrémités, différences simples.
   - Limitation à ± 25 %. Le nombre de points limités est écrit dans `grade_clamped_points`.
8. **Cap.**
   - `heading_i = atan2(Δx, −Δz)` en degrés, dans [0, 360), calculé sur les points voisins.
   - Lissage par moyenne circulaire glissante sur 3 points, soit environ 30 m.
9. **Coordonnées géographiques.** `lat` et `lon` de chaque point ré-échantillonné, par projection inverse.
10. **Écriture atomique.**
    - Écrire dans `<sortie>/.<nom>.world.tmp-<pid>`, puis renommer en `<sortie>/<nom>.world`.
    - Un dossier existant est remplacé seulement avec `--force` ; sinon, erreur.
    - Contenu : `manifest.json` (format §11 : `projection: "utm"`, `utm_zone`, source avec `gpx_sha256`, compilateur et version, `terrain.present: false`) et `route.json` (format §4).

### 3.3 Ligne de commande

```text
openride-compiler build <fichier.gpx> [--name NOM] [--out DOSSIER] [--out-and-back] [--force]
openride-compiler verify <dossier.world>
openride-compiler info <dossier.world>
```

- `--name` : par défaut, le nom du fichier sans extension, normalisé en minuscules et tirets ASCII.
- `--out` : par défaut `~/.local/share/openride/routes`.
- `verify` contrôle ce que liste le format §10 (structure, longueurs des tableaux, cohérence de `length_m`, boucle fermée, plages de valeurs). Il quitte avec le code 0 si tout est valide, 1 sinon, et liste les problèmes.
- `info` affiche le nom, la longueur, le type, la pente maximale et minimale, le dénivelé positif et le nombre de points limités.
- Codes de retour : 0 succès, 1 erreur d'entrée (GPX invalide ou trop court), 2 erreur interne.

### 3.4 Tests

- Les GPX de test sont **générés par les tests**, à partir de coordonnées calculées : aucun fichier réel n'est nécessaire.
- Garder un petit GPX réel anonymisé dans `compiler/tests/data/` est permis, à condition de le signaler.

## 4. Fichiers concernés

Tout le contenu de `compiler/` (nouveau). Une ligne dans `README.md` (section mise en route).

## 5. Modifications de contrat autorisées

Aucune. Si un point du format est ambigu (exemple : `utm_zone` pour une trace à cheval sur deux zones), choisir la règle la plus simple, la documenter dans le rapport et la poser en question.

## 6. Critères d'acceptation

1. `pytest` passe dans `compiler/`.
2. **Ligne droite.** Une droite plein nord de 2 000 m à 5 % de pente régulière donne :
   - `length_m` = 2 000 ± 2 m ;
   - `n` = 201 ;
   - pente des points intérieurs à 5,0 ± 0,1 % ;
   - cap à 0 ± 0,5° ;
   - `z` décroissant.
3. **Boucle.** Une boucle (cercle de 1 km de rayon) est détectée en `loop` : le dernier point est égal au premier, `alt_m` aussi.
4. **Trace courte.** Une trace de 400 m est refusée (code 1, message clair).
5. **Altitude absente.** Une trace sans altitude donne l'erreur prévue (code 1).
6. **Doublons.** Les points en double et les arrêts (50 points identiques) ne changent pas la longueur à 1 m près.
7. **Pente limitée.** Une marche de 30 m d'altitude sur 10 m produit des points limités à 25 %, et `grade_clamped_points` > 0.
8. **Formats.** Les sorties valident les schémas `docs/contracts/world/*.schema.json` et se chargent avec `openride_core.route.load_world` (installer `openride-core` en dépendance de test seulement).
9. **Écriture atomique.** Une erreur simulée au milieu de l'écriture ne laisse aucun dossier `<nom>.world` visible. Une compilation sans `--force` sur un dossier existant échoue sans le modifier.
10. **`verify`** détecte un tableau tronqué (code 1) et valide une sortie normale (code 0).
11. **Performance.** Un GPX synthétique de 30 km (environ 30 000 points d'entrée) compile en moins de 10 s.
12. **Essai manuel du propriétaire.** Une vraie trace de col compilée a une pente maximale à ± 1 point de celle de Garmin Connect (critère du sprint 2, hors recette automatique).

## 7. Hors périmètre

- Le terrain et le MNT (lot B2).
- OpenStreetMap.
- Le lancement du compilateur depuis le menu de l'engine.
- La lecture du parcours par le core (lot A).


## 8. Livraison (23 octobre 2026)

- Paquet `openride-compiler` livré et fusionné (`cli.py`, `gpx.py`, `pipeline.py`, `frame.py`, `writer.py`, `verify.py`, `constants.py`, `errors.py`).
- 53 tests unitaires et de contrat passants dans `compiler/tests/`.
