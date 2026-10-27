extends SceneTree

## Tests unitaires sans écran du mode d'affichage : display_mode.gd, argument `--display` de
## engine_args.gd et textes du réglage `render.display` (settings_view_model.gd).
## Lancement : godot --headless --path engine --script res://tests/unit/test_display_mode.gd

const DisplayMode := preload("res://scripts/display_mode.gd")
const EngineArgs := preload("res://scripts/engine_args.gd")
const SettingsViewModel := preload("res://scripts/settings_view_model.gd")

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _test_window_modes() -> void:
	_check(DisplayMode.VALID == ["windowed", "borderless", "fullscreen"],
		"trois modes, dans l'ordre des choix du core (config.py CHOICES)")
	_check(DisplayMode.window_mode("windowed") == DisplayServer.WINDOW_MODE_WINDOWED, "windowed : fenêtre")
	_check(DisplayMode.window_mode("borderless") == DisplayServer.WINDOW_MODE_FULLSCREEN,
		"borderless : plein écran sans bordure (compositeur gardé)")
	_check(DisplayMode.window_mode("fullscreen") == DisplayServer.WINDOW_MODE_EXCLUSIVE_FULLSCREEN,
		"fullscreen : plein écran exclusif")
	_check(not DisplayMode.is_valid("maximized") and DisplayMode.is_valid("fullscreen"), "noms inconnus refusés")
	_check(DisplayMode.WINDOW_SIZE == Vector2i(
			int(ProjectSettings.get_setting("display/window/size/viewport_width")),
			int(ProjectSettings.get_setting("display/window/size/viewport_height"))),
		"taille de la fenêtre = taille de project.godot")
	_check(not DisplayMode.apply("fullscreen"), "sans écran (--headless) : rien n'est appliqué")


func _test_mouse() -> void:
	_check(DisplayMode.mouse_mode(true) == Input.MOUSE_MODE_VISIBLE, "menu affiché : souris visible (clic des menus)")
	_check(DisplayMode.mouse_mode(false) == Input.MOUSE_MODE_HIDDEN, "en séance : souris masquée")


func _test_engine_args() -> void:
	_check(EngineArgs.parse(PackedStringArray())["display"] == "windowed",
		"sans --display : fenêtre (outils de test qui lancent Godot directement)")
	for name in DisplayMode.VALID:
		_check(EngineArgs.parse(PackedStringArray(["--display=" + name]))["display"] == name, "--display=" + name)
	var bad: Dictionary = EngineArgs.parse(PackedStringArray(["--display=maximized", "--quality=high"]))
	_check(bad["display"] == "windowed" and bad["quality"] == "high" and EngineArgs.last_error.contains("affichage"),
		"--display inconnu : repli sur la fenêtre avec message, autres arguments gardés")


func _test_setting_texts() -> void:
	var it := {"key": "render.display", "type": "choice", "choices": DisplayMode.VALID}
	_check(SettingsViewModel.format_value(it, "windowed") == "fenêtré", "texte : fenêtré")
	_check(SettingsViewModel.format_value(it, "borderless") == "plein écran sans bordure", "texte : sans bordure")
	_check(SettingsViewModel.format_value(it, "fullscreen") == "plein écran", "texte : plein écran")


func _init() -> void:
	_test_window_modes()
	_test_mouse()
	_test_engine_args()
	_test_setting_texts()
	print("test_display_mode : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
