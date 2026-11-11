extends SceneTree

## Tests sans écran des objets du « Grand Prix des objets » en 3D et de leurs sons (série GP, lot GP7) : boîtes
## (deux rangées de trois au plus), objets à la bonne voie, réserve d'instances (place gardée d'une trame à
## l'autre, libérée hors trame, aucune création en course), effets par préréglage (low sans particules),
## onomatopées et sons (doublons de `gp_hit` écartés) ; scène construite et mise à jour sans plantage.
## Lancement : godot --headless --path engine --script res://tests/unit/test_gp_scene.gd

const Model := preload("res://scripts/grandprix/gp_scene_model.gd")
const Sounds := preload("res://scripts/grandprix/gp_sound_model.gd")
const Scene := preload("res://scripts/grandprix/gp_scene.gd")
const EventSounds := preload("res://scripts/event_sounds_model.gd")

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _init() -> void:
	call_deferred("_run")


## Route droite vers le nord : s le long de -Z.
class FakeRoute:
	func sample(s: float) -> Dictionary:
		return {"x": 0.0, "y": 0.0, "z": -s, "heading_deg": 0.0}


func _count_nodes(n: Node) -> int:
	var c := 1
	for ch in n.get_children():
		c += _count_nodes(ch)
	return c


func _run() -> void:
	# Boîtes : trois par rangée, deux rangées au plus
	var bx: Array = Model.boxes({"boxes": [1950, 3450, 4950]})
	_check(bx.size() == 6 and bx[0]["s"] == 1950.0 and bx[5]["s"] == 3450.0, "boîtes : deux rangées de trois")
	_check(bx[0]["lateral"] == 0.68 and bx[1]["lateral"] == 1.45 and bx[2]["lateral"] == 2.22, "boîtes : une par voie")
	_check(Model.boxes(null).is_empty() and Model.boxes({"boxes": "x"}).is_empty(), "boîtes : trame absente ou mal formée")

	# Objets : voie, toute la route, sortes inconnues ignorées, douze au plus
	var gp := {"obj": [[17, "bottle", 1520.4, 2], [18, "musette", 1610.0, 0], [19, "storm", 1700.0, -1], [20, "gel", 1.0, 1],
		[21], "bad"]}
	var objs: Array = Model.objects(gp)
	_check(objs.size() == 3 and objs[0]["lateral"] == 2.22 and objs[1]["lateral"] == 0.68, "objet affiché à la bonne voie")
	_check(objs[2]["whole"] and objs[2]["lateral"] == Model.WHOLE_ROAD_M, "nuage d'orage : toute la route")
	var many: Array = []
	for i in range(20):
		many.append([i + 1, "bottle", 100.0 + i, i % 3])
	_check(Model.objects({"obj": many}).size() == Model.MAX_OBJECTS, "douze objets au plus")

	# Réserve : place gardée d'une trame à l'autre, libérée quand l'objet sort de la trame
	var m = Model.new()
	var a: Dictionary = m.assign(objs)
	var bottle_slot: int = a["bottle"].find(objs[0])
	_check(bottle_slot >= 0 and a["musette"].find(objs[1]) >= 0 and a["storm"].find(objs[2]) >= 0, "réserve : chaque objet a sa place")
	var later := [{"id": 22, "kind": "bottle", "s": 1500.0, "lateral": 0.68, "whole": false}, objs[0]]
	var b: Dictionary = m.assign(later)
	_check(b["bottle"][bottle_slot] == objs[0], "réserve : le bidon garde sa place (%d)" % bottle_slot)
	_check(b["musette"].count(null) == Model.POOL and b["storm"].count(null) == Model.POOL, "objets sortis de la trame : places libérées")
	var c: Dictionary = m.assign([])
	_check(c["bottle"].count(null) == Model.POOL, "trame vide : rien d'affiché")
	var full: Array = []
	for i in range(Model.POOL):
		full.append({"id": 40 + i, "kind": "homing", "s": 100.0, "lateral": 1.45, "whole": false})
	_check(m.assign(full)["homing"].count(null) == 0, "réserve pleine : douze musettes guidées")

	# Effets : par objet, par préréglage
	_check(Model.looks([["star", 5.2], ["bottle", 1.0]]) == ["halo", "slip"], "effets du cycliste (paires [objet, reste])")
	_check(Model.looks(["musette", "homing", "storm"]) == ["slip", "rain"], "effets d'un bot, sans doublon")
	_check(Model.looks(null).is_empty() and Model.looks(["bell"]).is_empty(), "sonnette : rien sur le coureur")
	_check(Model.shown_looks("low", ["gust", "slip", "kick"]) == ["slip"], "low : rafales et traits coupés")
	_check(Model.shown_looks("high", ["gust", "kick"]) == ["gust", "kick"], "high : tous les effets")
	_check(Model.particles("low", "rain") == 0 and Model.particles("low", "halo") == 0, "low : sans particules")
	_check(Model.particles("medium", "rain") > 0 and Model.particles("medium", "halo") == 0, "medium : averse limitée, sans étincelles")
	_check(Model.particles("high", "rain") > Model.particles("medium", "rain") and Model.particles("high", "halo") > 0,
		"high : averse et étincelles complètes")

	# Onomatopées : doublons du core écartés, durée bornée
	var hit := {"item": "bottle", "by": "bot2", "target": "me", "loss_s": 1.8}
	_check(m.on_hit(hit, 10.0) and not m.on_hit(hit, 11.0) and not m.on_hit(hit, 12.0), "gp_hit répété : une fois")
	var w: Array = m.words(10.5)
	_check(w.size() == 1 and w[0]["text"] == "ZIOUF !" and w[0]["target"] == "me", "glissade : « ZIOUF ! »")
	_check(m.words(10.0 + Model.WORD_S + 0.1).is_empty(), "onomatopée effacée")
	_check(m.on_hit(hit, 20.0), "même coup plus tard : nouveau")
	m.on_hit({"item": "storm", "by": "bot1", "target": "bot3", "loss_s": 2.0}, 20.1)
	_check(m.words(20.2).back()["text"] == "SPLASH !", "orage : « SPLASH ! »")

	# Sons
	var s = Sounds.new()
	_check(s.on_state({"roll_s": 1.8, "held": null, "n": 0}) == ["gp_roulette"], "tirage : roulette")
	_check(s.on_state({"roll_s": 0.9, "held": null, "n": 0}).is_empty(), "roulette jouée une fois")
	_check(s.on_state({"roll_s": 0.0, "held": "musette_x3", "n": 3}).is_empty(), "objet reçu : rien")
	_check(s.on_state({"roll_s": 0.0, "held": "musette_x3", "n": 2}) == ["gp_lancer"], "une musette lancée")
	_check(s.on_state({"roll_s": 0.0, "held": null, "n": 0}) == ["gp_lancer"], "dernière charge : lancer")
	s.on_state({"roll_s": 0.0, "held": "bell", "n": 1})
	_check(s.on_state({"roll_s": 0.0, "held": null, "n": 0}) == ["gp_sonnette"], "sonnette : dring")
	s.on_state({"roll_s": 0.0, "held": "team_car", "n": 1})
	_check(s.on_state({"roll_s": 0.0, "held": null, "n": 0}) == ["gp_klaxon"], "voiture d'équipe : klaxon")
	_check(s.on_state(null).is_empty() and s.on_state({"roll_s": 0.0, "held": null}).is_empty(), "hors du mode : rien")
	_check(Sounds.on_hit({"item": "homing", "target": "me"}) == "gp_glissade" and Sounds.on_hit({"item": "storm", "target": "me"}) == "gp_averse",
		"cycliste touché : glissade, averse")
	_check(Sounds.on_hit({"item": "storm", "target": "bot1"}) == "", "bot touché : pas de son")
	for j in ["gp_roulette", "gp_lancer", "gp_glissade", "gp_averse", "gp_sonnette", "gp_klaxon"]:
		_check(EventSounds.JINGLES.has(j) and EventSounds.duration_s(j) < 2.5, "son %s (%.2f s)" % [j, EventSounds.duration_s(j)])

	# Scène : construite une fois, mise à jour sans créer de nœud
	var sc = Scene.new()
	get_root().add_child(sc)
	var cam := Camera3D.new()
	get_root().add_child(cam)
	sc.step({"boxes": [1950]}, [], 0.0, cam)
	_check(not sc.visible and not sc.test_info()["active"], "sans route : rien")
	sc.set_route(FakeRoute.new())
	var before := _count_nodes(sc)
	var full_gp := {"boxes": [1950, 3450], "obj": many.slice(0, 12)}
	var riders := [{"id": "me", "pos": Vector3(1.2, 0.0, -1500.0), "heading": 0.0, "fx": [["star", 5.0], ["storm", 1.0]]},
		{"id": "bot1", "pos": Vector3(2.0, 0.0, -1530.0), "heading": 0.0, "fx": ["bottle"]},
		{"id": "bot2", "pos": null, "heading": 0.0, "fx": ["bottle"]}]
	sc.on_hit({"item": "bottle", "by": "me", "target": "bot1", "loss_s": 1.0}, 0.0)
	for q in ["low", "medium", "high"]:
		sc.set_quality(q)
		for f in range(Scene.WARM_FRAMES + 2):
			sc.step(full_gp, riders, 0.1 * f, cam)
			await process_frame
		var info: Dictionary = sc.test_info()
		_check(sc.visible and info["boxes"] == 6 and info["objects"] == 12, "%s : six boîtes, douze objets" % q)
		_check(info["looks"] == 3, "%s : effets des coureurs visibles (%d)" % [q, info["looks"]])
		_check(info["words"] == 1, "%s : onomatopée au-dessus du bot touché" % q)
		var rain: CPUParticles3D = sc._rigs[0]["rain"]
		_check(rain.emitting == (q != "low"), "%s : averse en particules seulement en medium et high" % q)
	_check(_count_nodes(sc) == before, "aucune création de nœud en course (%d nœuds)" % before)
	sc.step(null, riders, 1.0, cam)
	_check(not sc.visible, "hors du mode : scène cachée")
	sc.queue_free()
	cam.queue_free()

	print("test_gp_scene : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
