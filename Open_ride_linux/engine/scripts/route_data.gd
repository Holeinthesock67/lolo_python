extends RefCounted

## Lecture d'un parcours compilé `.world` et interpolation de sa couche route (Format .world v1).
##
## Traduction exacte de `core/src/openride_core/route.py` ; les deux sont tenues identiques par
## `docs/contracts/world/route_test_vectors.json` (test : engine/tests/unit/test_route_vectors.gd).
## Règle (format §4.5) : scalaires linéaires, cap par l'écart le plus court, position par
## Catmull-Rom centripète (α = 0,5) ; points fantômes aux extrémités, indices circulaires en boucle.
## Les calculs se font en float 64 bits ; seule la sortie Vector3 est en 32 bits.
## Pas de class_name : la scène est lancée sans passer par l'éditeur (charger par preload).

const FORMAT_NAME := "openride-world"
const SUPPORTED_MAJOR := 1
const KNOT_EPS_M := 1e-6

var version: String = "1.0"
var ds_m: float = 10.0
var n: int = 0
var length_m: float = 0.0
var type: String = "open"
var load_error: String = ""

var s: PackedFloat64Array = PackedFloat64Array()
var lat: PackedFloat64Array = PackedFloat64Array()
var lon: PackedFloat64Array = PackedFloat64Array()
var alt_m: PackedFloat64Array = PackedFloat64Array()
var x: PackedFloat64Array = PackedFloat64Array()
var z: PackedFloat64Array = PackedFloat64Array()
var grade_pct: PackedFloat64Array = PackedFloat64Array()
var heading_deg: PackedFloat64Array = PackedFloat64Array()


# --- chargement --------------------------------------------------------------------------

func _fail(message: String) -> bool:
	load_error = message
	push_error("Parcours invalide : " + message)
	return false


func _read_json(path: String) -> Variant:
	if not FileAccess.file_exists(path):
		return null
	var text := FileAccess.get_file_as_string(path)
	return JSON.parse_string(text)


## Charge un dossier `.world` (manifeste puis couche route). Renvoie vrai si tout est valide.
func load_world_dir(world_dir: String) -> bool:
	var manifest = _read_json(world_dir.path_join("manifest.json"))
	if typeof(manifest) != TYPE_DICTIONARY:
		return _fail("manifest.json absent ou illisible dans " + world_dir)
	if manifest.get("format", "") != FORMAT_NAME:
		return _fail("format inattendu : " + str(manifest.get("format", "")))
	var major := int(str(manifest.get("format_version", "0")).split(".")[0])
	if major > SUPPORTED_MAJOR:
		return _fail("format_version trop récent : " + str(manifest.get("format_version")))
	var route_info = manifest.get("route", {})
	var route_file: String = "route.json"
	if typeof(route_info) == TYPE_DICTIONARY:
		route_file = str(route_info.get("file", "route.json"))
	var data = _read_json(world_dir.path_join(route_file))
	if typeof(data) != TYPE_DICTIONARY:
		return _fail(route_file + " absent ou illisible dans " + world_dir)
	return load_route_dict(data)


func _column(data: Dictionary, key: String) -> PackedFloat64Array:
	var out := PackedFloat64Array()
	var raw = data.get(key, [])
	if typeof(raw) != TYPE_ARRAY:
		return out
	for value in raw:
		out.append(float(value))
	return out


## Charge le contenu d'un `route.json` déjà lu. Renvoie vrai si tout est valide.
func load_route_dict(data: Dictionary) -> bool:
	version = str(data.get("version", "1.0"))
	ds_m = float(data.get("ds_m", 0.0))
	n = int(data.get("n", 0))
	length_m = float(data.get("length_m", 0.0))
	type = str(data.get("type", "open"))
	if n < 2 or ds_m <= 0.0:
		return _fail("n ou ds_m invalide")
	lat = _column(data, "lat")
	lon = _column(data, "lon")
	alt_m = _column(data, "alt_m")
	x = _column(data, "x")
	z = _column(data, "z")
	grade_pct = _column(data, "grade_pct")
	heading_deg = _column(data, "heading_deg")
	for col in [lat, lon, alt_m, x, z, grade_pct, heading_deg]:
		if col.size() != n:
			return _fail("une colonne n'a pas n valeurs")
	var last_regular := (n - 2) * ds_m
	if not (last_regular < length_m and length_m <= last_regular + ds_m + 0.01):
		return _fail("length_m incohérent avec n et ds_m")
	if not (type in ["open", "loop", "out_and_back"]):
		return _fail("type de parcours inconnu : " + type)
	s = PackedFloat64Array()
	for i in range(n - 1):
		s.append(i * ds_m)
	s.append(length_m)
	if type == "loop" and Vector2(x[0] - x[n - 1], z[0] - z[n - 1]).length() > 1.0:
		return _fail("boucle non fermée")
	load_error = ""
	return true


# --- interpolation -----------------------------------------------------------------------

func is_loop() -> bool:
	return type == "loop"


## Boucle : s modulo la longueur ; sinon s borné à [0, longueur]. (« wrap » est déjà une fonction globale de Godot.)
func wrap_s(pos: float) -> float:
	if is_loop():
		return fposmod(pos, length_m)
	return clampf(pos, 0.0, length_m)


## [indice du segment, fraction u] pour une position déjà ramenée par wrap.
func _segment(pos: float) -> Array:
	var i: int = mini(int(pos / ds_m), n - 2)
	var s0: float = s[i]
	var s1: float = s[i + 1]
	var u: float = (pos - s0) / (s1 - s0) if s1 > s0 else 0.0
	return [i, clampf(u, 0.0, 1.0)]


func _point(k: int) -> PackedFloat64Array:
	if is_loop():
		var m := k % (n - 1)
		if m < 0:
			m += n - 1
		return PackedFloat64Array([x[m], alt_m[m], z[m]])
	if k < 0:
		return PackedFloat64Array([2.0 * x[0] - x[1], 2.0 * alt_m[0] - alt_m[1], 2.0 * z[0] - z[1]])
	if k > n - 1:
		var a := n - 1
		var b := n - 2
		return PackedFloat64Array([2.0 * x[a] - x[b], 2.0 * alt_m[a] - alt_m[b], 2.0 * z[a] - z[b]])
	return PackedFloat64Array([x[k], alt_m[k], z[k]])


static func _dist(a: PackedFloat64Array, b: PackedFloat64Array) -> float:
	var dx := a[0] - b[0]
	var dy := a[1] - b[1]
	var dz := a[2] - b[2]
	return sqrt(dx * dx + dy * dy + dz * dz)


static func _knot(a: PackedFloat64Array, b: PackedFloat64Array) -> float:
	return pow(maxf(_dist(a, b), KNOT_EPS_M), 0.5)


static func _lerp3(a: PackedFloat64Array, b: PackedFloat64Array, ta: float, tb: float, t: float) -> PackedFloat64Array:
	var wa := (tb - t) / (tb - ta)
	var wb := (t - ta) / (tb - ta)
	return PackedFloat64Array([wa * a[0] + wb * b[0], wa * a[1] + wb * b[1], wa * a[2] + wb * b[2]])


## Catmull-Rom centripète (Barry-Goldman) entre p1 (u = 0) et p2 (u = 1).
static func catmull_rom(p0: PackedFloat64Array, p1: PackedFloat64Array, p2: PackedFloat64Array,
		p3: PackedFloat64Array, u: float) -> PackedFloat64Array:
	var t0 := 0.0
	var t1 := t0 + _knot(p0, p1)
	var t2 := t1 + _knot(p1, p2)
	var t3 := t2 + _knot(p2, p3)
	var t := t1 + u * (t2 - t1)
	var a1 := _lerp3(p0, p1, t0, t1, t)
	var a2 := _lerp3(p1, p2, t1, t2, t)
	var a3 := _lerp3(p2, p3, t2, t3, t)
	var b1 := _lerp3(a1, a2, t0, t2, t)
	var b2 := _lerp3(a2, a3, t1, t3, t)
	return _lerp3(b1, b2, t1, t2, t)


static func _shortest_delta_deg(a: float, b: float) -> float:
	var d := fposmod(b - a, 360.0)
	return d - 360.0 if d > 180.0 else d


## Échantillon complet : x, y, z (repère du monde), lat, lon, alt_m, grade_pct, heading_deg.
func sample(pos: float) -> Dictionary:
	var seg := _segment(wrap_s(pos))
	var i: int = seg[0]
	var u: float = seg[1]
	var p := catmull_rom(_point(i - 1), _point(i), _point(i + 1), _point(i + 2), u)
	var h0: float = heading_deg[i]
	return {
		"x": p[0], "y": p[1], "z": p[2],
		"lat": lat[i] + (lat[i + 1] - lat[i]) * u,
		"lon": lon[i] + (lon[i + 1] - lon[i]) * u,
		"alt_m": alt_m[i] + (alt_m[i + 1] - alt_m[i]) * u,
		"grade_pct": grade_pct[i] + (grade_pct[i + 1] - grade_pct[i]) * u,
		"heading_deg": fposmod(h0 + u * _shortest_delta_deg(h0, heading_deg[i + 1]), 360.0),
	}


func sample_point(pos: float) -> Vector3:
	var smp := sample(pos)
	return Vector3(smp["x"], smp["y"], smp["z"])


func sample_heading_deg(pos: float) -> float:
	return sample(pos)["heading_deg"]


func sample_grade(pos: float) -> float:
	var seg := _segment(wrap_s(pos))
	var i: int = seg[0]
	var u: float = seg[1]
	return grade_pct[i] + (grade_pct[i + 1] - grade_pct[i]) * u
