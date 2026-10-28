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
## Lot P23, oiseaux de la campagne ouverte, au plus un groupe de chaque sorte par tronçon, posés près de la
## route du tronçon (abscisses `chunk_index * CHUNK_M` à `(chunk_index + 1) * CHUNK_M`) :
## - `{"type": "raptor", "id", "center": Vector3, "radius_m", "angle", "omega"}` : un rapace qui plane en
##   cercle de RAPTOR_RADIUS_M au-dessus d'un terrain ouvert (hors forêt), à RAPTOR_AGL_M du sol ;
## - `{"type": "vee", "id", "origin": Vector3, "dir": Vector3, "speed_mps", "span_m", "phase_m",
##   "members": [{"back", "side"}]}` : une volée en V qui traverse le ciel en ligne droite, à VEE_AGL_M du
##   sol, en passant au-dessus de `origin` (près de la route) ; sa trajectoire fait `span_m` de long ;
## - `{"type": "crows", "id", "pos": Vector3, "away": Vector3, "members": [{"pos", "land", "yaw"}]}` :
##   des corneilles posées au sol de CROW_ROAD_M de la route, hors forêt, qui s'envolent au passage du
##   cycliste vers `land`, à CROW_LAND_M plus loin de la route (fauna_behaviour.gd).
## Tirages des groupes P23 : hachage de la longueur du parcours et de l'indice du tronçon.
## Lot P24, bêtes des terrains ouverts du format 1.5 (P22) :
## - troupeaux (`herd`, comme ceux des points `livestock`) dans PASTURE_SHARE des prés (`meadow`, vaches ou,
##   une fois sur HORSE_SHARE, 2 à 6 chevaux) et des prairies (`grassland`, moutons, qui tiennent sur une pente
##   jusqu'à SHEEP_MAX_SLOPE) d'au moins PASTURE_MIN_M2, dans un disque de PASTURE_SPREAD_M autour d'un point
##   de la zone tiré de son identifiant ; aucun dans un pré qui a déjà un point `livestock` ;
## - `{"type": "hare", "id", "species": "hare", "pos", "yaw", "flee_dir"}` : au plus HARE_MAX lièvres par
##   tronçon, dans un champ (`farmland`) ou un pré, de HARE_ROAD_M de la route ; ils filent en zigzag loin de la
##   route au passage (fauna_behaviour.gd). Ils suivent la densité `deer` du thème (gibier).
## Un chevreuil porte aussi `"species": "deer"`.
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
# Lot P23 : oiseaux de la campagne ouverte
const CHUNK_M := 1000.0                # même découpage que les tronçons d'osm_streamer.gd
const RAPTOR_SHARE := 0.6              # part des tronçons qui ont un rapace, à fauna.birds = 1
const RAPTOR_ROAD_M := Vector2(60.0, 180.0)
const RAPTOR_AGL_M := Vector2(55.0, 90.0)
const RAPTOR_RADIUS_M := Vector2(35.0, 60.0)
const RAPTOR_OMEGA := Vector2(0.07, 0.11)
const VEE_SHARE := 0.5
const VEE_MIN := 5
const VEE_MAX := 11
const VEE_ROAD_M := 120.0              # le point de passage est à moins de VEE_ROAD_M de la route
const VEE_AGL_M := Vector2(90.0, 160.0)
const VEE_SPEED_MPS := Vector2(11.0, 14.0)
const VEE_SPAN_M := 1800.0
const VEE_SPACING_M := Vector2(4.0, 3.5)   # (en arrière, de côté) entre deux oiseaux de la volée
const CROW_SHARE := 0.7
const CROW_MIN := 4
const CROW_MAX := 9
const CROW_ROAD_M := Vector2(18.0, 50.0)
const CROW_SPREAD_M := 8.0
const CROW_LAND_M := Vector2(50.0, 80.0)
const OPEN_TRIES := 6
## Lot P24
const PASTURE_MIN_M2 := 5000.0
const PASTURE_SHARE := 0.7             # part des prés et prairies qui ont un troupeau, à fauna.livestock = 1
const PASTURE_SPREAD_M := 40.0
const HORSE_SHARE := 0.35              # part des troupeaux de pré qui sont des chevaux
const HORSE_MIN := 2
const HORSE_MAX := 6
const SHEEP_MAX_SLOPE := 0.45
const HARE_MAX := 2
const HARE_SHARE := 0.8                # chance de chaque lièvre du tronçon, à fauna.deer = 1
const HARE_ROAD_M := Vector2(15.0, 60.0)

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


## Vrai si une bête peut se tenir au sol en (x, z), sur une pente d'au plus `max_slope`.
static func ground_ok(ex: Dictionary, x: float, z: float, max_slope: float = MAX_SLOPE) -> bool:
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
		if not is_finite(gx) or not is_finite(gz) or sqrt(gx * gx + gz * gz) > max_slope:
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
				out.append({"type": "deer", "id": "%s_deer" % str(a.get("id", "")), "species": "deer",
					"pos": Vector3(pos2.x, _ground(ex, pos2.x, pos2.y, 0.0), pos2.y),
					"yaw": atan2(outward.x, outward.y), "flee_dir": Vector3(flee.x, 0.0, flee.y)})
				deer_done = true
				break

	if d_live > 0.0:
		out.append_array(_pastures(vegetation_areas, pois, d_live, ex))
	if d_deer > 0.0 and route != null and route.n >= 2:
		out.append_array(_hares(chunk_index, vegetation_areas, route, d_deer, ex))

	if d_birds > 0.0 and route != null and route.n >= 2:
		var wood_rings := []
		for a in woods:
			wood_rings.append(VegetationPlacer._packed_ring(a["outer"]))
		out.append_array(_open_country_birds(chunk_index, route, d_birds, ex, wood_rings))
	return out


## Point de la route à l'abscisse `s`, sa direction et son vecteur unitaire à droite, `{p, fwd, right}` (Vector2).
static func _route_frame(route, s: float) -> Dictionary:
	var i := clampi(int(s / maxf(route.ds_m, 1e-3)), 0, route.n - 2)
	var a := Vector2(route.x[i], route.z[i])
	var b := Vector2(route.x[i + 1], route.z[i + 1])
	var fwd := (b - a).normalized() if b.distance_squared_to(a) > 1e-6 else Vector2(1.0, 0.0)
	var u := clampf((s - i * route.ds_m) / maxf(route.ds_m, 1e-3), 0.0, 1.0)
	return {"p": a.lerp(b, u), "fwd": fwd, "right": Vector2(-fwd.y, fwd.x)}


static func _in_any(rings: Array, x: float, z: float) -> bool:
	for ring in rings:
		if VegetationPlacer._in_ring(x, z, ring):
			return true
	return false


## Groupes P23 du tronçon : rapace, volée en V, corneilles (voir l'en-tête).
static func _open_country_birds(chunk_index: int, route, d_birds: float, ex: Dictionary, wood_rings: Array) -> Array:
	var out := []
	var seed := _h(int(route.length_m * 10.0) & MASK32, chunk_index & MASK32, 23)
	var s0 := chunk_index * CHUNK_M
	var s_len := clampf(route.length_m - s0, 0.0, CHUNK_M)
	if s_len <= 0.0:
		return out
	var tag := "c%d" % chunk_index

	# Rapace en cercle au-dessus d'un terrain ouvert
	if _u(_h(seed, 1)) < d_birds * RAPTOR_SHARE:
		for t in range(OPEN_TRIES):
			var hh := _h(seed, 10 + t)
			var fr := _route_frame(route, s0 + s_len * _u(hh))
			var side := 1.0 if (hh >> 9) & 1 == 0 else -1.0
			var c2: Vector2 = fr["p"] + fr["right"] * side * lerpf(RAPTOR_ROAD_M.x, RAPTOR_ROAD_M.y, _u(VegetationPlacer._mix(hh + 1)))
			if _in_any(wood_rings, c2.x, c2.y):
				continue
			var radius := lerpf(RAPTOR_RADIUS_M.x, RAPTOR_RADIUS_M.y, _u(VegetationPlacer._mix(hh + 2)))
			var top := _ground(ex, c2.x, c2.y, 0.0)
			for j in range(8):
				var ang := TAU * j / 8.0
				top = maxf(top, _ground(ex, c2.x + cos(ang) * radius, c2.y + sin(ang) * radius, top))
			var cy := top + lerpf(RAPTOR_AGL_M.x, RAPTOR_AGL_M.y, _u(VegetationPlacer._mix(hh + 3)))
			out.append({"type": "raptor", "id": "%s_raptor" % tag, "center": Vector3(c2.x, cy, c2.y),
				"radius_m": radius, "angle": TAU * _u(VegetationPlacer._mix(hh + 4)),
				"omega": side * lerpf(RAPTOR_OMEGA.x, RAPTOR_OMEGA.y, _u(VegetationPlacer._mix(hh + 5)))})
			break

	# Volée en V qui traverse le ciel au-dessus de la route
	if _u(_h(seed, 2)) < d_birds * VEE_SHARE:
		var hv := _h(seed, 30)
		var fr := _route_frame(route, s0 + s_len * _u(hv))
		var o2: Vector2 = fr["p"] + fr["right"] * VEE_ROAD_M * (2.0 * _u(VegetationPlacer._mix(hv + 1)) - 1.0)
		# Cap de 30 à 150 degrés par rapport à la route : la volée la traverse, elle ne la suit pas
		var cross := deg_to_rad(lerpf(30.0, 150.0, _u(VegetationPlacer._mix(hv + 2))))
		var dir2: Vector2 = (fr["fwd"] as Vector2).rotated(cross if (hv >> 11) & 1 == 0 else -cross)
		var n := VEE_MIN + int(round((VEE_MAX - VEE_MIN) * _u(VegetationPlacer._mix(hv + 3))))
		var members := []
		for i in range(n):
			var rank := int((i + 1) / 2.0)
			members.append({"back": rank * VEE_SPACING_M.x, "side": (0.0 if i == 0 else (1.0 if i % 2 == 1 else -1.0)) * rank * VEE_SPACING_M.y})
		var gy := _ground(ex, o2.x, o2.y, 0.0)
		out.append({"type": "vee", "id": "%s_vee" % tag,
			"origin": Vector3(o2.x, gy + lerpf(VEE_AGL_M.x, VEE_AGL_M.y, _u(VegetationPlacer._mix(hv + 4))), o2.y),
			"dir": Vector3(dir2.x, 0.0, dir2.y),
			"speed_mps": lerpf(VEE_SPEED_MPS.x, VEE_SPEED_MPS.y, _u(VegetationPlacer._mix(hv + 5))),
			"span_m": VEE_SPAN_M, "phase_m": VEE_SPAN_M * _u(VegetationPlacer._mix(hv + 6)), "members": members})

	# Corneilles posées au sol, hors forêt, qui s'envolent au passage
	if _u(_h(seed, 3)) < d_birds * CROW_SHARE:
		for t in range(OPEN_TRIES):
			var hc := _h(seed, 50 + t)
			var fr := _route_frame(route, s0 + s_len * _u(hc))
			var side := 1.0 if (hc >> 9) & 1 == 0 else -1.0
			var away: Vector2 = fr["right"] * side
			var c2: Vector2 = fr["p"] + away * lerpf(CROW_ROAD_M.x, CROW_ROAD_M.y, _u(VegetationPlacer._mix(hc + 1)))
			if _in_any(wood_rings, c2.x, c2.y) or not ground_ok(ex, c2.x, c2.y):
				continue
			var n := CROW_MIN + int(round((CROW_MAX - CROW_MIN) * _u(VegetationPlacer._mix(hc + 2))))
			var land_d := lerpf(CROW_LAND_M.x, CROW_LAND_M.y, _u(VegetationPlacer._mix(hc + 3)))
			var members := []
			for i in range(n * TRIES_PER_BEAST):
				if members.size() >= n:
					break
				var hm := _h(seed, 100 + t * 64 + i)
				var ang := TAU * _u(hm)
				var off := Vector2(cos(ang), sin(ang)) * CROW_SPREAD_M * sqrt(_u(VegetationPlacer._mix(hm + 1)))
				var p2 := c2 + off
				if _in_any(wood_rings, p2.x, p2.y) or not ground_ok(ex, p2.x, p2.y):
					continue
				var l2 := p2 + away * land_d
				if _in_any(wood_rings, l2.x, l2.y) or not ground_ok(ex, l2.x, l2.y):
					l2 = p2 + away * land_d * 0.5
					if _in_any(wood_rings, l2.x, l2.y) or not ground_ok(ex, l2.x, l2.y):
						l2 = p2
				members.append({"pos": Vector3(p2.x, _ground(ex, p2.x, p2.y, 0.0), p2.y),
					"land": Vector3(l2.x, _ground(ex, l2.x, l2.y, 0.0), l2.y),
					"yaw": TAU * _u(VegetationPlacer._mix(hm + 2))})
			if members.is_empty():
				continue
			out.append({"type": "crows", "id": "%s_crows" % tag, "pos": Vector3(c2.x, _ground(ex, c2.x, c2.y, 0.0), c2.y),
				"away": Vector3(away.x, 0.0, away.y), "members": members})
			break
	return out


## Zones ouvertes de sorte `kinds`, triées par identifiant : [{id, kind, ring}].
static func _open_areas(areas: Array, kinds: Array) -> Array:
	var out := []
	for a in areas:
		if typeof(a) == TYPE_DICTIONARY and str(a.get("kind", "")) in kinds \
				and typeof(a.get("outer")) == TYPE_ARRAY and a["outer"].size() >= 3:
			out.append({"id": str(a.get("id", "")), "kind": str(a["kind"]), "ring": VegetationPlacer._packed_ring(a["outer"])})
	out.sort_custom(func(a, b): return a["id"] < b["id"])
	return out


## Troupeaux des prés et des prairies (lot P24, voir l'en-tête).
static func _pastures(areas: Array, pois: Array, d_live: float, ex: Dictionary) -> Array:
	var out := []
	for a in _open_areas(areas, ["meadow", "grassland"]):
		var ring: PackedVector2Array = a["ring"]
		var seed := VegetationPlacer.hash_string(a["id"])
		if _ring_area(ring) < PASTURE_MIN_M2 or _u(_h(seed, 31)) >= d_live * PASTURE_SHARE:
			continue
		var has_poi := false
		for p in pois:
			if typeof(p) == TYPE_DICTIONARY and str(p.get("kind", "")) == "livestock" \
					and VegetationPlacer._in_ring(float(p.get("x", 0.0)), float(p.get("z", 0.0)), ring):
				has_poi = true
				break
		if has_poi:
			continue
		var species := "sheep"
		if a["kind"] == "meadow":
			species = "horse" if _u(_h(seed, 32)) < HORSE_SHARE else "cow"
		var lo := HORSE_MIN if species == "horse" else HERD_MIN
		var hi := HORSE_MAX if species == "horse" else HERD_MAX
		var n := clampi(lo + int(round((hi - lo) * d_live * _u(_h(seed, 33)))), lo, hi)
		var slope := SHEEP_MAX_SLOPE if species == "sheep" else MAX_SLOPE
		# Centre du troupeau : un point de la zone (boîte de l'anneau, tirages rejetés hors de l'anneau)
		var box := Rect2(ring[0], Vector2.ZERO)
		for v in ring:
			box = box.expand(v)
		var centre := Vector2(INF, INF)
		for t in range(OPEN_TRIES * 2):
			var hc := _h(seed, 40 + t)
			var c := box.position + box.size * Vector2(_u(hc), _u(VegetationPlacer._mix(hc + 1)))
			if VegetationPlacer._in_ring(c.x, c.y, ring) and ground_ok(ex, c.x, c.y, slope):
				centre = c
				break
		if not is_finite(centre.x):
			continue
		var members := []
		var tries := 0
		while members.size() < n and tries < n * TRIES_PER_BEAST:
			var hh := _h(seed, 300 + tries)
			tries += 1
			var ang := TAU * _u(hh)
			var p2 := centre + Vector2(cos(ang), sin(ang)) * PASTURE_SPREAD_M * sqrt(_u(VegetationPlacer._mix(hh + 1)))
			if not VegetationPlacer._in_ring(p2.x, p2.y, ring) or not ground_ok(ex, p2.x, p2.y, slope):
				continue
			members.append({"pos": Vector3(p2.x, _ground(ex, p2.x, p2.y, 0.0), p2.y), "yaw": TAU * _u(VegetationPlacer._mix(hh + 2))})
		if not members.is_empty():
			out.append({"type": "herd", "id": "%s_herd" % a["id"], "species": species, "members": members})
	return out


## Lièvres des champs et des prés près de la route du tronçon (lot P24, voir l'en-tête).
static func _hares(chunk_index: int, areas: Array, route, d_deer: float, ex: Dictionary) -> Array:
	var out := []
	var fields := _open_areas(areas, ["farmland", "meadow"])
	var s0 := chunk_index * CHUNK_M
	var s_len := clampf(route.length_m - s0, 0.0, CHUNK_M)
	if fields.is_empty() or s_len <= 0.0:
		return out
	var rings := []
	for f in fields:
		rings.append(f["ring"])
	var seed := _h(int(route.length_m * 10.0) & MASK32, chunk_index & MASK32, 24)
	for i in range(HARE_MAX):
		if _u(_h(seed, 1 + i)) >= d_deer * HARE_SHARE:
			continue
		for t in range(OPEN_TRIES):
			var hh := _h(seed, 10 + i * 16 + t)
			var fr := _route_frame(route, s0 + s_len * _u(hh))
			var side := 1.0 if (hh >> 9) & 1 == 0 else -1.0
			var away: Vector2 = fr["right"] * side
			var p2: Vector2 = fr["p"] + away * lerpf(HARE_ROAD_M.x, HARE_ROAD_M.y, _u(VegetationPlacer._mix(hh + 1)))
			if not _in_any(rings, p2.x, p2.y) or not ground_ok(ex, p2.x, p2.y):
				continue
			out.append({"type": "hare", "id": "c%d_hare%d" % [chunk_index, i], "species": "hare",
				"pos": Vector3(p2.x, _ground(ex, p2.x, p2.y, 0.0), p2.y),
				"yaw": TAU * _u(VegetationPlacer._mix(hh + 2)), "flee_dir": Vector3(away.x, 0.0, away.y)})
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
			"birds", "vee", "crows":
				out["birds"] += (g["members"] as Array).size()
			"raptor":
				out["birds"] += 1
			"herd":
				out["animals"] += (g["members"] as Array).size()
			"deer", "hare":
				out["animals"] += 1
	return out
