extends SceneTree

## Tests sans écran des usagers dessinés sous le budget du préréglage (revue E6-03, `drawn_budget.gd`) : cyclistes du
## décor (road_cyclists_renderer.gd `drawn_riders`) et véhicules (traffic_renderer.gd `drawn_vehicles`).
## Lancement : godot --headless --path engine --script res://tests/unit/test_drawn_budget.gd

const DrawnBudget := preload("res://scripts/drawn_budget.gd")
const RoadCyclistsModel := preload("res://scripts/road_cyclists_model.gd")
const RoadCyclistsRenderer := preload("res://scripts/road_cyclists_renderer.gd")
const TrafficModel := preload("res://scripts/traffic_model.gd")
const TrafficRenderer := preload("res://scripts/traffic_renderer.gd")

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _ids(list: Array) -> Array:
	return list.map(func(u): return str(u["id"]))


## File de 6 cyclistes à 2,1 m l'un de l'autre, devant `s0`, et deux loin devant.
func _file(s0: float) -> Array:
	var out := []
	for i in range(6):
		out.append({"id": "f%d" % i, "s": s0 + 2.1 * i})
	out.append({"id": "loin1", "s": s0 + 300.0})
	out.append({"id": "loin2", "s": s0 + 500.0})
	return out


func _test_keep() -> void:
	var all := _file(1000.0)
	# Préréglage `low` (4 dessinés) : toute la file à côté du joueur reste dessinée, les lointains sont coupés.
	var kept := DrawnBudget.keep(all, true, 4, 1004.0)
	_check(_ids(kept) == ["f0", "f1", "f2", "f3", "f4", "f5"], "low : file de 6 à quelques mètres, tous dessinés (%s)" % str(_ids(kept)))
	# Le budget coupe toujours au-delà de ALWAYS_DRAWN_M : les plus proches d'abord.
	kept = DrawnBudget.keep(all, true, 4, 1000.0 + 300.0 - DrawnBudget.ALWAYS_DRAWN_M - 10.0)
	_check(kept.size() == 4 and _ids(kept).has("loin1") and not _ids(kept).has("loin2"), "loin de tous : budget de 4, les plus proches (%s)" % str(_ids(kept)))
	# Derrière la caméra aussi (doublés à 2 à 4 m).
	kept = DrawnBudget.keep(all, true, 2, 1000.0 + 2.1 * 5 + 3.0)
	_check(_ids(kept) == ["f0", "f1", "f2", "f3", "f4", "f5"], "file doublée juste derrière : pas de disparition (%s)" % str(_ids(kept)))
	# Ordre de la liste gardé ; sans `core_full`, sous le budget ou sans centre : tout.
	_check(DrawnBudget.keep(all, false, 2, 1000.0).size() == all.size(), "sans core_full : tout")
	_check(DrawnBudget.keep(all, true, 20, 1000.0).size() == all.size(), "sous le budget : tout")
	_check(DrawnBudget.keep(all, true, 2, NAN).size() == all.size(), "sans centre connu : tout")
	_check(DrawnBudget.ALWAYS_DRAWN_M == 60.0, "rayon toujours dessiné : 60 m (l'ancienne zone des proches du core)")


func _test_renderers() -> void:
	var tm = TrafficModel.new()
	tm.core_full = true
	tm.budget = 3
	tm.vehicles = [{"id": "v1", "s": 1010.0}, {"id": "v2", "s": 1020.0}, {"id": "v3", "s": 1030.0},
		{"id": "v4", "s": 1040.0}, {"id": "v5", "s": 1400.0}]
	var vs: Array = TrafficRenderer.drawn_vehicles(tm, 1000.0)
	_check(_ids(vs) == ["v1", "v2", "v3", "v4"], "véhicules : les 4 à moins de 60 m dessinés malgré un budget de 3 (%s)" % str(_ids(vs)))
	var rm = RoadCyclistsModel.new()
	rm.core_full = true
	rm.budget = 4
	var members := []
	for i in range(6):
		members.append({"id": "c1-%d" % i, "dl": 2.1 * i, "lateral": 1.5})
	rm.groups = [{"id": "c1", "s": 1010.5, "dir": 1, "members": members}]
	var rs: Array = RoadCyclistsRenderer.drawn_riders(rm, 1004.0)
	_check(rs.size() == 6, "cyclistes du décor : file de 6 dessinée en entier en low (%d)" % rs.size())


func _init() -> void:
	_test_keep()
	_test_renderers()
	print("test_drawn_budget : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
