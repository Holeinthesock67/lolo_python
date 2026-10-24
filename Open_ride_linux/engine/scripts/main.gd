extends Node3D

## Scène principale du moteur Godot : ruban de route et terrain par tronçons, caméra subjective et HUD.

# Chargement explicite : sans passer par l'éditeur, Godot ne connaît pas encore les class_name.
const IpcClientScript := preload("res://scripts/ipc_client.gd")
const RouteDataScript := preload("res://scripts/route_data.gd")
const CameraFollowScript := preload("res://scripts/camera_follow.gd")
const EngineArgs := preload("res://scripts/engine_args.gd")
const RenderQuality := preload("res://scripts/render_quality.gd")
const HudViewModel := preload("res://scripts/hud_view_model.gd")
const ErgViewModel := preload("res://scripts/erg_view_model.gd")
const ThemeLoader := preload("res://scripts/theme_loader.gd")
const ThemeRenderParams := preload("res://scripts/theme_render_params.gd")

const DEMO_ROUTE_ID := "demo"
const DEMO_WORLD := "res://demo/demo.world"
const ERROR_MIN_S := 5.0
const TEST_CAM_PERIOD_US := 50_000   # journal de la caméra à 20 Hz en mode test

@onready var ipc: Node = $IpcClient
@onready var camera: Camera3D = $Camera3D
@onready var streamer: Node3D = $WorldStreamer
@onready var world_env: WorldEnvironment = $WorldEnvironment
@onready var sun: DirectionalLight3D = $DirectionalLight3D
@onready var banner: Label = $HUD/Banner
@onready var hud_power: Label = $HUD/Margin/VBox/PowerLabel
@onready var hud_speed: Label = $HUD/Margin/VBox/SpeedLabel
@onready var hud_cadence: Label = $HUD/Margin/VBox/CadenceLabel
@onready var hud_grade: Label = $HUD/Margin/VBox/GradeLabel
@onready var hud_distance: Label = $HUD/Margin/VBox/DistanceLabel

var route
var routes_dir: String = ""
var follow = CameraFollowScript.new()
var session_state: String = ""
var _first_state_logged := false
var _route_id_requested = null
## Chargement de parcours en tâche de fond : {id, route, path, ok, task}.
var _route_job: Dictionary = {}
var _test_cam_last_us := 0
var _test_cam_last_s := NAN


var status_label: Label
var hud_hr: Label
var hud_erg: Label
var erg_view = ErgViewModel.new()
var _beep_player: AudioStreamPlayer

const BEEPS := {
	"PLUS_SHORT": [[880.0, 0.08]],
	"MINUS_SHORT": [[440.0, 0.08]],
	"PLUS_LONG": [[660.0, 0.10], [990.0, 0.14]],
	"MINUS_LONG": [[550.0, 0.10], [330.0, 0.14]],
}


func _ready() -> void:
	var cfg := EngineArgs.current()
	routes_dir = cfg["routes_dir"]
	if cfg["test_mode"]:
		Engine.max_fps = 60   # sans écran, le rendu n'est pas limité par la synchronisation verticale
	RenderQuality.apply_preset(RenderQuality.DEFAULT_PRESET, camera, sun, world_env.environment, get_viewport())
	RenderQuality.apply_fog(world_env.environment, false)
	var theme_res := ThemeLoader.load_named(cfg.get("theme", "default"))
	var theme_dict: Dictionary = theme_res.get("theme", {})
	var theme_dir: String = theme_res.get("theme_dir", "")
	streamer.set_theme(theme_dict, theme_dir)
	_apply_sky_params(theme_dict)
	ipc.state_received.connect(_on_state_received)
	ipc.input_event_received.connect(_on_input_event)
	ipc.hello_ack_received.connect(_on_hello_ack)
	ipc.error_received.connect(_on_core_error)
	ipc.shutdown_received.connect(_on_core_shutdown)
	ipc.core_lost.connect(_on_core_lost)
	ipc.core_returned.connect(_on_core_returned)
	ipc.command_failed.connect(_on_command_failed)
	ipc.test_message_received.connect(_on_test_message)
	banner.changed.connect(func(text: String) -> void:
		ipc.test_log("banner text=" + text.replace("\n", " | ")))
	var gen := AudioStreamGenerator.new()
	gen.mix_rate = 44100.0
	gen.buffer_length = 0.6
	_beep_player = AudioStreamPlayer.new()
	_beep_player.stream = gen
	add_child(_beep_player)
	_beep_player.play()
	# Fréquence cardiaque sous la cadence, puis ligne de l'entraînement ERG (cachée en SIM).
	var vbox := $HUD/Margin/VBox
	hud_hr = Label.new()
	hud_hr.text = "FC: " + HudViewModel.NO_VALUE
	vbox.add_child(hud_hr)
	vbox.move_child(hud_hr, hud_cadence.get_index() + 1)
	hud_erg = Label.new()
	hud_erg.visible = false
	vbox.add_child(hud_erg)
	# Ligne d'état de diagnostic : séance, trainer, entrée, raison de pause.
	status_label = Label.new()
	status_label.text = "ÉTAT: en attente du core…"
	$HUD/Margin/VBox.add_child(status_label)
	# Le HUD s'élargit avec ses textes (ligne ERG…) : le bandeau se replace pour ne jamais le recouvrir.
	var panel: Control = $HUD/Margin/Panel
	panel.resized.connect(func() -> void: banner.place_beside(panel.get_global_rect()))
	get_viewport().size_changed.connect(func() -> void: banner.place_beside(panel.get_global_rect()))
	# Le parcours est chargé d'après le route_id reçu dans state (_request_route).


func _apply_sky_params(theme_dict: Dictionary) -> void:
	var sky := ThemeRenderParams.sky_params(theme_dict)
	if sun != null:
		var sun_dir: Vector3 = sky["sun_direction"]
		sun.basis = Basis.looking_at(-sun_dir, Vector3.UP)
	# sky.fog_density est réservé au brouillard volumétrique (lot E3) : le brouillard en profondeur
	# d'E1, qui masque la limite des tuiles lointaines, n'est pas modifié ici.


func _on_input_event(event_name: String) -> void:
	# Bips distincts : court + aigu, court − grave, long + montant, long − descendant.
	if not BEEPS.has(event_name):
		return
	print("Bip : ", event_name)
	var pb := _beep_player.get_stream_playback() as AudioStreamGeneratorPlayback
	if pb == null:
		return
	var rate := 44100.0
	for note in BEEPS[event_name]:
		var n := int(rate * float(note[1]))
		for i in range(n):
			var env := minf(1.0, minf(float(i), float(n - i)) / 200.0)  # évite les claquements
			var v := sin(TAU * float(note[0]) * float(i) / rate) * 0.3 * env
			pb.push_frame(Vector2(v, v))


func _unhandled_input(event: InputEvent) -> void:
	# Touches + / − (ou flèches haut / bas) = boutons du Click, utiles sans Click ou en test.
	if event is InputEventKey and event.pressed and not event.echo:
		match event.keycode:
			KEY_EQUAL, KEY_PLUS, KEY_KP_ADD, KEY_UP:
				ipc.send_command("input_event", {"event": "PLUS_SHORT"})
			KEY_MINUS, KEY_KP_SUBTRACT, KEY_DOWN:
				ipc.send_command("input_event", {"event": "MINUS_SHORT"})
			KEY_PAGEUP:
				ipc.send_command("input_event", {"event": "PLUS_LONG"})
			KEY_PAGEDOWN:
				ipc.send_command("input_event", {"event": "MINUS_LONG"})


func _process(_delta: float) -> void:
	_poll_route_job()
	var now := Time.get_ticks_usec()
	if not follow.has_frame():
		return
	# Interpolation et extrapolation de s à la cadence de rendu (camera_follow.gd).
	var s_disp: float = follow.update(now)
	_test_log_camera(now, s_disp)
	if route:
		var s_route: float = route.wrap_s(s_disp)
		var pos: Vector3 = route.sample_point(s_route)
		# Caméra subjective placée à 1.4 m de hauteur (hauteur des yeux du cycliste)
		camera.global_position = pos + Vector3(0.0, 1.4, 0.0)

		# Orienter la caméra selon le cap de la route
		var heading: float = deg_to_rad(route.sample_heading_deg(s_route))
		# Dans Godot : -Z est le nord. La rotation Y s'applique sur le cap horaire.
		camera.rotation.y = -heading
		# Fenêtre de tronçons et de tuiles autour de la position affichée (world_streamer.gd).
		streamer.update_window(s_route, float(follow.last_frame["v"]), camera.global_position)


func _test_log_camera(now: int, s_disp: float) -> void:
	if not ipc.test_mode or now - _test_cam_last_us < TEST_CAM_PERIOD_US:
		return
	_test_cam_last_us = now
	var age_ms := int((now - int(follow.last_frame["t_us"])) / 1000)
	ipc.test_log("cam s=%.4f age_ms=%d frozen=%d moved=%d" % [s_disp, age_ms, int(follow.is_frozen(now)),
			int(is_nan(_test_cam_last_s) or s_disp != _test_cam_last_s)])
	_test_cam_last_s = s_disp


# --- parcours ----------------------------------------------------------------------------

## Dossier du parcours : <routes>/<route_id>.world, repli sur la démo embarquée pour « demo ».
func _route_path(route_id: String) -> String:
	var path := routes_dir.path_join(route_id + ".world")
	if DirAccess.dir_exists_absolute(path):
		return path
	if route_id == DEMO_ROUTE_ID:
		return DEMO_WORLD
	return ""


func _request_route(route_id) -> void:
	_route_id_requested = route_id
	if route_id == null or str(route_id) == "":
		return
	var path := _route_path(str(route_id))
	if path == "":
		var missing := routes_dir.path_join(str(route_id) + ".world")
		print("Parcours introuvable : ", missing)
		ipc.test_log("route_missing id=%s" % route_id)
		banner.show_message("route", "Parcours « %s » introuvable (%s)" % [route_id, missing])
		return
	if not _route_job.is_empty():
		# Un chargement est déjà en cours : son résultat sera ignoré (_poll_route_job).
		WorkerThreadPool.wait_for_task_completion(_route_job["task"])
	var job := {"id": str(route_id), "route": RouteDataScript.new(), "path": path, "ok": false}
	job["task"] = WorkerThreadPool.add_task(_load_route_job.bind(job), false, "chargement du parcours")
	_route_job = job


## Exécuté dans un fil de WorkerThreadPool : lecture des fichiers et contrôles, sans toucher à la scène.
func _load_route_job(job: Dictionary) -> void:
	job["ok"] = job["route"].load_world_dir(job["path"])


func _poll_route_job() -> void:
	if _route_job.is_empty() or not WorkerThreadPool.is_task_completed(_route_job["task"]):
		return
	var job := _route_job
	_route_job = {}
	WorkerThreadPool.wait_for_task_completion(job["task"])
	if job["id"] != str(_route_id_requested):
		return
	if not job["ok"]:
		banner.show_message("route", "Parcours « %s » invalide : %s" % [job["id"], job["route"].load_error])
		return
	route = job["route"]
	follow.loop_length_m = route.length_m if route.is_loop() else 0.0
	follow.reset()
	# Changement de parcours : tronçons et tuiles vidés puis reconstruits autour de s = 0.
	streamer.set_world(route, job["path"])
	RenderQuality.apply_fog(world_env.environment, streamer.has_terrain)
	streamer.update_window(0.0, 0.0, route.sample_point(0.0) + Vector3(0.0, 1.4, 0.0))
	banner.clear_message("route")
	print("Parcours « %s » chargé : %.0f m, type %s, terrain %s (%s)" % [job["id"], route.length_m, route.type,
			"présent" if streamer.has_terrain else "absent (sol plat)", job["path"]])
	ipc.test_log("route_loaded id=%s length_m=%.1f path=%s" % [job["id"], route.length_m, job["path"]])


# --- messages du core --------------------------------------------------------------------

## Messages de test (--test-mode) : « screenshot » enregistre l'image affichée en PNG et journalise
## l'état des éléments du HUD (texte, visibilité, rectangle à l'écran), pour tests/visual_check.py.
func _on_test_message(msg: Dictionary) -> void:
	if str(msg.get("action", "")) == "screenshot":
		_test_screenshot(str(msg.get("path", "")), str(msg.get("tag", "")))


func _test_screenshot(path: String, tag: String) -> void:
	await RenderingServer.frame_post_draw
	var img := get_viewport().get_texture().get_image()
	var err := img.save_png(path) if path != "" else ERR_FILE_BAD_PATH
	var widgets := {}
	var nodes := {
		"panel": $HUD/Margin/Panel, "power": hud_power, "speed": hud_speed, "cadence": hud_cadence,
		"hr": hud_hr, "grade": hud_grade, "distance": hud_distance, "erg": hud_erg,
		"status": status_label, "banner": banner,
	}
	# Rectangles en pixels de l'image : la mise à l'échelle canvas_items (base 1280×720) est appliquée.
	var to_pixels := get_viewport().get_final_transform()
	for key in nodes:
		var c: Control = nodes[key]
		var r := to_pixels * c.get_global_rect()
		widgets[key] = {
			"text": c.text if c is Label else "",
			"visible": c.is_visible_in_tree(),
			"rect": [r.position.x, r.position.y, r.size.x, r.size.y],
		}
	var meshes := 0
	for n in streamer.find_children("*", "MeshInstance3D", true, false):
		if (n as MeshInstance3D).is_visible_in_tree():
			meshes += 1
	var info := {
		"tag": tag, "path": path, "ok": err == OK, "size": [img.get_width(), img.get_height()],
		"fps": Engine.get_frames_per_second(), "meshes": meshes, "ticks_ms": Time.get_ticks_msec(),
		"ui_scale": to_pixels.get_scale().x,
		"draw_calls": Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME),
		"camera": [camera.global_position.x, camera.global_position.y, camera.global_position.z],
		"widgets": widgets,
	}
	ipc.test_log("screenshot " + JSON.stringify(info))


func _on_hello_ack(_ack: Dictionary) -> void:
	# ipc.core_config garde ftp_w, gears_total et theme pour l'affichage.
	pass


func _on_core_error(code: String, message: String) -> void:
	banner.show_message("error", "Erreur du core [%s] : %s" % [code, message], ERROR_MIN_S)
	banner.set_sticky("error", session_state == "ERROR")


func _on_core_shutdown() -> void:
	banner.clear_message("core_lost")
	banner.show_message("shutdown", "Le core s'est arrêté")


func _on_core_lost() -> void:
	if not banner.has_message("shutdown"):
		banner.show_message("core_lost", "Core non joignable (nouvel essai chaque seconde)")


func _on_core_returned() -> void:
	banner.clear_message("core_lost")


func _on_command_failed(cmd_name: String) -> void:
	banner.show_message("command", "Commande « %s » sans réponse du core" % cmd_name, ERROR_MIN_S)


func _on_state_received(state: Dictionary) -> void:
	if not _first_state_logged:
		_first_state_logged = true
		print("Premier état reçu du core : ", state.get("session_state", "?"), " trainer=", state.get("trainer_status", "?"))
	banner.clear_message("shutdown")
	var new_session_state := str(state.get("session_state", ""))
	if new_session_state != session_state:
		session_state = new_session_state
		# Une erreur reste au moins 5 s ; au-delà, elle reste tant que la séance est en ERROR.
		if banner.has_message("error"):
			banner.set_sticky("error", session_state == "ERROR")
	var route_id = state.get("route_id", null)
	if route_id != _route_id_requested:
		_request_route(route_id)
	var running := session_state == "RUNNING"
	follow.push_frame(Time.get_ticks_usec(), float(state.get("s", 0.0)), float(state.get("v", 0.0)), running)
	ipc.test_log("state seq=%d s=%.3f session=%s" % [int(state.get("seq", 0)), float(state.get("s", 0.0)), session_state])

	if not state.has("gears_total"):
		state["gears_total"] = ipc.core_config.get("gears_total", 24)
	var erg_eval: Dictionary = erg_view.update(state.get("erg", null), Time.get_ticks_usec() / 1e6)
	var lines := HudViewModel.session_lines(state, erg_eval)
	hud_power.text = lines["power"]
	hud_speed.text = lines["speed"]
	hud_cadence.text = lines["cadence"]
	hud_hr.text = lines["hr"]
	hud_grade.text = lines["grade"]
	hud_distance.text = lines["distance"]
	hud_erg.text = lines["erg"]
	hud_erg.visible = lines["erg"] != ""
	var pause = state.get("pause_reason", null)
	status_label.text = "ÉTAT: %s%s | TRAINER: %s | ENTRÉE: %s" % [
		state.get("session_state", "?"),
		(" (" + str(pause) + ")") if pause != null else "",
		state.get("trainer_status", "?"),
		state.get("input_status", "?")]


func _exit_tree() -> void:
	if not _route_job.is_empty():
		WorkerThreadPool.wait_for_task_completion(_route_job["task"])
