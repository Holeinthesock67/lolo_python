extends RefCounted

## Distance à la route sur TOUT le parcours (garde-fou « rien du paysage sur la chaussée »), sans nœud.
## Pas de class_name : charger par preload("res://scripts/road_clearance.gd").
##
## Un objet du décor posé à partir d'un point de la route (touffes d'herbe, détails de sol) ne connaît que
## ce point : dans une épingle, au creux d'un virage serré ou là où le parcours repasse près de lui-même
## (boucle, croisement, aller-retour), il peut tomber sur une AUTRE portion de la route. Cette grille range
## chaque segment de l'axe dans toutes les cases que touche son rectangle : `distance(x, z)` est exacte
## jusqu'à `cell_m` quel que soit le pas de la route, et `is_clear(x, z, d)` dit si le point est à plus de
## `d` mètres de l'axe partout. Utilisée par grass_tufts.gd et ground_details.gd à la génération, et par le
## contrôle des parcours de démonstration (tests/test_herbe_route.gd).

const DEFAULT_CELL_M := 25.0

var route = null
var cell_m := DEFAULT_CELL_M
var _grid := {}                      # Vector2i -> PackedInt32Array (indice i du segment [i ; i + 1])


func _init(route_data = null, p_cell_m: float = DEFAULT_CELL_M) -> void:
	cell_m = maxf(p_cell_m, 1.0)
	route = route_data
	if route == null or route.n < 2:
		return
	for i in range(route.n - 1):
		var x0: float = minf(route.x[i], route.x[i + 1])
		var x1: float = maxf(route.x[i], route.x[i + 1])
		var z0: float = minf(route.z[i], route.z[i + 1])
		var z1: float = maxf(route.z[i], route.z[i + 1])
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
				var a := Vector2(route.x[i], route.z[i])
				var b := Vector2(route.x[i + 1], route.z[i + 1])
				best = minf(best, p.distance_to(Geometry2D.get_closest_point_to_segment(p, a, b)))
	return best


## Vrai si le point est à `clear_m` mètres ou plus de l'axe de la route, sur tout le parcours
## (`clear_m` ≤ `cell_m`). Sans route : toujours vrai.
func is_clear(x: float, z: float, clear_m: float) -> bool:
	if _grid.is_empty():
		return true
	return distance(x, z) >= clear_m
