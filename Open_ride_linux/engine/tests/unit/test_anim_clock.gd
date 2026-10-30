extends SceneTree

## Horloge des animations (anim_clock.gd) : personnages et animaux animés par l'uniforme global anim_time et non
## par TIME (sinon ils bougent encore quand main.gd fige le décor, core non joignable), horloge qui avance
## l'uniforme global, et main.gd qui ne l'avance plus, ni la caméra ni le décor, quand le bandeau « core_lost » est affiché
## (le journal caméra du mode test reste écrit, pour le scénario 4 de fake_core.py).
## Lancement : godot --headless --path engine --script res://tests/unit/test_anim_clock.gd

const AnimClock := preload("res://scripts/anim_clock.gd")

var _failures := 0
var _checked := 0


func _init() -> void:
	_run()
	print("test_anim_clock : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _run() -> void:
	var time_re := RegEx.create_from_string("\\bTIME\\b")
	for path in ["res://shaders/crowd.gdshaderinc", "res://shaders/fauna.gdshader"]:
		var code := FileAccess.get_file_as_string(path)
		_check(code.contains("global uniform float anim_time;") and time_re.search(code) == null,
			"%s : animé par anim_time, sans TIME" % path.get_file())
	_check(ProjectSettings.has_setting("shader_globals/anim_time"), "anim_time déclaré dans [shader_globals] de project.godot")
	var t0 := AnimClock.seconds
	AnimClock.advance(0.5)
	AnimClock.advance(-1.0)
	_check(is_equal_approx(AnimClock.seconds, t0 + 0.5), "l'horloge avance de 0,5 s et ne recule pas")
	# Sans écran (pilote factice), le serveur de rendu ne relit pas les uniformes globaux : null
	var v = RenderingServer.global_shader_parameter_get(AnimClock.PARAM)
	_check(v == null or is_equal_approx(float(v), AnimClock.seconds), "uniforme global anim_time à jour (%s)" % str(v))
	var main_code := FileAccess.get_file_as_string("res://scripts/main.gd")
	_check(main_code.contains("if not banner.has_message(\"core_lost\"):\n\t\tAnimClock.advance(delta)"),
		"main.gd : horloge figée tant que le core ne répond pas")
	_check(main_code.contains("if banner.has_message(\"core_lost\"):\n\t\treturn\n\tif route:"),
		"main.gd : caméra, avatar et décor figés tant que le core ne répond pas")
	# Le journal caméra du mode test passe avant ce return (scénario 4 de fake_core.py : caméra figée journalisée).
	_check(main_code.find("_test_log_camera(now, s_disp)") < main_code.find("if banner.has_message(\"core_lost\"):\n\t\treturn"),
		"main.gd : caméra journalisée en mode test même core muet")
