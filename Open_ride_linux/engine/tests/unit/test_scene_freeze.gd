extends SceneTree

## Scène figée des tests graphiques (lot X20, message `_test` « freeze ») : à un même instant, le vent, la phase
## de l'herbe et des arbres, les nuages et l'horloge des personnages ne dépendent plus de l'historique des images ;
## deux passages figés au même instant donnent donc la même image (visual_check.py --fige).
## Lancement : godot --headless --path engine --script res://tests/unit/test_scene_freeze.gd

const AnimClock := preload("res://scripts/anim_clock.gd")
const WindModel := preload("res://scripts/wind_model.gd")
const SkyClouds := preload("res://scripts/sky_clouds.gd")

var _failures := 0
var _checked := 0


func _init() -> void:
	_run()
	print("test_scene_freeze : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _wind_with_history(steps: int) -> WindModel:
	var w := WindModel.new()
	w.set_theme_wind({"speed_kmh": 20.0, "from_deg": 250.0, "gust_pct": 40.0})
	for i in steps:
		w.evaluate(i * 0.37)
	return w


func _run() -> void:
	# Vent : deux histoires différentes, même vent après settle(t).
	var a := _wind_with_history(3)
	var b := _wind_with_history(400)
	a.settle(30.0)
	b.settle(30.0)
	var ea := a.evaluate(30.0)
	var eb := b.evaluate(30.0)
	_check(is_equal_approx(ea["strength"], eb["strength"]) and is_equal_approx(ea["gust"], eb["gust"])
		and (ea["dir"] as Vector3).is_equal_approx(eb["dir"]) and is_equal_approx(ea["phase"], eb["phase"]),
		"vent figé : même force, rafale, direction et phase quelle que soit l'histoire (%s)" % str(ea))
	_check(ea["strength"] > 0.0 and ea["phase"] > 0.0, "vent du thème posé sur sa cible, phase avancée depuis 0")
	var again := a.evaluate(30.0)
	_check(is_equal_approx(again["phase"], ea["phase"]), "même instant, pas nul : la phase ne bouge plus")
	var calm := WindModel.new()
	calm.settle(12.0)
	_check(calm.evaluate(12.0)["strength"] == 0.0, "sans vent du thème ni du core : calme")

	# Nuages : placés depuis 0, sans l'historique des images.
	var m1 := SkyClouds.build_material({"coverage": 0.3}, "flat")
	var m2 := SkyClouds.build_material({"coverage": 0.3}, "flat")
	for i in 50:
		SkyClouds.update(m1, ea, 1.0 / 60.0)
	SkyClouds.place(m1, ea, 30.0)
	SkyClouds.place(m2, ea, 30.0)
	var o1: Vector2 = m1.get_shader_parameter("cloud_offset")
	var o2: Vector2 = m2.get_shader_parameter("cloud_offset")
	_check(o1.is_equal_approx(o2) and o1.length() > 0.0, "nuages placés au même endroit à 30 s (%s)" % str(o1))

	# Horloge des personnages et des animaux : figée, puis libérée.
	AnimClock.freeze(12.5)
	AnimClock.advance(1.0)
	_check(AnimClock.frozen and is_equal_approx(AnimClock.seconds, 12.5), "horloge figée à 12,5 s malgré advance")
	AnimClock.freeze(NAN)
	AnimClock.advance(1.0)
	_check(not AnimClock.frozen and is_equal_approx(AnimClock.seconds, 13.5), "horloge libérée : elle repart")

	# main.gd : message « freeze » et décor appelé au même instant avec un pas nul.
	var main_code := FileAccess.get_file_as_string("res://scripts/main.gd")
	_check(main_code.contains("\"freeze\":") and main_code.contains("AnimClock.freeze(_freeze_t)"),
		"main.gd : message de test « freeze » relayé à l'horloge")
	_check(main_code.contains("now_s = _freeze_t\n\t\tdelta = 0.0") and main_code.contains("living_world.freeze(_freeze_t)"),
		"main.gd : décor vivant figé à l'instant imposé")
