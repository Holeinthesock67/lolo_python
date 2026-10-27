extends RefCounted

## Placement déterministe de la végétation (Lot K3, Format .world v1 §3, §7 et §9), sans aucun nœud.
##
## Calcule où poser les arbres d'une tuile : dans les polygones `vegetation` du `.world` ou, sans
## polygone, selon un bruit de densité. L'affichage (MultiMeshInstance3D, modèles, niveaux de détail)
## reste aux lots E3 et E4. Pas de class_name : charger par preload("res://scripts/vegetation_placer.gd").
##
## Méthode : grille à tirage décalé (un candidat par cellule, position tirée dans la cellule).
## - Zones OSM : grille alignée sur l'origine du monde, de pas sqrt(10 000 / densité par ha) ; la graine
##   dérive de l'`id` du polygone et de l'indice de la cellule. Le résultat ne dépend donc pas du
##   découpage en tuiles, et le nombre d'arbres d'une zone est proche de surface × densité.
## - Sans zone : grille de la tuile au pas de la densité maximale du bruit (50 % du maximum du thème) ;
##   chaque candidat est gardé avec la probabilité donnée par un bruit de valeur à graine fixe, continu
##   d'une tuile à l'autre ; le tirage dérive de (tile_x, tile_z) et de l'indice de la cellule.
## Hachages et bruit maison sur des entiers 32 bits : même sortie d'une exécution et d'une machine à
## l'autre (aucun appel à randi() ni à String.hash()).
## Exclusions : couloir de la route (road.width_m / 2 + 4 m de l'axe), altitude au-dessus de
## vegetation.treeline_m, pente du terrain au-dessus de terrain.slope_threshold_deg, trous des polygones.
## La pente est celle de la maille de SLOPE_GRID_M qui contient l'arbre (hauteurs aux quatre coins) :
## un appel de `height_at` par arbre au lieu de trois.
## Vitesse (lot O1) : les valeurs du bruit aux nœuds entiers sont calculées une fois par tuile
## (`_lattice`) puis interpolées (`_lattice_noise`) avec les mêmes opérations que `_value_noise` :
## résultat identique au bit près. `last_profile` donne le temps de chaque étape du dernier appel.

const KIND_FACTOR := {"wood": 1.0, "scrub": 0.4, "orchard": 0.6}   # autres kind : ignorés (§7)
const NOISE_MAX_FRACTION := 0.5
const NOISE_SCALE_M := 180.0
const NOISE_SEED := 0x5EED0001
const ROAD_MARGIN_M := 4.0
const ROAD_SUBSTEP_M := 2.0        # axe de la route échantillonné tous les 2 m (Catmull-Rom)
const ROAD_BUCKET_M := 25.0
const SLOPE_GRID_M := 10.0         # pente lue sur une grille de 10 m de la tuile (résolution du MNT)
const SCALE_MIN := 0.7
const SCALE_MAX := 1.3

# Valeurs du thème par défaut, si le thème passé est incomplet.
const DEFAULT_TREELINE_M := 2000.0
const DEFAULT_MAX_DENSITY := 400.0
const DEFAULT_ROAD_WIDTH_M := 6.0
const DEFAULT_SLOPE_DEG := 22.0

const MASK32 := 0xFFFFFFFF
const NOISE_SCALE2_M := NOISE_SCALE_M * 0.37   # seconde octave

## Temps des étapes du dernier `place_tile`, en ms : candidats (bruit ou zones), route, filtre.
var last_profile := {}


# --- hachage et tirages -------------------------------------------------------------------

## Mélange 32 bits (finaliseur de type murmur3).
static func _mix(h: int) -> int:
	h = h & MASK32
	h ^= h >> 16
	h = (h * 0x85EBCA6B) & MASK32
	h ^= h >> 13
	h = (h * 0xC2B2AE35) & MASK32
	h ^= h >> 16
	return h


static func hash3(a: int, b: int, c: int) -> int:
	var h := _mix(a ^ 0x9E3779B9)
	h = _mix(h ^ (b & MASK32))
	h = _mix(h ^ (c & MASK32))
	return h


## FNV-1a 32 bits sur les octets UTF-8 : graine d'un polygone dérivée de son `id`.
static func hash_string(text: String) -> int:
	var h := 0x811C9DC5
	for byte in text.to_utf8_buffer():
		h = ((h ^ byte) * 0x01000193) & MASK32
	return h


static func _unit(h: int) -> float:
	return float(h & 0xFFFFFF) / 16777216.0


## Bruit de valeur 2D dans [0, 1], continu, à graine fixe (deux octaves).
static func density_noise(x: float, z: float) -> float:
	var v := 0.65 * _value_noise(x / NOISE_SCALE_M, z / NOISE_SCALE_M, NOISE_SEED)
	v += 0.35 * _value_noise(x / (NOISE_SCALE_M * 0.37), z / (NOISE_SCALE_M * 0.37), NOISE_SEED + 1)
	return clampf(v, 0.0, 1.0)


## Valeurs `_unit(hash3(seed, ix, iz))` des nœuds [ix0, ix0 + nx[ × [iz0, iz0 + nz[, rangées par lignes.
static func _lattice(seed: int, ix0: int, iz0: int, nx: int, nz: int) -> PackedFloat64Array:
	var out := PackedFloat64Array()
	out.resize(nx * nz)
	for j in range(nz):
		for i in range(nx):
			out[j * nx + i] = _unit(hash3(seed, ix0 + i, iz0 + j))
	return out


## `_value_noise` lu dans une grille de `_lattice` qui couvre (fx, fz) : mêmes opérations, même résultat.
static func _lattice_noise(fx: float, fz: float, lat: PackedFloat64Array, ix0: int, iz0: int, nx: int) -> float:
	var ix := int(floor(fx))
	var iz := int(floor(fz))
	var tx := fx - ix
	var tz := fz - iz
	tx = tx * tx * (3.0 - 2.0 * tx)
	tz = tz * tz * (3.0 - 2.0 * tz)
	var k := (iz - iz0) * nx + (ix - ix0)
	var a := lat[k]
	var b := lat[k + 1]
	var c := lat[k + nx]
	var d := lat[k + nx + 1]
	return lerpf(lerpf(a, b, tx), lerpf(c, d, tx), tz)


static func _value_noise(fx: float, fz: float, seed: int) -> float:
	var ix := int(floor(fx))
	var iz := int(floor(fz))
	var tx := fx - ix
	var tz := fz - iz
	tx = tx * tx * (3.0 - 2.0 * tx)
	tz = tz * tz * (3.0 - 2.0 * tz)
	var a := _unit(hash3(seed, ix, iz))
	var b := _unit(hash3(seed, ix + 1, iz))
	var c := _unit(hash3(seed, ix, iz + 1))
	var d := _unit(hash3(seed, ix + 1, iz + 1))
	return lerpf(lerpf(a, b, tx), lerpf(c, d, tx), tz)


# --- géométrie ------------------------------------------------------------------------------

static func point_in_ring(px: float, pz: float, ring: Array) -> bool:
	return _in_ring(px, pz, _packed_ring(ring))


static func _packed_ring(ring: Array) -> PackedVector2Array:
	var out := PackedVector2Array()
	for p in ring:
		out.append(Vector2(float(p[0]), float(p[1])))
	return out


## Règle pair-impair sur un anneau déjà converti (boucle typée : c'est le cœur du placement).
static func _in_ring(px: float, pz: float, ring: PackedVector2Array) -> bool:
	var inside := false
	var n := ring.size()
	var j := n - 1
	for i in range(n):
		var a: Vector2 = ring[i]
		var b: Vector2 = ring[j]
		if (a.y > pz) != (b.y > pz) and px < (b.x - a.x) * (pz - a.y) / (b.y - a.y) + a.x:
			inside = not inside
		j = i
	return inside


static func _ring_bounds(ring: Array) -> Rect2:
	var lo := Vector2(INF, INF)
	var hi := Vector2(-INF, -INF)
	for p in ring:
		lo = Vector2(minf(lo.x, float(p[0])), minf(lo.y, float(p[1])))
		hi = Vector2(maxf(hi.x, float(p[0])), maxf(hi.y, float(p[1])))
	return Rect2(lo, hi - lo)


static func _theme_value(theme: Dictionary, section: String, key: String, fallback: float) -> float:
	var sec = theme.get(section, {})
	if typeof(sec) == TYPE_DICTIONARY:
		var v = sec.get(key, null)
		if typeof(v) == TYPE_INT or typeof(v) == TYPE_FLOAT:
			return float(v)
	return fallback


## Segments de l'axe de la route proches du rectangle `rect`, rangés par case de ROAD_BUCKET_M.
## Renvoie {cle Vector2i : PackedVector4Array (x0, z0, x1, z1)}.
static func _road_buckets(route, rect: Rect2, corridor: float) -> Dictionary:
	var buckets := {}
	if route == null or route.n < 2:
		return buckets
	var grown := rect.grow(corridor + route.ds_m)
	var prev := Vector2.ZERO
	var have_prev := false
	for i in range(route.n - 1):
		var a := Vector2(route.x[i], route.z[i])
		var b := Vector2(route.x[i + 1], route.z[i + 1])
		var seg_rect := Rect2(a, Vector2.ZERO).expand(b)
		if not grown.intersects(seg_rect, true):
			have_prev = false
			continue
		var s0: float = route.s[i]
		var s1: float = route.s[i + 1]
		var steps := maxi(1, int(ceil((s1 - s0) / ROAD_SUBSTEP_M)))
		if not have_prev:
			var p0: Vector3 = route.sample_point(s0)
			prev = Vector2(p0.x, p0.z)
			have_prev = true
		for k in range(1, steps + 1):
			var p: Vector3 = route.sample_point(s0 + (s1 - s0) * k / float(steps))
			var cur := Vector2(p.x, p.z)
			var r := Rect2(prev, Vector2.ZERO).expand(cur).grow(corridor)
			var bx0 := int(floor(r.position.x / ROAD_BUCKET_M))
			var bz0 := int(floor(r.position.y / ROAD_BUCKET_M))
			var bx1 := int(floor(r.end.x / ROAD_BUCKET_M))
			var bz1 := int(floor(r.end.y / ROAD_BUCKET_M))
			for bx in range(bx0, bx1 + 1):
				for bz in range(bz0, bz1 + 1):
					var key := Vector2i(bx, bz)
					if not buckets.has(key):
						buckets[key] = PackedVector4Array()
					buckets[key].append(Vector4(prev.x, prev.y, cur.x, cur.y))
			prev = cur
	return buckets


static func _near_road(buckets: Dictionary, px: float, pz: float, corridor: float) -> bool:
	var key := Vector2i(int(floor(px / ROAD_BUCKET_M)), int(floor(pz / ROAD_BUCKET_M)))
	if not buckets.has(key):
		return false
	var c2 := corridor * corridor
	var p := Vector2(px, pz)
	for seg in buckets[key]:
		var a := Vector2(seg.x, seg.y)
		var ab := Vector2(seg.z, seg.w) - a
		var len2 := ab.length_squared()
		var t := 0.0 if len2 <= 0.0 else clampf((p - a).dot(ab) / len2, 0.0, 1.0)
		if (a + ab * t).distance_squared_to(p) < c2:
			return true
	return false


# --- placement ------------------------------------------------------------------------------

## Arbres de la tuile (tile_x, tile_z), qui couvre [tile_x × taille ; (tile_x + 1) × taille[ en x et
## de même en z. `height_at.call(x, z)` donne l'altitude du terrain ; `route` (route_data.gd ou null)
## sert au couloir de la route ; `theme` est un thème fusionné (theme_loader.gd) ; `areas` les polygones
## `vegetation` (§7). Chaque élément : Vector4(x, y, z, échelle) dans le repère du monde.
func place_tile(tile_x: int, tile_z: int, tile_size_m: float, height_at: Callable,
		route, theme: Dictionary, areas: Array = []) -> PackedVector4Array:
	var out := PackedVector4Array()
	if tile_size_m <= 0.0:
		return out
	var tile := Rect2(tile_x * tile_size_m, tile_z * tile_size_m, tile_size_m, tile_size_m)
	var ctx := {
		"treeline": _theme_value(theme, "vegetation", "treeline_m", DEFAULT_TREELINE_M),
		"max_density": maxf(0.0, _theme_value(theme, "vegetation", "max_density_per_ha", DEFAULT_MAX_DENSITY)),
		"max_slope": tan(deg_to_rad(clampf(_theme_value(theme, "terrain", "slope_threshold_deg", DEFAULT_SLOPE_DEG), 0.0, 89.9))),
		"corridor": _theme_value(theme, "road", "width_m", DEFAULT_ROAD_WIDTH_M) * 0.5 + ROAD_MARGIN_M,
		"height_at": height_at,
	}
	var t0 := Time.get_ticks_usec()
	ctx["roads"] = _road_buckets(route, tile, ctx["corridor"])
	var t1 := Time.get_ticks_usec()
	var cand := PackedFloat64Array()   # triplets (x, z, tirage de l'échelle)
	if areas.is_empty():
		_place_noise(cand, tile_x, tile_z, tile, ctx)
	else:
		for area in areas:
			_place_area(cand, area, tile, ctx)
	var t2 := Time.get_ticks_usec()
	_filter(out, cand, tile, height_at, ctx)
	var t3 := Time.get_ticks_usec()
	last_profile = {"route_ms": (t1 - t0) / 1000.0, "candidats_ms": (t2 - t1) / 1000.0,
		"filtre_ms": (t3 - t2) / 1000.0, "candidats": cand.size() / 3, "arbres": out.size()}
	return out


func _place_area(cand: PackedFloat64Array, area: Variant, tile: Rect2, ctx: Dictionary) -> void:
	if typeof(area) != TYPE_DICTIONARY:
		return
	var factor = KIND_FACTOR.get(str(area.get("kind", "")), null)
	var outer = area.get("outer", [])
	if factor == null or typeof(outer) != TYPE_ARRAY or outer.size() < 3:
		return
	var density := clampf(float(area.get("density", 0.0)), 0.0, 1.0) * float(factor) * float(ctx["max_density"])
	if density <= 0.0:
		return
	var outer_ring := _packed_ring(outer)
	var holes: Array[PackedVector2Array] = []
	var raw_holes = area.get("holes", [])
	if typeof(raw_holes) == TYPE_ARRAY:
		for hole in raw_holes:
			if typeof(hole) == TYPE_ARRAY and hole.size() >= 3:
				holes.append(_packed_ring(hole))
	var box := _ring_bounds(outer).intersection(tile)
	if box.size.x <= 0.0 or box.size.y <= 0.0:
		return
	var cell := sqrt(10000.0 / density)
	var tx0 := tile.position.x
	var tz0 := tile.position.y
	var tx1 := tile.end.x
	var tz1 := tile.end.y
	var seed := hash_string(str(area.get("id", "")))
	var cx0 := int(floor(box.position.x / cell))
	var cz0 := int(floor(box.position.y / cell))
	var cx1 := int(floor(box.end.x / cell))
	var cz1 := int(floor(box.end.y / cell))
	for cz in range(cz0, cz1 + 1):
		var hz := _mix(seed ^ _mix(cz ^ 0x9E3779B9))   # = hash3(seed, ·, cz) calculé une fois par rangée
		for cx in range(cx0, cx1 + 1):
			var h := _mix(hz ^ (cx & MASK32))
			var px := (cx + _unit(h)) * cell
			var pz := (cz + _unit(_mix(h + 1))) * cell
			if px < tx0 or px >= tx1 or pz < tz0 or pz >= tz1 or not _in_ring(px, pz, outer_ring):
				continue
			var in_hole := false
			for hole in holes:
				if _in_ring(px, pz, hole):
					in_hole = true
					break
			if not in_hole:
				cand.append(px)
				cand.append(pz)
				cand.append(_unit(_mix(h + 2)))


func _place_noise(cand: PackedFloat64Array, tile_x: int, tile_z: int, tile: Rect2, ctx: Dictionary) -> void:
	var density := float(ctx["max_density"]) * NOISE_MAX_FRACTION
	if density <= 0.0:
		return
	var cells := maxi(1, int(round(tile.size.x / sqrt(10000.0 / density))))
	var cell := tile.size.x / cells
	var seed := hash3(0x7EE5, tile_x, tile_z)
	# Nœuds du bruit des deux octaves qui couvrent la tuile (une maille de marge de chaque côté).
	var ax0 := int(floor(tile.position.x / NOISE_SCALE_M)) - 1
	var az0 := int(floor(tile.position.y / NOISE_SCALE_M)) - 1
	var an := int(floor(tile.end.x / NOISE_SCALE_M)) - ax0 + 3
	var anz := int(floor(tile.end.y / NOISE_SCALE_M)) - az0 + 3
	var lat1 := _lattice(NOISE_SEED, ax0, az0, an, anz)
	var bx0 := int(floor(tile.position.x / NOISE_SCALE2_M)) - 1
	var bz0 := int(floor(tile.position.y / NOISE_SCALE2_M)) - 1
	var bn := int(floor(tile.end.x / NOISE_SCALE2_M)) - bx0 + 3
	var bnz := int(floor(tile.end.y / NOISE_SCALE2_M)) - bz0 + 3
	var lat2 := _lattice(NOISE_SEED + 1, bx0, bz0, bn, bnz)
	var n := cand.size()
	cand.resize(n + cells * cells * 3)
	for j in range(cells):
		var hj := _mix(seed ^ _mix(j ^ 0x9E3779B9))
		for i in range(cells):
			var h := _mix(hj ^ i)
			var px := tile.position.x + (i + _unit(h)) * cell
			var pz := tile.position.y + (j + _unit(_mix(h + 1))) * cell
			# = density_noise(px, pz), lu dans les grilles des nœuds
			var v := 0.65 * _lattice_noise(px / NOISE_SCALE_M, pz / NOISE_SCALE_M, lat1, ax0, az0, an)
			v += 0.35 * _lattice_noise(px / NOISE_SCALE2_M, pz / NOISE_SCALE2_M, lat2, bx0, bz0, bn)
			if _unit(_mix(h + 3)) >= clampf(v, 0.0, 1.0):
				continue
			cand[n] = px
			cand[n + 1] = pz
			cand[n + 2] = _unit(_mix(h + 2))
			n += 3
	cand.resize(n)


## Applique les exclusions aux candidats et écrit les arbres gardés.
func _filter(out: PackedVector4Array, cand: PackedFloat64Array, tile: Rect2, height_at: Callable,
		ctx: Dictionary) -> void:
	if cand.is_empty():
		return
	var roads: Dictionary = ctx["roads"]
	var corridor: float = ctx["corridor"]
	var treeline: float = ctx["treeline"]
	var max_slope: float = ctx["max_slope"]
	# Grille des hauteurs de la tuile, pour la pente.
	var cells := maxi(1, int(ceil(tile.size.x / SLOPE_GRID_M)))
	var step := tile.size.x / cells
	var grid := PackedFloat64Array()
	grid.resize((cells + 1) * (cells + 1))
	for j in range(cells + 1):
		for i in range(cells + 1):
			grid[j * (cells + 1) + i] = float(height_at.call(tile.position.x + i * step, tile.position.y + j * step))
	var slope_ok := PackedByteArray()
	slope_ok.resize(cells * cells)
	for j in range(cells):
		for i in range(cells):
			var h00 := grid[j * (cells + 1) + i]
			var h10 := grid[j * (cells + 1) + i + 1]
			var h01 := grid[(j + 1) * (cells + 1) + i]
			var h11 := grid[(j + 1) * (cells + 1) + i + 1]
			var gx := ((h10 + h11) - (h00 + h01)) / (2.0 * step)
			var gz := ((h01 + h11) - (h00 + h10)) / (2.0 * step)
			var g := sqrt(gx * gx + gz * gz)
			slope_ok[j * cells + i] = 1 if is_finite(g) and g <= max_slope else 0
	var n := out.size()
	out.resize(n + cand.size() / 3)
	var k := 0
	while k < cand.size():
		var px := cand[k]
		var pz := cand[k + 1]
		var u := cand[k + 2]
		k += 3
		var ci := clampi(int((px - tile.position.x) / step), 0, cells - 1)
		var cj := clampi(int((pz - tile.position.y) / step), 0, cells - 1)
		if slope_ok[cj * cells + ci] == 0:
			continue
		if not roads.is_empty() and _near_road(roads, px, pz, corridor):
			continue
		var y := float(height_at.call(px, pz))
		if not is_finite(y) or y > treeline:
			continue
		out[n] = Vector4(px, y, pz, SCALE_MIN + (SCALE_MAX - SCALE_MIN) * u)
		n += 1
	out.resize(n)
