extends RefCounted

## Bateaux du décor (Lot P29), sans nœud ni effet sur la physique.
## Pas de class_name : charger par preload("res://scripts/boat_model.gd").
##
## Les chemins viennent des tâches de fond d'osm_streamer.gd (`extras.boats` de `chunk_loaded`),
## `water_paths(areas, lines, road)`, d'après la couche `water` (format .world §8) :
## - plans d'eau `lake`, `reservoir` et `sea` (la mer quand l'engine la lira, lot U9) : boucles en ellipse
##   tout entières dans l'eau, à LOOP_MARGIN_M du bord, des îles et de la route au moins, et à SEPARATION_M
##   l'une de l'autre au moins. Un voilier par SAIL_M2 sur un plan d'eau de SAIL_MIN_M2 au moins (au plus
##   SAIL_MAX), une barque par ROW_M2 sur un plan d'eau de ROW_MIN_M2 au moins (au plus ROW_MAX), un pédalo
##   près du bord (à moins de PEDALO_SHORE_M) sur un lac de PEDALO_MIN_M2 une fois sur deux ; un étang
##   (`pond`) de POND_MIN_M2 n'a qu'une barque, une fois sur trois. En mer : voiliers près de la côte, ferry
##   et porte-conteneurs sur une ligne droite au large, qui repassent tous les SHIP_PERIOD_S.
## - cours d'eau `canal` de BARGE_CANAL_M de large ou `river` de BARGE_RIVER_M : péniches tous les
##   BARGE_SPACING_M, dans un sens ou l'autre, sur leur moitié droite ; `river` de PADDLE_RIVER_M : canoës et
##   kayaks tous les PADDLE_SPACING_M, plus vite dans le sens du courant (sens des points), au bord droit.
##   Rien sur un `stream`. Les lignes arrivent coupées à la route (osm_streamer.gd `cut_lines_at_road`).
## Tout dépend de l'identifiant du plan d'eau ou du cours d'eau et de l'horloge : même parcours, mêmes
## bateaux. `set_chunk(k, paths)` / `remove_chunk(k)` suivent les tronçons (un plan d'eau vu par deux
## tronçons ne compte qu'une fois) ; `update(cam_pos, dt_s, wind_eval, weather_eval, paused)` avance
## l'horloge (figée en pause), rentre les petits bateaux par grand vent (STORM_WIND) ou sous la pluie
## (RAIN_HOME), garde au plus `budget` bateaux (`living(preset).boats`) et MAX_AT_ONCE de chaque sorte, les
## plus proches de la caméra (à moins de RANGE_M, SHIP_RANGE_M pour les navires), triés toutes les
## RESELECT_S, et remplit `boats` : {id, kind, color, xform, sail, wake_m, dist}. Chaque bateau tangue et
## roule selon sa taille et le vent ; un voilier gîte sous le vent et sa bôme (`sail`, angle autour du mât)
## passe du côté sous le vent.

const VegetationPlacer := preload("res://scripts/vegetation_placer.gd")
const FaunaPlacer := preload("res://scripts/fauna_placer.gd")
const TrafficModel := preload("res://scripts/traffic_model.gd")

const SMALL := ["rowboat", "pedalo", "canoe", "kayak"]
const MAX_AT_ONCE := {"sailboat": 6, "rowboat": 6, "pedalo": 3, "canoe": 4, "kayak": 4, "barge": 2, "ferry": 1, "cargo": 1}
const SPEED_MPS := {"sailboat": 2.2, "rowboat": 0.8, "pedalo": 0.6, "canoe": 1.2, "kayak": 1.2, "barge": 2.0, "ferry": 8.0, "cargo": 8.0}
const UPSTREAM_MPS := 0.7
## Roulis et tangage de chaque sorte (degrés à vent nul), période (s), pilonnement (m).
const SWELL := {
	"sailboat": [2.0, 4.0, 0.06], "rowboat": [3.0, 3.0, 0.05], "pedalo": [2.5, 3.0, 0.04], "canoe": [2.0, 2.6, 0.03],
	"kayak": [2.0, 2.4, 0.03], "barge": [0.4, 7.0, 0.02], "ferry": [0.6, 9.0, 0.2], "cargo": [0.4, 11.0, 0.2],
}
const SEA_SWELL_K := 2.0
const HEEL_MAX_RAD := 0.35
const BOOM_MAX_RAD := 1.35
const WAKE_S := {"sailboat": 10.0, "barge": 14.0, "ferry": 25.0, "cargo": 25.0}

const RANGE_M := 1500.0
const SHIP_RANGE_M := 8000.0
const RESELECT_S := 0.5
const STORM_WIND := 0.7
const RAIN_HOME := 0.3

const LOOP_MARGIN_M := 15.0
const SEA_MARGIN_M := 40.0
const SEPARATION_M := 20.0
const ROAD_CLEAR_M := 25.0
const LOOP_POINTS := 20
const LOOP_TRIES := 14
const SAIL_M2 := 80000.0
const SAIL_MIN_M2 := 50000.0
const SAIL_MAX := 6
const SAIL_RADIUS_M := Vector2(40.0, 120.0)
const SEA_SAIL_SHORE_M := 2000.0
const ROW_M2 := 40000.0
const ROW_MIN_M2 := 10000.0
const ROW_MAX := 3
const ROW_RADIUS_M := Vector2(15.0, 40.0)
const PEDALO_MIN_M2 := 20000.0
const PEDALO_SHORE_M := 60.0
const PEDALO_RADIUS_M := Vector2(8.0, 15.0)
const POND_MIN_M2 := 5000.0
const POND_ROW_SHARE := 1.0 / 3.0
const BARGE_CANAL_M := 10.0
const BARGE_RIVER_M := 30.0
const BARGE_SPACING_M := 2000.0
const PADDLE_RIVER_M := 8.0
const PADDLE_SPACING_M := 1500.0
const MIN_LINE_M := 40.0
const END_EASE_M := 8.0
const SHIP_SHORE_M := Vector2(3000.0, 6000.0)
const SHIP_LEG_M := 6000.0
const SHIP_MIN_M := 4000.0
const SHIP_AREA_M2 := 150000000.0
const SHIP_MAX_LINES := 4
const SHIP_PERIOD_S := {"ferry": 900.0, "cargo": 600.0}

var budget: int = 0
var clock_s := 0.0
var boats: Array = []              # {id, kind, color, xform, sail, wake_m, dist}
var paths: Dictionary = {}         # k -> Array de chemins
var reselects := 0
var _sel: Array = []               # [chemin, indice du bateau]
var _sel_at := -INF
var _dirty := true
var _home := {}                    # sortes rentrées par le temps qu'il fait


func set_budget(n: int) -> void:
	budget = maxi(0, n)
	_dirty = true


func reset() -> void:
	paths.clear()
	boats.clear()
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


func count(kind: String) -> int:
	var n := 0
	for b in boats:
		if b["kind"] == kind:
			n += 1
	return n


static func _u(h: int) -> float:
	return TrafficModel._u(h)


static func _hu(seed: int, a: int, b: int = 0) -> float:
	return _u(VegetationPlacer.hash3(seed, a, b))


# --- Chemins (tâches de fond) ---------------------------------------------------------------------------

## Chemins des bateaux d'un tronçon : `areas` et `lines` de la couche `water` (lignes coupées à la route),
## `road` : axe de la route du tronçon (points x, z), pour garder les boucles à l'écart d'un pont.
static func water_paths(areas: Array, lines: Array, road: PackedVector2Array = PackedVector2Array()) -> Array:
	var out := []
	for a in areas:
		if typeof(a) == TYPE_DICTIONARY:
			out.append_array(area_paths(a, road))
	for l in lines:
		if typeof(l) == TYPE_DICTIONARY:
			out.append_array(line_paths(l))
	return out


static func _ring(raw) -> PackedVector2Array:
	var r := PackedVector2Array()
	if typeof(raw) == TYPE_ARRAY:
		for p in raw:
			r.append(Vector2(float(p[0]), float(p[1])))
	return r


## Boucles d'un plan d'eau.
static func area_paths(a: Dictionary, road: PackedVector2Array = PackedVector2Array()) -> Array:
	var kind := str(a.get("kind", ""))
	var outer := _ring(a.get("outer", []))
	if outer.size() < 3 or not kind in ["lake", "pond", "reservoir", "sea"]:
		return []
	var holes := []
	var area := FaunaPlacer._ring_area(outer)
	for h in a.get("holes", []):
		var hr := _ring(h)
		if hr.size() >= 3:
			holes.append(hr)
			area -= FaunaPlacer._ring_area(hr)
	var id := str(a.get("id", ""))
	var seed := VegetationPlacer.hash_string("water:" + id)
	var level := float(a.get("level_y", 0.0))
	var sea := kind == "sea"
	var shape := {"outer": outer, "holes": holes, "road": road, "margin": SEA_MARGIN_M if sea else LOOP_MARGIN_M,
		"rect": _rect(outer)}
	var out := []
	var loops := []   # [centre, rayon le plus grand] déjà placés
	var want := []    # [sorte, rayons, distance au bord la plus grande]
	if kind != "pond":
		if area >= SAIL_MIN_M2:
			for i in range(clampi(int(area / SAIL_M2), 1, SAIL_MAX)):
				want.append(["sailboat", SAIL_RADIUS_M, SEA_SAIL_SHORE_M if sea else INF])
		if not sea and area >= ROW_MIN_M2:
			for i in range(clampi(int(area / ROW_M2), 1, ROW_MAX)):
				want.append(["rowboat", ROW_RADIUS_M, INF])
		if kind == "lake" and area >= PEDALO_MIN_M2 and _hu(seed, 3) < 0.5:
			want.append(["pedalo", PEDALO_RADIUS_M, PEDALO_SHORE_M])
	elif area >= POND_MIN_M2 and _hu(seed, 4) < POND_ROW_SHARE:
		want.append(["rowboat", Vector2(8.0, 15.0), INF])
	for i in range(want.size()):
		var w: Array = want[i]
		var loop := _fit_loop(shape, seed, i, w[1], w[2], loops)
		if loop.is_empty():
			continue
		loops.append([loop["centre"], maxf(loop["radii"].x, loop["radii"].y)])
		var bid := "%s#%d" % [id, i]
		var bs := VegetationPlacer.hash_string(bid)
		var speed: float = SPEED_MPS[w[0]]
		loop["id"] = bid
		loop["type"] = "loop"
		loop["level"] = level
		loop["sea"] = sea
		loop["boats"] = [{"id": bid, "kind": w[0], "color": int(VegetationPlacer.hash3(bs, 1, 0) % 16),
			"dir": 1.0 if _hu(bs, 2) < 0.5 else -1.0, "phase": _hu(bs, 3), "speed": speed, "swell": _hu(bs, 4)}]
		var rmax := maxf(loop["radii"].x, loop["radii"].y)
		loop["rect"] = Rect2(loop["centre"] - Vector2.ONE * rmax, Vector2.ONE * 2.0 * rmax)
		out.append(loop)
	if sea:
		for n in range(clampi(int(area / SHIP_AREA_M2), 1, SHIP_MAX_LINES)):
			for s in ["ferry", "cargo"]:
				var ship := _ship_line(shape, seed, s, level, n)
				if not ship.is_empty():
					out.append(ship)
	return out


static func _rect(ring: PackedVector2Array) -> Rect2:
	var r := Rect2(ring[0], Vector2.ZERO)
	for p in ring:
		r = r.expand(p)
	return r


## Distance de `p` au bord le plus proche (contour, îles, route) ; négative hors de l'eau.
static func _shore_dist(shape: Dictionary, p: Vector2) -> float:
	var outer: PackedVector2Array = shape["outer"]
	if not Geometry2D.is_point_in_polygon(p, outer):
		return -1.0
	var d := _ring_dist(outer, p)
	for h in shape["holes"]:
		if Geometry2D.is_point_in_polygon(p, h):
			return -1.0
		d = minf(d, _ring_dist(h, p))
	var road: PackedVector2Array = shape["road"]
	for i in range(road.size() - 1):
		d = minf(d, FaunaPlacer._seg_dist(p, road[i], road[i + 1]) - ROAD_CLEAR_M + float(shape["margin"]))
	return d


static func _ring_dist(ring: PackedVector2Array, p: Vector2) -> float:
	var d := INF
	for i in range(ring.size()):
		d = minf(d, FaunaPlacer._seg_dist(p, ring[i], ring[(i + 1) % ring.size()]))
	return d


## Boucle en ellipse dans l'eau : {centre, radii, angle} ou {} ; `shore_max` : distance au bord la plus
## grande du centre (pédalos près du bord, voiliers près de la côte).
static func _fit_loop(shape: Dictionary, seed: int, i: int, radius: Vector2, shore_max: float, loops: Array) -> Dictionary:
	var rect: Rect2 = shape["rect"]
	var margin: float = shape["margin"]
	for t in range(LOOP_TRIES):
		var c := rect.position + rect.size * Vector2(_hu(seed, 100 + i, 2 * t), _hu(seed, 100 + i, 2 * t + 1))
		var cd := _shore_dist(shape, c)
		if cd < margin + radius.x or cd > shore_max:
			continue
		# Le plus grand rayon qui tient, entre radius.x et radius.y
		var r := minf(lerpf(radius.x, radius.y, _hu(seed, 200 + i, t)), cd - margin)
		var k := lerpf(0.5, 0.8, _hu(seed, 300 + i, t))
		var ang := PI * _hu(seed, 400 + i, t)
		var radii := Vector2(r, r * k)
		var ok := true
		for l in loops:
			if c.distance_to(l[0]) < r + float(l[1]) + SEPARATION_M:
				ok = false
				break
		if not ok:
			continue
		for j in range(LOOP_POINTS):
			if _shore_dist(shape, _ellipse(c, radii, ang, TAU * j / LOOP_POINTS)) < margin:
				ok = false
				break
		if ok:
			return {"centre": c, "radii": radii, "angle": ang}
	return {}


static func _ellipse(c: Vector2, radii: Vector2, ang: float, th: float) -> Vector2:
	return c + Vector2(radii.x * cos(th), radii.y * sin(th)).rotated(ang)


## Ligne droite `n` d'un navire au large, dans la mer, de SHIP_MIN_M à SHIP_LEG_M ; {} si rien ne tient.
static func _ship_line(shape: Dictionary, seed: int, kind: String, level: float, n: int) -> Dictionary:
	var rect: Rect2 = shape["rect"]
	var salt := (7 if kind == "ferry" else 11) + 16 * n
	for t in range(LOOP_TRIES):
		var c := rect.position + rect.size * Vector2(_hu(seed, 500 + salt, 2 * t), _hu(seed, 500 + salt, 2 * t + 1))
		var cd := _shore_dist(shape, c)
		if cd < SHIP_SHORE_M.x or cd > SHIP_SHORE_M.y:
			continue
		var d := Vector2.from_angle(PI * _hu(seed, 600 + salt, t))
		var span: Vector2 = _span(shape["outer"], c, d)
		var t0 := maxf(span.x + SHIP_SHORE_M.x * 0.5, -SHIP_LEG_M * 0.5)
		var t1 := minf(span.y - SHIP_SHORE_M.x * 0.5, SHIP_LEG_M * 0.5)
		if t1 - t0 < SHIP_MIN_M:
			continue
		var a := c + d * t0
		var b := c + d * t1
		var pts := PackedVector3Array([Vector3(a.x, level, a.y), Vector3(b.x, level, b.y)])
		var path := _line_path("%s:%d:%d" % [kind, seed, n], pts, 0.0)
		var speed: float = SPEED_MPS[kind]
		path["spacing"] = maxf(speed * float(SHIP_PERIOD_S[kind]) - float(path["length"]), 0.0)
		path["sea"] = true
		path["boats"] = [{"id": path["id"], "kind": kind, "color": 0, "dir": 1 if _hu(seed, 700 + salt) < 0.5 else -1,
			"lateral": 0.0, "phase": _hu(seed, 800 + salt), "speed": speed, "swell": _hu(seed, 900 + salt)}]
		return path
	return {}


## Morceau de la droite `o + d·t` dans l'anneau qui contient `o` : Vector2(t0, t1).
static func _span(ring: PackedVector2Array, o: Vector2, d: Vector2) -> Vector2:
	var lo := -INF
	var hi := INF
	for i in range(ring.size()):
		var a := ring[i]
		var e := ring[(i + 1) % ring.size()] - a
		var den := d.cross(e)
		if absf(den) < 1e-9:
			continue
		var w := a - o
		var s := w.cross(d) / den
		if s >= 0.0 and s < 1.0:
			var t := w.cross(e) / den
			if t < 0.0:
				lo = maxf(lo, t)
			else:
				hi = minf(hi, t)
	return Vector2(lo, hi) if is_finite(lo) and is_finite(hi) else Vector2.ZERO


## Bateaux d'un cours d'eau (points [x, z, y]).
static func line_paths(l: Dictionary) -> Array:
	var kind := str(l.get("kind", ""))
	var width := float(l.get("width_m", 0.0))
	var pts := PackedVector3Array()
	for p in l.get("points", []):
		pts.append(Vector3(float(p[0]), float(p[2]), float(p[1])))
	var id := str(l.get("id", ""))
	var out := []
	var barge := (kind == "canal" and width >= BARGE_CANAL_M) or (kind == "river" and width >= BARGE_RIVER_M)
	var paddle := kind == "river" and width >= PADDLE_RIVER_M
	if barge:
		var p := _line_path("barge:" + id, pts, BARGE_SPACING_M)
		if not p.is_empty():
			p["boats"] = _line_boats(p, "barge", width * 0.25, false)
			out.append(p)
	if paddle:
		var p := _line_path("paddle:" + id, pts, PADDLE_SPACING_M)
		if not p.is_empty():
			p["boats"] = _line_boats(p, "canoe", maxf(width * 0.4 - 0.5, 1.5), true)
			out.append(p)
	return out


static func _line_path(id: String, pts: PackedVector3Array, spacing: float) -> Dictionary:
	if pts.size() < 2:
		return {}
	var cum := PackedFloat32Array([0.0])
	var rect := Rect2(Vector2(pts[0].x, pts[0].z), Vector2.ZERO)
	for i in range(1, pts.size()):
		cum.append(cum[i - 1] + Vector2(pts[i].x - pts[i - 1].x, pts[i].z - pts[i - 1].z).length())
		rect = rect.expand(Vector2(pts[i].x, pts[i].z))
	var length := cum[cum.size() - 1]
	if length < MIN_LINE_M:
		return {}
	return {"id": id, "type": "line", "pts": pts, "cum": cum, "length": length, "rect": rect, "spacing": spacing,
		"sea": false, "boats": []}


## Péniches (dans un sens ou l'autre) ou canoës et kayaks (plus vite dans le sens du courant), à `lateral`
## de l'axe sur la droite de leur sens.
static func _line_boats(path: Dictionary, kind: String, lateral: float, paddle: bool) -> Array:
	var spacing: float = path["spacing"]
	var length: float = path["length"]
	var seed := VegetationPlacer.hash_string(path["id"])
	var n := maxi(1, int(round((length + spacing) / spacing)))
	var out := []
	for j in range(n):
		var h := VegetationPlacer.hash3(seed, 10 + j, 0x29)
		var dir := 1 if _u(h) < 0.5 else -1
		var k := kind
		var speed: float = SPEED_MPS[kind]
		if paddle:
			k = "canoe" if _u(VegetationPlacer._mix(h + 1)) < 0.5 else "kayak"
			speed = SPEED_MPS[k] if dir == 1 else UPSTREAM_MPS
		out.append({"id": "%s#%d" % [path["id"], j], "kind": k, "color": int(VegetationPlacer._mix(h + 2) % 16), "dir": dir,
			"lateral": lateral, "phase": (j + 0.6 * _u(VegetationPlacer._mix(h + 3))) / n, "speed": speed,
			"swell": _u(VegetationPlacer._mix(h + 4))})
	return out


# --- Positions ------------------------------------------------------------------------------------------

## Place du bateau `j` du chemin à l'horloge `t` : {pos, fwd (Vector2 unitaire), scale} ; {} s'il est
## entre deux passages.
static func place(path: Dictionary, j: int, t: float) -> Dictionary:
	var b: Dictionary = path["boats"][j]
	if path["type"] == "loop":
		var radii: Vector2 = path["radii"]
		var r := (radii.x + radii.y) * 0.5
		var dir: float = b["dir"]
		var th := TAU * float(b["phase"]) + dir * float(b["speed"]) * t / r
		var c: Vector2 = path["centre"]
		var ang: float = path["angle"]
		var p := _ellipse(c, radii, ang, th)
		var f := Vector2(-radii.x * sin(th), radii.y * cos(th)).rotated(ang) * dir
		return {"pos": Vector3(p.x, float(path["level"]), p.y), "fwd": f.normalized(), "scale": 1.0}
	var length: float = path["length"]
	var period := length + float(path["spacing"])
	var u := fposmod(float(b["phase"]) * period + float(b["speed"]) * t, period)
	if u > length:
		return {}
	var dirl: int = b["dir"]
	var d := u if dirl == 1 else length - u
	var cum: PackedFloat32Array = path["cum"]
	var pts: PackedVector3Array = path["pts"]
	var i := clampi(cum.bsearch(d) - 1, 0, pts.size() - 2)
	var seg := maxf(cum[i + 1] - cum[i], 1e-4)
	var p3 := pts[i].lerp(pts[i + 1], clampf((d - cum[i]) / seg, 0.0, 1.0))
	var f3 := (pts[i + 1] - pts[i]) * float(dirl)
	var fh := Vector2(f3.x, f3.z)
	fh = fh.normalized() if fh.length() > 1e-5 else Vector2(0.0, -1.0)
	var right := Vector3(-fh.y, 0.0, fh.x)
	p3 += right * float(b["lateral"])
	return {"pos": p3, "fwd": fh, "scale": clampf(minf(u, length - u) / END_EASE_M, 0.05, 1.0)}


## Repère d'un bateau : cap `fwd`, roulis et tangage de la houle, gîte du voilier ; {xform, sail}.
static func pose(kind: String, pl: Dictionary, swell_phase: float, sea: bool, t: float, wind_eval: Dictionary) -> Dictionary:
	var fwd: Vector2 = pl["fwd"]
	var yaw := atan2(-fwd.x, -fwd.y)
	var strength := float(wind_eval.get("strength", 0.0))
	var sw: Array = SWELL[kind]
	var k := (0.5 + strength) * (SEA_SWELL_K if sea else 1.0)
	var w := TAU * t / float(sw[1]) + TAU * swell_phase
	var roll := deg_to_rad(float(sw[0])) * k * sin(w)
	var pitch := deg_to_rad(float(sw[0])) * 0.6 * k * sin(w * 0.77 + 1.3)
	var heave := float(sw[2]) * k * sin(w * 1.1 + 0.4)
	var sail := 0.0
	if kind == "sailboat":
		var wd: Vector3 = wind_eval.get("dir", Vector3.ZERO)
		var wl := Basis(Vector3.UP, yaw).inverse() * Vector3(wd.x, 0.0, wd.z)
		if Vector2(wl.x, wl.z).length() > 1e-4:
			sail = clampf(atan2(wl.x, wl.z), -BOOM_MAX_RAD, BOOM_MAX_RAD)
			# Gîte sous le vent (vers le côté où passe la bôme), plus forte vent de travers
			roll += -signf(sail) * HEEL_MAX_RAD * clampf(strength, 0.0, 1.0) * absf(sin(sail))
	var basis := Basis(Vector3.UP, yaw) * Basis(Vector3.RIGHT, pitch) * Basis(Vector3.BACK, roll)
	var s: float = pl["scale"]
	var pos: Vector3 = pl["pos"] + Vector3.UP * heave * s
	return {"xform": Transform3D(basis.scaled(Vector3.ONE * s), pos), "sail": sail, "roll": roll}


func update(cam_pos: Vector3, dt_s: float, wind_eval: Dictionary, weather_eval: Dictionary, paused: bool = false) -> void:
	if not paused:
		clock_s += dt_s
	var home := {}
	if float(wind_eval.get("strength", 0.0)) > STORM_WIND:
		for k in ["sailboat", "rowboat", "pedalo"]:
			home[k] = true
	if float(weather_eval.get("rain", 0.0)) >= RAIN_HOME:
		for k in ["pedalo", "canoe", "kayak"]:
			home[k] = true
	if home != _home:
		_home = home
		_dirty = true
	if _dirty or clock_s - _sel_at >= RESELECT_S - 1e-6 or clock_s < _sel_at:
		_select(cam_pos)
	boats.clear()
	for s in _sel:
		var path: Dictionary = s[0]
		var j: int = s[1]
		var pl := place(path, j, clock_s)
		if pl.is_empty():
			continue
		var b: Dictionary = path["boats"][j]
		var kind: String = b["kind"]
		var po := pose(kind, pl, float(b["swell"]), bool(path["sea"]), clock_s, wind_eval)
		boats.append({"id": b["id"], "kind": kind, "color": b["color"], "xform": po["xform"], "sail": po["sail"],
			"wake_m": float(b["speed"]) * float(WAKE_S.get(kind, 0.0)) * float(pl["scale"]),
			"dist": (pl["pos"] as Vector3).distance_to(cam_pos)})


func _select(cam_pos: Vector3) -> void:
	_dirty = false
	_sel_at = clock_s
	reselects += 1
	_sel.clear()
	if budget <= 0:
		return
	var c2 := Vector2(cam_pos.x, cam_pos.z)
	var found := []
	var seen := {}
	var keys := paths.keys()
	keys.sort()
	for k in keys:
		for path in paths[k]:
			if seen.has(path["id"]):
				continue
			seen[path["id"]] = true
			var ships: bool = bool(path["sea"]) and path["type"] == "line"
			var range_m := SHIP_RANGE_M if ships else RANGE_M
			if not (path["rect"] as Rect2).grow(range_m).has_point(c2):
				continue
			for j in range((path["boats"] as Array).size()):
				if _home.has(path["boats"][j]["kind"]):
					continue
				var pl := place(path, j, clock_s)
				if pl.is_empty():
					continue
				var d2 := (pl["pos"] as Vector3).distance_squared_to(cam_pos)
				if d2 <= range_m * range_m:
					found.append([d2, path, j])
	found.sort_custom(func(a, b): return a[0] < b[0])
	var per := {}
	for f in found:
		if _sel.size() >= budget:
			break
		var kind: String = f[1]["boats"][f[2]]["kind"]
		var n: int = per.get(kind, 0)
		if n < MAX_AT_ONCE[kind]:
			per[kind] = n + 1
			_sel.append([f[1], f[2]])
