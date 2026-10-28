extends RefCounted

## Lecture des couches OpenStreetMap d'un `.world` (Lot K4, Format .world v1 §2, §6, §7, §8, §8 ter et §10),
## sans aucun nœud ni affichage. Le rendu (bâtiments extrudés, forêts, eau, sons) reste au lot E4.
## Pas de class_name : charger par preload("res://scripts/osm_layers.gd").
##
## Règles (format §10) : un champ inconnu est ignoré ; une version majeure supérieure à 1 est refusée ;
## un élément dont un champ obligatoire manque ou est invalide (type, anneau de moins de 3 points,
## `density` hors de [0, 1], `kind` inconnu…) est ignoré et compté dans `ignored`. Un fichier absent
## ou illisible donne `ok = false` et un message dans `error`, jamais une erreur Godot.

const SUPPORTED_MAJOR := 1
const CHUNK_LENGTH_M := 1000.0
const OSM_LAYERS := ["buildings", "vegetation", "poi", "water", "roads"]
const KNOWN_LAYERS := ["terrain", "buildings", "vegetation", "poi", "water", "roads"]

const BUILDING_ROOFS := ["flat", "gabled"]
const VEGETATION_KINDS := ["wood", "scrub", "orchard", "meadow", "farmland", "grassland"]   # 1.5 : terrains ouverts (P22)
const VEGETATION_OPEN_KINDS := ["meadow", "farmland", "grassland"]
const POI_KINDS := ["church_bell", "river", "livestock", "village", "viewpoint", "wind_turbine", "flag"]   # 1.2 : P12
const WATER_LINE_KINDS := ["river", "stream", "canal"]
const WATER_AREA_KINDS := ["lake", "pond", "reservoir"]
const ROAD_KINDS := ["motorway", "trunk", "primary", "secondary", "tertiary", "unclassified", "residential", "track"]   # 1.5 : P22


static func _is_number(v: Variant) -> bool:
	return (typeof(v) == TYPE_INT or typeof(v) == TYPE_FLOAT) and is_finite(float(v))


static func _major(version: Variant) -> int:
	if typeof(version) != TYPE_STRING:
		return -1
	var parts := (version as String).split(".")
	if parts.size() != 2 or not parts[0].is_valid_int() or not parts[1].is_valid_int():
		return -1
	return int(parts[0])


static func _is_point(p: Variant, dims: int) -> bool:
	if typeof(p) != TYPE_ARRAY or (p as Array).size() != dims:
		return false
	for c in p:
		if not _is_number(c):
			return false
	return true


static func _is_ring(ring: Variant) -> bool:
	if typeof(ring) != TYPE_ARRAY or (ring as Array).size() < 3:
		return false
	for p in ring:
		if not _is_point(p, 2):
			return false
	return true


static func _has_rings(item: Dictionary) -> bool:
	if not _is_ring(item.get("outer", null)):
		return false
	var holes = item.get("holes", null)
	if typeof(holes) != TYPE_ARRAY:
		return false
	for h in holes:
		if not _is_ring(h):
			return false
	return true


static func _has_id(item: Dictionary) -> bool:
	var id = item.get("id", null)
	return typeof(id) == TYPE_STRING and not (id as String).is_empty()


static func _valid_building(b: Dictionary) -> bool:
	return _has_id(b) and _has_rings(b) and _is_number(b.get("base_y", null)) \
		and _is_number(b.get("height_m", null)) and float(b["height_m"]) > 0.0 \
		and str(b.get("roof", "")) in BUILDING_ROOFS and typeof(b.get("hint", null)) == TYPE_DICTIONARY


static func _valid_vegetation(a: Dictionary) -> bool:
	var d = a.get("density", null)
	return _has_id(a) and _has_rings(a) and str(a.get("kind", "")) in VEGETATION_KINDS \
		and _is_number(d) and float(d) >= 0.0 and float(d) <= 1.0


static func _valid_poi(p: Dictionary) -> bool:
	var name = p.get("name", null)
	return _has_id(p) and str(p.get("kind", "")) in POI_KINDS and _is_number(p.get("x", null)) \
		and _is_number(p.get("y", null)) and _is_number(p.get("z", null)) \
		and _is_number(p.get("radius_m", null)) and float(p["radius_m"]) > 0.0 \
		and p.has("name") and (name == null or typeof(name) == TYPE_STRING)


static func _valid_water_line(l: Dictionary) -> bool:
	var pts = l.get("points", null)
	if not (_has_id(l) and str(l.get("kind", "")) in WATER_LINE_KINDS and _is_number(l.get("width_m", null))
			and float(l["width_m"]) > 0.0 and typeof(pts) == TYPE_ARRAY and (pts as Array).size() >= 2):
		return false
	for p in pts:
		if not _is_point(p, 3):
			return false
	return true


static func _valid_road(r: Dictionary) -> bool:
	var pts = r.get("points", null)
	var lanes = r.get("lanes", null)
	if not (_has_id(r) and str(r.get("kind", "")) in ROAD_KINDS and _is_number(lanes) and float(lanes) >= 1.0
			and typeof(r.get("oneway", null)) == TYPE_BOOL and _is_number(r.get("speed_kmh", null))
			and float(r["speed_kmh"]) > 0.0 and typeof(pts) == TYPE_ARRAY and (pts as Array).size() >= 2):
		return false
	for p in pts:
		if not _is_point(p, 3):
			return false
	return true


static func _valid_water_area(a: Dictionary) -> bool:
	return _has_id(a) and _has_rings(a) and str(a.get("kind", "")) in WATER_AREA_KINDS \
		and _is_number(a.get("level_y", null))


## Garde les éléments valides de `doc[key]` ; renvoie [éléments, nombre ignoré] ou null si la liste manque.
static func _filter(doc: Dictionary, key: String, valid: Callable) -> Variant:
	var raw = doc.get(key, null)
	if typeof(raw) != TYPE_ARRAY:
		return null
	var kept := []
	var ignored := 0
	for item in raw:
		if typeof(item) == TYPE_DICTIONARY and valid.call(item):
			kept.append(item)
		else:
			ignored += 1
	return [kept, ignored]


static func chunk_path(world_dir: String, layer: String, k: int) -> String:
	return world_dir.path_join(layer).path_join("chunk_%d.json" % k)


## Lit `<layer>/chunk_<k>.json`. Renvoie {ok, items, ignored, error, version} ; pour `water`, aussi
## `lines` et `areas` (items = lines puis areas).
## Monde vivant (lot W10, format §13) : avec `route` vivante, lit à la place les fichiers de carré
## `tile_<ix>_<iz>.json` que touche le tronçon k, coordonnées rendues absolues (voir `load_chunk_live`).
static func load_chunk(world_dir: String, layer: String, k: int, route = null) -> Dictionary:
	if route != null and route.live:
		return load_chunk_live(world_dir, layer, k, route)
	return _load_file(chunk_path(world_dir, layer, k), layer, Vector2.ZERO)


static func tile_path(world_dir: String, layer: String, ix: int, iz: int) -> String:
	return world_dir.path_join(layer).path_join("tile_%d_%d.json" % [ix, iz])


## Marge autour du tronçon de route dans laquelle on lit les carrés d'un monde vivant.
const LIVE_MARGIN_M := 300.0
const TILE_M := 1000.0


## Boîte [xmin, zmin, xmax, zmax] des points de route du tronçon k, élargie de `margin`.
static func chunk_bounds(route, k: int, margin: float) -> Rect2:
	var ds: float = route.ds_m
	var i0 := clampi(floori(k * CHUNK_LENGTH_M / ds), 0, route.n - 1)
	var i1 := clampi(ceili((k + 1) * CHUNK_LENGTH_M / ds), 0, route.n - 1)
	var r := Rect2(route.x[i0], route.z[i0], 0.0, 0.0)
	for i in range(i0, i1 + 1):
		r = r.expand(Vector2(route.x[i], route.z[i]))
	return r.grow(margin)


static func _tiles_of_rect(r: Rect2) -> Array:
	var out := []
	for ix in range(floori(r.position.x / TILE_M), floori(r.end.x / TILE_M) + 1):
		for iz in range(floori(r.position.y / TILE_M), floori(r.end.y / TILE_M) + 1):
			out.append(Vector2i(ix, iz))
	return out


## Carrés à lire pour le tronçon k : ceux que touche sa boîte, sauf ceux déjà confiés à un tronçon
## plus bas (un carré n'est affiché qu'une fois, par le premier tronçon qui le touche).
static func chunk_tiles(route, k: int) -> Array:
	var out := []
	var earlier := []
	for kk in range(k):
		earlier.append(_tiles_of_rect(chunk_bounds(route, kk, LIVE_MARGIN_M)))
	var taken := {}
	for e in earlier:
		for t in e:
			taken[t] = true
	for t in _tiles_of_rect(chunk_bounds(route, k, LIVE_MARGIN_M)):
		if not taken.has(t):
			out.append(t)
	return out


## Monde vivant : fusionne les carrés du tronçon k. Un carré absent est ignoré (il n'est pas encore
## prêt) ; `ok` est vrai si au moins un carré a été lu ou si aucun n'était attendu.
static func load_chunk_live(world_dir: String, layer: String, k: int, route) -> Dictionary:
	var res := {"ok": true, "items": [], "ignored": 0, "error": "", "version": "1.0"}
	if layer == "water":
		res["lines"] = []
		res["areas"] = []
	for t in chunk_tiles(route, k):
		var path := tile_path(world_dir, layer, t.x, t.y)
		if not FileAccess.file_exists(path):
			continue
		var one := _load_file(path, layer, Vector2(t.x * TILE_M, t.y * TILE_M))
		if not one["ok"]:
			res["error"] = one["error"]
			continue
		(res["items"] as Array).append_array(one["items"])
		res["ignored"] = int(res["ignored"]) + int(one["ignored"])
		if layer == "water":
			(res["lines"] as Array).append_array(one["lines"])
			(res["areas"] as Array).append_array(one["areas"])
	return res


static func _shift_ring(ring: Variant, off: Vector2) -> void:
	if typeof(ring) != TYPE_ARRAY:
		return
	for p in ring:
		if typeof(p) == TYPE_ARRAY and (p as Array).size() >= 2 and _is_number(p[0]) and _is_number(p[1]):
			p[0] = float(p[0]) + off.x
			p[1] = float(p[1]) + off.y


## Coordonnées horizontales relatives au coin de tuile -> repère de la séance (format §13) ;
## les altitudes restent telles quelles.
static func _make_absolute(doc: Dictionary, layer: String, off: Vector2) -> void:
	match layer:
		"buildings", "vegetation":
			var raw = doc.get("buildings" if layer == "buildings" else "areas", [])
			if typeof(raw) != TYPE_ARRAY:
				return
			for item in raw:
				if typeof(item) != TYPE_DICTIONARY:
					continue
				_shift_ring(item.get("outer", null), off)
				var holes = item.get("holes", null)
				if typeof(holes) == TYPE_ARRAY:
					for h in holes:
						_shift_ring(h, off)
		"poi":
			var pts = doc.get("points", [])
			if typeof(pts) != TYPE_ARRAY:
				return
			for p in pts:
				if typeof(p) == TYPE_DICTIONARY and _is_number(p.get("x", null)) and _is_number(p.get("z", null)):
					p["x"] = float(p["x"]) + off.x
					p["z"] = float(p["z"]) + off.y
		"water", "roads":
			var lines = doc.get("lines", [])
			if typeof(lines) == TYPE_ARRAY:
				for l in lines:
					if typeof(l) == TYPE_DICTIONARY:
						_shift_ring(l.get("points", null), off)
			var areas = doc.get("areas", [])
			if typeof(areas) == TYPE_ARRAY:
				for a in areas:
					if typeof(a) != TYPE_DICTIONARY:
						continue
					_shift_ring(a.get("outer", null), off)
					var holes = a.get("holes", null)
					if typeof(holes) == TYPE_ARRAY:
						for h in holes:
							_shift_ring(h, off)


static func _load_file(path: String, layer: String, offset: Vector2) -> Dictionary:
	var res := {"ok": false, "items": [], "ignored": 0, "error": "", "version": ""}
	if not layer in OSM_LAYERS:
		res["error"] = "couche inconnue : " + layer
		return res
	if not FileAccess.file_exists(path):
		res["error"] = "fichier absent : " + path
		return res
	var f := FileAccess.open(path, FileAccess.READ)
	if f == null:
		res["error"] = "fichier illisible : %s (%s)" % [path, error_string(FileAccess.get_open_error())]
		return res
	var json := JSON.new()
	if json.parse(f.get_as_text()) != OK:
		res["error"] = "JSON invalide dans %s, ligne %d : %s" % [path, json.get_error_line(), json.get_error_message()]
		return res
	var doc = json.data
	if typeof(doc) != TYPE_DICTIONARY:
		res["error"] = "objet JSON attendu dans " + path
		return res
	var major := _major(doc.get("version", null))
	res["version"] = str(doc.get("version", ""))
	if major < 0:
		res["error"] = "version absente ou mal formée dans %s : %s" % [path, res["version"]]
		return res
	if major > SUPPORTED_MAJOR:
		res["error"] = "version %s non prise en charge dans %s (majeur %d au plus)" % [res["version"], path, SUPPORTED_MAJOR]
		return res
	if offset != Vector2.ZERO:
		_make_absolute(doc, layer, offset)
	match layer:
		"buildings", "vegetation", "poi", "roads":
			var key: String = {"buildings": "buildings", "vegetation": "areas", "poi": "points", "roads": "lines"}[layer]
			var valid: Callable = {"buildings": _valid_building, "vegetation": _valid_vegetation, "poi": _valid_poi,
				"roads": _valid_road}[layer]
			var got = _filter(doc, key, valid)
			if got == null:
				res["error"] = "liste « %s » absente dans %s" % [key, path]
				return res
			res["items"] = got[0]
			res["ignored"] = got[1]
		"water":
			var lines = _filter(doc, "lines", _valid_water_line)
			var areas = _filter(doc, "areas", _valid_water_area)
			if lines == null or areas == null:
				res["error"] = "listes « lines » et « areas » attendues dans " + path
				return res
			res["lines"] = lines[0]
			res["areas"] = areas[0]
			res["items"] = lines[0] + areas[0]
			res["ignored"] = lines[1] + areas[1]
	res["ok"] = true
	return res


## Couches connues dont `present` est vrai dans le manifeste (couches inconnues ignorées, §10) ;
## [] si le manifeste a un `format_version` de majeur supérieur à 1.
static func layers_present(manifest: Dictionary) -> Array:
	var out := []
	if _major(manifest.get("format_version", "1.0")) > SUPPORTED_MAJOR:
		return out
	var layers = manifest.get("layers", {})
	if typeof(layers) != TYPE_DICTIONARY:
		return out
	for name in KNOWN_LAYERS:
		var info = layers.get(name, null)
		if typeof(info) == TYPE_DICTIONARY and info.get("present", false) == true:
			out.append(name)
	return out


## Tronçons de 1 km (k = floor(s / 1000), comme le compilateur) qui couvrent la fenêtre [s_from ; s_to],
## dans l'ordre de parcours. Parcours ouvert : fenêtre bornée à [0 ; longueur]. Boucle : fenêtre ramenée
## modulo la longueur, traversée de l'arrivée comprise ; tous les tronçons si elle dépasse un tour.
## Le dernier indice est floor(longueur / 1000) : le compilateur y range ce qui est le plus près du
## tout dernier point de la route.
static func chunks_for_window(s_from: float, s_to: float, route) -> Array[int]:
	var out: Array[int] = []
	if route == null or route.n < 2 or not is_finite(s_from) or not is_finite(s_to):
		return out
	if s_to < s_from:
		var tmp := s_from
		s_from = s_to
		s_to = tmp
	var length: float = route.length_m
	var last_k := int(floor(length / CHUNK_LENGTH_M))
	var spans := []
	if not route.is_loop():
		var a := clampf(s_from, 0.0, length)
		var b := clampf(s_to, 0.0, length)
		spans.append([a, b])
	elif s_to - s_from >= length:
		spans.append([0.0, length])
	else:
		var a: float = fposmod(s_from, length)
		var b: float = a + (s_to - s_from)
		if b <= length:
			spans.append([a, b])
		else:
			spans.append([a, length])
			spans.append([0.0, b - length])
	for span in spans:
		var k0 := int(floor(span[0] / CHUNK_LENGTH_M))
		var k1 := mini(int(floor(span[1] / CHUNK_LENGTH_M)), last_k)
		for k in range(k0, k1 + 1):
			if not out.has(k):
				out.append(k)
	return out
