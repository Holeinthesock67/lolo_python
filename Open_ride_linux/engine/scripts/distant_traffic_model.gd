extends RefCounted

## Véhicules lointains (Lot P25) : circulation sur les routes voisines de la couche `roads` (format 1.5, P22)
## et tracteurs qui labourent les champs (`farmland`), sans aucun nœud ni effet sur la physique.
## Pas de class_name : charger par preload("res://scripts/distant_traffic_model.gd").
##
## `prepare(route, roads_by_chunk, vegetation_by_chunk, seed)` (statique, tâche de fond) fait le plan :
## - routes : chaque morceau a des véhicules avec la chance ROAD_RATE de sa sorte (hachage de son identifiant) ;
##   au plus un véhicule par voie et par SPACING_M ; sens tiré au hasard sur une route à double sens, celui du
##   tracé sur une route à sens unique ; tous les véhicules d'une voie roulent à la même vitesse (`speed_kmh`
##   de la couche moins 0 à MAX_SLOWDOWN, plafonnée par sorte) et gardent leur écart ; sorte tirée comme sur la
##   route du parcours (traffic_model.gd `pick_kind`, sans bus, ni tracteur sur `motorway`). Un véhicule arrivé
##   au bout de son morceau repart du début (END_TRIM_M de chaque bout, réduit à rien sur FADE_M) ;
## - champs : un champ d'au moins FIELD_MIN_M2 à moins de FIELD_ROUTE_M de la route reçoit un tracteur et sa
##   charrue avec la chance FIELD_SHARE (hachage de son identifiant), au plus un par tronçon de 1 000 m ; il fait
##   des allers-retours à FIELD_KMH le long du grand axe du champ, passes espacées de PASS_STEP_M et coupées au
##   contour (FIELD_MARGIN_M du bord), demi-tours en demi-cercle (TURN_S environ), puis repart en sens inverse.
## `configure(plan, budget)`, `set_chunk_loaded(k, loaded)` (tronçons d'osm_streamer.gd), puis `update(rider_pos,
## dt_s, paused)` une fois par image : toutes les SELECT_PERIOD_S, les `budget` véhicules les plus proches du
## cycliste à moins de MAX_DIST_M, sur des tronçons chargés ; `vehicles` : [{id, kind, xform, scale, paint,
## wheel, dist_m, field, chunk}] replacés à chaque image jusqu'à DETAIL_M, au-delà une image sur QUARTER (le
## quart du budget par image, comme le bétail de P11). En pause, tout est figé.

const VegetationPlacer := preload("res://scripts/vegetation_placer.gd")
const TrafficModel := preload("res://scripts/traffic_model.gd")
const VehicleMesh := preload("res://scripts/vehicle_mesh.gd")

const ROAD_RATE := {"motorway": 1.0, "trunk": 1.0, "primary": 0.8, "secondary": 0.6, "tertiary": 0.45,
	"unclassified": 0.3, "residential": 0.3, "track": 0.1}
const SPACING_M := 400.0
const LANE_W_M := 3.2
const MAX_SLOWDOWN := 0.15
const KIND_MAX_KMH := {"truck": 90.0, "bus": 90.0, "tractor": 25.0, "van": 130.0}
const END_TRIM_M := 10.0
const FADE_M := 10.0
const MAX_DIST_M := 1500.0
const SELECT_PERIOD_S := 0.5
const FIELD_MIN_M2 := 20000.0
const FIELD_ROUTE_M := 400.0
const FIELD_SHARE := 0.3
const FIELD_KMH := 8.0
const PASS_STEP_M := 6.0
const FIELD_MARGIN_M := 6.0
const TURN_SEGMENTS := 6
const MIN_PASS_M := 20.0
const CHUNK_M := 1000.0
const DETAIL_M := 400.0
const QUARTER := 4

var budget: int = 12
var vehicles: Array = []
var _slots: Array = []           # {id, chunk, line (index), offset_m, dir, lane_off, speed_mps, kind, paint, field}
var _lines: Array = []           # {pts: PackedVector3Array, cum: PackedFloat32Array, len, center: Vector3, radius}
var _paths: Array = []           # chemins des tracteurs au champ, même forme que _lines
var _loaded: Dictionary = {}
var _selected: Array = []        # indices dans _slots
var _entries: Dictionary = {}    # indice dans _slots -> véhicule de `vehicles` (gardé tant qu'il est choisi)
var _frame := 0
var _clock := 0.0
var _select_at := -INF


static func _u(h: int) -> float:
	return float(h & 0xFFFFFF) / 16777216.0


## Polyligne `[Vector3]` -> {pts, cum, len, center, radius}.
static func _polyline(pts: PackedVector3Array) -> Dictionary:
	var cum := PackedFloat32Array([0.0])
	var c := Vector3.ZERO
	for i in range(1, pts.size()):
		cum.append(cum[i - 1] + Vector2(pts[i].x - pts[i - 1].x, pts[i].z - pts[i - 1].z).length())
	for p in pts:
		c += p
	c /= maxf(1.0, pts.size())
	var r := 0.0
	for p in pts:
		r = maxf(r, Vector2(p.x - c.x, p.z - c.z).length())
	return {"pts": pts, "cum": cum, "len": cum[cum.size() - 1], "center": c, "radius": r}


## Point et direction (unitaire, horizontale) à la distance `d` le long d'une polyligne.
static func _at(line: Dictionary, d: float) -> Array:
	var cum: PackedFloat32Array = line["cum"]
	var pts: PackedVector3Array = line["pts"]
	var lo := 0
	var hi := cum.size() - 1
	d = clampf(d, 0.0, float(line["len"]))
	while hi - lo > 1:
		var mid := (lo + hi) >> 1
		if cum[mid] <= d:
			lo = mid
		else:
			hi = mid
	var seg := maxf(cum[hi] - cum[lo], 1e-6)
	var t := (d - cum[lo]) / seg
	var dirv := pts[hi] - pts[lo]
	dirv.y = 0.0
	return [pts[lo].lerp(pts[hi], t), dirv.normalized() if dirv.length_squared() > 1e-8 else Vector3.FORWARD]


## Plan des véhicules lointains (voir l'en-tête), calculé sans nœud (tâche de fond) ; `vegetation_by_chunk` :
## k -> zones de la couche végétation ; `roads_by_chunk` : k -> morceaux de la couche `roads` ; `height_at`
## (Callable x, z -> y, facultatif) : sol des champs (sinon l'altitude de la route la plus proche).
static func prepare(route, roads_by_chunk: Dictionary, vegetation_by_chunk: Dictionary, seed: int = 0,
		height_at: Callable = Callable()) -> Dictionary:
	var lines := []
	var slots := []
	var keys := roads_by_chunk.keys()
	keys.sort()
	for k in keys:
		for r in roads_by_chunk[k]:
			if typeof(r) != TYPE_DICTIONARY:
				continue
			var kind := str(r.get("kind", ""))
			var id := str(r.get("id", ""))
			var h := VegetationPlacer.hash3(seed, VegetationPlacer.hash_string(id), 0x0AD5)
			if _u(h) >= float(ROAD_RATE.get(kind, 0.0)):
				continue
			var pts := PackedVector3Array()
			for p in r.get("points", []):
				pts.append(Vector3(float(p[0]), float(p[2]), float(p[1])))
			var line := _polyline(pts)
			var usable := float(line["len"]) - 2.0 * END_TRIM_M
			if usable < 20.0:
				continue
			var li := lines.size()
			lines.append(line)
			var lanes := maxi(1, int(r.get("lanes", 2)))
			var oneway: bool = r.get("oneway", false)
			var per_dir := lanes if oneway else maxi(1, lanes / 2)
			var dirs := [1] if oneway else [1, -1]
			var per_lane := maxi(1, int(floor(usable / SPACING_M)))
			for dir in dirs:
				for lane in range(per_dir):
					var hl := VegetationPlacer._mix(h + 17 * (lane + 1) + (5 if dir < 0 else 0))
					# Double sens : sens de chaque voie tiré au hasard ; au moins une voie occupée
					if not oneway and dirs.size() == 2 and (hl >> 11) & 1 == 1 and not (dir == 1 and lane == 0):
						continue
					var lane_off := (float(lane) + 0.5) * LANE_W_M if not oneway else ((float(lane) + 0.5) - lanes * 0.5) * LANE_W_M
					var speed_kmh := float(r.get("speed_kmh", 50.0)) * (1.0 - MAX_SLOWDOWN * _u(hl))
					var start := _u(VegetationPlacer._mix(hl + 1)) * usable
					for i in range(per_lane):
						var hv := VegetationPlacer._mix(hl + 100 + i)
						var vk := TrafficModel.pick_kind(_u(hv), false, (hv >> 7) & 1)
						if kind == "motorway" and vk == "tractor":
							vk = "car_a" if (hv >> 8) & 1 == 0 else "car_b"
						if kind == "track":
							vk = "tractor" if (hv >> 9) & 3 != 0 else vk
						var spd := minf(speed_kmh, float(KIND_MAX_KMH.get(vk, speed_kmh)))
						if vk == "tractor":
							spd = minf(spd, 25.0)
						slots.append({"id": "%s_%d_%d_%d" % [id, dir, lane, i], "chunk": int(k), "line": li,
							"offset_m": fposmod(start + i * usable / per_lane, usable), "dir": dir, "lane_off": lane_off,
							"speed_mps": spd / 3.6, "kind": vk, "paint": VehicleMesh.paint(vk, int(hv >> 12)), "field": false})
	var paths := []
	var vkeys := vegetation_by_chunk.keys()
	vkeys.sort()
	for k in vkeys:
		var fields := []
		for a in vegetation_by_chunk[k]:
			if typeof(a) == TYPE_DICTIONARY and str(a.get("kind", "")) == "farmland" and typeof(a.get("outer")) == TYPE_ARRAY \
					and (a["outer"] as Array).size() >= 3:
				fields.append(a)
		fields.sort_custom(func(a, b): return str(a.get("id", "")) < str(b.get("id", "")))
		for a in fields:
			var hf := VegetationPlacer.hash3(seed, VegetationPlacer.hash_string(str(a.get("id", ""))), 0xF1E1D)
			if _u(hf) >= FIELD_SHARE:
				continue
			var ring := VegetationPlacer._packed_ring(a["outer"])
			if absf(_ring_area(ring)) < FIELD_MIN_M2 or _route_distance(route, ring, int(k)) > FIELD_ROUTE_M:
				continue
			var path := field_path(ring, 0.0)
			if path.is_empty():
				continue
			for i in range(path.size()):
				var q := path[i]
				q.y = float(height_at.call(q.x, q.z)) if height_at.is_valid() else _route_alt(route, Vector2(q.x, q.z), int(k))
				path[i] = q
			paths.append(_polyline(path))
			slots.append({"id": "%s_tractor" % str(a.get("id", "")), "chunk": int(k), "line": -paths.size(),
				"offset_m": _u(VegetationPlacer._mix(hf + 1)) * float(paths[paths.size() - 1]["len"]) * 2.0,
				"dir": 1, "lane_off": 0.0, "speed_mps": FIELD_KMH / 3.6, "kind": "tractor_plough",
				"paint": VehicleMesh.paint("tractor", int(hf >> 9)), "field": true})
			break   # au plus un tracteur par tronçon
	return {"lines": lines, "paths": paths, "slots": slots}


## Altitude de la route au point le plus proche de `p` (pas de 50 m sur le tronçon `k` et ses voisins).
static func _route_alt(route, p: Vector2, k: int) -> float:
	if route == null:
		return 0.0
	var best := INF
	var y := 0.0
	var s := maxf(0.0, (k - 1) * CHUNK_M)
	while s <= minf(float(route.length_m), (k + 2) * CHUNK_M):
		var smp: Dictionary = route.sample(s)
		var d := p.distance_to(Vector2(float(smp["x"]), float(smp["z"])))
		if d < best:
			best = d
			y = float(smp["y"]) if smp.has("y") else float(smp["alt_m"])
		s += 50.0
	return y


static func _ring_area(ring: PackedVector2Array) -> float:
	var a := 0.0
	for i in range(ring.size()):
		var p := ring[i]
		var q := ring[(i + 1) % ring.size()]
		a += p.x * q.y - q.x * p.y
	return a * 0.5


## Distance la plus courte d'un sommet du contour à la route, sur le tronçon `k` et ses voisins (pas de 25 m).
static func _route_distance(route, ring: PackedVector2Array, k: int) -> float:
	if route == null:
		return INF
	var best := INF
	var s := maxf(0.0, (k - 1) * CHUNK_M)
	var s_end := minf(float(route.length_m), (k + 2) * CHUNK_M)
	while s <= s_end:
		var smp: Dictionary = route.sample(s)
		var p := Vector2(float(smp["x"]), float(smp["z"]))
		for v in ring:
			best = minf(best, p.distance_to(v))
		s += 25.0
	return best


## Chemin du tracteur dans un champ : passes parallèles au grand axe (analyse des sommets du contour),
## espacées de PASS_STEP_M, coupées au contour à FIELD_MARGIN_M du bord (plus long morceau de chaque passe),
## reliées par des demi-tours ; bouts communs de deux passes voisines ramenés au plus court. [] si moins de
## deux passes de MIN_PASS_M.
static func field_path(ring: PackedVector2Array, y: float) -> PackedVector3Array:
	var c := Vector2.ZERO
	for v in ring:
		c += v
	c /= ring.size()
	var sxx := 0.0
	var szz := 0.0
	var sxz := 0.0
	for v in ring:
		var d := v - c
		sxx += d.x * d.x
		szz += d.y * d.y
		sxz += d.x * d.y
	var ang := 0.5 * atan2(2.0 * sxz, sxx - szz)
	var ax := Vector2(cos(ang), sin(ang))
	var nx := Vector2(-ax.y, ax.x)
	var lo := INF
	var hi := -INF
	for v in ring:
		var w := (v - c).dot(nx)
		lo = minf(lo, w)
		hi = maxf(hi, w)
	var passes := []
	var w := lo + FIELD_MARGIN_M
	while w <= hi - FIELD_MARGIN_M:
		var span := _clip(ring, c + nx * w, ax)
		if span.y - span.x >= MIN_PASS_M + 2.0 * FIELD_MARGIN_M:
			passes.append(Vector3(w, span.x + FIELD_MARGIN_M, span.y - FIELD_MARGIN_M))
		elif passes.size() >= 2:
			break
		else:
			passes.clear()
		w += PASS_STEP_M
	if passes.size() < 2:
		return PackedVector3Array()
	# Bouts communs : passe paire vers +, demi-tour au bout + avec la suivante ; impaire vers -, au bout -
	for i in range(passes.size() - 1):
		var a: Vector3 = passes[i]
		var b: Vector3 = passes[i + 1]
		if i % 2 == 0:
			var e := minf(a.z, b.z)
			passes[i] = Vector3(a.x, a.y, e)
			passes[i + 1] = Vector3(b.x, b.y, e)
		else:
			var e2 := maxf(a.y, b.y)
			passes[i] = Vector3(a.x, e2, a.z)
			passes[i + 1] = Vector3(b.x, e2, b.z)
	for i in range(passes.size()):
		var pv: Vector3 = passes[i]
		if pv.z - pv.y < MIN_PASS_M:
			passes.resize(i)
			break
	if passes.size() < 2:
		return PackedVector3Array()
	var out := PackedVector3Array()
	var to3 := func(p: Vector2) -> Vector3:
		return Vector3(p.x, y, p.y)
	for i in range(passes.size()):
		var p: Vector3 = passes[i]
		var from := p.y if i % 2 == 0 else p.z
		var to := p.z if i % 2 == 0 else p.y
		out.append(to3.call(c + nx * p.x + ax * from))
		out.append(to3.call(c + nx * p.x + ax * to))
		if i + 1 < passes.size():
			# Demi-tour : demi-cercle de rayon PASS_STEP_M / 2 au bout `to`, vers la passe suivante
			var mid := c + nx * (p.x + PASS_STEP_M * 0.5) + ax * to
			var out_dir := ax * (1.0 if i % 2 == 0 else -1.0)
			for j in range(1, TURN_SEGMENTS):
				var t := PI * float(j) / TURN_SEGMENTS
				out.append(to3.call(mid - nx * cos(t) * PASS_STEP_M * 0.5 + out_dir * sin(t) * PASS_STEP_M * 0.5))
	return out


## Intervalle [début, fin] (le long de `ax`) du plus long morceau de la droite `p + t × ax` dans le contour.
static func _clip(ring: PackedVector2Array, p: Vector2, ax: Vector2) -> Vector2:
	var ts := []
	var nrm := Vector2(-ax.y, ax.x)
	for i in range(ring.size()):
		var a := ring[i]
		var b := ring[(i + 1) % ring.size()]
		var da := (a - p).dot(nrm)
		var db := (b - p).dot(nrm)
		if (da > 0.0) == (db > 0.0) or da == db:
			continue
		var q := a + (b - a) * (da / (da - db))
		ts.append((q - p).dot(ax))
	ts.sort()
	var best := Vector2(0.0, 0.0)
	for i in range(0, ts.size() - 1, 2):
		if ts[i + 1] - ts[i] > best.y - best.x:
			best = Vector2(ts[i], ts[i + 1])
	return best


func configure(plan: Dictionary, distant_budget: int) -> void:
	_lines = plan.get("lines", [])
	_paths = plan.get("paths", [])
	_slots = plan.get("slots", [])
	budget = maxi(0, distant_budget)
	_selected.clear()
	_entries.clear()
	vehicles.clear()
	_clock = 0.0
	_select_at = -INF


func set_budget(distant_budget: int) -> void:
	budget = maxi(0, distant_budget)
	_select_at = -INF


func set_chunk_loaded(k: int, loaded: bool) -> void:
	if loaded:
		_loaded[k] = true
	else:
		_loaded.erase(k)
	_select_at = -INF


func slot_count() -> int:
	return _slots.size()


## Position, cap, distance parcourue sur la ligne et facteur d'échelle (0 à 1, bouts des routes) d'une place.
func place(slot: Dictionary) -> Dictionary:
	var li: int = slot["line"]
	var dist := float(slot["offset_m"]) + float(slot["speed_mps"]) * _clock
	var xf: Transform3D
	var scale := 1.0
	if li < 0:
		var path: Dictionary = _paths[-li - 1]
		var length := float(path["len"])
		var d := fposmod(dist, 2.0 * length)
		var back := d > length
		var dd := 2.0 * length - d if back else d
		var at := _at(path, dd)
		var fwd: Vector3 = at[1] * (-1.0 if back else 1.0)
		xf = Transform3D(Basis(Vector3.UP, atan2(-fwd.x, -fwd.z)), at[0])
	else:
		var line: Dictionary = _lines[li]
		var usable := float(line["len"]) - 2.0 * END_TRIM_M
		var u := fposmod(dist, usable)
		scale = clampf(minf(u, usable - u) / FADE_M, 0.0, 1.0)
		var d2 := END_TRIM_M + (u if int(slot["dir"]) > 0 else usable - u)
		var at2 := _at(line, d2)
		var fwd2: Vector3 = at2[1] * float(slot["dir"])
		var right := Vector3(-fwd2.z, 0.0, fwd2.x)
		xf = Transform3D(Basis(Vector3.UP, atan2(-fwd2.x, -fwd2.z)), at2[0] + right * float(slot["lane_off"]))
	return {"xform": xf, "dist": dist, "scale": scale}


func update(rider_pos: Vector3, dt_s: float, paused: bool = false) -> void:
	if not paused:
		_clock += dt_s
	_frame += 1
	if _clock - _select_at >= SELECT_PERIOD_S or _select_at == -INF:
		_select_at = _clock
		_select(rider_pos)
	vehicles.clear()
	for j in range(_selected.size()):
		var i: int = _selected[j]
		var e: Dictionary = _entries.get(i, {})
		# Au-delà de DETAIL_M, un véhicule n'est replacé qu'une image sur QUARTER (quart du budget par image)
		if e.is_empty() or float(e["dist_m"]) <= DETAIL_M or (j + _frame) % QUARTER == 0 or paused:
			var slot: Dictionary = _slots[i]
			var pl := place(slot)
			var xf: Transform3D = pl["xform"]
			if e.is_empty():
				e = {"id": slot["id"], "kind": slot["kind"], "paint": slot["paint"], "field": slot["field"], "chunk": slot["chunk"]}
				_entries[i] = e
			e["xform"] = xf
			e["scale"] = pl["scale"]
			e["wheel"] = float(pl["dist"]) / float(VehicleMesh.KINDS[slot["kind"]]["wheel_r"])
			e["dist_m"] = xf.origin.distance_to(rider_pos)
		if float(e["dist_m"]) <= MAX_DIST_M:
			vehicles.append(e)


## Les `budget` places les plus proches du cycliste, sur des tronçons chargés, à moins de MAX_DIST_M.
func _select(rider_pos: Vector3) -> void:
	var cand := []
	var p2 := Vector2(rider_pos.x, rider_pos.z)
	for i in range(_slots.size()):
		var slot: Dictionary = _slots[i]
		if not _loaded.has(int(slot["chunk"])):
			continue
		var li: int = slot["line"]
		var line: Dictionary = _paths[-li - 1] if li < 0 else _lines[li]
		var c: Vector3 = line["center"]
		if p2.distance_to(Vector2(c.x, c.z)) - float(line["radius"]) > MAX_DIST_M:
			continue
		var o: Vector3 = (place(slot)["xform"] as Transform3D).origin
		var d := o.distance_to(rider_pos)
		if d <= MAX_DIST_M:
			cand.append([d, i])
	cand.sort_custom(func(a, b): return a[0] < b[0] or (a[0] == b[0] and a[1] < b[1]))
	_selected.clear()
	var kept := {}
	for j in range(mini(budget, cand.size())):
		_selected.append(cand[j][1])
		if _entries.has(cand[j][1]):
			kept[cand[j][1]] = _entries[cand[j][1]]
	_entries = kept


## Tracteur au champ le plus proche (son de son moteur) : {pos, dist_m} ou {}.
func nearest_field_tractor(rider_pos: Vector3) -> Dictionary:
	var best := {}
	for v in vehicles:
		if v["field"] and (best.is_empty() or float(v["dist_m"]) < float(best["dist_m"])):
			best = {"pos": (v["xform"] as Transform3D).origin, "dist_m": v["dist_m"]}
	return best
