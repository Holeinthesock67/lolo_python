extends RefCounted

## Lecture d'un parcours compilé `.world` et interpolation de sa couche route (Format .world v1).
##
## Traduction exacte de `core/src/openride_core/route.py` ; les deux sont tenues identiques par
## `docs/contracts/world/route_test_vectors.json` (test : engine/tests/unit/test_route_vectors.gd).
## Règle (format §4.5) : scalaires linéaires, cap par l'écart le plus court, position par
## Catmull-Rom centripète (α = 0,5) ; points fantômes aux extrémités, indices circulaires en boucle.
## Les calculs se font en float 64 bits ; seule la sortie Vector3 est en 32 bits.
## Couche facultative `segments.json` (format 1.3, §8 bis, lot T8) : lue si le manifeste la déclare,
## dans `segments` (dictionnaires `{id, name, type, s_start, s_end, length_m, avg_grade_pct, gain_m,
## category}`, triés par `s_start`) ; absente ou invalide : aucun segment, la route reste chargée.
## Relief affiché (lot Q2, amplifié au lot Y15) : `relief_k` multiplie l'écart d'altitude au départ du parcours,
## `display_y(alt)` = alt_m[0] + (alt − alt_m[0]) × relief_k. `sample()["y"]` et `sample_point()` donnent cette
## hauteur affichée : route, caméra, avatar, bots, décor et terrain la suivent tous de la même façon. `alt_m` et
## `grade_pct` restent les vraies valeurs (HUD, profil, physique du core).
## Pas de class_name : la scène est lancée sans passer par l'éditeur (charger par preload).

const FORMAT_NAME := "openride-world"
const SUPPORTED_MAJOR := 1
const KNOT_EPS_M := 1e-6
const SEGMENTS_MAJOR := 1
const MAX_SEGMENTS := 200
const SEGMENT_TYPES := ["sprint", "climb"]

var version: String = "1.0"
var ds_m: float = 10.0
var n: int = 0
var length_m: float = 0.0
var type: String = "open"
var load_error: String = ""
## Vrai : un refus de chargement n'écrit pas dans le journal d'erreurs de Godot (essais de refus).
var quiet_errors := false

var s: PackedFloat64Array = PackedFloat64Array()
var lat: PackedFloat64Array = PackedFloat64Array()
var lon: PackedFloat64Array = PackedFloat64Array()
var alt_m: PackedFloat64Array = PackedFloat64Array()
var x: PackedFloat64Array = PackedFloat64Array()
var z: PackedFloat64Array = PackedFloat64Array()
var grade_pct: PackedFloat64Array = PackedFloat64Array()
var heading_deg: PackedFloat64Array = PackedFloat64Array()
var relief_k := 1.0                 # exagération visuelle du relief (`--visual-grade`), 1,0 : relief réel

var segments: Array = []            # couche segments (série T) ; vide sans couche
var segments_present := false       # couche déclarée et valide : seule source des montées du décor
var segments_error: String = ""


# --- chargement --------------------------------------------------------------------------

func _fail(message: String) -> bool:
	load_error = message
	if not quiet_errors:
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
	if manifest.get("live", false) == true:
		return load_live_dir(world_dir)          # monde vivant (§13) : même chargement quel que soit l'identifiant
	var route_info = manifest.get("route", {})
	var route_file: String = "route.json"
	if typeof(route_info) == TYPE_DICTIONARY:
		route_file = str(route_info.get("file", "route.json"))
	var data = _read_json(world_dir.path_join(route_file))
	if typeof(data) != TYPE_DICTIONARY:
		return _fail(route_file + " absent ou illisible dans " + world_dir)
	if not load_route_dict(data):
		return false
	_load_segments_layer(world_dir, manifest)
	return true


## Couche `segments` déclarée par le manifeste (`layers.segments.present`) ; un fichier invalide est
## ignoré avec un message dans la console.
func _load_segments_layer(world_dir: String, manifest: Dictionary) -> void:
	segments = []
	segments_present = false
	segments_error = ""
	var layers = manifest.get("layers", {})
	var info = layers.get("segments", {}) if typeof(layers) == TYPE_DICTIONARY else {}
	if typeof(info) != TYPE_DICTIONARY or not bool(info.get("present", false)):
		return
	var file := str(info.get("file", "segments.json"))
	if not load_segments_dict(_read_json(world_dir.path_join(file))):
		print("Couche segments ignorée (%s) : %s" % [world_dir.path_join(file), segments_error])


## Contenu d'un `segments.json` déjà lu (route chargée avant). Renvoie vrai s'il est valide.
func load_segments_dict(data: Variant) -> bool:
	segments = []
	segments_present = false
	segments_error = ""
	if typeof(data) != TYPE_DICTIONARY or typeof(data.get("segments")) != TYPE_ARRAY:
		segments_error = "fichier absent ou illisible"
		return false
	var major := int(str(data.get("version", "0")).split(".")[0])
	if major != SEGMENTS_MAJOR:
		segments_error = "version de couche inconnue : " + str(data.get("version"))
		return false
	var raw: Array = data["segments"]
	if raw.size() > MAX_SEGMENTS:
		segments_error = "plus de %d segments" % MAX_SEGMENTS
		return false
	var out: Array = []
	var ids := {}
	for i in range(raw.size()):
		var seg = raw[i]
		var why := _segment_problem(seg, ids)
		if why != "":
			segments_error = "segment %d : %s" % [i + 1, why]
			return false
		ids[str(seg["id"])] = true
		var cat = seg.get("category")
		out.append({
			"id": str(seg["id"]), "name": str(seg.get("name", seg["id"])).left(48), "type": str(seg["type"]),
			"s_start": float(seg["s_start"]), "s_end": float(seg["s_end"]),
			"length_m": float(seg.get("length_m", float(seg["s_end"]) - float(seg["s_start"]))),
			"avg_grade_pct": float(seg.get("avg_grade_pct", 0.0)), "gain_m": float(seg.get("gain_m", 0.0)),
			"category": null if cat == null else str(cat),
		})
	out.sort_custom(func(a, b): return float(a["s_start"]) < float(b["s_start"]))
	segments = out
	segments_present = true
	return true


func _segment_problem(seg: Variant, ids: Dictionary) -> String:
	if typeof(seg) != TYPE_DICTIONARY:
		return "pas un objet"
	if typeof(seg.get("id")) != TYPE_STRING or str(seg["id"]).is_empty():
		return "identifiant manquant"
	if ids.has(str(seg["id"])):
		return "identifiant en double " + str(seg["id"])
	if not (str(seg.get("type", "")) in SEGMENT_TYPES):
		return "type inconnu " + str(seg.get("type", ""))
	for key in ["s_start", "s_end"]:
		if not (typeof(seg.get(key)) in [TYPE_INT, TYPE_FLOAT]):
			return key + " manquant"
	var s0 := float(seg["s_start"])
	var s1 := float(seg["s_end"])
	if not (0.0 <= s0 and s0 < s1 and s1 <= length_m + 0.01):
		return "%.0f–%.0f m hors du parcours" % [s0, s1]
	return ""


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


# --- monde vivant (lot W10, format §13) -------------------------------------------------

## Monde vivant : route assemblée à partir de `route/part_<k>.json` (parties de 1 km, bord partagé).
var live := false
var live_dir := ""
## Parties lues, dans l'ordre ; les parties non relues d'une révision à l'autre restent le même objet.
var parts: Array = []


## Lit les parties `from_part`, `from_part + 1`… jusqu'à la première absente. Sans accès à l'objet :
## utilisable dans une tâche de fond. Renvoie {ok, parts, error}.
static func read_parts(world_dir: String, from_part: int) -> Dictionary:
	var out := []
	var k := from_part
	while true:
		var path := world_dir.path_join("route").path_join("part_%d.json" % k)
		if not FileAccess.file_exists(path):
			break
		var data = JSON.parse_string(FileAccess.get_file_as_string(path))
		if typeof(data) != TYPE_DICTIONARY or not (data.get("n", 0) is int or data.get("n", 0) is float) \
				or int(data.get("n", 0)) < 2:
			return {"ok": false, "parts": [], "error": "partie %d illisible dans %s" % [k, world_dir]}
		out.append(data)
		k += 1
	return {"ok": true, "parts": out, "error": ""}


## Charge un dossier `live` (manifeste `live: true`, puis toutes les parties).
func load_live_dir(world_dir: String) -> bool:
	var manifest = _read_json(world_dir.path_join("manifest.json"))
	if typeof(manifest) != TYPE_DICTIONARY or manifest.get("format", "") != FORMAT_NAME:
		return _fail("manifest.json absent ou inattendu dans " + world_dir)
	if manifest.get("live", false) != true:
		return _fail("monde non vivant : " + world_dir)
	live_dir = world_dir
	live = true
	parts = []
	return reload_from_part(0)


## Remplace les parties à partir de `k` par celles du disque (lecture synchrone ; `live_world.gd` fait la
## lecture en tâche de fond avec `read_parts`, puis appelle `replace_parts`).
func reload_from_part(k: int) -> bool:
	var res := read_parts(live_dir, k)
	if not res["ok"]:
		return _fail(res["error"])
	return replace_parts(k, res["parts"])


## Nouvelle route (objet neuf, lisible depuis un autre fil) : parties 0 à k − 1 de celle-ci, mêmes objets, puis
## `new_parts`. Renvoie null si l'assemblage est invalide (`load_error` de celle-ci le dit) ; celle-ci ne change pas.
func revised_from(k: int, new_parts: Array):
	var fresh = get_script().new()
	fresh.live = true
	fresh.live_dir = live_dir
	fresh.quiet_errors = quiet_errors
	fresh.relief_k = relief_k
	fresh.parts = parts.duplicate()
	if not fresh.replace_parts(k, new_parts):
		load_error = fresh.load_error
		return null
	return fresh


## Garde les parties 0 à k − 1 (mêmes objets) et prend `new_parts` pour la suite, puis réassemble les colonnes.
## Si la nouvelle route est invalide, l'ancienne reste en place.
func replace_parts(k: int, new_parts: Array) -> bool:
	if k < 0 or k > parts.size():
		return _fail("partie %d demandée, %d connues" % [k, parts.size()])
	var merged: Array = parts.slice(0, k) + new_parts
	var res := _assemble(merged)
	if not res["ok"]:
		return _fail(res["error"])
	var old_parts := parts
	var saved := [version, ds_m, n, length_m, type, s, lat, lon, alt_m, x, z, grade_pct, heading_deg]
	if not load_route_dict(res["route"]):
		parts = old_parts
		version = saved[0]; ds_m = saved[1]; n = saved[2]; length_m = saved[3]; type = saved[4]
		s = saved[5]; lat = saved[6]; lon = saved[7]; alt_m = saved[8]; x = saved[9]; z = saved[10]
		grade_pct = saved[11]; heading_deg = saved[12]
		return false
	parts = merged
	return true


const COLUMN_KEYS := ["lat", "lon", "alt_m", "x", "z", "grade_pct", "heading_deg"]


## Colonnes d'une route unique à partir des parties : le premier point de chaque partie suivante
## (bord partagé) est omis ; `s0_m` de chaque partie doit tomber sur la fin de la précédente.
static func _assemble(all_parts: Array) -> Dictionary:
	if all_parts.is_empty():
		return {"ok": false, "error": "aucune partie de route"}
	var route := {"version": "1.0", "type": "open", "ds_m": float(all_parts[0].get("ds_m", 0.0))}
	var cols := {}
	for key in COLUMN_KEYS:
		cols[key] = []
	var end_s := 0.0
	for i in range(all_parts.size()):
		var part: Dictionary = all_parts[i]
		var count := int(part.get("n", 0))
		if i > 0 and absf(float(part.get("s0_m", -1.0)) - end_s) > 1e-6:
			return {"ok": false, "error": "partie %d : s0_m ne prolonge pas la partie précédente" % i}
		for key in COLUMN_KEYS:
			var col = part.get(key, [])
			if typeof(col) != TYPE_ARRAY or (col as Array).size() != count:
				return {"ok": false, "error": "partie %d : colonne %s invalide" % [i, key]}
			var from := 0 if i == 0 else 1
			(cols[key] as Array).append_array((col as Array).slice(from))
		end_s = float(part.get("s0_m", 0.0)) + float(part.get("length_m", 0.0))
	for key in COLUMN_KEYS:
		route[key] = cols[key]
	route["n"] = (cols["x"] as Array).size()
	route["length_m"] = end_s
	return {"ok": true, "route": route, "error": ""}


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


## Hauteur affichée d'une altitude réelle (relief exagéré par `relief_k` autour du départ du parcours).
func display_y(alt: float) -> float:
	if relief_k == 1.0 or n == 0:
		return alt
	return alt_m[0] + (alt - alt_m[0]) * relief_k


## Échantillon complet : x, y, z (repère du monde, y à la hauteur affichée), lat, lon, alt_m, grade_pct
## (vraies valeurs), heading_deg.
func sample(pos: float) -> Dictionary:
	var seg := _segment(wrap_s(pos))
	var i: int = seg[0]
	var u: float = seg[1]
	var p := catmull_rom(_point(i - 1), _point(i), _point(i + 1), _point(i + 2), u)
	var h0: float = heading_deg[i]
	return {
		"x": p[0], "y": display_y(p[1]), "z": p[2],
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
