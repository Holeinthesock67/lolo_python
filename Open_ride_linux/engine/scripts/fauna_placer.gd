extends RefCounted

## Placement déterministe des animaux d'un tronçon OSM (Lot P11, Format .world v1 §7 à §9, thème 1.2
## `fauna`), sans aucun nœud. Pas de class_name : charger par preload("res://scripts/fauna_placer.gd").
##
## `place_chunk(chunk_index, vegetation_areas, pois, route, density, ctx)` rend des groupes :
## - `{"type": "herd", "id", "species": "cow" | "sheep", "members": [{"pos": Vector3, "yaw": float}]}` :
##   3 à 12 bêtes autour de chaque point `livestock`, dans un disque de HERD_RADIUS_M ;
## - `{"type": "birds", "id", "center": Vector3, "ground_y", "radius_m", "members": [{"angle", "r",
##   "h", "phase", "omega"}]}` : une bande de 5 à 15 oiseaux au-dessus d'une forêt (`wood`) d'au
##   moins 2 ha, le centre de 25 à 45 m au-dessus du sol et assez haut pour que l'orbite reste à plus
##   de BIRD_MIN_AGL_M du point le plus haut du sol dessous ;
## - `{"type": "deer", "id", "pos": Vector3, "yaw", "flee_dir": Vector3}` : un site de chevreuil en
##   lisière, au plus un tronçon sur DEER_EVERY_CHUNKS (un tous les 3 km), fuite vers la forêt et
##   loin de la route.
## `density` : `{birds, livestock, deer}` de 0 à 1 (thème 1.2 `fauna`), DEFAULT_DENSITY pour une clé
## absente. `ctx` facultatif : `height_at` (Callable x, z -> y ; sinon l'altitude du point ou 0),
## `buildings` (éléments à `outer`), `water` (`{lines, areas}` de la couche eau), `road_width_m`.
## Exclusions des bêtes au sol : couloir de la route (moitié de la largeur + ROAD_MARGIN_M, et jamais
## moins de MIN_ROAD_CLEARANCE_M de l'axe), eau, bâtiments, pente au-dessus de MAX_SLOPE.
## Tirages dérivés du hachage de VegetationPlacer (même sortie d'une machine à l'autre).

const VegetationPlacer := preload("res://scripts/vegetation_placer.gd")

const DEFAULT_DENSITY := {"birds": 0.5, "livestock": 0.6, "deer": 0.3}
const HERD_MIN := 3
const HERD_MAX := 12
const HERD_RADIUS_M := 30.0
const FLOCK_MIN := 5
const FLOCK_MAX := 15
const FLOCK_MIN_AREA_M2 := 20000.0     # forêt d'au moins 2 ha pour une bande
const BIRD_MIN_AGL_M := 15.0
const BIRD_WAVE_M := 3.0               # ondulation verticale des oiseaux (fauna_behaviour.gd)
const BIRD_CENTER_AGL_M := Vector2(25.0, 45.0)
const DEER_EVERY_CHUNKS := 3
const DEER_EDGE_OFFSET_M := 6.0
const ROAD_MARGIN_M := 2.0
const MIN_ROAD_CLEARANCE_M := 4.0
const WATER_MARGIN_M := 2.0
const MAX_SLOPE := 0.25
const DEFAULT_ROAD_WIDTH_M := 6.0
const TRIES_PER_BEAST := 6

const MASK32 := 0xFFFFFFFF


static func _h(seed: int, a: int, b: int = 0) -> int:
	return VegetationPlacer.hash3(seed, a, b)


static func _u(h: int) -> float:
	return float(h & 0xFFFFFF) / 16777216.0


static func _density(density: Dictionary, key: String) -> float:
	var v = density.get(key, DEFAULT_DENSITY[key])
	if typeof(v) != TYPE_INT and typeof(v) != TYPE_FLOAT:
		v = DEFAULT_DENSITY[key]
	return clampf(float(v), 0.0, 1.0)


## Contexte d'exclusion commun (anneaux convertis une fois, segments de la route par case).
static func _make_ctx(ctx: Dictionary, route, bounds: Rect2) -> Dictionary:
	var road_w := float(ctx.get("road_width_m", DEFAULT_ROAD_WIDTH_M))
	var corridor := maxf(road_w * 0.5 + ROAD_MARGIN_M, MIN_ROAD_CLEARANCE_M)
	var out := {
		"corridor": corridor,
		"roads": VegetationPlacer._road_buckets(route, bounds, corridor) if route != null else {},
		"height_at": ctx.get("height_at", Callable()),
		"buildings": [],
		"water_areas": [],
		"water_lines": [],
	}
	for b in ctx.get("buildings", []):
		if typeof(b) == TYPE_DICTIONARY and typeof(b.get("outer")) == TYPE_ARRAY and b["outer"].size() >= 3:
			out["buildings"].append(VegetationPlacer._packed_ring(b["outer"]))
	var water: Dictionary = ctx.get("water", {})
	for a in water.get("areas", []):
		if typeof(a) == TYPE_DICTIONARY and typeof(a.get("outer")) == TYPE_ARRAY and a["outer"].size() >= 3:
			out["water_areas"].append(VegetationPlacer._packed_ring(a["outer"]))
	for l in water.get("lines", []):
		if typeof(l) != TYPE_DICTIONARY or typeof(l.get("points")) != TYPE_ARRAY:
			continue
		var pts := PackedVector2Array()
		for p in l["points"]:
			pts.append(Vector2(float(p[0]), float(p[1])))
		var half := float(l.get("width_m", 2.0)) * 0.5 + WATER_MARGIN_M
		out["water_lines"].append({"pts": pts, "half": half})
	return out


static func _ground(ex: Dictionary, x: float, z: float, fallback: float) -> float:
	var f: Callable = ex["height_at"]
	if f.is_valid():
		var y := float(f.call(x, z))
		if is_finite(y):
			return y
	return fallback


static func _seg_dist(p: Vector2, a: Vector2, b: Vector2) -> float:
	var ab := b - a
	var len2 := ab.length_squared()
	var t := 0.0 if len2 <= 0.0 else clampf((p - a).dot(ab) / len2, 0.0, 1.0)
	return (a + ab * t).distance_to(p)


## Vrai si une bête peut se tenir au sol en (x, z).
static func ground_ok(ex: Dictionary, x: float, z: float) -> bool:
	var roads: Dictionary = ex["roads"]
	if not roads.is_empty() and VegetationPlacer._near_road(roads, x, z, ex["corridor"]):
		return false
	for ring in ex["buildings"]:
		if VegetationPlacer._in_ring(x, z, ring):
			return false
	for ring in ex["water_areas"]:
		if VegetationPlacer._in_ring(x, z, ring):
			return false
	var p := Vector2(x, z)
	for wl in ex["water_lines"]:
		var pts: PackedVector2Array = wl["pts"]
		for i in range(pts.size() - 1):
			if _seg_dist(p, pts[i], pts[i + 1]) < float(wl["half"]):
				return false
	var f: Callable = ex["height_at"]
	if f.is_valid():
		var d := 2.0
		var gx := (float(f.call(x + d, z)) - float(f.call(x - d, z))) / (2.0 * d)
		var gz := (float(f.call(x, z + d)) - float(f.call(x, z - d))) / (2.0 * d)
		if not is_finite(gx) or not is_finite(gz) or sqrt(gx * gx + gz * gz) > MAX_SLOPE:
			return false
	return true


static func _area_bounds(areas: Array, pois: Array) -> Rect2:
	var r := Rect2()
	var first := true
	for a in areas:
		if typeof(a) == TYPE_DICTIONARY and typeof(a.get("outer")) == TYPE_ARRAY and a["outer"].size() >= 3:
			var b := VegetationPlacer._ring_bounds(a["outer"])
			r = b if first else r.merge(b)
			first = false
	for p in pois:
		if typeof(p) == TYPE_DICTIONARY:
			var b := Rect2(float(p.get("x", 0.0)), float(p.get("z", 0.0)), 0.0, 0.0)
			r = b if first else r.merge(b)
			first = false
	return r.grow(HERD_RADIUS_M + 60.0)


static func _ring_area(ring: PackedVector2Array) -> float:
	var s := 0.0
	var n := ring.size()
	for i in range(n):
		var a := ring[i]
		var b := ring[(i + 1) % n]
		s += a.x * b.y - b.x * a.y
	return absf(s) * 0.5


static func _ring_centroid(ring: PackedVector2Array) -> Vector2:
	var c := Vector2.ZERO
	for p in ring:
		c += p
	return c / maxf(1.0, float(ring.size()))


## Animaux du tronçon `chunk_index` (voir l'en-tête).
static func place_chunk(chunk_index: int, vegetation_areas: Array, pois: Array, route,
		density: Dictionary, ctx: Dictionary = {}) -> Array:
	var out := []
	var ex := _make_ctx(ctx, route, _area_bounds(vegetation_areas, pois))
	var d_live := _density(density, "livestock")
	var d_birds := _density(density, "birds")
	var d_deer := _density(density, "deer")

	# Troupeaux autour des points livestock
	if d_live > 0.0:
		for p in pois:
			if typeof(p) != TYPE_DICTIONARY or str(p.get("kind", "")) != "livestock":
				continue
			var seed := VegetationPlacer.hash_string(str(p.get("id", "")))
			var n := clampi(HERD_MIN + int(round((HERD_MAX - HERD_MIN) * d_live * _u(_h(seed, 1)))), HERD_MIN, HERD_MAX)
			var cx := float(p.get("x", 0.0))
			var cz := float(p.get("z", 0.0))
			var cy := float(p.get("y", 0.0))
			var members := []
			var tries := 0
			while members.size() < n and tries < n * TRIES_PER_BEAST:
				var hh := _h(seed, 100 + tries)
				tries += 1
				var ang := TAU * _u(hh)
				var rad := HERD_RADIUS_M * sqrt(_u(VegetationPlacer._mix(hh + 1)))
				var x := cx + cos(ang) * rad
				var z := cz + sin(ang) * rad
				if not ground_ok(ex, x, z):
					continue
				members.append({"pos": Vector3(x, _ground(ex, x, z, cy), z), "yaw": TAU * _u(VegetationPlacer._mix(hh + 2))})
			if not members.is_empty():
				out.append({"type": "herd", "id": str(p.get("id", "")),
					"species": "cow" if (seed & 1) == 0 else "sheep", "members": members})

	# Bandes d'oiseaux et site de chevreuil en lisière
	var deer_slot := posmod(chunk_index, DEER_EVERY_CHUNKS) == 0
	var deer_done := false
	var woods := []
	for a in vegetation_areas:
		if typeof(a) == TYPE_DICTIONARY and str(a.get("kind", "")) == "wood" \
				and typeof(a.get("outer")) == TYPE_ARRAY and a["outer"].size() >= 3:
			woods.append(a)
	woods.sort_custom(func(a, b): return str(a.get("id", "")) < str(b.get("id", "")))
	for a in woods:
		var ring := VegetationPlacer._packed_ring(a["outer"])
		var seed := VegetationPlacer.hash_string(str(a.get("id", "")))
		var area_m2 := _ring_area(ring)
		var c2 := _ring_centroid(ring)
		if d_birds > 0.0 and area_m2 >= FLOCK_MIN_AREA_M2 and _u(_h(seed, 7)) < d_birds:
			var gy := _ground(ex, c2.x, c2.y, 0.0)
			var agl := lerpf(BIRD_CENTER_AGL_M.x, BIRD_CENTER_AGL_M.y, _u(_h(seed, 8)))
			var n_birds := clampi(FLOCK_MIN + int(round((FLOCK_MAX - FLOCK_MIN) * _u(_h(seed, 9)))), FLOCK_MIN, FLOCK_MAX)
			var radius := clampf(sqrt(area_m2) * 0.25, 15.0, 60.0)
			var members := []
			for i in range(n_birds):
				var hb := _h(seed, 200 + i)
				members.append({
					"angle": TAU * _u(hb),
					"r": radius * lerpf(0.6, 1.0, _u(VegetationPlacer._mix(hb + 1))),
					"h": lerpf(-4.0, 4.0, _u(VegetationPlacer._mix(hb + 2))),
					"phase": TAU * _u(VegetationPlacer._mix(hb + 3)),
					"omega": lerpf(0.12, 0.22, _u(VegetationPlacer._mix(hb + 4))),
				})
			# Sol le plus haut sous l'orbite : aucun oiseau à moins de BIRD_MIN_AGL_M du sol
			var top := gy
			for j in range(16):
				var ang := TAU * j / 16.0
				for rr in [radius * 0.6, radius]:
					top = maxf(top, _ground(ex, c2.x + cos(ang) * rr, c2.y + sin(ang) * rr, gy))
			var cy := maxf(gy + agl, top + BIRD_MIN_AGL_M + 4.0 + BIRD_WAVE_M)
			out.append({"type": "birds", "id": str(a.get("id", "")), "center": Vector3(c2.x, cy, c2.y),
				"ground_y": gy, "radius_m": radius, "members": members})
		if deer_slot and not deer_done and d_deer > 0.0 and _u(_h(seed, chunk_index & MASK32, 11)) < d_deer:
			# Lisière : un sommet de l'anneau, poussé hors de la forêt, à l'opposé du centre
			var start := int(_u(_h(seed, 12)) * ring.size())
			for t in range(ring.size()):
				var v := ring[(start + t) % ring.size()]
				var outward := (v - c2).normalized()
				var pos2 := v + outward * DEER_EDGE_OFFSET_M
				if VegetationPlacer._in_ring(pos2.x, pos2.y, ring) or not ground_ok(ex, pos2.x, pos2.y):
					continue
				var flee := -outward
				var away := _away_from_road(route, pos2)
				if away != Vector2.ZERO and flee.dot(away) < 0.3:
					flee = (flee + away * 2.0).normalized()
				out.append({"type": "deer", "id": "%s_deer" % str(a.get("id", "")),
					"pos": Vector3(pos2.x, _ground(ex, pos2.x, pos2.y, 0.0), pos2.y),
					"yaw": atan2(outward.x, outward.y), "flee_dir": Vector3(flee.x, 0.0, flee.y)})
				deer_done = true
				break
	return out


## Direction horizontale unitaire qui s'éloigne du point de la route le plus proche (zéro sans route).
static func _away_from_road(route, p: Vector2) -> Vector2:
	if route == null or route.n < 2:
		return Vector2.ZERO
	var best := INF
	var best_q := Vector2.ZERO
	for i in range(route.n - 1):
		var a := Vector2(route.x[i], route.z[i])
		var b := Vector2(route.x[i + 1], route.z[i + 1])
		var ab := b - a
		var len2 := ab.length_squared()
		var t := 0.0 if len2 <= 0.0 else clampf((p - a).dot(ab) / len2, 0.0, 1.0)
		var q := a + ab * t
		var d := q.distance_squared_to(p)
		if d < best:
			best = d
			best_q = q
	var v := p - best_q
	return v.normalized() if v.length_squared() > 1e-6 else Vector2.ZERO


## Nombre d'animaux des groupes, par catégorie de budget (`birds`, `animals`).
static func count(groups: Array) -> Dictionary:
	var out := {"birds": 0, "animals": 0}
	for g in groups:
		match str(g.get("type", "")):
			"birds":
				out["birds"] += (g["members"] as Array).size()
			"herd":
				out["animals"] += (g["members"] as Array).size()
			"deer":
				out["animals"] += 1
	return out
