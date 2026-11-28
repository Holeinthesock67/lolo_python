extends RefCounted

## Chaussée dessinée unique (lot CD1, cadrage plans/CADRAGE_CHAUSSEE_DESSINEE_2026-11-26.md, version simple) :
## LA réponse de l'engine à « où est la chaussée ? », pour tous les poseurs du décor. Sans nœud, sans class_name :
## charger par preload("res://scripts/drawn_road.gd").
##
## Avant ce module, quatre axes coexistaient (road_clearance.gd pour l'herbe, VegetationPlacer._road_buckets pour les
## arbres, les points bruts de la route pour l'eau, rien pour les bâtiments des parcours compilés), chacun avec sa
## propre idée de la chaussée : herbe dans une épingle (31/10), dans un virage serré (21/11), sur les amorces (26/11).
##
## Contenu, construit une fois par route (version simple : la route d'un parcours fixe ou d'une démo ne change pas ;
## la mise à jour révision par révision du monde ouvert libre est hors du lot, abandonné le 27/11) :
## - l'axe de la route telle que l'engine la dessine (Catmull-Rom de route_data.gd `sample_xyzh`, tous les
##   AXIS_STEP_M, le pas des coupes du ruban) ;
## - les amorces du départ et de l'arrivée (road_builder.gd `lead_segments`, `axis_sample`), là où elles sont dessinées ;
## - des polylignes de chaussée en plus (`add_polyline`, reprise de #1056 : branches de carrefour), facultatives.
## Une seule grille : cases de `cell_m`, chaque segment rangé dans toutes les cases que touche son rectangle.
##
## Questions : `distance`, `is_clear`, `nearest`, `segments_in`. Lecture seule après construction : sûre depuis
## plusieurs fils à la fois. `shared(route)` rend l'instance commune à tous les poseurs d'une même route.

const RoadBuilder := preload("res://scripts/road_builder.gd")

const DEFAULT_CELL_M := 25.0
## Pas des points de l'axe : celui des coupes du ruban (road_builder.gd SECTION_STEP_M), même règle que le générateur
## (compiler road_ground.py). Les segments droits entre les points du parcours s'écartent de la route dessinée
## jusqu'à 1,2 m dans un virage serré (21/11).
const AXIS_STEP_M := 2.0

var cell_m := DEFAULT_CELL_M
var _grid := {}                      # Vector2i -> PackedInt32Array (indice i du segment [i ; i + 1])
var _ax := PackedFloat64Array()      # points de l'axe dessiné (route, amorces, polylignes ajoutées)
var _az := PackedFloat64Array()
var _as := PackedFloat64Array()      # abscisse s du point (amorce de départ < 0 ; polyligne ajoutée : NAN)

static var _cache := {}              # instance_id de la route -> {"ref": WeakRef, "road": DrawnRoad}
static var _cache_mutex := Mutex.new()


func _init(route_data = null, p_cell_m: float = DEFAULT_CELL_M) -> void:
	cell_m = maxf(p_cell_m, 1.0)
	# La route n'est pas gardée : la table de `shared` la suit par une référence faible, la chaussée ne doit pas la
	# tenir en vie après la séance.
	var route = route_data
	if route == null or route.n < 2:
		return
	# Amorces de chaussée avant le départ et après l'arrivée (road_builder.gd `lead_segments`) : dessinées comme la
	# route, donc tenues dégagées elles aussi (26/11, Almería et Funchal : herbe et rochers sur les amorces).
	var leads: bool = route.has_method("sample") and route.has_method("sample_point")
	var s_from := -RoadBuilder.LEAD_IN_M if leads and RoadBuilder.has_lead_in(route) else 0.0
	var s_to: float = route.length_m + (RoadBuilder.LEAD_OUT_M if leads and RoadBuilder.has_lead_out(route) else 0.0)
	var steps := maxi(int(ceil((s_to - s_from) / AXIS_STEP_M)), 1)
	for k in range(steps + 1):
		var s_k := minf(s_from + k * AXIS_STEP_M, s_to)
		var p: Vector4
		if s_k >= 0.0 and s_k <= route.length_m:
			p = route.sample_xyzh(s_k)
		else:
			var a: Dictionary = RoadBuilder.axis_sample(route, s_k)
			p = Vector4(float(a["x"]), float(a["y"]), float(a["z"]), 0.0)
		_ax.append(p.x)
		_az.append(p.z)
		_as.append(s_k)
	_insert(0, _ax.size() - 1)


## Chaussée commune d'une route : construite au premier appel (dans le fil de l'appelant), puis rendue telle quelle
## à tous les poseurs de cette route. Une route neuve (autre instance) a la sienne. Sans route : null.
static func shared(route_data) -> RefCounted:
	if route_data == null or route_data.n < 2:
		return null
	var id: int = route_data.get_instance_id()
	_cache_mutex.lock()
	var entry = _cache.get(id)
	if entry != null and entry["ref"].get_ref() != route_data:
		entry = null
	if entry == null:
		# Ménage des routes disparues : la table reste petite (une route par séance, quelques-unes dans les tests).
		for k in _cache.keys():
			if _cache[k]["ref"].get_ref() == null:
				_cache.erase(k)
		var script: GDScript = load("res://scripts/drawn_road.gd")
		entry = {"ref": weakref(route_data), "road": script.new(route_data)}
		_cache[id] = entry
	_cache_mutex.unlock()
	return entry["road"]


## Chaussée dessinée en plus de la route (reprise de #1056 `add_polyline` : amorces des branches non suivies des
## carrefours), axe (x, z), sans la relier à la route. À appeler avant de partager l'instance entre des fils.
func add_polyline(line: PackedVector2Array) -> void:
	if line.size() < 2:
		return
	var start := _ax.size()
	for p in line:
		_ax.append(p.x)
		_az.append(p.y)
		_as.append(NAN)
	_insert(start, _ax.size() - 1)


func _insert(from_i: int, to_i: int) -> void:
	for i in range(from_i, to_i):
		var x0: float = minf(_ax[i], _ax[i + 1])
		var x1: float = maxf(_ax[i], _ax[i + 1])
		var z0: float = minf(_az[i], _az[i + 1])
		var z1: float = maxf(_az[i], _az[i + 1])
		for cz in range(floori(z0 / cell_m), floori(z1 / cell_m) + 1):
			for cx in range(floori(x0 / cell_m), floori(x1 / cell_m) + 1):
				var c := Vector2i(cx, cz)
				var ids: PackedInt32Array = _grid.get(c, PackedInt32Array())
				ids.append(i)
				_grid[c] = ids


func is_empty() -> bool:
	return _grid.is_empty()


## Distance horizontale du point à la chaussée dessinée (axe), exacte jusqu'à `cell_m` (au-delà : INF ou plus).
func distance(x: float, z: float) -> float:
	var c := Vector2i(floori(x / cell_m), floori(z / cell_m))
	var best := INF
	var p := Vector2(x, z)
	for dz in range(-1, 2):
		for dx in range(-1, 2):
			var ids: PackedInt32Array = _grid.get(c + Vector2i(dx, dz), PackedInt32Array())
			for i in ids:
				var a := Vector2(_ax[i], _az[i])
				var b := Vector2(_ax[i + 1], _az[i + 1])
				best = minf(best, p.distance_to(Geometry2D.get_closest_point_to_segment(p, a, b)))
	return best


## Vrai si le point est à `clear_m` mètres ou plus de l'axe partout (route, amorces, polylignes ajoutées),
## `clear_m` ≤ `cell_m`. Sans chaussée : toujours vrai. Ne lit que les cases à portée et s'arrête au premier segment
## trop proche (poseurs d'arbres : des milliers de candidats par tuile).
func is_clear(x: float, z: float, clear_m: float) -> bool:
	if _grid.is_empty():
		return true
	var p := Vector2(x, z)
	var c2 := clear_m * clear_m
	for cz in range(floori((z - clear_m) / cell_m), floori((z + clear_m) / cell_m) + 1):
		for cx in range(floori((x - clear_m) / cell_m), floori((x + clear_m) / cell_m) + 1):
			var ids = _grid.get(Vector2i(cx, cz))
			if ids == null:
				continue
			for i in (ids as PackedInt32Array):
				var a := Vector2(_ax[i], _az[i])
				var b := Vector2(_ax[i + 1], _az[i + 1])
				if p.distance_squared_to(Geometry2D.get_closest_point_to_segment(p, a, b)) < c2:
					return false
	return true


## Point de la chaussée le plus proche (à moins de `cell_m`) : {"d": distance, "s": abscisse (NAN sur une polyligne
## ajoutée), "side": −1 à gauche du sens de marche, +1 à droite, 0 sur l'axe}. Vide si rien à portée.
func nearest(x: float, z: float) -> Dictionary:
	var c := Vector2i(floori(x / cell_m), floori(z / cell_m))
	var p := Vector2(x, z)
	var best := INF
	var best_i := -1
	var best_q := Vector2.ZERO
	for dz in range(-1, 2):
		for dx in range(-1, 2):
			var ids: PackedInt32Array = _grid.get(c + Vector2i(dx, dz), PackedInt32Array())
			for i in ids:
				var q := Geometry2D.get_closest_point_to_segment(p, Vector2(_ax[i], _az[i]), Vector2(_ax[i + 1], _az[i + 1]))
				var d := p.distance_to(q)
				if d < best:
					best = d
					best_i = i
					best_q = q
	if best_i < 0:
		return {}
	var a := Vector2(_ax[best_i], _az[best_i])
	var b := Vector2(_ax[best_i + 1], _az[best_i + 1])
	var seg_len := a.distance_to(b)
	var t := 0.0 if seg_len <= 0.0 else a.distance_to(best_q) / seg_len
	var s_val: float = _as[best_i] + (_as[best_i + 1] - _as[best_i]) * t
	# Repère de la séance : x vers l'est, z vers le sud ; côté = signe du produit vectoriel (direction × point).
	var cross := (b - a).cross(p - a)
	var side := 0 if absf(cross) < 1e-9 or best < 1e-6 else (1 if cross > 0.0 else -1)
	return {"d": best, "s": s_val, "side": side}


## Segments de la chaussée dont le rectangle touche `rect` : Vector4(x0, z0, x1, z1), sans doublon (contours des
## bâtiments, cours d'eau).
func segments_in(rect: Rect2) -> PackedVector4Array:
	var out := PackedVector4Array()
	if _grid.is_empty():
		return out
	var seen := {}
	for cz in range(floori(rect.position.y / cell_m), floori(rect.end.y / cell_m) + 1):
		for cx in range(floori(rect.position.x / cell_m), floori(rect.end.x / cell_m) + 1):
			var ids = _grid.get(Vector2i(cx, cz))
			if ids == null:
				continue
			for i in (ids as PackedInt32Array):
				if seen.has(i):
					continue
				seen[i] = true
				var a := Vector2(_ax[i], _az[i])
				var b := Vector2(_ax[i + 1], _az[i + 1])
				if Rect2(a, Vector2.ZERO).expand(b).intersects(rect, true):
					out.append(Vector4(a.x, a.y, b.x, b.y))
	return out


## Vrai si un segment de la chaussée touche `rect` (un poseur saute le contrôle d'une tuile loin de la route).
func touches(rect: Rect2) -> bool:
	for cz in range(floori(rect.position.y / cell_m), floori(rect.end.y / cell_m) + 1):
		for cx in range(floori(rect.position.x / cell_m), floori(rect.end.x / cell_m) + 1):
			var ids = _grid.get(Vector2i(cx, cz))
			if ids == null:
				continue
			for i in (ids as PackedInt32Array):
				if Rect2(Vector2(_ax[i], _az[i]), Vector2.ZERO).expand(Vector2(_ax[i + 1], _az[i + 1])).intersects(rect, true):
					return true
	return false


## Garde finale des objets du bord de route (lot CD1d) : marge au-delà de la demi-largeur de chaussée. Petite, car
## l'objet est posé à partir de SA portion (à demi-largeur + son écart, au moins 0,3 m) : seule une AUTRE portion
## (épingle, route qui repasse, amorce) peut l'en rapprocher. Couvre l'écart des cordes de 2 m dans un virage serré.
const EDGE_GUARD_M := 0.2


## Vrai si `pos` n'est sur aucune chaussée dessinée de la route : à plus de `half_width_m` + EDGE_GUARD_M de tout axe.
## Sans route : vrai.
static func off_road(route_data, pos: Vector3, half_width_m: float) -> bool:
	var road = shared(route_data)
	return road == null or road.is_clear(pos.x, pos.z, half_width_m + EDGE_GUARD_M)
