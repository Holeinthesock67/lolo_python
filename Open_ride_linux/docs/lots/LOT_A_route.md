# Lot A – Lecteur `.world` et interpolation de route partagés (core et engine)

## 1. Objectif

Créer **un seul** module de lecture de parcours compilés (`.world`) dans le core Python et son équivalent dans l'engine Godot, avec la même règle d'interpolation et des vecteurs de test communs qui prouvent que les deux donnent les mêmes valeurs.

Ce lot corrige le constat E3 de l'audit :
- le core et l'engine utilisent aujourd'hui deux parcours factices différents ;
- le code de production importe des outils de démonstration ;
- l'interpolation de Catmull-Rom imposée par le format n'est implémentée nulle part.

Il traite aussi M9 (parcours en boucle) et la partie « world » de M6 (schémas).

## 2. À lire

1. `docs/lots/00_INDEX.md` (règles communes).
2. `docs/contracts/world_format_v1.md`, en entier, en particulier §2 (manifeste), §3 (repère), §4 (couche route) et §10 (lecture et compatibilité).
3. `docs/SRS_v1.1.md` §5 (physique, fin de parcours) et §12 (test « Route »).
4. Code existant :
   - `core/src/openride_core/session.py` : méthodes `_on_command` et `_step` ;
   - `core/src/openride_core/tools/fake_world.py` ;
   - `core/src/openride_core/tools/fit_demo.py` : classe `LinearRoute` ;
   - `engine/scripts/route_data.gd`.

## 3. Situation actuelle

- `session.py` construit le parcours avec `LinearRoute(build_route(5000.0))`, importés depuis `tools/`, en ignorant `route_id`.
- `engine/scripts/main.gd` lit `res://demo/demo.world/route.json` (4 000 m, généré avec un ancien profil de pente), via `route_data.gd`, qui interpole linéairement.
- `tools/fake_world.py` sait écrire un dossier `.world` (manifeste et `route.json`) avec une projection locale équirectangulaire.

## 4. Travail demandé

### 4.1 Module Python `core/src/openride_core/route.py` (nouveau)

API attendue. Les noms peuvent être ajustés si le rapport l'explique.

```python
class WorldError(Exception):
    code: str          # "route_not_found" ou "route_invalid" (codes du contrat IPC)

@dataclass(frozen=True)
class RouteSample:
    x: float; y: float; z: float          # repère du monde (y = altitude lissée)
    lat: float; lon: float; alt_m: float
    grade_pct: float; heading_deg: float  # cap dans [0, 360)

class Route:
    length_m: float; n: int; ds_m: float; type: str   # "open", "loop", "out_and_back"
    def wrap(self, s: float) -> float: ...            # boucle : s modulo longueur ; sinon borné à [0, longueur]
    def sample(self, s: float) -> RouteSample: ...
    def grade_at(self, s: float) -> float: ...        # raccourci rapide pour la boucle à 50 Hz

@dataclass
class World:
    path: Path; manifest: dict; route: Route

def routes_dir() -> Path: ...                         # ~/.local/share/openride/routes (config.ROUTES_DIR)
def load_world(path: Path) -> World: ...
def find_world(route_id: str, root: Path | None = None) -> Path: ...   # <root>/<route_id>.world
```

**Validation au chargement** (format §10). Toute violation lève `WorldError("route_invalid")`, avec un message précis. Un dossier absent lève `WorldError("route_not_found")`.
- `manifest.json` présent ; `format` = `openride-world` ; majeur de `format_version` ≤ 1.
- `route.json` présent ; chaque tableau a exactement `n` valeurs ; `n ≥ 2`.
- Les abscisses `s_i` sont strictement croissantes. Le dernier point est à `length_m`, à 1 cm près.
- Pour un parcours `loop`, le dernier point coïncide avec le premier, à 1 m près.
- Les champs inconnus sont ignorés.

**Interpolation : règle exacte, à recopier dans le format (§4.5).**

- **Abscisses des points :** `s_i = i × ds_m` pour `i < n − 1`, et `s_{n−1} = length_m`.
- **Segment courant :** pour une position `s` (déjà passée par `wrap`), on prend le segment `[i, i+1]` qui contient `s`. Au point final, `i = n − 2`. On note `u = (s − s_i) / (s_{i+1} − s_i)`, dans `[0, 1]`.
- **Grandeurs scalaires** (`grade_pct`, `lat`, `lon`, `alt_m`) : interpolation linéaire en `u`.
- **Cap :** `h_i + u × d`, où `d` est l'écart le plus court entre `h_i` et `h_{i+1}`, dans ]−180, 180]. Le résultat est ramené dans [0, 360).
- **Position** `(x, alt_m, z)` : spline de Catmull-Rom centripète (Barry-Goldman, α = 0,5) sur les points `P_{i−1}, P_i, P_{i+1}, P_{i+2}`, la distance étant mesurée en 3D :
  - nœuds : `t0 = 0`, `t1 = t0 + |P_i − P_{i−1}|^0,5`, `t2 = t1 + |P_{i+1} − P_i|^0,5`, `t3 = t2 + |P_{i+2} − P_{i+1}|^0,5`. Toute distance inférieure à 1e-6 m est remplacée par 1e-6 m ;
  - paramètre : `t = t1 + u × (t2 − t1)` ;
  - calcul :
    ```
    A1 = (t1−t)/(t1−t0)·P_{i−1} + (t−t0)/(t1−t0)·P_i
    A2 = (t2−t)/(t2−t1)·P_i     + (t−t1)/(t2−t1)·P_{i+1}
    A3 = (t3−t)/(t3−t2)·P_{i+1} + (t−t2)/(t3−t2)·P_{i+2}
    B1 = (t2−t)/(t2−t0)·A1 + (t−t0)/(t2−t0)·A2
    B2 = (t3−t)/(t3−t1)·A2 + (t−t1)/(t3−t1)·A3
    C  = (t2−t)/(t2−t1)·B1 + (t−t1)/(t2−t1)·B2
    ```
  - **extrémités d'un parcours ouvert :** points fantômes `P_{−1} = 2·P_0 − P_1` et `P_n = 2·P_{n−1} − P_{n−2}` ;
  - **parcours en boucle :** les indices tournent sur les `n − 1` points distincts. Le voisin avant `P_0` est `P_{n−2}` ; le voisin après `P_{n−1}` (= `P_0`) est `P_1`.
- **`out_and_back`** se lit comme `open` : le compilateur écrit déjà la géométrie complète, aller et retour.
- **Hors bornes :** `wrap` borne `s` à `[0, length_m]` pour `open` et `out_and_back`. Pour `loop`, il le ramène modulo `length_m`.

**Performance.** `grade_at` doit coûter moins de 20 µs par appel en Python 3.11 sur un parcours de 3 000 points (accès indexé direct, sans recherche linéaire).

### 4.2 Vecteurs de test partagés

- **Générateur :** `core/src/openride_core/tools/route_vectors.py` (nouveau) crée `docs/contracts/world/route_test_vectors.json`. Le fichier généré est versionné.
- **Contenu :**
  - un petit parcours ouvert d'environ 12 points, avec virages, montée et descente, et un dernier segment plus court que `ds_m` ;
  - un petit parcours en boucle ;
  - pour chacun, une liste de valeurs de `s` : 0 ; exactement sur des points ; au milieu de segments ; dans le dernier segment court ; `length_m` ; au-delà des bornes ; et, pour la boucle, au-delà d'un tour ;
  - pour chaque valeur, les résultats attendus de `sample(s)`.
- **Source de vérité :** l'implémentation Python. Les valeurs sont écrites avec au moins 9 chiffres significatifs.

### 4.3 Schémas JSON (`docs/contracts/world/`, nouveau dossier)

- `manifest.schema.json` et `route.schema.json` (JSON Schema 2020-12), conformes à `world_format_v1.md` §2, §4 et §11.
- Un test Python valide contre ces schémas : `demo.world`, les parcours des vecteurs de test, et l'exemple de manifeste du format §11.

### 4.4 Parcours de démonstration unique

- `tools/fake_world.py` garde son générateur, mais écrit désormais le parcours de démonstration (5 000 m, profil doux actuel de `build_route`) sous le nom `demo`.
- Le core crée `<routes_dir>/demo.world` s'il manque, au premier `select_route` de `demo`.
- Régénérer `engine/demo/demo.world/` avec **exactement** le même contenu. L'engine lit toujours ce dossier jusqu'au lot D ; ensuite il lira le parcours par `route_id`.

### 4.5 Intégration au core

**Dans `session.py` :**
- supprimer les imports `tools.fake_world` et `tools.fit_demo` ;
- sur `select_route` : passer en `LOADING`, charger `find_world(route_id)` avec `load_world`, puis passer en `READY`. Remplir `route_id` et `route_length_m`.
- en cas de `WorldError` : envoyer l'erreur `error` du contrat (`route_not_found` ou `route_invalid`) et revenir à l'état précédent ;
- dans `_step` :
  - utiliser `route.sample(route.wrap(s))` pour la pente, l'altitude et la position, et `route.grade_at(...)` pour la pente anticipée ;
  - `physics.s` reste la distance cumulée, utilisée par le journal et le FIT ;
  - pour un parcours `loop`, la séance ne s'arrête pas en fin de route ;
  - pour `open`, elle s'arrête à `s ≥ length_m`, comme aujourd'hui.

**Ailleurs :**
- `tools/fit_demo.py` utilise `route.Route` au lieu de `LinearRoute`. Supprimer `LinearRoute`.
- `--autostart` (dans `session.py`) continue de fonctionner avec `route_id` = `demo`.

### 4.6 Engine

- `engine/scripts/route_data.gd` :
  - lit `manifest.json` puis `route.json` d'un dossier `.world` donné en paramètre ;
  - applique **la même règle** d'interpolation ;
  - expose `sample_point(s) -> Vector3`, `sample_heading_deg(s) -> float`, `sample_grade(s) -> float`, `wrap(s) -> float`, `length_m`, `type`.
  - Calculer en `float` GDScript (64 bits) et ne convertir en `Vector3` (32 bits) qu'à la fin.
- `engine/scripts/main.gd` : adapter les appels. La caméra prend `deg_to_rad(sample_heading_deg(s))`, avec la même convention de signe qu'aujourd'hui.
- `engine/tests/test_route_vectors.gd` (nouveau) : script lancé par `godot --headless --path engine --script res://tests/test_route_vectors.gd`. Il lit `route_test_vectors.json` (chemin passé en argument, ou relatif au dépôt), compare chaque vecteur et quitte avec le code 0 si tout passe, 1 sinon.
- **Tolérances :** 1 cm sur la position, 1e-4 sur la pente, 1e-3 degré sur le cap.

### 4.7 Clarification du format

Ajouter dans `world_format_v1.md` §4 la règle exacte du §4.1 ci-dessus et le chemin des vecteurs de test. C'est une précision, pas un changement : `format_version` reste 1.0. Ajouter une ligne au journal des changements du document.

## 5. Fichiers concernés

- **Nouveaux :**
  - `core/src/openride_core/route.py`
  - `core/src/openride_core/tools/route_vectors.py`
  - `core/tests/test_route.py`
  - `docs/contracts/world/manifest.schema.json`
  - `docs/contracts/world/route.schema.json`
  - `docs/contracts/world/route_test_vectors.json`
  - `engine/tests/test_route_vectors.gd`
- **Modifiés :**
  - `core/src/openride_core/session.py`
  - `core/src/openride_core/tools/fake_world.py`
  - `core/src/openride_core/tools/fit_demo.py`
  - `core/tests/test_drivers_session.py` (adaptations seulement)
  - `engine/scripts/route_data.gd`
  - `engine/scripts/main.gd`
  - `engine/demo/demo.world/*`
  - `docs/contracts/world_format_v1.md` (§4 et journal)
- **Dépendance de test** autorisée dans `[project.optional-dependencies] dev` : `jsonschema`.

## 6. Modifications de contrat autorisées

- Seulement la clarification de `world_format_v1.md` §4 décrite au §4.7.
- Aucune modification du contrat IPC.

## 7. Critères d'acceptation

1. `pytest` passe en entier dans `core/`.
2. Le parcours passe exactement par ses points : `sample(s_i)` redonne `P_i` à 1e-9 m près, pour tous les `i` des deux parcours de test.
3. **Parcours rectiligne à pente constante** dont le dernier segment est plus court que `ds_m` :
   - toutes les positions restent sur la droite, à 1e-9 m près ;
   - la position est linéaire en `s`, à 1e-9 m près, sur les segments dont les voisins sont espacés de `ds_m`.
   - Près du segment court, la spline centripète avance légèrement à vitesse non uniforme (environ 25 cm d'écart mesuré en préparant ce lot). C'est attendu, et ce n'est pas une erreur.
4. Le chargement d'un `.world` invalide lève `WorldError` avec le bon code, pour chacun de ces cas :
   - dossier absent ;
   - `route.json` absent ;
   - tableau de mauvaise longueur ;
   - majeur de version égal à 2 ;
   - dernier point loin de `length_m` ;
   - boucle non fermée.
5. `grade_at` coûte moins de 20 µs en moyenne sur 100 000 appels, pour 3 000 points (test de performance tolérant, marqué pour pouvoir être sauté sur une machine lente).
6. `godot --headless --path engine --script res://tests/test_route_vectors.gd` quitte avec le code 0 et affiche le nombre de vecteurs vérifiés.
7. Le core et l'engine lisent le même parcours de démonstration. Un test vérifie que `engine/demo/demo.world/route.json` est identique au parcours généré par `fake_world`.
8. Un essai `openride-core run --trainer mock --input none --autostart` de 5 s produit un journal et un FIT, sans erreur dans le log.
9. Sur un parcours `loop` de test, `_step` fait passer `s` au-delà de la longueur sans terminer la séance, et la pente revient à celle du départ.
10. `session.py` n'importe plus rien depuis `tools/`.

## 8. Hors périmètre

- Le compilateur GPX (lot B1).
- La lecture des tuiles de terrain.
- Le choix du parcours par l'engine selon `route_id` (lot D).
- Le rendu en ruban (lot E1).
