# Lot B2 – Compilateur : couche terrain (MNT Copernicus GLO-30)

## 1. Objectif

Ajouter au compilateur du lot B1 :
- la production de la couche terrain (tuiles proches à 10 m et lointaines à 50 m) ;
- la récupération de l'altitude manquante d'une trace, à partir d'un modèle numérique de terrain (MNT) mis en cache.

Ce lot correspond à la seconde moitié du sprint 2.

## 2. À lire

1. `docs/lots/00_INDEX.md`.
2. `docs/SRS_v1.1.md` §7 : étapes 3 et 5, sources d'altitude, deux étages de cache, durées.
3. `docs/contracts/world_format_v1.md` : §5 (terrain) en entier, §10 (régénération, tuile manquante), §11.
4. Le code livré par le lot B1, dans `compiler/`.

## 3. Travail demandé

### 3.1 Interface `ElevationProvider`

```python
class ElevationProvider(Protocol):
    name: str                    # "copernicus_glo30", "synthetic", …
    native_resolution_m: float
    def elevations(self, lats: np.ndarray, lons: np.ndarray) -> np.ndarray: ...   # NaN si inconnu
```

**Implémentations demandées :**

- **`CopernicusGlo30Provider`**, fournisseur réel.
  - Tuiles GeoTIFF optimisées pour le cloud (COG) de 1° × 1°, servies par le compartiment public AWS `copernicus-dem-30m` : `https://copernicus-dem-30m.s3.amazonaws.com/<nom>/<nom>.tif`.
  - Nom des tuiles : `Copernicus_DSM_COG_10_<N|S><lat 2 chiffres>_00_<E|W><lon 3 chiffres>_00_DEM`, les coordonnées étant celles du coin sud-ouest.
  - Les tuiles absentes correspondent à la mer : altitude 0. La liste officielle est dans `tileList.txt`, à la racine du compartiment. **Vérifier ce nommage sur le service réel avant de coder**, et le noter dans le rapport.
  - Lecture avec `rasterio` et interpolation bilinéaire.
- **`SyntheticProvider`**, pour les tests : altitude analytique, par exemple `1000 + 200·sin(x/700)·cos(z/900)` dans le repère du parcours, ou une fonction donnée.
- **`IgnRgeAltiProvider`** n'est **pas** demandé. Laisser un emplacement documenté.

### 3.2 Cache brut

- Tuiles téléchargées dans `~/.cache/openride/dem/copernicus_glo30/<nom>.tif`, ce dossier pouvant être changé par variable d'environnement pour les tests.
- **Téléchargement :**
  - écriture atomique (fichier temporaire, puis renommage) ;
  - délai d'attente de 60 s ;
  - 3 reprises à délai croissant ;
  - message de progression par tuile.
- Une tuile présente dans le cache n'est jamais retéléchargée. Une compilation relancée ne fait donc **aucun** accès réseau.
- L'option `--offline` interdit le réseau : une tuile manquante produit une erreur claire.

### 3.3 Altitude de la route

- Si le GPX n'a pas d'altitude, entièrement ou en partie, l'altitude brute vient du fournisseur, avant le lissage de Savitzky-Golay. Cela remplace l'erreur du lot B1.
- **Altitude GPX aberrante :** si plus de 5 % des points s'écartent du MNT de plus de 50 m, on prend l'altitude du MNT et on émet un avertissement. Le seuil est un paramètre, à ajuster sur des traces réelles ; le rapport donne les valeurs observées.
- Le manifeste indique la source utilisée (`route.alt_source` : `gpx` ou le nom du fournisseur).

### 3.4 Tuiles de terrain

Le format §5 fait foi :
- 101 × 101 valeurs `float32` petit-boutistes par tuile ;
- bords partagés entre tuiles voisines ;
- indices de tuile `ix`, `iz` éventuellement négatifs ;
- `NaN` pour une donnée absente.

**Étendue :**
- **niveau proche** (maille 10 m, tuile de 1 000 m) : les tuiles qui touchent une bande de ± 400 m autour de la route ;
- **niveau lointain** (maille 50 m, tuile de 5 000 m) : bande de ± 5 km.

**Échantillonnage :**
- chaque échantillon `(x, z)` est ramené en latitude et longitude par projection inverse (UTM du manifeste) ;
- l'altitude vient du fournisseur ;
- interroger le fournisseur par lots vectorisés, pas point par point.

**Fondu avec la route, niveau proche seulement :**
- `d` est la distance horizontale de l'échantillon au ruban : distance à l'axe moins la demi-largeur de chaussée, 3 m par défaut ;
- `y_route` est l'altitude lissée du point de route le plus proche ;
- pour `d ≤ 4 m` : `y = y_route − 0,05` ;
- pour `d ≥ 25 m` : `y = y_mnt` ;
- entre les deux : fondu en douceur (smoothstep) de `y_route − 0,05` vers `y_mnt` ;
- la recherche du plus proche point de route utilise un index spatial (`scipy.spatial.cKDTree`), pas une boucle.

Fichiers : `terrain/near/tile_<ix>_<iz>.f32` et `terrain/far/tile_<ix>_<iz>.f32`.

**Manifeste :**
- `layers.terrain` passe à `present: true`, avec `version`, `sources`, `near_cell_m: 10`, `far_cell_m: 50` ;
- liste des tuiles écrites, pour que `verify` les contrôle.

### 3.5 Ligne de commande

- `openride-compiler build x.gpx --layers route,terrain`. Par défaut, `route,terrain`.
- `openride-compiler add-layer <dossier.world> terrain` :
  - régénère la couche terrain seule, sans toucher à `route.json` ;
  - écriture atomique par couche : dossier `terrain` temporaire, puis remplacement.
- `verify` contrôle aussi :
  - la taille des tuiles (40 804 octets) ;
  - la présence des tuiles listées ;
  - l'égalité des bords partagés ;
  - l'absence de `NaN` dans la bande de ± 25 m autour de la route.

## 4. Fichiers concernés

- `compiler/` : nouveaux modules `elevation.py`, `terrain.py` et `cache.py` (noms indicatifs), modification de la ligne de commande et de la chaîne de traitement du lot B1, nouveaux tests.
- Dépendance ajoutée : `rasterio`.
- Une ligne dans `README.md`.

## 5. Modifications de contrat autorisées

- Le champ `route.alt_source` du manifeste et la liste des tuiles dans `layers.terrain` sont des ajouts compatibles (format §10, mineur 1.0 → 1.1).
- Les reporter dans `world_format_v1.md` et dans `docs/contracts/world/manifest.schema.json`, s'il existe, avec une ligne au journal des changements.

## 6. Critères d'acceptation

**Tests automatiques**, tous avec `SyntheticProvider`, sans réseau :

1. `pytest` passe dans `compiler/`, réseau coupé.
2. **Tuile proche :** une tuile écrite pèse 40 804 octets ; relue, l'échantillon `(i, j)` vaut l'altitude synthétique de `(ix·T + i·10, iz·T + j·10)` à 1 cm près, hors bande de fondu.
3. **Bords partagés :** la colonne 100 d'une tuile égale la colonne 0 de sa voisine, à l'octet près.
4. **Fondu :** à 2 m du ruban, `|y − (y_route − 0,05)| < 1 cm` ; à 30 m, `|y − y_mnt| < 1 cm`.
5. **Couverture :** chaque point de route a ses tuiles proches dans un rayon de 400 m et ses tuiles lointaines dans un rayon de 5 km ; aucune tuile n'est écrite au-delà de l'étendue plus une tuile.
6. **Altitude absente :** une trace sans altitude se compile, et l'altitude de la route suit le MNT synthétique.
7. **`add-layer terrain`** ne modifie pas `route.json` (même somme SHA-256) et remplace bien les tuiles.

**Essais réels :**

8. Une compilation réelle d'une trace de 30 km dans les Alpes télécharge les tuiles une fois. La seconde compilation se fait **sans réseau**, ce que vérifie l'option `--offline`. Fournir dans le rapport la durée et le volume de chaque passe.
9. Par défaut, le test d'intégration réseau est marqué `@pytest.mark.network` et sauté ; il se lance avec `pytest -m network`.

## 7. Hors périmètre

- Le rendu du terrain (lot E1).
- OpenStreetMap.
- La source IGN.
- La couverture du sol.

## 8. Livraison (23 octobre 2026)

Réalisé par Claude, branche `lot-b2-compilateur-terrain`, fusionné dans `main` (PR #9). Critères 1 à 7 et 9 tenus par les tests automatiques (95 tests, réseau coupé, en Python 3.11, 3.13 et 3.14 ; 75 tests du core inchangés). Critère 8 vérifié sur le service réel (voir ci-dessous).

**Nommage Copernicus vérifié sur le service réel :** `tileList.txt` (26 450 tuiles) et `https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_N45_00_E006_00_DEM/Copernicus_DSM_COG_10_N45_00_E006_00_DEM.tif` répondent ; tuile de 3 600 × 3 600 `float32`, EPSG:4326, pixels centrés sur la grille (bord gauche à 5,99986°), sans valeur `nodata`, environ 42 Mo.

**Essai réel (critère 8)** : trace approchée de 30,6 km de Bourg-d'Oisans au col du Lautaret, sans altitude (segments droits entre des points de passage, donc pentes non représentatives).
- Première passe : 4 tuiles (N44/N45 × E005/E006) et la liste, 165 Mo, 17 s en tout (2 s par tuile).
- Seconde passe avec `--offline` : 6 s, aucun accès réseau.
- Résultat : 65 tuiles proches, 24 lointaines, 3,7 Mo ; `verify` valide.

**Écarts assumés :**
- Une compilation consulte toujours le MNT, même avec `--layers route`, pour contrôler l'altitude GPX (§3.3).
- Seuil d'altitude aberrante : 50 m sur plus de 5 % des points, inchangé. `build` affiche l'écart médian, l'écart maximal et la part de points hors seuil. **Valeurs sur traces réelles à relever par le propriétaire** (aucune vraie trace avec altitude n'était disponible).
- Bord des tuiles Copernicus : un point situé entre le dernier centre de pixel d'une tuile et la tuile voisine (bande de 30 m le long des degrés entiers) prend la valeur du bord, soit un écart d'au plus une maille.
- Fondu : la distance est mesurée à la polyligne de la route (et non au sommet le plus proche), et `y_route` est l'altitude interpolée au point le plus proche de l'axe. Si le MNT est inconnu à moins de 25 m du ruban, le terrain prend l'altitude de la route.
- Manifeste 1.1 : en plus de `route.alt_source` et de `layers.terrain.tiles`, ajout de `native_resolution_m` (demandé par le §5 du format) et de `road_half_width_m`.
- Sans fournisseur (usage en bibliothèque), `compile_route` garde le refus du lot B1, avec le message « altitude absente et aucune source MNT fournie ».
- `add-layer` repasse `format_version` à 1.1.
- `CLAUDE.md` mis à jour à la fusion (couche terrain, `--offline`, `add-layer`), avec l'accord du propriétaire.

