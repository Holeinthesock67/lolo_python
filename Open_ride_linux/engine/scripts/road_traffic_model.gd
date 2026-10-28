extends RefCounted

## Circulation des routes voisines et tracteurs des champs (Lot P25), sans nœud ni effet sur la physique.
## Pas de class_name : charger par preload("res://scripts/road_traffic_model.gd").
##
## Les chemins viennent des tâches de fond d'osm_streamer.gd (`extras.traffic` de `chunk_loaded`) :
## - `road_paths(lines)` : routes de la couche `roads` (format .world 1.5, lot P22) ; chaque route porte un
##   flot de véhicules, un tous les SPACING_M de sa sorte en moyenne, de sortes tirées d'après MIX (que des
##   tracteurs sur une piste) ; chaque véhicule a son sens (un seul sens sur une voie unique ou un sens
##   unique), sa voie (à droite de son sens, LANE_M de large) et sa couleur. Tous ceux d'une même voie roulent
##   à la même vitesse (celle de la route, ou celle du plus lent, un tracteur), donc ne se rattrapent jamais.
##   Un véhicule parcourt la route puis disparaît pendant SPACING_M avant de revenir à son début ; il grandit
##   sur END_EASE_M à chaque bout au lieu d'apparaître d'un coup.
## - `field_paths(areas, height_at)` : un champ cultivé (`farmland`) de FIELD_MIN_M2 au moins sur
##   FIELD_SHARE porte un tracteur qui le herse : rangs parallèles tous les FIELD_ROW_M, à FIELD_MARGIN_M
##   du bord, dans un sens tiré d'après le champ, parcourus en aller et retour à FIELD_SPEED_MPS, posés
##   sur le sol (`height_at`, tous les FIELD_STEP_M).
## Tout dépend de l'identifiant de la route ou du champ et de l'horloge du modèle : même parcours, même
## circulation. `set_chunk(k, paths)` / `remove_chunk(k)` suivent les tronçons ; `update(cam_pos, dt_s,
## paused)` avance l'horloge (figée en pause), garde au plus `budget` véhicules (`living(preset)
## .distant_vehicles`), les plus proches de la caméra à moins de RANGE_M, triés toutes les RESELECT_S, et
## remplit `vehicles` : {id, kind, color, xform}.

const VegetationPlacer := preload("res://scripts/vegetation_placer.gd")
const FaunaPlacer := preload("res://scripts/fauna_placer.gd")
const TrafficModel := preload("res://scripts/traffic_model.gd")

const RANGE_M := 900.0
const RESELECT_S := 0.5
const LANE_M := 3.2
const END_EASE_M := 6.0
const SPEED_SPREAD := Vector2(0.8, 1.0)   # part de la vitesse de la route, tirée par voie
const MIN_PATH_M := 10.0
const SPACING_M := {
	"motorway": 160.0, "trunk": 200.0, "primary": 300.0, "secondary": 450.0, "tertiary": 650.0,
	"unclassified": 900.0, "residential": 900.0, "track": 2500.0,
}
const MIX := {
	"motorway": {"car_a": 0.35, "car_b": 0.2, "van": 0.15, "truck": 0.2, "bus": 0.05, "moto": 0.05},
	"trunk": {"car_a": 0.35, "car_b": 0.2, "van": 0.15, "truck": 0.2, "bus": 0.05, "moto": 0.05},
	"primary": {"car_a": 0.3, "car_b": 0.3, "van": 0.14, "truck": 0.1, "bus": 0.06, "moto": 0.06, "tractor": 0.04},
	"secondary": {"car_a": 0.3, "car_b": 0.3, "van": 0.14, "truck": 0.1, "bus": 0.06, "moto": 0.06, "tractor": 0.04},
	"tertiary": {"car_a": 0.3, "car_b": 0.3, "van": 0.12, "truck": 0.04, "moto": 0.06, "tractor": 0.18},
	"unclassified": {"car_a": 0.3, "car_b": 0.3, "van": 0.12, "truck": 0.04, "moto": 0.06, "tractor": 0.18},
	"residential": {"car_a": 0.35, "car_b": 0.4, "van": 0.15, "moto": 0.1},
	"track": {"tractor": 1.0},
}
const FIELD_MIN_M2 := 20000.0
const FIELD_SHARE := 0.4
const FIELD_ROW_M := 9.0
const FIELD_MARGIN_M := 8.0
const FIELD_MIN_ROW_M := 30.0
const FIELD_MAX_ROWS := 14
const FIELD_SPEED_MPS := 2.2
const FIELD_STEP_M := 10.0
const FIELD_KIND := "tractor_field"

var budget: int = 0
var clock_s := 0.0
var vehicles: Array = []           # {id, kind, color, xform}
var paths: Dictionary = {}         # k -> Array de chemins
var reselects := 0                 # tris faits (tests)
var _sel: Array = []               # [chemin, indice du véhicule]
var _sel_at := -INF
var _dirty := true


func set_budget(n: int) -> void:
	budget = maxi(0, n)
	_dirty = true


func reset() -> void:
	paths.clear()
	vehicles.clear()
	_sel.clear()
	clock_s = 0.0
	_dirty = true


func set_chunk(k: int, chunk_paths: Array) -> void:
	if chunk_paths.is_empty():
		remove_chunk(k)
		return
	paths[k] = chunk_paths
	_dirty = true


func remove_chunk(k: int) -> void:
	if paths.erase(k):
		_dirty = true


func path_count() -> int:
	var n := 0
	for k in paths:
		n += (paths[k] as Array).size()
	return n


static func _u(h: int) -> float:
	return TrafficModel._u(h)


# --- Chemins (tâches de fond) ---------------------------------------------------------------------------

## Chemins des routes voisines : `lines` de la couche `roads` lue par osm_layers.gd (points [x, z, y]).
static func road_paths(lines: Array) -> Array:
	var out := []
	for l in lines:
		if typeof(l) != TYPE_DICTIONARY or not MIX.has(str(l.get("kind", ""))):
			continue
		var pts := PackedVector3Array()
		for p in l.get("points", []):
			pts.append(Vector3(float(p[0]), float(p[2]), float(p[1])))
		var path := _path(str(l.get("id", "")), str(l["kind"]), pts, int(l.get("lanes", 2)), bool(l.get("oneway", false)),
			float(l.get("speed_kmh", 50.0)) / 3.6)
		if not path.is_empty():
			out.append(path)
	return out


## Chemins des tracteurs des champs : `areas` de la couche `vegetation`, sol donné par `height_at(x, z)`.
static func field_paths(areas: Array, height_at: Callable) -> Array:
	var out := []
	for a in FaunaPlacer._open_areas(areas, ["farmland"]):
		var ring: PackedVector2Array = a["ring"]
		var seed := VegetationPlacer.hash_string("field:" + str(a["id"]))
		if FaunaPlacer._ring_area(ring) < FIELD_MIN_M2 or _u(VegetationPlacer.hash3(seed, 1, 0)) >= FIELD_SHARE:
			continue
		var flat := field_rows(ring, PI * _u(VegetationPlacer.hash3(seed, 2, 0)))
		if flat.size() < 2:
			continue
		var pts := PackedVector3Array()
		for i in range(flat.size() - 1):
			var a2 := flat[i]
			var b2 := flat[i + 1]
			var steps := maxi(1, int(ceil(a2.distance_to(b2) / FIELD_STEP_M)))
			for s in range(steps):
				var p := a2.lerp(b2, float(s) / steps)
				pts.append(Vector3(p.x, float(height_at.call(p.x, p.y)), p.y))
		var last := flat[flat.size() - 1]
		pts.append(Vector3(last.x, float(height_at.call(last.x, last.y)), last.y))
		var path := _path("field:" + str(a["id"]), "field", pts, 1, true, FIELD_SPEED_MPS)
		if not path.is_empty():
			out.append(path)
	return out


## Rangs d'un champ dans le sens `angle` (rad) : points (x, z) du trajet en zigzag, rang après rang.
static func field_rows(ring: PackedVector2Array, angle: float) -> PackedVector2Array:
	var d := Vector2(cos(angle), sin(angle))
	var nrm := Vector2(-d.y, d.x)
	var c := FaunaPlacer._ring_centroid(ring)
	var omin := INF
	var omax := -INF
	for p in ring:
		var o := (p - c).dot(nrm)
		omin = minf(omin, o)
		omax = maxf(omax, o)
	var rows := []
	var o := omin + FIELD_MARGIN_M
	while o <= omax - FIELD_MARGIN_M:
		var base := c + nrm * o
		var span := _row_span(ring, base, d)
		if span.y - span.x - 2.0 * FIELD_MARGIN_M >= FIELD_MIN_ROW_M:
			rows.append([base + d * (span.x + FIELD_MARGIN_M), base + d * (span.y - FIELD_MARGIN_M)])
		o += FIELD_ROW_M
	if rows.size() > FIELD_MAX_ROWS:
		var from := (rows.size() - FIELD_MAX_ROWS) / 2
		rows = rows.slice(from, from + FIELD_MAX_ROWS)
	var out := PackedVector2Array()
	for i in range(rows.size()):
		var r: Array = rows[i]
		if i % 2 == 0:
			out.append(r[0])
			out.append(r[1])
		else:
			out.append(r[1])
			out.append(r[0])
	return out


## Plus long morceau de la droite `o + d·t` dans l'anneau : Vector2(t0, t1), ou (0, 0) si elle ne le coupe pas.
static func _row_span(ring: PackedVector2Array, o: Vector2, d: Vector2) -> Vector2:
	var ts: Array[float] = []
	var n := ring.size()
	for i in range(n):
		var a := ring[i]
		var e := ring[(i + 1) % n] - a
		var den := d.cross(e)
		if absf(den) < 1e-9:
			continue
		var w := a - o
		var s := w.cross(d) / den
		if s >= 0.0 and s < 1.0:
			ts.append(w.cross(e) / den)
	ts.sort()
	var best := Vector2.ZERO
	for k in range(0, ts.size() - 1, 2):
		if ts[k + 1] - ts[k] > best.y - best.x:
			best = Vector2(ts[k], ts[k + 1])
	return best


## Chemin et ses véhicules ; {} s'il est trop court. `kind` : sorte de route, ou `field`.
static func _path(id: String, kind: String, pts: PackedVector3Array, lanes: int, oneway: bool, speed_mps: float) -> Dictionary:
	if pts.size() < 2:
		return {}
	var cum := PackedFloat32Array([0.0])
	var rect := Rect2(Vector2(pts[0].x, pts[0].z), Vector2.ZERO)
	for i in range(1, pts.size()):
		cum.append(cum[i - 1] + pts[i].distance_to(pts[i - 1]))
		rect = rect.expand(Vector2(pts[i].x, pts[i].z))
	var length := cum[cum.size() - 1]
	if length < MIN_PATH_M:
		return {}
	var seed := VegetationPlacer.hash_string(id)
	var path := {"id": id, "kind": kind, "pts": pts, "cum": cum, "length": length, "rect": rect,
		"lanes": maxi(1, lanes), "oneway": oneway, "field": kind == "field", "cars": []}
	if kind == "field":
		path["spacing"] = 0.0
		path["cars"] = [{"id": id + "#0", "kind": FIELD_KIND, "color": int(VegetationPlacer.hash3(seed, 3, 0) % TrafficModel.COLORS),
			"dir": 1, "lateral": 0.0, "phase": _u(VegetationPlacer.hash3(seed, 4, 0)), "speed": speed_mps}]
		return path
	var spacing: float = SPACING_M[kind]
	path["spacing"] = spacing
	var single := oneway or lanes <= 1
	var per_dir := lanes if oneway else maxi(1, lanes / 2)
	var single_dir := 1 if oneway or _u(VegetationPlacer.hash3(seed, 5, 0)) < 0.5 else -1
	var n := maxi(1, int(round((length + spacing) / spacing)))
	var cars := []
	for j in range(n):
		var h := VegetationPlacer.hash3(seed, 10 + j, 0x51)
		var dir := single_dir if single else (1 if _u(h) < 0.5 else -1)
		var lane := mini(per_dir - 1, int(_u(VegetationPlacer._mix(h + 1)) * per_dir))
		var lateral := 0.0
		if oneway:
			lateral = (lane - (lanes - 1) * 0.5) * LANE_M
		elif lanes > 1:
			lateral = (lane + 0.5) * LANE_M
		cars.append({"id": "%s#%d" % [id, j], "kind": _pick(MIX[kind], _u(VegetationPlacer._mix(h + 2))),
			"color": int(VegetationPlacer._mix(h + 3) % TrafficModel.COLORS), "dir": dir, "lane": lane,
			"lateral": lateral, "phase": (j + 0.6 * _u(VegetationPlacer._mix(h + 4))) / n})
	# Une vitesse par voie et par sens : celle de la route, tirée par voie, ou celle du plus lent
	var lane_speed := {}
	for c in cars:
		var key := Vector2i(int(c["dir"]), int(c["lane"]))
		if not lane_speed.has(key):
			lane_speed[key] = speed_mps * lerpf(SPEED_SPREAD.x, SPEED_SPREAD.y,
				_u(VegetationPlacer.hash3(seed, 6 + key.x, key.y)))
		lane_speed[key] = minf(float(lane_speed[key]), TrafficModel.KINDS[c["kind"]]["kmh"].y / 3.6)
	for c in cars:
		c["speed"] = lane_speed[Vector2i(int(c["dir"]), int(c["lane"]))]
	path["cars"] = cars
	return path


static func _pick(mix: Dictionary, u: float) -> String:
	var acc := 0.0
	for k in mix:
		acc += float(mix[k])
		if u < acc:
			return k
	return mix.keys()[mix.size() - 1]


# --- Positions ------------------------------------------------------------------------------------------

## Place du véhicule `j` du chemin à l'horloge `t` : {pos, xform} ; {} s'il est entre deux passages.
static func place(path: Dictionary, j: int, t: float) -> Dictionary:
	var car: Dictionary = path["cars"][j]
	var length: float = path["length"]
	var d := 0.0
	var dir: int = car["dir"]
	var scale := 1.0
	if path["field"]:
		var u := fposmod(float(car["phase"]) * 2.0 * length + float(car["speed"]) * t, 2.0 * length)
		dir = 1
		d = u
		if u > length:
			d = 2.0 * length - u
			dir = -1
	else:
		var period := length + float(path["spacing"])
		var u := fposmod(float(car["phase"]) * period + float(car["speed"]) * t, period)
		if u > length:
			return {}
		d = u if dir == 1 else length - u
		scale = clampf(minf(u, length - u) / END_EASE_M, 0.05, 1.0)
	var cum: PackedFloat32Array = path["cum"]
	var pts: PackedVector3Array = path["pts"]
	var i := clampi(cum.bsearch(d) - 1, 0, pts.size() - 2)
	var seg := maxf(cum[i + 1] - cum[i], 1e-4)
	var p := pts[i].lerp(pts[i + 1], clampf((d - cum[i]) / seg, 0.0, 1.0))
	var f := (pts[i + 1] - pts[i]) * float(dir)
	var fh := Vector2(f.x, f.z)
	if fh.length() < 1e-5:
		fh = Vector2(0.0, -1.0)
	fh = fh.normalized()
	var right := Vector3(-fh.y, 0.0, fh.x)
	p += right * float(car["lateral"])
	var pitch := atan2(f.y, Vector2(f.x, f.z).length())
	var basis := Basis(Vector3.UP, atan2(-fh.x, -fh.y)) * Basis(Vector3.RIGHT, pitch)
	return {"pos": p, "xform": Transform3D(basis.scaled(Vector3.ONE * scale), p)}


func update(cam_pos: Vector3, dt_s: float, paused: bool = false) -> void:
	if not paused:
		clock_s += dt_s
	if _dirty or clock_s - _sel_at >= RESELECT_S - 1e-6 or clock_s < _sel_at:
		_select(cam_pos)
	vehicles.clear()
	for s in _sel:
		var path: Dictionary = s[0]
		var j: int = s[1]
		var pl := place(path, j, clock_s)
		if pl.is_empty():
			continue
		var car: Dictionary = path["cars"][j]
		vehicles.append({"id": car["id"], "kind": car["kind"], "color": car["color"], "xform": pl["xform"]})


func _select(cam_pos: Vector3) -> void:
	_dirty = false
	_sel_at = clock_s
	reselects += 1
	_sel.clear()
	if budget <= 0:
		return
	var c2 := Vector2(cam_pos.x, cam_pos.z)
	var found := []
	var keys := paths.keys()
	keys.sort()
	for k in keys:
		for path in paths[k]:
			if not (path["rect"] as Rect2).grow(RANGE_M).has_point(c2):
				continue
			for j in range((path["cars"] as Array).size()):
				var pl := place(path, j, clock_s)
				if pl.is_empty():
					continue
				var d2 := (pl["pos"] as Vector3).distance_squared_to(cam_pos)
				if d2 <= RANGE_M * RANGE_M:
					found.append([d2, path, j])
	found.sort_custom(func(a, b): return a[0] < b[0])
	for i in range(mini(budget, found.size())):
		_sel.append([found[i][1], found[i][2]])
