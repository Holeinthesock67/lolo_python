extends RefCounted

## Distance à la route sur TOUT le parcours (garde-fou « rien du paysage sur la chaussée »), sans nœud.
## Pas de class_name : charger par preload("res://scripts/road_clearance.gd").
##
## Un objet du décor posé à partir d'un point de la route (touffes d'herbe, détails de sol) ne connaît que
## ce point : dans une épingle, au creux d'un virage serré ou là où le parcours repasse près de lui-même
## (boucle, croisement, aller-retour), il peut tomber sur une AUTRE portion de la route. Cette grille range
## chaque segment de l'axe dans toutes les cases que touche son rectangle : `distance(x, z)` est exacte
## jusqu'à `cell_m` quel que soit le pas de la route, et `is_clear(x, z, d)` dit si le point est à plus de
## `d` mètres de l'axe partout, amorces du départ et de l'arrivée comprises (road_builder.gd). Utilisée par
## grass_tufts.gd et ground_details.gd à la génération, et par le contrôle des parcours de démonstration
## (tests/test_herbe_route.gd).

const RoadBuilder := preload("res://scripts/road_builder.gd")

const DEFAULT_CELL_M := 25.0
## Pas des points de l'axe : celui des coupes du ruban (road_builder.gd SECTION_STEP_M). L'axe est la route telle que
## l'engine la dessine (Catmull-Rom de route_data.gd), pas les segments droits entre les points du parcours, qui
## s'en écartent jusqu'à 1,2 m dans un virage serré (21/11 : touffes d'herbe 18 cm à l'intérieur du ruban, banc
## du lac d'Annecy). Même règle que le générateur (compiler road_ground.py).
const AXIS_STEP_M := 2.0

var route = null
var cell_m := DEFAULT_CELL_M
var _grid := {}                      # Vector2i -> PackedInt32Array (indice k du segment [k ; k + 1] de l'axe)
var _ax := PackedFloat64Array()      # points de l'axe dessiné
var _az := PackedFloat64Array()


func _init(route_data = null, p_cell_m: float = DEFAULT_CELL_M) -> void:
	cell_m = maxf(p_cell_m, 1.0)
	route = route_data
	if route == null or route.n < 2:
		return
	# Amorces de chaussée avant le départ et après l'arrivée (road_builder.gd `lead_segments`) : dessinées comme la
	# route, donc tenues dégagées elles aussi (26/11, bancs d'Almería et de Funchal : 308 et 2 252 touffes d'herbe,
	# rochers compris, sur l'amorce d'arrivée ou de départ d'une balade du monde ouvert).
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
	for i in range(_ax.size() - 1):
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


## Distance horizontale du point à l'axe de la route, exacte jusqu'à `cell_m` (au-delà : INF ou plus).
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


## Vrai si le point est à `clear_m` mètres ou plus de l'axe de la route, sur tout le parcours
## (`clear_m` ≤ `cell_m`). Sans route : toujours vrai.
func is_clear(x: float, z: float, clear_m: float) -> bool:
	if _grid.is_empty():
		return true
	return distance(x, z) >= clear_m
