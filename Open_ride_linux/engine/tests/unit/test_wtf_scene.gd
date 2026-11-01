extends SceneTree

## Tests sans écran des gags en 3D du mode « What the fuck » (série WTF, lots WTF5 et WTF6) : objet `wtf` de la
## trame `state` traduit en voile, roulis, vues imposées, bonds, soleil et objets posés le long de la route
## (wtf_scene_model.gd), puis posés par wtf_scene.gd sur une route droite factice.
## Lancement : godot --headless --path engine --script res://tests/unit/test_wtf_scene.gd

const M := preload("res://scripts/wtf/wtf_scene_model.gd")
const WtfScene := preload("res://scripts/wtf/wtf_scene.gd")

var _failures := 0
var _checked := 0


## Route droite vers le nord (−Z), plate : le point à s mètres est (0, 0, −s).
class StraightRoute:
	extends RefCounted
	func wrap_s(s: float) -> float:
		return s
	func sample_heading_deg(_s: float) -> float:
		return 0.0
	func sample_point(s: float) -> Vector3:
		return Vector3(0.0, 0.0, -s)


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _init() -> void:
	call_deferred("_run")


func _kinds(v: Dictionary) -> Dictionary:
	var out := {}
	for p in v["props"]:
		out[p["kind"]] = int(out.get(p["kind"], 0)) + 1
	return out


func _ev(ev: Dictionary, quality := "medium") -> Dictionary:
	return M.view({"points": 0, "event": ev}, 10.0, quality)


func _run() -> void:
	var off: Dictionary = M.view(null, 0.0)
	_check(not off["active"] and off["props"].is_empty() and off["tint"].a == 0.0, "hors mode WTF : rien")
	var idle: Dictionary = M.view({"points": 0, "event": null, "next_s": 5}, 0.0)
	_check(idle["active"] and idle["props"].is_empty() and idle["camera"] == "" and idle["roll_deg"] == 0.0,
		"entre deux gags, règles permanentes coupées : rien à poser")

	var moon := _ev({"id": "gravity", "planet": "moon", "hop_m": 1.4, "left_s": 30})
	_check(moon["tint"] == M.TINT_MOON and is_equal_approx(moon["hop_m"], 1.4), "Lune : voile gris et bonds")
	var jup := _ev({"id": "gravity", "planet": "jupiter", "hop_m": 0.0, "left_s": 30})
	_check(jup["tint"] == M.TINT_JUPITER and jup["hop_m"] == 0.0, "Jupiter : voile rougeâtre, pas de bond")
	_check(_ev({"id": "upside_down", "left_s": 30})["roll_deg"] == 180.0, "monde à l'envers : caméra retournée")
	var col := _ev({"id": "collapse", "gap_m": 40.0, "left_s": 30})
	var chunks: Array = col["props"].filter(func(p): return p["kind"] == "chunk")
	_check(chunks.size() == 6 and chunks[0]["ds"] == -40.0 and chunks[1]["ds"] < -40.0, "effondrement : tronçons derrière")
	_check(chunks[3]["up"] < chunks[1]["up"], "les tronçons les plus loin sont tombés plus bas")
	var cheese := _ev({"id": "cheese", "gap_m": 80.0, "squashed": false, "left_s": 30})
	_check(_kinds(cheese) == {"cheese": 1} and cheese["props"][0]["ds"] == -80.0, "fromage : meule 80 m derrière")
	_check(_ev({"id": "cheese", "gap_m": 0.0, "squashed": true})["props"][0]["ds"] == 0.0, "écrasé : meule sur le cycliste")
	var storm_low := _ev({"id": "storm", "pushback_m": 3.0, "cows": 40, "left_s": 30}, "low")
	var storm_high := _ev({"id": "storm", "pushback_m": 3.0, "cows": 40, "left_s": 30}, "high")
	_check(_kinds(storm_low)["cow"] == 8 and _kinds(storm_high)["cow"] == 24, "tornade : 8 vaches en low, 24 en high")
	_check(_kinds(_ev({"id": "storm", "cows": 3}, "high"))["cow"] == 3, "la tornade se remplit peu à peu")
	var cow: Dictionary = storm_low["props"].filter(func(p): return p["kind"] == "cow")[0]
	_check(cow["scale"] == M.COW_SCALE and absf(cow["ds"]) < 40.0, "vaches cartoon assez grosses et assez près pour être vues")
	_check(storm_low["tint"] == M.TINT_STORM, "tempête : ciel sombre")
	var tiny := _ev({"id": "tiny", "scale": 0.025, "set": "kitchen", "left_s": 30})
	_check(tiny["camera"] == "tiny" and _kinds(tiny).has("plate") and _kinds(tiny).has("cup"), "vélo minuscule : cuisine géante")
	_check(_ev({"id": "camera", "view": "snail"})["camera"] == "snail", "caméra escargot")
	var arrive := _ev({"id": "chef", "phase": "arrive", "dish": null})
	_check(_kinds(arrive) == {"chef": 1}, "chef qui arrive : tandem, plat caché")
	var reveal := _ev({"id": "chef", "phase": "reveal", "dish": "chili"})
	_check(_kinds(reveal) == {"chef": 1, "dish_chili": 1}, "révélation : chef et plat")
	var eat := _ev({"id": "chef", "phase": "eat", "dish": "jelly"})
	_check(_kinds(eat) == {"dish_jelly": 1} and eat["tint"] == M.TINT_JELLY, "gelée mangée : voile vert, plus de chef")

	var amb: Dictionary = M.view({"points": 0, "event": null, "kata": {"size": 3.0, "count": 4, "last": "cow",
		"next": [[35.2, "car"], [110.0, "church"]]}, "skins": {"b1": "whale"}, "attack": "b1", "clock_h": 26.0,
		"fish": true}, 1.0, "low")
	var k := _kinds(amb)
	_check(k.get("ball", 0) == 1 and k.get("kata_car", 0) == 1 and k.get("kata_church", 0) == 1, "Katamari : boule et objets à venir")
	var ball: Dictionary = amb["props"].filter(func(p): return p["kind"] == "ball")[0]
	_check(is_equal_approx(ball["scale"], 3.0) and is_equal_approx(ball["up"], 3.0 * M.KATA_BALL_M), "la boule grossit")
	_check(ball["lateral"] > 0.0, "boule poussée à droite, hors du centre de l'image")
	var big: Dictionary = M.view({"points": 0, "event": null, "kata": {"size": 6.0}}, 0.0)["props"][0]
	_check(is_equal_approx(big["scale"], M.KATA_SHOW_MAX), "la boule affichée cesse de grossir à × 3")
	_check(k.get("fish", 0) == 6, "pluie de poissons : 6 en low")
	_check(is_equal_approx(amb["sun_hour"], 2.0), "heure ramenée à 0–24 h")
	_check(amb["skins"] == {"b1": "whale"} and amb["attack"] == "b1", "costumes et attaque transmis")
	_check(is_equal_approx(M.sun_elevation_deg(12.0), 60.0) and M.sun_elevation_deg(0.0) < 0.0, "soleil : midi haut, minuit sous l'horizon")

	# Nœud : pose sur une route droite factice, sans scène.
	var scene = WtfScene.new()
	root.add_child(scene)
	var route := StraightRoute.new()
	var sun := DirectionalLight3D.new()
	root.add_child(sun)
	sun.rotation = Vector3(-0.5, 0.3, 0.0)
	var bots := func(id: String): return Vector3(2.0, 0.0, -100.0) if id == "b1" else null
	scene.step(cheese, route, 100.0, bots, sun)
	var info: Dictionary = scene.test_info()
	_check(info["active"] and info["props"] == {"cheese": 1}, "nœud : meule posée")
	var wheel: Node3D = scene.find_child("Wtf_cheese", true, false)
	_check(wheel != null and is_equal_approx(wheel.global_position.z, -20.0), "meule 80 m derrière le cycliste (s = 20)")
	scene.step(amb, route, 100.0, bots, sun)
	info = scene.test_info()
	_check(not info["props"].has("cheese") and info["props"].get("fish", 0) == 6, "objets du gag fini cachés, poissons posés")
	_check(info["skins"] == 1, "costume posé sur le bot affiché")
	_check(not is_equal_approx(sun.rotation.x, -0.5), "soleil réglé par l'horloge")
	scene.step(M.view(null, 0.0), null, 0.0, Callable(), sun)
	_check(not scene.is_active() and is_equal_approx(sun.rotation.x, -0.5) and scene.test_info()["props"].is_empty(),
		"fin du mode : soleil rendu, tout caché")

	# Caméra : roulis et vue imposée amenés en 1 s.
	var cam := Camera3D.new()
	root.add_child(cam)
	scene.step(_ev({"id": "upside_down"}), route, 100.0, Callable(), sun)
	cam.global_transform = Transform3D.IDENTITY
	scene.apply_camera(cam, Vector3.ZERO, 0.0, 0.5)
	_check(is_equal_approx(scene.test_info()["roll_deg"], 90.0), "roulis à mi-chemin après 0,5 s")
	scene.apply_camera(cam, Vector3.ZERO, 0.0, 0.6)
	_check(is_equal_approx(scene.test_info()["roll_deg"], 180.0), "monde retourné après 1 s")
	scene.step(_ev({"id": "camera", "view": "pigeon"}), route, 100.0, Callable(), sun)
	cam.global_transform = Transform3D.IDENTITY
	scene.apply_camera(cam, Vector3.ZERO, 0.0, 1.0)
	_check(scene.forced_camera() and cam.global_position.y > 8.0, "vue du pigeon : caméra en hauteur")
	var snail := WtfScene.camera_goal("snail", Vector3.ZERO, 0.0, 0.0)
	_check(snail.origin.y < 0.5, "vue de l'escargot au ras du sol")

	scene.queue_free()
	sun.queue_free()
	cam.queue_free()
	print("test_wtf_scene : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
