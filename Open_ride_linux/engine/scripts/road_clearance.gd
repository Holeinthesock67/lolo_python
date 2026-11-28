extends RefCounted

## Distance à la route sur TOUT le parcours (garde-fou « rien du paysage sur la chaussée »), sans nœud.
## Pas de class_name : charger par preload("res://scripts/road_clearance.gd").
##
## Lot CD1a : simple façade de la chaussée dessinée unique (drawn_road.gd), gardée pour ses appelants (grass_tufts.gd,
## ground_details.gd, volcano_fx.gd, tests/test_herbe_route.gd) ; même résultat qu'avant (axe en Catmull-Rom tous les
## 2 m, amorces du départ et de l'arrivée, grille de 25 m). Avec la taille de case par défaut, l'instance est celle
## que partagent tous les poseurs de la route (`DrawnRoad.shared`) : construite une fois au lieu d'une par poseur.

const DrawnRoad := preload("res://scripts/drawn_road.gd")

const DEFAULT_CELL_M := DrawnRoad.DEFAULT_CELL_M
const AXIS_STEP_M := DrawnRoad.AXIS_STEP_M

var route = null
var cell_m := DEFAULT_CELL_M
var drawn: DrawnRoad = null


func _init(route_data = null, p_cell_m: float = DEFAULT_CELL_M) -> void:
	cell_m = maxf(p_cell_m, 1.0)
	route = route_data
	if route == null or route.n < 2:
		return
	if is_equal_approx(cell_m, DrawnRoad.DEFAULT_CELL_M):
		drawn = DrawnRoad.shared(route)
	else:
		drawn = DrawnRoad.new(route, cell_m)


func is_empty() -> bool:
	return drawn == null or drawn.is_empty()


## Distance horizontale du point à l'axe de la route, exacte jusqu'à `cell_m` (au-delà : INF ou plus).
func distance(x: float, z: float) -> float:
	return INF if drawn == null else drawn.distance(x, z)


## Vrai si le point est à `clear_m` mètres ou plus de l'axe de la route, sur tout le parcours
## (`clear_m` ≤ `cell_m`). Sans route : toujours vrai.
func is_clear(x: float, z: float, clear_m: float) -> bool:
	return drawn == null or drawn.is_clear(x, z, clear_m)
