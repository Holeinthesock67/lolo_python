extends SceneTree

## Tests sans écran des marques des segments et des arches de bonus (lot T8) : lecture de la couche
## `segments` par route_data.gd, modèle segment_markers_model.gd (panneaux, portiques, arches, fenêtre
## autour de la caméra, montées pour le décor) et affichage segment_markers.gd (nœuds, budget).
## Lancement : godot --headless --path engine --script res://tests/unit/test_segment_markers_model.gd

const RouteDataScript := preload("res://scripts/route_data.gd")
const Model := preload("res://scripts/segment_markers_model.gd")
const SegmentMarkers := preload("res://scripts/segment_markers.gd")
const LivingDecor := preload("res://scripts/living_decor.gd")
const ClimbTest := preload("res://tests/unit/test_climb_detector.gd")

const MAX_NODES := 50

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _flat(_s: float) -> float:
	return 0.0


func _init() -> void:
	call_deferred("_run")


func _summary(marks: Array) -> Array:
	var out := []
	for m in marks:
		out.append("%s@%d" % [m["kind"], int(round(float(m["s"])))])
	return out


func _run() -> void:
	_vectors()
	_demo_route()
	_without_layer_and_invalid()
	_loop_and_window()
	_render()
	print("test_segment_markers_model : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)


## Vecteurs partagés avec le core (ArchSchedule et lecture de powerups.toml, lots T6 et T8).
func _vectors() -> void:
	var doc = JSON.parse_string(FileAccess.get_file_as_string("res://tests/data/arch_schedule_vectors.json"))
	_check(typeof(doc) == TYPE_DICTIONARY, "vecteurs des arches lisibles")
	if typeof(doc) != TYPE_DICTIONARY:
		return
	var bad := []
	for case in doc["positions"]:
		var got := Model.arch_positions(float(case["every_m"]), float(case["length_m"]))
		var want := PackedFloat64Array()
		for p in case["positions"]:
			want.append(float(p))
		if got != want:
			bad.append("%s : %s" % [str(case), str(got)])
	_check(bad.is_empty(), "positions des arches identiques au core (%s)" % str(bad))
	bad = []
	for case in doc["files"]:
		var got := Model.arch_every_m_from_text(str(case["text"]))
		if absf(got - float(case["arch_every_m"])) > 1e-6:
			bad.append("%s → %s" % [str(case["text"]).c_escape(), str(got)])
	_check(bad.is_empty(), "arch_every_m de powerups.toml lu comme le core (%s)" % str(bad))
	_check(Model.arch_every_m_from_file("res://tests/data/absent_powerups.toml") == Model.DEFAULT_ARCH_EVERY_M,
		"sans fichier : une arche tous les 5 000 m")


## Parcours de démonstration : montée de 0 à 1 500 m (cat. 4), sprint de 2 860 à 3 290 m, 5 km.
func _demo_route() -> void:
	var route = RouteDataScript.new()
	_check(route.load_world_dir("res://demo/demo.world"), "demo.world chargé : " + route.load_error)
	_check(route.segments_present and route.segments.size() == 2
		and route.segments[0]["id"] == "climb1" and route.segments[1]["id"] == "sprint1",
		"couche segments lue : climb1 puis sprint1 (%s)" % str(route.segments))
	var marks: Array = Model.items(route, route.segments, 5000.0)
	var expect := ["start@0", "panel@15", "panel@500", "panel@1000", "finish@1500", "panel@1860",
		"panel@2360", "panel@2660", "start@2860", "finish@3290"]
	_check(_summary(marks) == expect, "marques du parcours de démonstration (%s)" % str(_summary(marks)))
	var texts := {}
	for m in marks:
		if m["kind"] == "panel":
			texts[int(round(float(m["s"])))] = m["lines"]
	_check(texts.get(15) == ["Montée de 4e catégorie", "1,5 km à 3,6 %"],
		"pied de montée au départ : catégorie, longueur et pente (%s)" % str(texts.get(15)))
	_check(texts.get(500) == ["Sommet dans 1 km"] and texts.get(1000) == ["Sommet dans 500 m"],
		"sommet dans 1 km et 500 m")
	_check(texts.get(1860) == ["Sprint dans 1 km"] and texts.get(2360) == ["Sprint dans 500 m"]
		and texts.get(2660) == ["Sprint dans 200 m"], "sprint dans 1 km, 500 m et 200 m")
	var gantry: Dictionary = marks[0]
	_check(gantry["lines"] == ["Montée 1", "Départ"] and gantry["type"] == "climb" and marks[4]["lines"][1] == "Arrivée",
		"portiques : nom du segment, départ et arrivée")
	_check(marks.all(func(m): return m["kind"] != "panel" or int(m["side"]) == -1), "panneaux à gauche de la route")
	_check(Model.category_text("HC") == "hors catégorie" and Model.category_text("1") == "1re catégorie"
		and Model.category_text("3") == "3e catégorie", "noms des catégories")
	var climbs: Array = LivingDecor.climbs_of(route)
	_check(climbs.size() == 1 and float(climbs[0]["start_s"]) == 0.0 and float(climbs[0]["summit_s"]) == 1500.0
		and is_equal_approx(float(climbs[0]["summit_alt_m"]), float(route.sample(1500.0)["alt_m"]))
		and float(climbs[0]["max_km_grade_pct"]) >= float(climbs[0]["avg_grade_pct"]) - 0.5,
		"décor : montée prise dans la couche segments (%s)" % str(climbs))


func _without_layer_and_invalid() -> void:
	var plain = ClimbTest.make_route(12000.0, Callable(self, "_flat"))
	_check(not plain.segments_present and plain.segments.is_empty(), "route sans couche : aucun segment")
	_check(_summary(Model.items(plain, plain.segments, 5000.0)) == ["arch@5000", "arch@10000"],
		"route sans couche : seulement les arches")
	_check(Model.items(plain, plain.segments, 0.0).is_empty(), "arch_every_m = 0 : aucune arche")
	_check(LivingDecor.climbs_of(plain).is_empty(), "décor : détection de climb_detector.gd sans couche")
	var good := {"version": "1.0", "segments": [
		{"id": "sprint1", "name": "Sprint", "type": "sprint", "s_start": 4000.0, "s_end": 4400.0, "extra": 1}]}
	_check(plain.load_segments_dict(good) and plain.segments.size() == 1, "champ inconnu ignoré")
	var cases := {
		"type inconnu": {"version": "1.0", "segments": [{"id": "a", "type": "descente", "s_start": 1.0, "s_end": 2.0}]},
		"hors du parcours": {"version": "1.0", "segments": [{"id": "a", "type": "climb", "s_start": 1.0, "s_end": 99000.0}]},
		"version": {"version": "2.0", "segments": []},
		"double": {"version": "1.0", "segments": [{"id": "a", "type": "climb", "s_start": 1.0, "s_end": 2.0},
			{"id": "a", "type": "sprint", "s_start": 3.0, "s_end": 4.0}]},
		"illisible": null,
	}
	for label in cases:
		var ok: bool = plain.load_segments_dict(cases[label])
		_check(not ok and plain.segments.is_empty() and not plain.segments_present and plain.segments_error != "",
			"couche invalide (%s) ignorée : %s" % [label, plain.segments_error])


func _loop_and_window() -> void:
	var loop = ClimbTest.make_route(5000.0, Callable(self, "_flat"))
	loop.type = "loop"   # boucle fictive (la route d'essai n'est pas fermée) : seules les positions comptent
	var ok: bool = loop.load_segments_dict({"version": "1.0", "segments": [
		{"id": "sprint1", "name": "Sprint", "type": "sprint", "s_start": 300.0, "s_end": 700.0}]})
	_check(ok, "boucle : couche lue")
	var marks: Array = Model.items(loop, loop.segments, 0.0)
	_check(_summary(marks) == ["panel@100", "start@300", "finish@700", "panel@4300", "panel@4800"],
		"boucle : panneaux d'approche au tour précédent (%s)" % str(_summary(marks)))
	var starts := Model.starts(marks)
	var seen := []
	for i in Model.window(starts, 4900.0, 5000.0, true):
		seen.append(_summary([marks[i]])[0])
	seen.sort()
	_check(seen == ["panel@100", "start@300"], "fenêtre à cheval sur la ligne (%s)" % str(seen))
	var open_seen := Model.window(starts, 4700.0, 5000.0, false)
	_check(open_seen.size() == 1 and marks[open_seen[0]]["s"] == 4800.0,
		"parcours ouvert : pas de retour au départ (%s)" % str(open_seen))
	_check(Model.window(starts, 2500.0, 5000.0, true).is_empty(), "rien de proche : aucune marque")


func _render() -> void:
	var route = RouteDataScript.new()
	route.load_world_dir("res://demo/demo.world")
	var view = SegmentMarkers.new()
	root.add_child(view)
	view.set_route(route, 5000.0, 6.0)
	view.update(0.0, true)
	_check(_summary(view.shown()).size() == 2, "départ : portique et panneau de la montée (%s)" % str(_summary(view.shown())))
	view.update(2650.0, true)
	var shown := _summary(view.shown())
	shown.sort()
	_check(shown == ["panel@2660", "start@2860"], "avant le sprint : panneau des 200 m et portique (%s)" % str(shown))
	_check(view.active_node_count() > 0 and view.active_node_count() < MAX_NODES,
		"budget : %d nœuds actifs (moins de %d)" % [view.active_node_count(), MAX_NODES])
	view.update(4500.0, true)
	_check(view.shown().is_empty() and view.active_node_count() == 0, "aucun segment proche : aucun nœud")
	var long = ClimbTest.make_route(12000.0, Callable(self, "_flat"))
	view.set_route(long, 5000.0, 6.0)
	view.update(4800.0, false)
	_check(view.shown().is_empty(), "arches cachées en ERG ou option « Bonus » coupée")
	view.update(4800.0, true)
	_check(_summary(view.shown()) == ["arch@5000"], "arche de bonus à 5 000 m")
	var arch: Node3D = view.get_children().filter(func(n): return not n.is_queued_for_deletion())[0]
	_check(absf(arch.global_position.x - float(long.sample(5000.0)["x"])) < 0.01, "arche posée sur la route")
	view.queue_free()
