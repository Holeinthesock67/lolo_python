extends RefCounted

## Usagers de la route dessinés sous le budget du préréglage (revue E6-03) : cyclistes du décor
## (road_cyclists_renderer.gd `drawn_riders`, autour de la caméra) et véhicules (traffic_renderer.gd
## `drawn_vehicles`, autour du cycliste). Depuis AS11 le core fait rouler tout le monde (`core_full`) et le budget ne
## règle que le nombre dessiné ; il ne coupe jamais à moins de ALWAYS_DRAWN_M (l'ancienne zone des proches du core) :
## en `low` (4 cyclistes dessinés), dans une file de 6, les deux derniers apparaissaient et disparaissaient à quelques
## mètres du joueur.
## Pas de class_name : charger par preload("res://scripts/drawn_budget.gd").

const ALWAYS_DRAWN_M := 60.0

## Usagers `all` ({id, s}) à dessiner autour de `center_s` : tous sans `core_full` ou sous le budget ; sinon tous ceux
## à moins de ALWAYS_DRAWN_M, puis les plus proches au-delà tant que le budget le permet ; dans l'ordre de `all`.
static func keep(all: Array, core_full: bool, budget: int, center_s: float) -> Array:
	if not core_full or all.size() <= budget or is_nan(center_s):
		return all
	var by_dist := all.duplicate()
	by_dist.sort_custom(func(a, b): return absf(float(a["s"]) - center_s) < absf(float(b["s"]) - center_s))
	var keep := {}
	for i in range(by_dist.size()):
		var u: Dictionary = by_dist[i]
		if i >= budget and absf(float(u["s"]) - center_s) >= ALWAYS_DRAWN_M:
			break
		keep[str(u["id"])] = true
	return all.filter(func(u): return keep.has(str(u["id"])))
