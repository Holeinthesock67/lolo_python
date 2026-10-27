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
const TreeRenderer := preload("res://scripts/tree_renderer.gd")
const OsmStreamer := preload("res://scripts/osm_streamer.gd")
const SoundPlayer := preload("res://scripts/sound_player.gd")
const ErgView := preload("res://scripts/erg_view.gd")
const CueModel := preload("res://scripts/cue_model.gd")
const MenuFlow := preload("res://scripts/menu_flow.gd")
const MenuModel := preload("res://scripts/menu_model.gd")
const MenuView := preload("res://scripts/menu_view.gd")
const LivingWorld := preload("res://scripts/living_world.gd")

const DEMO_ROUTE_ID := "demo"
const DEMO_WORLD := "res://demo/demo.world"
const ERROR_MIN_S := 5.0
const TEST_CAM_PERIOD_US := 50_000   # journal de la caméra à 20 Hz en mode test
## Décor en fond des menus (lot N6) : caméra lente le long du parcours choisi (ou de la démo).
const MENU_CAMERA_MPS := 4.0
## Code de sortie de l'engine qui demande au lanceur `openride` de tout relancer (nouveaux appareils
## enregistrés, lot N13) ; voir core/src/openride_core/launcher.py.
const EXIT_RELAUNCH := 64

@onready var ipc: Node = $IpcClient
@onready var camera: Camera3D = $Camera3D
@onready var streamer: Node3D = $WorldStreamer
@onready var world_env: WorldEnvironment = $WorldEnvironment
@onready var sun: DirectionalLight3D = $DirectionalLight3D
@onready var banner: Label = $HUD/Banner
@onready var hud: CanvasLayer = $HUD

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

var erg_view = ErgViewModel.new()
## Bandeau et histogramme ERG (lot N7), dans le HUD.
var erg_panel = null
var _beep_player: AudioStreamPlayer
var sound_player = null
var _quality_name: String = "low"
var _frame_times: Array[float] = []
var _last_perf_log_us: int = 0

const BEEPS := {
	"PLUS_SHORT": [[880.0, 0.08]],
	"MINUS_SHORT": [[440.0, 0.08]],
	"PLUS_LONG": [[660.0, 0.10], [990.0, 0.14]],
	"MINUS_LONG": [[550.0, 0.10], [330.0, 0.14]],
}
const BEEP_LEVEL := 0.3
## Bip de changement de bloc ERG à T − 3 s (lot N7) : une seule note, plus aiguë, plus longue et plus
## forte que les bips d'appui, pour passer au-dessus du vent et de la roue libre (SoundPlayer).
const ERG_BEEP := [[1320.0, 0.30]]
const ERG_BEEP_LEVEL := 0.6
## Consignes d'essai (cue_model.gd) : deux notes montantes, aussi fortes que le bip ERG.
const CUE_BEEP := [[880.0, 0.15], [1320.0, 0.25]]

var _cues = CueModel.new()
## Menus (lot N6) : déroulé (menu_flow.gd) et affichage (menu_view.gd).
var menu_flow = MenuFlow.new()
var menu_view = null
var _last_state: Dictionary = {}
var _menu_s := 0.0
## Décor vivant, première vague (lot P16) : vent, arbres et herbe, nuages, fonds sonores.
var living_world = null
var _living_enabled := true


func _ready() -> void:
	var cfg := EngineArgs.current()
	routes_dir = cfg["routes_dir"]
	if cfg["test_mode"]:
		Engine.max_fps = 60   # sans écran, le rendu n'est pas limité par la synchronisation verticale
	_quality_name = str(cfg.get("quality", RenderQuality.DEFAULT_PRESET))
	_living_enabled = bool(cfg.get("living", true))
	if streamer.tree_renderer == null:
		var tree_rend = TreeRenderer.new()
		tree_rend.name = "TreeRenderer"
		streamer.add_child(tree_rend)
		streamer.tree_renderer = tree_rend
	if streamer.osm_streamer == null:
		var osm_st = OsmStreamer.new()
		osm_st.name = "OsmStreamer"
		streamer.add_child(osm_st)
		streamer.osm_streamer = osm_st
	if sound_player == null:
		sound_player = SoundPlayer.new()
		sound_player.name = "SoundPlayer"
		add_child(sound_player)
		if streamer.osm_streamer != null:
			streamer.osm_streamer.sound_player = sound_player
	RenderQuality.apply_preset(_quality_name, camera, sun, world_env.environment, get_viewport(), streamer)
	RenderQuality.apply_fog(world_env.environment, false)
	# Le moteur Compatibility (OpenGL, GPU modestes, tests sous Xvfb) dessine le PhysicalSkyMaterial
	# presque noir : ciel procédural aux couleurs du ciel d'E1 à la place.
	if RenderingServer.get_rendering_device() == null:   # Compatibility : pas de RenderingDevice
		var sky_mat := ProceduralSkyMaterial.new()
		sky_mat.sky_top_color = Color(0.38, 0.65, 0.98)
		sky_mat.sky_horizon_color = Color(0.65, 0.75, 0.85)
		world_env.environment.sky.sky_material = sky_mat
	var theme_res := ThemeLoader.load_named(cfg.get("theme", "default"))
	var theme_dict: Dictionary = theme_res.get("theme", {})
	var theme_dir: String = theme_res.get("theme_dir", "")
	streamer.set_theme(theme_dict, theme_dir)
	_apply_sky_params(theme_dict)
	living_world = LivingWorld.new()
	living_world.name = "LivingWorld"
	add_child(living_world)
	living_world.configure(_quality_name, _living_enabled, theme_dict, world_env.environment, sound_player,
		streamer.osm_streamer, streamer.tree_renderer)
	living_world.terrain_material = streamer.get("_terrain_material")
	print("Décor vivant : %s (préréglage %s)" % ["actif" if _living_enabled else "coupé (rendu 1.0)", _quality_name])
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
	# Le bandeau passe sous le panneau central du HUD (ERG, montée, état) pour ne jamais le recouvrir.
	var center: Control = hud.panel_center
	var place_banner := func() -> void: banner.offset_top = center.get_global_rect().end.y + banner.MARGIN / 2.0
	center.resized.connect(place_banner)
	get_viewport().size_changed.connect(place_banner)
	place_banner.call()
	erg_panel = ErgView.new()
	hud.add_child(erg_panel)
	hud.show_erg_line = false   # la ligne de texte ERG du panneau central laisse la place au bandeau
	menu_view = MenuView.new()
	hud.add_child(menu_view)
	hud.move_child(banner, -1)   # le bandeau reste lisible au-dessus du menu
	ipc.routes_received.connect(func(items: Array, _msg: Dictionary) -> void:
		menu_flow.set_routes(items)
		_refresh_menu())
	ipc.workouts_received.connect(func(items: Array, _msg: Dictionary) -> void:
		menu_flow.set_workouts(items)
		if erg_panel != null and erg_panel.has_method("set_profiles"):
			erg_panel.set_profiles(items)
		_refresh_menu())
	ipc.list_failed.connect(func(list_name: String, _message: String) -> void:
		menu_flow.list_failed(list_name)
		_refresh_menu())
	ipc.scan_results_received.connect(func(msg: Dictionary) -> void:
		ipc.test_log("scan_results done=%s items=%d plus=%s" % [str(msg.get("done", false)),
				(msg.get("items", []) as Array).size() if msg.get("items") is Array else 0, str(msg.get("plus_address"))])
		menu_flow.on_scan_results(msg)
		_refresh_menu())
	ipc.command_acked.connect(func(cmd_name: String, _cmd_id: int) -> void:
		menu_flow.on_command_acked(cmd_name)
		_refresh_menu())


func _apply_sky_params(theme_dict: Dictionary) -> void:
	var sky := ThemeRenderParams.sky_params(theme_dict)
	if sun != null:
		var sun_dir: Vector3 = sky["sun_direction"]
		sun.basis = Basis.looking_at(-sun_dir, Vector3.UP)
	var horizon: Color = sky.get("horizon_color", RenderQuality.FOG_COLOR)
	var fog_dens: float = float(sky.get("fog_density", 0.01))
	RenderQuality.apply_fog(world_env.environment, streamer.has_terrain, horizon, fog_dens)


func _on_input_event(event_name: String) -> void:
	# Bips distincts : court + aigu, court − grave, long + montant, long − descendant.
	if not BEEPS.has(event_name):
		return
	print("Bip : ", event_name)
	_play_tones(BEEPS[event_name], BEEP_LEVEL)
	_menu_event(event_name)


# --- menus (lot N6) ----------------------------------------------------------------------

## Événement du Click (relayé par le core) ou du clavier, menu affiché : navigation et action.
func _menu_event(event_name: String) -> void:
	if not menu_flow.is_visible():
		return
	_run_menu_action(menu_flow.handle(event_name))
	_refresh_menu()


func _run_menu_action(act: Dictionary) -> void:
	var name := str(act.get("action", ""))
	if name == "":
		return
	ipc.test_log("menu_action " + JSON.stringify(act))
	match name:
		"list":
			ipc.list_routes()
			ipc.list_workouts()
		"quit":
			print("Quitter demandé depuis le menu.")
			get_tree().quit()
		"relaunch":
			print("Relance d'OpenRide demandée depuis le menu (code %d)." % EXIT_RELAUNCH)
			get_tree().quit(EXIT_RELAUNCH)
		"scan_devices":
			ipc.scan_devices()
		"identify_click_plus":
			menu_flow.pairing.identify_cmd_id = ipc.identify_click_plus()
		"pair_devices":
			ipc.pair_devices(act.get("args", {}))
		"select_route":
			ipc.send_command("select_route", {"route_id": act["route_id"]})
		"select_workout":
			ipc.send_command("select_workout", {"workout_id": act["workout_id"]})
		"end_session":
			ipc.send_command("end_session", {"save": bool(act.get("save", true))})
		"start", "resume":
			ipc.send_command(name)


func _refresh_menu() -> void:
	if menu_view == null:
		return
	var shown: bool = menu_flow.is_visible()
	menu_view.visible = shown
	if shown:
		menu_view.update_display(menu_flow.state(), _last_state, menu_flow.summary, menu_flow.show_details)


func _play_tones(notes: Array, level: float) -> void:
	var pb := _beep_player.get_stream_playback() as AudioStreamGeneratorPlayback
	if pb == null:
		return
	var rate := 44100.0
	for note in notes:
		var n := int(rate * float(note[1]))
		for i in range(n):
			var env := minf(1.0, minf(float(i), float(n - i)) / 200.0)  # évite les claquements
			var v := sin(TAU * float(note[0]) * float(i) / rate) * level * env
			pb.push_frame(Vector2(v, v))


func _unhandled_input(event: InputEvent) -> void:
	# Touches + / − (ou flèches haut / bas) = boutons du Click, utiles sans Click ou en test.
	if event is InputEventKey and event.pressed and not event.echo:
		if menu_flow.is_visible():
			# Menu affiché : navigation locale (Entrée valide, Échap revient), bip sans passer par le core.
			var ev := MenuModel.key_to_event(event.keycode)
			if ev != "":
				_play_tones(BEEPS[ev], BEEP_LEVEL)
				_menu_event(ev)
			return
		match event.keycode:
			KEY_P, KEY_SPACE, KEY_ESCAPE:
				ipc.send_command("pause")   # l'écran de pause s'ouvre quand le core passe en PAUSED
			KEY_EQUAL, KEY_PLUS, KEY_KP_ADD, KEY_UP:
				ipc.send_command("input_event", {"event": "PLUS_SHORT"})
			KEY_MINUS, KEY_KP_SUBTRACT, KEY_DOWN:
				ipc.send_command("input_event", {"event": "MINUS_SHORT"})
			KEY_PAGEUP:
				ipc.send_command("input_event", {"event": "PLUS_LONG"})
			KEY_PAGEDOWN:
				ipc.send_command("input_event", {"event": "MINUS_LONG"})


func _process(delta: float) -> void:
	_poll_route_job()
	_record_frame_perf(delta)
	var now := Time.get_ticks_usec()
	if _menu_camera(delta):
		return
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
		_step_living(delta, s_route, float(follow.last_frame["v"]))


## Décor vivant (lot P16), une fois par image : vent, herbe, nuages, ambiance sonore.
## Core non joignable : le décor se fige avec la caméra (pas de nuages ni d'herbe qui bougent).
func _step_living(delta: float, s_route: float, v: float) -> void:
	if living_world == null or route == null or banner.has_message("core_lost"):
		return
	var smp: Dictionary = route.sample(s_route)
	living_world.step(Time.get_ticks_msec() / 1000.0, delta, camera.global_position, s_route, v,
		float(smp["heading_deg"]), float(smp["alt_m"]), session_state == "PAUSED")


## Décor en fond des menus hors séance (accueil, choix, bilan) : la caméra avance lentement sur le
## parcours chargé. En pause, la vue reste où la séance s'est arrêtée. Pas en mode test : les captures
## de référence des tests graphiques restent reproductibles.
func _menu_camera(delta: float) -> bool:
	if ipc.test_mode or route == null or not session_state in ["IDLE", "READY", "FINISHED"]:
		return false
	_menu_s = route.wrap_s(_menu_s + MENU_CAMERA_MPS * delta)
	var pos: Vector3 = route.sample_point(_menu_s)
	camera.global_position = pos + Vector3(0.0, 1.4, 0.0)
	camera.rotation.y = -deg_to_rad(route.sample_heading_deg(_menu_s))
	streamer.update_window(_menu_s, MENU_CAMERA_MPS, camera.global_position)
	_step_living(delta, _menu_s, MENU_CAMERA_MPS)
	return true


## Mesure des images par seconde et statistiques toutes les 30 s (Lot E3 §4.6)
func _record_frame_perf(delta: float) -> void:
	_frame_times.append(delta * 1000.0)
	var now := Time.get_ticks_usec()
	if _last_perf_log_us == 0:
		_last_perf_log_us = now
		return
	if now - _last_perf_log_us >= 30_000_000:
		var n := _frame_times.size()
		if n > 0:
			var total_ms := 0.0
			for t in _frame_times:
				total_ms += t
			var avg_fps := float(n) / (total_ms / 1000.0) if total_ms > 0.0 else 0.0
			var sorted := _frame_times.duplicate()
			sorted.sort()
			var p50: float = sorted[int(floor(float(n) * 0.50))]
			var p99: float = sorted[mini(int(floor(float(n) * 0.99)), n - 1)]
			var max_ms: float = sorted[n - 1]
			var trees: int = streamer.tree_renderer.get_active_tree_count() if streamer.tree_renderer != null else 0
			var draw_calls := RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME)
			print("[perf-rendu] images/s moy %.1f ; temps d'image p50 %.1f / p99 %.1f / max %.1f ms ; arbres %d ; appels de dessin %d ; préréglage %s" % [
				avg_fps, p50, p99, max_ms, trees, draw_calls, _quality_name])
		_frame_times.clear()
		_last_perf_log_us = now


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
	_menu_s = 0.0
	# Changement de parcours : tronçons et tuiles vidés puis reconstruits autour de s = 0.
	streamer.set_world(route, job["path"])
	if living_world != null:
		living_world.set_route(route, float(streamer.get("_road_width_m")))
		living_world.terrain_material = streamer.get("_terrain_material")
	var sky_params := ThemeRenderParams.sky_params(streamer._theme_dict)
	var horizon: Color = sky_params.get("horizon_color", RenderQuality.FOG_COLOR)
	var fog_dens: float = float(sky_params.get("fog_density", 0.01))
	RenderQuality.apply_fog(world_env.environment, streamer.has_terrain, horizon, fog_dens)
	streamer.update_window(0.0, 0.0, route.sample_point(0.0) + Vector3(0.0, 1.4, 0.0))
	banner.clear_message("route")
	banner.clear_message("cue")
	if _cues.load_for_route(job["id"]):
		print("[essai] %d consignes chargées (%s)" % [_cues.cues.size(), CueModel.path_for(job["id"])])
	elif _cues.load_error != "":
		print("[essai] consignes ignorées (%s) : %s" % [CueModel.path_for(job["id"]), _cues.load_error])
	print("Parcours « %s » chargé : %.0f m, type %s, terrain %s (%s)" % [job["id"], route.length_m, route.type,
			"présent" if streamer.has_terrain else "absent (sol plat)", job["path"]])
	ipc.test_log("route_loaded id=%s length_m=%.1f path=%s" % [job["id"], route.length_m, job["path"]])


# --- messages du core --------------------------------------------------------------------

## Messages de test (--test-mode) : « screenshot » enregistre l'image affichée en PNG et journalise
## l'état des éléments du HUD (texte, visibilité, rectangle à l'écran), pour tests/visual_check.py ;
## « menu_input » joue un appui du Click dans les menus.
func _on_test_message(msg: Dictionary) -> void:
	match str(msg.get("action", "")):
		"screenshot":
			_test_screenshot(str(msg.get("path", "")), str(msg.get("tag", "")))
		"menu_input":   # appui simulé dans les menus (banc des menus, tests/menu_bench.py)
			var ev := str(msg.get("event", ""))
			if ev in MenuModel.EVENTS:
				_menu_event(ev)


func _test_screenshot(path: String, tag: String) -> void:
	await RenderingServer.frame_post_draw
	var img := get_viewport().get_texture().get_image()
	var err := img.save_png(path) if path != "" else ERR_FILE_BAD_PATH
	var widgets := {}
	var nodes := {
		"panel": hud.panel_center, "power": hud.power_val, "target": hud.target_val, "speed": hud.speed_val, "cadence": hud.cadence_val,
		"hr": hud.hr_val, "grade": hud.grade_val, "distance": hud.distance_val, "erg": hud.erg_label,
		"status": hud.status_label, "banner": banner, "menu": menu_view, "menu_title": menu_view.title_label,
		"erg_title": erg_panel.title_label, "erg_target": erg_panel.target_label,
		"erg_remaining": erg_panel.remaining_label, "erg_next": erg_panel.next_label, "erg_hist": erg_panel.histogram,
		"wind": hud.panel_wind, "wind_speed": hud.wind_speed_label, "wind_level": hud.wind_level_label,
		"wind_verdict": hud.wind_verdict_label,
	}
	# Rectangles en pixels de l'image : la mise à l'échelle canvas_items (base 1280×720) est appliquée.
	var to_pixels := get_viewport().get_final_transform()
	for key in nodes:
		var c: Control = nodes[key]
		var r := to_pixels * c.get_global_rect()
		widgets[key] = {
			"text": c.text if c is Label else _widget_text(key),
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


## Texte des zones composées du menu (éléments, appareils, bilan), pour les tests graphiques.
func _widget_text(key: String) -> String:
	if key == "menu":
		return "%s || %s || %s || %s" % [menu_view.status_label.text, menu_view.items_text(), menu_view.devices.text() if menu_view.devices.visible else "",
				menu_view.summary.text() if menu_view.summary.visible else ""]
	return ""


func _on_hello_ack(_ack: Dictionary) -> void:
	# ipc.core_config garde ftp_w, gears_total et theme pour l'affichage. Core (re)démarré : listes
	# redemandées au prochain état affichant le menu.
	menu_flow.lists_needed()


func _on_core_error(code: String, message: String) -> void:
	menu_flow.on_error(code, message)
	_refresh_menu()
	banner.show_message("error", "Erreur du core [%s] : %s" % [code, message], ERROR_MIN_S)
	banner.set_sticky("error", session_state == "ERROR")


func _on_core_shutdown() -> void:
	menu_flow.session_state = ""   # plus de core : menu caché jusqu'à la trame suivante
	_refresh_menu()
	banner.clear_message("core_lost")
	banner.show_message("shutdown", "Le core s'est arrêté")


func _on_core_lost() -> void:
	if not banner.has_message("shutdown"):
		banner.show_message("core_lost", "Core non joignable (nouvel essai chaque seconde)")


func _on_core_returned() -> void:
	banner.clear_message("core_lost")


func _on_command_failed(cmd_name: String) -> void:
	if cmd_name in ["list_routes", "list_workouts"]:
		return   # liste sans réponse : le menu l'indique (signal list_failed), pas de bandeau
	banner.show_message("command", "Commande « %s » sans réponse du core" % cmd_name, ERROR_MIN_S)


func _on_state_received(state: Dictionary) -> void:
	if not _first_state_logged:
		_first_state_logged = true
		print("Premier état reçu du core : ", state.get("session_state", "?"), " trainer=", state.get("trainer_status", "?"))
	banner.clear_message("shutdown")
	_last_state = menu_flow.with_devices(state)
	for act in menu_flow.on_state(state, Time.get_ticks_msec() / 1000.0):
		_run_menu_action(act)
	_refresh_menu()
	var new_session_state := str(state.get("session_state", ""))
	if new_session_state != session_state:
		session_state = new_session_state
		# Une erreur reste au moins 5 s ; au-delà, elle reste tant que la séance est en ERROR.
		if banner.has_message("error"):
			banner.set_sticky("error", session_state == "ERROR")
	var route_id = state.get("route_id", null)
	if (route_id == null or str(route_id) == "") and menu_flow.is_visible():
		route_id = DEMO_ROUTE_ID   # aucun parcours choisi : la démo tourne en fond des menus (lot N6)
	if route_id != _route_id_requested:
		_request_route(route_id)
	var running := session_state == "RUNNING"
	follow.push_frame(Time.get_ticks_usec(), float(state.get("s", 0.0)), float(state.get("v", 0.0)), running)
	ipc.test_log("state seq=%d s=%.3f session=%s" % [int(state.get("seq", 0)), float(state.get("s", 0.0)), session_state])

	if running and route != null:
		_give_cues(state)

	if not state.has("gears_total"):
		state["gears_total"] = ipc.core_config.get("gears_total", 24)
	var erg_eval: Dictionary = erg_view.update(state.get("erg", null), Time.get_ticks_usec() / 1e6)
	if erg_eval.get("beep", false):
		_play_tones(ERG_BEEP, ERG_BEEP_LEVEL)
		print("Bip ERG : bloc ", int(state["erg"].get("block_index", 0)))
		ipc.test_log("erg_beep block=%d" % int(state["erg"].get("block_index", 0)))
	if erg_panel != null:
		erg_panel.ftp_w = float(ipc.core_config.get("ftp_w", 0.0))
		erg_panel.update_display(state.get("erg", null), erg_eval)

	if hud != null and hud.has_method("update_display"):
		hud.update_display(state, erg_eval, route, float(state.get("s", 0.0)))
	if living_world != null:
		# Vent du core (lot P16) : modèle du décor et indicateur du HUD, par rapport au cap de la route
		var wind_now_s := Time.get_ticks_msec() / 1000.0
		living_world.on_state(state, wind_now_s)
		var heading_deg: float = route.sample_heading_deg(route.wrap_s(float(state.get("s", 0.0)))) if route != null else 0.0
		if hud != null and hud.has_method("update_wind"):
			hud.update_wind(living_world.wind_hud(state, heading_deg, wind_now_s))

	if sound_player != null and camera != null:
		var now_s := float(Time.get_ticks_msec()) / 1000.0
		sound_player.update_audio(state, now_s, camera.position)


## Consignes d'essai atteintes : bandeau, bip et ligne « [essai] » dans le journal du lanceur.
func _give_cues(state: Dictionary) -> void:
	var s := float(state.get("s", 0.0))
	for c in _cues.update(s):
		banner.show_message("cue", "Consigne %d/%d : %s" % [c["index"], c["count"], c["text"]], c["duration_s"])
		if c["beep"]:
			_play_tones(CUE_BEEP, ERG_BEEP_LEVEL)
		print("[essai] consigne %d/%d à %.0f m, t = %.0f s, braquet %s : %s" % [c["index"], c["count"], s,
				float(state.get("t", 0.0)), str(state.get("gear", "?")), c["text"]])
		ipc.test_log("cue index=%d s=%.1f" % [c["index"], s])


func _exit_tree() -> void:
	if not _route_job.is_empty():
		WorkerThreadPool.wait_for_task_completion(_route_job["task"])
