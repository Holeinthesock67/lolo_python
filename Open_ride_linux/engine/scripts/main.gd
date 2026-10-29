extends Node3D

## Scène principale du moteur Godot : ruban de route et terrain par tronçons, caméra subjective et HUD.

# Chargement explicite : sans passer par l'éditeur, Godot ne connaît pas encore les class_name.
const IpcClientScript := preload("res://scripts/ipc_client.gd")
const RouteDataScript := preload("res://scripts/route_data.gd")
const CameraFollowScript := preload("res://scripts/camera_follow.gd")
const CameraViews := preload("res://scripts/camera_views.gd")
const EngineArgs := preload("res://scripts/engine_args.gd")
const AnimClock := preload("res://scripts/anim_clock.gd")
const RenderQuality := preload("res://scripts/render_quality.gd")
const DisplayMode := preload("res://scripts/display_mode.gd")
const HudViewModel := preload("res://scripts/hud_view_model.gd")
const HudView := preload("res://scripts/hud_view.gd")
const ErgViewModel := preload("res://scripts/erg_view_model.gd")
const ThemeLoader := preload("res://scripts/theme_loader.gd")
const ThemeRenderParams := preload("res://scripts/theme_render_params.gd")
const TreeRenderer := preload("res://scripts/tree_renderer.gd")
const OsmStreamer := preload("res://scripts/osm_streamer.gd")
const SoundPlayer := preload("res://scripts/sound_player.gd")
const AudioMix := preload("res://scripts/audio_mix.gd")
const FpsCounter := preload("res://scripts/fps_counter.gd")
const ErgView := preload("res://scripts/erg_view.gd")
const CueModel := preload("res://scripts/cue_model.gd")
const MenuFlow := preload("res://scripts/menu_flow.gd")
const BotsViewModel := preload("res://scripts/bots_view_model.gd")
const BotsView := preload("res://scripts/bots_view.gd")
const AvatarModel := preload("res://scripts/avatar_model.gd")
const AvatarView := preload("res://scripts/avatar_view.gd")
const EquipmentMeshes := preload("res://scripts/equipment_meshes.gd")
const WorkoutChartModel := preload("res://scripts/workout_chart_model.gd")
const WorkoutChartView := preload("res://scripts/workout_chart_view.gd")
const MenuModel := preload("res://scripts/menu_model.gd")
const KeyMap := preload("res://scripts/key_map.gd")
const MenuView := preload("res://scripts/menu_view.gd")
const PerfProbe := preload("res://scripts/perf_probe.gd")
const LivingWorld := preload("res://scripts/living_world.gd")
const LivingDecor := preload("res://scripts/living_decor.gd")
const SegmentMarkers := preload("res://scripts/segment_markers.gd")
const SegmentMarkersModel := preload("res://scripts/segment_markers_model.gd")
const SegmentHudModel := preload("res://scripts/segment_hud_model.gd")
const RogueHost := preload("res://scripts/rogue/rogue_host.gd")
const EventSoundsModel := preload("res://scripts/event_sounds_model.gd")
const LiveWorld := preload("res://scripts/live_world.gd")
const JunctionView := preload("res://scripts/junction_view.gd")
const WorldMenuView := preload("res://scripts/world_menu_view.gd")

const DEMO_ROUTE_ID := "demo"
const OW_PREFIX := "ow:"
## Colonnes du profil d'altitude de la carte de détail des menus (parcours entier).
const ROUTE_PROFILE_COLUMNS := 120
const DEMO_WORLD := "res://demo/demo.world"
const ERROR_MIN_S := 5.0
const TEST_CAM_PERIOD_US := 50_000   # journal de la caméra à 20 Hz en mode test
## Décor en fond des menus (lot N6) : caméra lente le long du parcours choisi (ou de la démo).
const MENU_CAMERA_MPS := 4.0
## Code de sortie de l'engine qui demande au lanceur `openride` de tout relancer (nouveaux appareils
## enregistrés, lot N13) ; voir core/src/openride_core/launcher.py.
const EXIT_RELAUNCH := 64
## Code de sortie « relancer en session simulée » (menu « Session simulée »).
const EXIT_SIM := 65

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
## Profil d'altitude du dernier parcours chargé, pour la carte de détail des menus : {id, profile}.
var _route_profile := {}
## Monde ouvert (lot W10) : suit les révisions du monde que le générateur prolonge ; inactif hors monde ouvert.
var live_world = LiveWorld.new()
## Panneau du carrefour et attributions (lot W12) ; null avant _ready.
var junction_view = null
## Menu « Monde ouvert » (lot W11) : globe, carte, préchargement ; caché hors de ce menu.
var world_menu_view = null
## Chargement de parcours en tâche de fond : {id, route, path, ok, task}.
var _route_job: Dictionary = {}
var _test_cam_last_us := 0
var _test_cam_last_s := NAN

var erg_view = ErgViewModel.new()
## Bandeau et histogramme ERG (lot N7), dans le HUD.
var erg_panel = null
## Compteur d'images/s du HUD (réglage `render.fps`, caché par défaut).
var fps_counter = null
var _beep_player: AudioStreamPlayer
var sound_player = null
var _quality_name: String = "low"
var _visual_grade_scale: float = 1.0   # exagération visuelle du relief (--visual-grade, lots Q2 et Y15)
var _base_fov := 65.0                  # champ de vision de la scène, avant la respiration selon la pente (lot Y15)
var _theme_name: String = "default"
var _display_name: String = DisplayMode.DEFAULT   # mode d'affichage en place (--display, puis le menu)
## Vues de caméra (lot V12) : modèle (camera_views.gd) et dernière valeur de render.camera reçue du core.
var camera_views = CameraViews.new()
var _camera_setting := ""
var _display_setting := ""   # dernière valeur de render.display reçue du core (vide avant la première liste)
var _frame_times: Array[float] = []
var _last_perf_log_us: int = 0
## Sonde de performance (lot X13), active avec --perf-probe=FICHIER.csv.
var _probe = PerfProbe.new()

const BEEPS := {
	"PLUS_SHORT": [[880.0, 0.08]],
	"MINUS_SHORT": [[440.0, 0.08]],
	"PLUS_LONG": [[660.0, 0.10], [990.0, 0.14]],
	"MINUS_LONG": [[550.0, 0.10], [330.0, 0.14]],
	"A_SHORT": [[880.0, 0.08]],
	"A_LONG": [[660.0, 0.10], [990.0, 0.14]],
	"Y_SHORT": [[550.0, 0.10], [330.0, 0.14]],
	"LEFT_SHORT": [[440.0, 0.08]],
	"RIGHT_SHORT": [[880.0, 0.08]],
	"UP_SHORT": [[880.0, 0.08]],
	"DOWN_SHORT": [[440.0, 0.08]],
	"Z_SHORT": [[880.0, 0.08]],
	"Z_LONG": [[660.0, 0.10], [990.0, 0.14]],
}
const BEEP_LEVEL := 0.3
## Durées d'affichage du rappel des commandes en séance et de l'explication d'un appui ambigu.
const CONTROLS_HINT_S := 10.0
const PRESS_HINT_S := 4.0
## Bip de changement de bloc ERG à T − 3 s (lot N7) : une seule note, plus aiguë, plus longue et plus
## forte que les bips d'appui, pour passer au-dessus du vent et de la roue libre (SoundPlayer).
const ERG_BEEP := [[1320.0, 0.30]]
const ERG_BEEP_LEVEL := 0.6
## Consignes d'essai (cue_model.gd) : deux notes montantes, aussi fortes que le bip ERG.
const CUE_BEEP := [[880.0, 0.15], [1320.0, 0.25]]

var _cues = CueModel.new()
## Menus (lot N6) : déroulé (menu_flow.gd) et affichage (menu_view.gd), plein écran sur une couche
## au-dessus du HUD, qui est caché pendant un menu (lot « présentation des menus »).
var menu_flow = MenuFlow.new()
## Clavier = Click (lot O17) : touche et durée d'appui vers événement du Click.
var key_map = KeyMap.new()
## Bots à l'écran (lot O7) : modèle (écarts, visibilité) et silhouettes sur la route.
var bots_model = BotsViewModel.new()
var bots_view: Node3D
## Avatar du cycliste (lot V6) : modèle sans nœud (pédalier, danseuse) et vue ; caché en vue subjective, la
## seule caméra du jeu avant le lot V12. `_avatar_cam` : caméra de contrôle du banc visuel (« follow »,
## « side » ou « » sans), qui montre l'avatar sans changer la caméra du jeu.
var avatar_model = AvatarModel.new()
var avatar_view: Node3D
var _avatar_cam := ""
## Courbes de la séance (lot O14) : un modèle, deux vues (bandeau ERG, panneau SIM), taille par réglage.
var chart_model = WorkoutChartModel.new()
var chart_sim = null
var chart_mode := "hidden"   # jusqu'au hello_ack (core sans le champ : histogramme ERG de N7)
var _chart_workout := ""
var _chart_points := 0
var menu_view = null
var menu_layer: CanvasLayer = null
var _last_state: Dictionary = {}
var _menu_s := 0.0
## Décor vivant, première vague (lot P16) : vent, arbres et herbe, nuages, fonds sonores.
var living_world = null
var _theme_dict: Dictionary = {}   # thème courant, pour le décor vivant
var _living_enabled := true
## Décor vivant, deuxième vague (lot P17) : météo, animaux, éoliennes, véhicules, bord de route, foule.
var living_decor = null
## Série T (lot T8) : lignes, portiques et panneaux des segments, arches de bonus.
var segment_markers = null
## Série T (lot T9) : blocs segment et bonus du HUD.
var segment_hud = SegmentHudModel.new()
## Jingles des événements du parcours (lot T17) : sommet, sprint, arche, fin de séance.
var event_sounds = EventSoundsModel.new()
var _beep_until_s := -INF
## Série R (lot R10) : scène du mode Cyber-Rogue, instanciée quand `state.mode` vaut « ROGUE ».
var rogue_host = RogueHost.new()


func _ready() -> void:
	var cfg := EngineArgs.current()
	routes_dir = cfg["routes_dir"]
	if cfg.get("sim_session", false):
		menu_flow.menu.set_sim_session(true)
	if cfg["test_mode"]:
		Engine.max_fps = 60   # sans écran, le rendu n'est pas limité par la synchronisation verticale
	_quality_name = str(cfg.get("quality", RenderQuality.DEFAULT_PRESET))
	camera_views.set_view(str(cfg.get("camera", CameraViews.DEFAULT_VIEW)))
	_display_name = str(cfg.get("display", DisplayMode.DEFAULT))
	DisplayMode.apply(_display_name)
	print("Mode d'affichage : ", _display_name)
	_visual_grade_scale = float(cfg.get("visual_grade", EngineArgs.DEFAULT_VISUAL_GRADE))
	_base_fov = camera.fov
	if str(cfg.get("perf_probe", "")) != "":
		_probe.open(str(cfg["perf_probe"]), get_viewport(), _quality_name)
	_living_enabled = bool(cfg.get("living", true))
	streamer.culling = bool(cfg.get("culling", false))
	streamer.test_log = bool(cfg["test_mode"])
	streamer.forced_biome = str(cfg.get("biome", "auto"))
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
	streamer.osm_streamer.set_preset(_quality_name)
	RenderQuality.apply_fog(world_env.environment, _quality_name, false)
	_report_quality(_quality_name, "cli" if _quality_from_cli() else "defaut")
	# Le moteur Compatibility (OpenGL, GPU modestes, tests sous Xvfb) dessine le PhysicalSkyMaterial
	# presque noir : ciel procédural aux couleurs du ciel d'E1 à la place.
	if RenderingServer.get_rendering_device() == null:   # Compatibility : pas de RenderingDevice
		var sky_mat := ProceduralSkyMaterial.new()
		sky_mat.sky_top_color = Color(0.38, 0.65, 0.98)
		sky_mat.sky_horizon_color = Color(0.65, 0.75, 0.85)
		world_env.environment.sky.sky_material = sky_mat
	_apply_theme(str(cfg.get("theme", "default")))
	living_world = LivingWorld.new()
	living_world.name = "LivingWorld"
	add_child(living_world)
	living_world.configure(_quality_name, _living_enabled, _theme_dict, world_env.environment, sound_player,
		streamer.osm_streamer, streamer.tree_renderer)
	living_world.terrain_material = streamer.get("_terrain_material")
	living_decor = LivingDecor.new()
	living_decor.name = "LivingDecor"
	add_child(living_decor)
	living_decor.living_world = living_world
	living_decor.configure(_quality_name, _living_enabled, _theme_dict, world_env.environment, sound_player, streamer)
	living_decor.set_fog_base(world_env.environment)
	bots_view = BotsView.new()
	add_child(bots_view)
	avatar_view = AvatarView.new()
	add_child(avatar_view)
	_configure_avatar()
	segment_markers = SegmentMarkers.new()
	segment_markers.name = "SegmentMarkers"
	add_child(segment_markers)
	print("Décor vivant : %s (préréglage %s)" % ["actif" if _living_enabled else "coupé (rendu 1.0)", _quality_name])
	ipc.state_received.connect(_on_state_received)
	ipc.room_received.connect(rogue_host.on_room)
	ipc.loot_received.connect(rogue_host.on_loot)
	ipc.input_event_received.connect(_on_input_event)
	ipc.hello_ack_received.connect(_on_hello_ack)
	ipc.garage_received.connect(_on_garage)
	ipc.xp_result_received.connect(_on_xp_result)
	ipc.progression_received.connect(_on_progression)
	ipc.error_received.connect(_on_core_error)
	ipc.shutdown_received.connect(_on_core_shutdown)
	ipc.core_lost.connect(_on_core_lost)
	ipc.core_returned.connect(_on_core_returned)
	ipc.command_failed.connect(_on_command_failed)
	ipc.test_message_received.connect(_on_test_message)
	ipc.segment_result_received.connect(func(msg: Dictionary) -> void:
		if segment_hud.on_result(msg, Time.get_ticks_msec() / 1000.0):
			print("Segment terminé : %s en %s s" % [msg.get("segment_id", "?"), msg.get("time_s", "?")])
			ipc.test_log("segment_result id=%s" % msg.get("segment_id", "?"))
			_play_event(event_sounds.on_segment_result(msg)))
	banner.changed.connect(func(text: String) -> void:
		ipc.test_log("banner text=" + text.replace("\n", " | ")))
	var gen := AudioStreamGenerator.new()
	gen.mix_rate = 44100.0
	gen.buffer_length = 0.6
	_beep_player = AudioStreamPlayer.new()
	_beep_player.stream = gen
	_beep_player.bus = AudioMix.bus(AudioMix.EVENTS)
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
	var chart_erg = WorkoutChartView.new()
	chart_erg.model = chart_model
	erg_panel.set_chart(chart_erg, chart_mode)
	chart_sim = WorkoutChartView.new()
	chart_sim.model = chart_model
	chart_sim.anchor_top = 1.0
	chart_sim.anchor_bottom = 1.0
	chart_sim.anchor_right = 1.0
	# Entre les colonnes du HUD, juste au-dessus du profil d'altitude.
	var chart_x := HudView.TOP_MARGIN + HudView.COLUMN_W + HudView.TOP_MARGIN
	chart_sim.offset_left = chart_x
	chart_sim.offset_right = -chart_x
	chart_sim.offset_bottom = -HudView.PROFILE_RESERVE - HudView.BLOCK_GAP
	chart_sim.offset_top = chart_sim.offset_bottom - 120.0
	chart_sim.visible = false
	hud.add_child(chart_sim)
	junction_view = JunctionView.new()
	hud.add_child(junction_view)
	world_menu_view = WorldMenuView.new()
	hud.add_child(world_menu_view)
	fps_counter = FpsCounter.new()
	hud.add_child(fps_counter)
	ipc.world_menu_received.connect(_on_world_menu_received)
	ipc.world_status_received.connect(func(msg: Dictionary) -> void: _world_menu_status(msg))
	hud.show_erg_line = false   # la ligne de texte ERG du panneau central laisse la place au bandeau
	menu_layer = CanvasLayer.new()
	menu_layer.name = "MenuLayer"
	menu_layer.layer = hud.layer + 1
	add_child(menu_layer)
	menu_view = MenuView.new()
	menu_layer.add_child(menu_view)
	banner.reparent(menu_layer)   # le bandeau reste lisible au-dessus du menu, HUD caché ou non
	menu_view.item_clicked.connect(func(item_id: String) -> void:
		# Clic sur un élément : focus dessus puis validation, comme un appui long sur A.
		print("Souris : clic sur ", item_id)
		if menu_flow.is_visible() and menu_flow.menu.focus_item(item_id):
			_play_tones(BEEPS["A_LONG"], BEEP_LEVEL)
			_menu_event("A_LONG"))
	menu_view.mouse_event.connect(func(ev: String) -> void:
		print("Souris : ", ev)
		if menu_flow.is_visible():
			_play_tones(BEEPS[ev], BEEP_LEVEL)
			_menu_event(ev))
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
	ipc.settings_received.connect(_on_settings)
	ipc.imports_received.connect(func(items: Array, _msg: Dictionary) -> void:
		menu_flow.set_import_candidates(items)
		_refresh_menu())
	ipc.workout_saved_received.connect(func(msg: Dictionary) -> void:
		ipc.test_log("workout_saved id=%s" % str(msg.get("workout_id", "")))
		if menu_flow.on_workout_saved(msg):
			ipc.list_workouts()
		_refresh_menu())
	ipc.plans_received.connect(func(msg: Dictionary) -> void:
		menu_flow.on_plans(msg)
		_refresh_menu())
	ipc.command_acked.connect(func(cmd_name: String, _cmd_id: int) -> void:
		menu_flow.on_command_acked(cmd_name)
		_refresh_menu())


## Qualité réellement appliquée (lot X32) : ligne toujours écrite, ligne de test pour les bancs
## (engine/tests/quality_guard.py) et préréglage noté dans la sonde de performance (lot X13).
func _report_quality(requested: String, source: String) -> void:
	print("Qualité appliquée : %s (demandée %s, source %s)" % [_quality_name, requested, source])
	ipc.test_log("quality applied=%s requested=%s source=%s" % [_quality_name, requested, source])
	_probe.preset = _quality_name


## Vrai si --quality figure dans les arguments de l'engine (sinon, valeur par défaut d'engine_args.gd).
static func _quality_from_cli() -> bool:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--quality="):
			return true
	return false


## Réglages reçus du core (lot O4) : menu mis à jour ; qualité, thème et mode d'affichage appliqués tout de
## suite, volumes aux bus audio (audio_mix.gd), compteur d'images/s montré ou caché.
func _on_settings(msg: Dictionary) -> void:
	menu_flow.on_settings(msg)
	AudioMix.apply_settings(menu_flow.settings.items)
	fps_counter.set_mode(str(menu_flow.settings.item(FpsCounter.SETTING_KEY).get("value", "off")))
	var q := str(menu_flow.settings.item("render.quality").get("value", _quality_name))
	if q != _quality_name and q in EngineArgs.VALID_QUALITIES:
		_quality_name = q
		RenderQuality.apply_preset(_quality_name, camera, sun, world_env.environment, get_viewport(), streamer)
		if streamer.tree_renderer != null:
			streamer.tree_renderer.set_preset(_quality_name)
		if streamer.osm_streamer != null:
			streamer.osm_streamer.set_preset(_quality_name)
		_report_quality(q, "reglage")
	elif q != _quality_name:
		_report_quality(q, "reglage")   # valeur inconnue : la qualité appliquée ne change pas, et le journal le dit
	var th := str(menu_flow.settings.item("render.theme").get("value", _theme_name))
	if th != _theme_name:
		_apply_theme(th)
	var ch := str(menu_flow.settings.item("render.chart").get("value", chart_mode))
	if ch != chart_mode and ch in WorkoutChartView.MODES:
		chart_mode = ch
		_apply_chart_mode()
	# Au lancement, --display décide (le lanceur y met [render] display, ou OPENRIDE_DISPLAY) ; seule une
	# valeur changée ensuite au menu change la fenêtre, pour que les bancs gardent leur fenêtre forcée.
	var disp := str(menu_flow.settings.item("render.display").get("value", ""))
	if DisplayMode.is_valid(disp):
		if _display_setting != "" and disp != _display_setting and disp != _display_name:
			_display_name = disp
			DisplayMode.apply(_display_name)
			print("Mode d'affichage : ", _display_name)
		_display_setting = disp
	# Vue de caméra choisie au menu (lot V12) : appliquée si elle change après la première réception.
	var cam := str(menu_flow.settings.item("render.camera").get("value", ""))
	if CameraViews.is_valid(cam):
		if _camera_setting != "" and cam != _camera_setting and cam != camera_views.current:
			camera_views.set_view(cam)
			print("Vue de caméra : ", cam)
		_camera_setting = cam
	var ftp = menu_flow.settings.item("rider.ftp_w").get("value", null)
	if ftp != null:
		ipc.core_config["ftp_w"] = ftp
	_refresh_menu()


func _apply_theme(name: String) -> void:
	_theme_name = name
	var theme_res := ThemeLoader.load_named(name)
	var theme_dict: Dictionary = theme_res.get("theme", {})
	_theme_dict = theme_dict
	streamer.set_theme(theme_dict, theme_res.get("theme_dir", ""))
	_apply_sky_params(theme_dict)
	if route != null and _route_job.is_empty():
		streamer.set_world(route, _route_path(str(_route_id_requested)))   # décor reconstruit avec le thème
	print("Thème : ", name)


## Ciel et brouillard du thème ; avec un modèle de biome actif (série U, lot U17), ceux du biome du départ :
## densité du brouillard du biome, horizon voilé par `haze` (poussière, brume) et teinté par `light_tint`.
func _apply_sky_params(theme_dict: Dictionary) -> void:
	var sky := ThemeRenderParams.sky_params(theme_dict)
	var model = streamer.biome_model
	if model != null and model.active():
		sky = model.params(streamer.start_biome())["sky"]
	if sun != null:
		var sun_dir: Vector3 = sky["sun_direction"]
		sun.basis = Basis.looking_at(-sun_dir, Vector3.UP)
	var horizon: Color = sky.get("horizon_color", RenderQuality.FOG_COLOR)
	if sky.has("haze"):
		horizon = horizon.lerp(RenderQuality.HAZE_COLOR, float(sky["haze"]) * 0.6) * (sky["light_tint"] as Color)
	var fog_dens: float = float(sky.get("fog_density", 0.01))
	RenderQuality.apply_fog(world_env.environment, _quality_name, streamer.has_terrain, horizon, fog_dens)


func _on_input_event(event_name: String) -> void:
	if event_name in ["PLUS_UNCLEAR", "MINUS_UNCLEAR"]:
		print("Appui ambigu : ", event_name)
		banner.show_message("press", HudViewModel.unclear_press_text(event_name, menu_flow.is_visible()), PRESS_HINT_S)
		return
	# Bips distincts : court + aigu, court − grave, long + montant, long − descendant.
	if not BEEPS.has(event_name):
		return
	print("Bip : ", event_name)
	_play_tones(BEEPS[event_name], BEEP_LEVEL)
	if _camera_event(event_name):
		return
	_menu_event(event_name)


## Vues de caméra au Click (lot V12, spécification générale §7.1) : A court et flèche haut, vue suivante ; flèche
## bas, vue précédente ; A long, vue par défaut. Seulement quand rien n'est affiché à choisir (menu, carrefour du
## monde ouvert) : A agit alors sur le choix. Renvoie vrai quand l'événement a servi à changer de vue.
func _camera_event(event_name: String) -> bool:
	if event_name not in ["A_SHORT", "A_LONG", "UP_SHORT", "DOWN_SHORT"]:
		return false
	if menu_flow.is_visible() or (world_menu_view != null and world_menu_view.visible):
		return false
	if event_name.begins_with("A_") and junction_view != null and junction_view.vm.is_visible():
		return false
	var now_s := Time.get_ticks_usec() / 1000000.0
	var changed := false
	match event_name:
		"A_SHORT", "UP_SHORT":
			changed = camera_views.next_view(now_s)
		"DOWN_SHORT":
			changed = camera_views.previous_view(now_s)
		"A_LONG":
			changed = camera_views.reset_default(now_s)
	if changed:
		print("Vue de caméra : ", camera_views.current)
	return true


## Écrit la vue choisie dans `[render] camera` quelques secondes après le dernier changement.
func _remember_camera_view(now_s: float) -> void:
	if camera_views.remember_due(now_s):
		_camera_setting = camera_views.current
		ipc.set_setting("render.camera", camera_views.current)


# --- menus (lot N6) ----------------------------------------------------------------------

## Événement du Click (relayé par le core) ou du clavier, menu affiché : navigation et action.
func _menu_event(event_name: String) -> void:
	if world_menu_view != null and world_menu_view.visible:
		_world_menu_event(event_name)
		return
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
			ipc.list_settings()
			ipc.list_plans()
			if act.get("route_id") != null:
				ipc.send_command("select_route", {"route_id": act["route_id"]})
		"quit":
			print("Quitter demandé depuis le menu.")
			get_tree().quit()
		"relaunch", "relaunch_sim":
			var code := EXIT_SIM if name == "relaunch_sim" else EXIT_RELAUNCH
			print("Relance d'OpenRide demandée depuis le menu (code %d)." % code)
			get_tree().quit(code)
		"scan_devices":
			ipc.scan_devices()
		"identify_click_plus":
			menu_flow.pairing.identify_cmd_id = ipc.identify_click_plus()
		"pair_devices":
			ipc.pair_devices(act.get("args", {}))
		"set_setting":
			ipc.set_setting(str(act["key"]), act["value"])
		"list_imports":
			ipc.list_imports()
		"list_plans":
			ipc.list_plans()
		"start_plan":
			ipc.start_plan(str(act["id"]), act.get("start_date", null))
		"stop_plan":
			ipc.stop_plan()
		"accept_ftp":
			ipc.accept_ftp(bool(act.get("force", false)))
		"create_workout":
			ipc.create_workout(act["args"])
		"import_workout":
			ipc.import_workout(str(act["path"]))
		"set_difficulty":
			ipc.send_set_difficulty(int(act["pct"]))
		"set_ride_mode":   # session libre : SIM, ERG ou ERG cadence depuis la pause (lot O18)
			ipc.send_command("set_ride_mode", act["args"])
		"select_route":
			ipc.send_command("select_route", {"route_id": act["route_id"]})
		"select_workout":
			ipc.send_command("select_workout", {"workout_id": act["workout_id"]})
		"end_session":
			ipc.send_command("end_session", {"save": bool(act.get("save", true))})
		"start", "resume":
			ipc.send_command(name, act.get("args", {}))
		"start_run":
			ipc.start_run(act.get("args", {}))
		"open_world_menu":
			world_menu_view.open()
			ipc.send_command("world_regions")
		"list_garage":
			ipc.request_garage()
		"equip":
			ipc.send_command("equip", {"slot": str(act["slot"]), "item_id": str(act["item_id"])})
		"buy":
			ipc.send_command("buy", {"item_id": str(act["item_id"])})
		"set_avatar":
			ipc.send_command("set_avatar", {"avatar": act["avatar"]})


# --- menu « Monde ouvert » (lot W11) -----------------------------------------------------

## Événement du menu pendant que le globe est ouvert : le modèle répond par une action à envoyer au core.
func _world_menu_event(event_name: String) -> void:
	_run_world_action(world_menu_view.vm.handle(event_name))
	world_menu_view.update_display()


func _run_world_action(act: Dictionary) -> void:
	match str(act.get("action", "")):
		"close":
			world_menu_view.close()
			_refresh_menu()
		"cancel_loading":
			ipc.send_command("end_session", {"save": false})
			world_menu_view.vm.reset()
		"world_search":
			ipc.send_command("world_search", {"query": act["query"]})
		"world_map":
			ipc.send_command("world_map", {"lat": act["lat"], "lon": act["lon"], "radius_m": act["radius_m"]})
		"world_pin":
			ipc.send_command("world_pin", {"region_id": act["region_id"], "pinned": act["pinned"]})
		"start_open_world":
			ipc.send_command("start_open_world", act["args"])


func _on_world_menu_received(kind: String, msg: Dictionary) -> void:
	var vm = world_menu_view.vm
	match kind:
		"places":
			vm.on_places(msg.get("items", []))
		"world_map":
			vm.on_map(msg)
		"world_regions":
			vm.on_regions(msg.get("items", []))
	world_menu_view.update_display()


func _world_menu_status(msg: Dictionary) -> void:
	if world_menu_view != null:
		world_menu_view.vm.on_status(msg)
		world_menu_view.update_display()


## Touches du clavier pendant le menu : lettres et chiffres pour la recherche, Retour arrière efface.
func _world_menu_key(event: InputEventKey) -> bool:
	var vm = world_menu_view.vm
	if event.keycode == KEY_BACKSPACE and vm.state == "search" and vm.query != "":
		_run_world_action(vm.backspace())
		world_menu_view.update_display()
		return true
	var ch := char(event.unicode) if event.unicode > 31 else ""
	if ch != "" and (ch.to_lower() != ch.to_upper() or ch.is_valid_int() or ch == " " or ch == "'") \
			and vm.state in ["globe", "search"]:
		_run_world_action(vm.type_text(ch))
		world_menu_view.update_display()
		return true
	return false


func _refresh_menu() -> void:
	if menu_view == null:
		return
	var shown: bool = menu_flow.is_visible() and not (world_menu_view != null and world_menu_view.visible)
	menu_view.visible = shown
	hud.visible = not shown   # menu plein écran : rien du HUD de séance derrière lui
	if shown:
		var st: Dictionary = menu_flow.state()
		if st["card"].has("id") and st["card"]["id"] == _route_profile.get("id"):
			st["card"]["profile"] = _route_profile["profile"]
		menu_view.update_display(st, _last_state, menu_flow.summary, menu_flow.show_details)


## Jingle d'événement (lot T17), joué par SoundPlayer sur le bus « Events » ; nom vide : rien.
func _play_event(jingle: String) -> void:
	if jingle.is_empty():
		return
	if sound_player != null:
		sound_player.play_event(jingle)
	print("Jingle : ", jingle)
	ipc.test_log("event_sound kind=" + jingle)


func _play_tones(notes: Array, level: float) -> void:
	var pb := _beep_player.get_stream_playback() as AudioStreamGeneratorPlayback
	if pb == null:
		return
	var rate := 44100.0
	var total_s := 0.0
	for note in notes:
		total_s += float(note[1])
	_beep_until_s = Time.get_ticks_msec() / 1000.0 + total_s
	for note in notes:
		var n := int(rate * float(note[1]))
		for i in range(n):
			var env := minf(1.0, minf(float(i), float(n - i)) / 200.0)  # évite les claquements
			var v := sin(TAU * float(note[0]) * float(i) / rate) * level * env
			pb.push_frame(Vector2(v, v))


func _unhandled_input(event: InputEvent) -> void:
	# Clavier = Click, touche pour touche (lot O17, key_map.gd) : l'événement part au relâchement, puis suit le
	# chemin d'un appui du Click. Menu affiché : traité ici (bip, menu), sans passer par le core ; en séance :
	# envoyé au core (input_event), qui le traite et le relaie à l'engine comme un appui du Click.
	var key := event as InputEventKey
	if key == null or key.echo:
		return
	var now_s := Time.get_ticks_usec() / 1000000.0
	if key.pressed:
		if world_menu_view != null and world_menu_view.visible and _world_menu_key(key):
			return   # saisie de la recherche du monde ouvert : la touche est une lettre, pas un bouton
		key_map.press(key.keycode, key.shift_pressed, now_s)
		return
	var ev: String = key_map.release(key.keycode, now_s)
	if ev == "":
		return
	if menu_flow.is_visible() or (world_menu_view != null and world_menu_view.visible):
		_on_input_event(ev)
	else:
		ipc.send_command("input_event", {"event": ev})


func _notification(what: int) -> void:
	if what == NOTIFICATION_APPLICATION_FOCUS_OUT:
		key_map.reset()   # le relâchement des touches enfoncées ne viendra pas


func _process(delta: float) -> void:
	var menu_shown: bool = menu_flow.is_visible() or (world_menu_view != null and world_menu_view.visible)
	var mouse := DisplayMode.mouse_mode(menu_shown)
	if Input.mouse_mode != mouse:
		Input.mouse_mode = mouse
	_poll_route_job()
	_poll_live_world()
	_record_frame_perf(delta)
	fps_counter.add_frame(delta)
	_probe.frame(delta, streamer)
	var now := Time.get_ticks_usec()
	_remember_camera_view(now / 1000000.0)
	# Personnages et animaux (anim_clock.gd) : figés avec le décor quand le core ne répond plus.
	if not banner.has_message("core_lost"):
		AnimClock.advance(delta)
	if rogue_host.is_active():
		return      # la scène du Cyber-Rogue a sa propre caméra et son propre décor
	if _menu_camera(delta):
		camera_views.snap()
		return
	if not follow.has_frame():
		return
	# Interpolation et extrapolation de s à la cadence de rendu (camera_follow.gd), figée 1,1 s après la
	# dernière trame ; journalisée en mode test même core muet (scénario 4 de fake_core.py).
	var s_disp: float = follow.update(now)
	_test_log_camera(now, s_disp)
	# Core non joignable : la scène se fige entière (caméra et son lissage, avatar, tuiles, décor vivant), comme
	# l'horloge des personnages et des animaux ci-dessus.
	if banner.has_message("core_lost"):
		return
	if route:
		var s_route: float = route.wrap_s(s_disp)
		var pos: Vector3 = route.sample_point(s_route)
		# Cap et pente de la route (lot Q2) ; dans Godot, -Z est le nord et la rotation Y suit le cap horaire.
		var heading: float = deg_to_rad(route.sample_heading_deg(s_route))
		var pitch_deg: float = follow.pitch_deg(route, s_route, float(follow.last_frame["v"]))
		# Vue de caméra courante (lot V12) : subjective à 1,4 m (hauteur des yeux), suivi proche ou éloigné, latérale.
		camera.global_transform = camera_views.step(delta, camera_views.goal(pos, heading, pitch_deg))
		camera.fov = CameraViews.fov_deg(_base_fov, pitch_deg)   # respire avec la pente (lot Y15)
		avatar_view.set_visible_for_view(_avatar_view_name())
		# Fenêtre de tronçons et de tuiles autour de la position affichée (world_streamer.gd).
		_step_avatar(pos, heading, now, pitch_deg)
		_probe.distance_m = s_route
		streamer.update_window(s_route, float(follow.last_frame["v"]), camera.global_position)
		_step_living(delta, s_route, float(follow.last_frame["v"]))
		if bots_model.count() > 0:
			_show_bots(s_route, float(follow.last_frame["v"]))
		# Arches de bonus seulement quand le core en donne (champ `powerup` : SIM, option « Bonus »).
		segment_markers.update(s_route, _last_state.has("powerup"))


## Décor vivant (lot P16), une fois par image : vent, herbe, nuages, ambiance sonore.
## Core non joignable : pas appelé (_process fige toute la scène), donc ni nuages ni herbe qui bougent.
func _step_living(delta: float, s_route: float, v: float) -> void:
	if living_world == null or route == null:
		return
	var smp: Dictionary = route.sample(s_route)
	var now_s := Time.get_ticks_msec() / 1000.0
	var paused := session_state == "PAUSED"
	living_world.step(now_s, delta, camera.global_position, s_route, v, float(smp["heading_deg"]),
		float(smp["alt_m"]), paused)
	if living_decor != null:
		living_decor.step(now_s, delta, camera.global_position, s_route, v, float(smp["alt_m"]), paused,
			living_world.last_wind, _last_state, now_s < _beep_until_s)


## Décor en fond des menus hors séance (accueil, choix, bilan) : la caméra avance lentement sur le
## parcours chargé. En pause, la vue reste où la séance s'est arrêtée. Pas en mode test : les captures
## de référence des tests graphiques restent reproductibles.
func _menu_camera(delta: float) -> bool:
	if ipc.test_mode or route == null or not session_state in ["IDLE", "READY", "FINISHED"]:
		return false
	_menu_s = route.wrap_s(_menu_s + MENU_CAMERA_MPS * delta)
	var pos: Vector3 = route.sample_point(_menu_s)
	camera.global_position = pos + Vector3(0.0, 1.4, 0.0)
	camera.fov = _base_fov
	camera.rotation.y = -deg_to_rad(route.sample_heading_deg(_menu_s))
	camera.rotation.x = deg_to_rad(CameraViews.camera_pitch_deg(follow.pitch_deg(route, _menu_s, MENU_CAMERA_MPS)))
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

## Monde ouvert : applique la dernière révision lue (route prolongée, carrefours) et tient les amorces
## des branches à jour. Les tronçons de ruban touchés sont reconstruits, les autres gardés.
func _poll_live_world() -> void:
	if live_world.route == null:
		return
	var upd: Dictionary = live_world.poll()
	if upd.has("route"):
		route = upd["route"]
		streamer.swap_route(route, int(upd["from_part"]))
		if living_world != null:
			living_world.set_route(route, float(streamer.get("_road_width_m")))
		ipc.test_log("world_revision rev=%d length_m=%.1f from_part=%d" % [upd["revision"], route.length_m, upd["from_part"]])
	elif upd.has("error"):
		print("Monde ouvert : révision %d illisible : %s" % [upd["revision"], upd["error"]])
		ipc.test_log("world_revision_error rev=%d" % upd["revision"])
	if follow.has_frame():
		streamer.set_previews(live_world.previews(float(follow.last_frame["s"])))

## Dossier du parcours : <routes>/<route_id>.world, repli sur la démo embarquée pour « demo ».
func _route_path(route_id: String) -> String:
	if route_id.begins_with(OW_PREFIX):
		# Monde ouvert : « ow:<id> » désigne <open_world_dir>/<id>.world (contrat IPC 1.5, hello_ack.config).
		var ow_dir := str(ipc.core_config.get("open_world_dir", ""))
		var ow_path := ow_dir.path_join(route_id.trim_prefix(OW_PREFIX) + ".world")
		return ow_path if ow_dir != "" and DirAccess.dir_exists_absolute(ow_path) else ""
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
	job["route"].relief_k = _visual_grade_scale   # relief affiché (lot Q2) : toute la scène suit la route
	job["task"] = WorkerThreadPool.add_task(_load_route_job.bind(job), false, "chargement du parcours")
	_route_job = job


## Exécuté dans un fil de WorkerThreadPool : lecture des fichiers et contrôles, sans toucher à la scène.
func _load_route_job(job: Dictionary) -> void:
	if str(job["id"]).begins_with(OW_PREFIX):
		job["ok"] = job["route"].load_live_dir(job["path"])
	else:
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
	if route.live:
		live_world.adopt(job["path"], route)
	else:
		live_world.close()
		streamer.set_previews([])
	follow.loop_length_m = route.length_m if route.is_loop() else 0.0
	bots_model.loop_length_m = follow.loop_length_m
	follow.reset()
	_menu_s = 0.0
	# Changement de parcours : tronçons et tuiles vidés puis reconstruits autour de s = 0.
	streamer.set_world(route, job["path"])
	if living_world != null:
		living_world.set_route(route, float(streamer.get("_road_width_m")))
		living_world.terrain_material = streamer.get("_terrain_material")
	_apply_sky_params(streamer._theme_dict)
	if living_decor != null:
		living_decor.set_fog_base(world_env.environment)
		living_decor.set_route(route, job["path"], float(streamer.get("_road_width_m")))
	var arch_every_m := SegmentMarkersModel.arch_every_m_from_file()
	segment_markers.set_route(route, arch_every_m, float(streamer.get("_road_width_m")))
	event_sounds.set_route(arch_every_m, route.length_m, route.is_loop())
	segment_hud.set_segments(route.segments)
	menu_flow.records.set_segments(route.segments)
	_route_profile = {"id": job["id"], "profile": hud.vm.profile(route, 0.0, 0.0, route.length_m, ROUTE_PROFILE_COLUMNS)}
	_refresh_menu()
	if route.segments_present:
		print("Segments du parcours : %d" % route.segments.size())
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
	_probe.route_ready()   # démarrage : première image jouable comptée à partir d'ici (lot X15)


# --- messages du core --------------------------------------------------------------------

## Messages de test (--test-mode) : « screenshot » enregistre l'image affichée en PNG et journalise
## l'état des éléments du HUD (texte, visibilité, rectangle à l'écran), pour tests/visual_check.py ;
## « command » fait envoyer une commande par l'engine ;
## « key » et « mouse » jouent une touche ou la souris par le vrai chemin des entrées de Godot, en menu comme en
## séance ; « menu_state » journalise l'état des menus (banc des menus, tests/menu_bench.py).
func _on_test_message(msg: Dictionary) -> void:
	match str(msg.get("action", "")):
		"screenshot":
			_test_screenshot(str(msg.get("path", "")), str(msg.get("tag", "")))
		"key":
			_test_key(str(msg.get("key", "")), bool(msg.get("shift", false)), int(msg.get("hold_ms", 100)))
		"mouse":
			_test_mouse(str(msg.get("kind", "click")), str(msg.get("item", "")), msg.get("at", []))
		"menu_state":
			ipc.test_log("menu_state " + JSON.stringify(_test_menu_state(str(msg.get("req", "")))))
		"weather":   # météo imposée (tests graphiques du lot P17)
			if living_decor != null and typeof(msg.get("weather")) == TYPE_DICTIONARY:
				living_decor.set_weather(msg["weather"])
		"menu_focus":   # focus sur un élément de l'écran courant du menu (tests graphiques du Garage, lot V8)
			menu_flow.menu.focus_item(str(msg.get("id", "")))
			_refresh_menu()
		"avatar_camera":   # caméra de contrôle derrière (« follow ») ou à côté (« side ») de l'avatar (lot V6)
			_avatar_cam = str(msg.get("view", "")) if str(msg.get("view", "")) in ["follow", "side"] else ""
			avatar_view.set_visible_for_view(_avatar_view_name())
		"command":   # commande du contrat envoyée par l'engine lui-même (pause, end_session…)
			ipc.send_command(str(msg.get("name", "")), msg.get("args", {}) if msg.get("args") is Dictionary else {})


## Touche simulée (nom de OS.find_keycode_from_string : « A », « Enter », « Escape »…) : appui, puis relâchement
## `hold_ms` plus tard, par Input.parse_input_event : même chemin qu'une vraie touche (_unhandled_input, key_map.gd).
## Les deux événements sont traités tout de suite (flush_buffered_events) et l'attente bloque l'image en cours :
## la durée mesurée par key_map.gd est celle demandée, même à 1 image/s sous Xvfb.
func _test_key(key_name: String, shift: bool, hold_ms: int) -> void:
	var code := OS.find_keycode_from_string(key_name)
	if code == KEY_NONE:
		ipc.test_log("key unknown=%s" % key_name)
		return
	var down := InputEventKey.new()
	down.keycode = code
	down.physical_keycode = code
	down.shift_pressed = shift
	down.pressed = true
	if key_name.length() == 1:
		down.unicode = (key_name.to_upper() if shift else key_name.to_lower()).unicode_at(0)
	Input.parse_input_event(down)
	Input.flush_buffered_events()
	OS.delay_usec(maxi(hold_ms, 0) * 1000)
	var up: InputEventKey = down.duplicate()
	up.pressed = false
	Input.parse_input_event(up)
	Input.flush_buffered_events()
	ipc.test_log("key done=%s shift=%s hold_ms=%d" % [key_name, shift, hold_ms])


## Souris simulée : `kind` click (bouton gauche), right, wheel_up, wheel_down ou move ; sur la rangée de l'élément
## `item` du menu, sinon au point `at` ([x, y] en pixels de la fenêtre), sinon au centre de la fenêtre. Déplacement,
## appui puis relâchement à l'image suivante (rangées mises en page), par Input.parse_input_event (même chemin que la
## vraie souris), traités tout de suite.
func _test_mouse(kind: String, item: String, at) -> void:
	await get_tree().process_frame   # mise en page des rangées tout juste affichées faite (conteneurs triés en différé)
	var to_pixels := get_viewport().get_final_transform()
	var pos := get_viewport().get_visible_rect().get_center() * to_pixels.get_scale()
	if item != "":
		var r: Rect2 = menu_view.item_rect(item)
		if not r.has_area():
			ipc.test_log("mouse hidden=%s" % item)
			return
		pos = to_pixels * r.get_center()
	elif at is Array and at.size() == 2:
		pos = Vector2(float(at[0]), float(at[1]))
	var move := InputEventMouseMotion.new()
	move.position = pos
	move.global_position = pos
	Input.parse_input_event(move)
	Input.flush_buffered_events()
	var buttons := {"click": MOUSE_BUTTON_LEFT, "right": MOUSE_BUTTON_RIGHT, "wheel_up": MOUSE_BUTTON_WHEEL_UP,
		"wheel_down": MOUSE_BUTTON_WHEEL_DOWN}
	if buttons.has(kind):
		var press := InputEventMouseButton.new()
		press.position = pos
		press.global_position = pos
		press.button_index = buttons[kind]
		press.button_mask = 1 << (int(buttons[kind]) - 1)
		press.pressed = true
		Input.parse_input_event(press)
		Input.flush_buffered_events()
		var release: InputEventMouseButton = press.duplicate()
		release.pressed = false
		release.button_mask = 0
		Input.parse_input_event(release)
		Input.flush_buffered_events()
	ipc.test_log("mouse done=%s item=%s at=%d,%d" % [kind, item, int(pos.x), int(pos.y)])


## État des menus pour le banc (`req` : numéro de la demande, rendu tel quel) : écran, titre, focus, éléments,
## rangées affichées avec leur rectangle en pixels, aide des boutons, pastilles des appareils, carte de détail, séance,
## monde ouvert, Cyber-Rogue.
func _test_menu_state(req: String) -> Dictionary:
	var st: Dictionary = menu_flow.state()
	var items: Array = []
	for it in st["items"]:
		items.append({"id": str(it.get("id", "")), "label": str(it.get("label", "")), "detail": str(it.get("detail", "")),
			"enabled": bool(it.get("enabled", true))})
	var focus := int(st["focus"])
	var to_pixels := get_viewport().get_final_transform()
	var rows: Array = []
	for row in menu_view.test_rows():
		var r: Rect2 = to_pixels * (row["rect"] as Rect2)
		rows.append({"id": row["id"], "text": row["text"], "focused": row["focused"],
			"rect": [r.position.x, r.position.y, r.size.x, r.size.y]})
	var world := {"visible": world_menu_view != null and world_menu_view.visible}
	if world["visible"]:
		world["state"] = str(world_menu_view.vm.state)
	return {"req": req, "visible": menu_view.visible, "screen": st["screen"], "title": st["title"],
		"status": st["status"], "focus": focus, "focus_id": items[focus]["id"] if focus >= 0 and focus < items.size() else "",
		"group": menu_flow.settings_group, "editing": st["editing"], "items": items, "rows": rows,
		"hint": menu_view.hint_text(), "devices": menu_view.devices.text() if menu_view.devices.visible else "",
		"card": menu_view.card.text() if menu_view.card.visible else "", "session_state": menu_flow.session_state, "world_menu": world,
		"rogue": rogue_host.is_active(), "hud": hud.visible, "quality": _quality_name}


func _avatar_info() -> Dictionary:
	if avatar_view == null:
		return {}
	var info: Dictionary = avatar_view.test_info()
	info["standing"] = avatar_model.standing
	info["crank"] = avatar_model.crank_angle
	info["on_screen"] = avatar_view.visible and not camera.is_position_behind(avatar_view.global_position + Vector3(0.0, 1.0, 0.0)) \
		and get_viewport().get_visible_rect().has_point(camera.unproject_position(avatar_view.global_position + Vector3(0.0, 1.0, 0.0)))
	return info


func _test_screenshot(path: String, tag: String) -> void:
	await RenderingServer.frame_post_draw
	var img := get_viewport().get_texture().get_image()
	var err := img.save_png(path) if path != "" else ERR_FILE_BAD_PATH
	_probe.mark_capture()   # pic de la lecture et de l'écriture : hors p99 de la sonde (lot X35)
	var widgets := {}
	var nodes := {
		"panel": hud.panel_center, "power": hud.power_val, "target": hud.target_val, "speed": hud.speed_val, "cadence": hud.cadence_val,
		"hr": hud.hr_val, "grade": hud.grade_val, "distance": hud.distance_val, "erg": hud.erg_label,
		"status": hud.status_label, "banner": banner, "menu": menu_view, "menu_title": menu_view.title_label,
		"menu_card": menu_view.card, "garage_preview": menu_view.preview, "button_bar": menu_view.button_bar,
		"erg_title": erg_panel.title_label, "erg_target": erg_panel.target_label,
		"erg_remaining": erg_panel.remaining_label, "erg_next": erg_panel.next_label, "erg_hist": erg_panel.histogram, "chart_erg": erg_panel.chart, "chart_sim": chart_sim,
		"bots_panel": hud.panel_bots, "bots_line1": hud.bots_lines[0], "bots_line2": hud.bots_lines[1],
		"bots_gap1": hud.bots_gaps[0],
		"bots_jerseys": hud.jerseys_label, "segment_panel": hud.panel_segment,
		"segment_title": hud.segment_title, "segment_main": hud.segment_main, "bonus_panel": hud.panel_bonus,
		"bonus_held": hud.bonus_held, "panel_left": hud.panel_left, "panel_right": hud.panel_right,
		"profile": hud.profile_panel,
		"power_caption": hud.power_val.get_meta("caption"), "speed_caption": hud.speed_val.get_meta("caption"),
		"cadence_caption": hud.cadence_val.get_meta("caption"), "hr_caption": hud.hr_val.get_meta("caption"),
		"grade_caption": hud.grade_val.get_meta("caption"),
		"target_caption": hud.target_val.get_meta("caption"), "gear": hud.gear_val, "time": hud.time_val,
		"wind": hud.panel_wind, "wind_speed": hud.wind_speed_label, "wind_level": hud.wind_level_label,
		"wind_verdict": hud.wind_verdict_label, "draft": hud.draft_label,
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
	# Voisins immédiats : la ligne de l'encart qui porte leur triangle (lot X22), cachée sans voisin affiché.
	for dir in ["ahead", "behind"]:
		var line: Label = hud.neighbor_line(dir)
		var r := to_pixels * line.get_global_rect() if line != null else Rect2()
		widgets["bots_" + dir] = {"text": line.text if line != null else "", "visible": line != null,
			"rect": [r.position.x, r.position.y, r.size.x, r.size.y]}
	var meshes := 0
	for n in streamer.find_children("*", "MeshInstance3D", true, false):
		if (n as MeshInstance3D).is_visible_in_tree():
			meshes += 1
	var info := {
		"tag": tag, "path": path, "ok": err == OK, "size": [img.get_width(), img.get_height()],
		"fps": Engine.get_frames_per_second(), "meshes": meshes, "ticks_ms": Time.get_ticks_msec(),
		"quality": _quality_name,
		"ui_scale": to_pixels.get_scale().x,
		"draw_calls": Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME),
		"camera": [camera.global_position.x, camera.global_position.y, camera.global_position.z],
		"camera_view": camera_views.effective(), "camera_transition": camera_views.in_transition(),
		"widgets": widgets,
		"decor": living_decor.test_info(camera) if living_decor != null else {},
		"bots": bots_view.test_info(camera) if bots_view != null else {},
		"avatar": _avatar_info(),
		"garage": _garage_info(),
		"rogue": rogue_host.test_info(),
	}
	ipc.test_log("screenshot " + JSON.stringify(info))


## Garage (lot V8) pour les tests : solde, choix, avatar enregistré et brouillon, états des pièces, aperçu 3D.
func _garage_info() -> Dictionary:
	var g = menu_flow.garage
	var states := {}
	for it in g.items:
		states[str(it["id"])] = str(it.get("state", ""))
	var out := {"enabled": g.enabled, "level": g.level, "coins": g.coins, "equipped": g.equipped, "avatar": g.saved_avatar,
		"draft": g.draft_avatar, "dirty": g.is_dirty(), "message": g.message, "states": states, "preview": {}}
	if menu_view.preview.visible:
		out["preview"] = menu_view.preview.test_info()
	return out


## Texte des zones composées du menu (éléments, appareils, bilan), pour les tests graphiques.
func _widget_text(key: String) -> String:
	if key == "menu":
		return "%s || %s || %s || %s || %s" % [menu_view.status_label.text, menu_view.items_text(), menu_view.devices.text() if menu_view.devices.visible else "",
				(menu_view.summary.text() + " || " + menu_view.summary.progress_text()) if menu_view.summary.visible else "", menu_view.card.text() if menu_view.card.visible else ""]
	return ""


## Avatar (lot V6) : réglages du profil et FTP du hello_ack (core sans `progression` : avatar par défaut).
func _configure_avatar() -> void:
	var prog = ipc.core_config.get("progression", {})
	var raw = prog.get("avatar") if prog is Dictionary else null
	camera_views.has_avatar = prog is Dictionary and not prog.is_empty()   # sans avatar : vue subjective seule (2.0-CAM-3)
	avatar_model.configure(raw, float(ipc.core_config.get("ftp_w", 0.0)))
	avatar_view.configure(avatar_model.settings, 0)
	avatar_view.set_visible_for_view(_avatar_view_name())


## Vue de caméra courante (l'avatar est masqué en subjective) ; une caméra de contrôle de test prend le pas.
func _avatar_view_name() -> String:
	return _avatar_cam if _avatar_cam != "" else camera_views.effective()


## Une fois par image : pédalier et position du modèle d'après la dernière trame, avatar posé sur la route.
## `pos` : point de la route sous le cycliste (déjà à l'échelle du relief), `heading` en radians.
func _step_avatar(pos: Vector3, heading: float, now_us: int, pitch_deg: float) -> void:
	if avatar_view == null:
		return
	var paused := session_state == "PAUSED"
	avatar_model.update(now_us / 1000000.0, _last_state.get("cadence", null), _last_state.get("power", null),
		_last_state.get("grade", null), paused)
	if not avatar_view.visible:
		return
	avatar_view.apply(avatar_model)
	var v = _last_state.get("v", 0.0)
	avatar_view.set_speed(float(v) * 3.6 if (v is float or v is int) else 0.0, now_us / 1000000.0)
	avatar_view.position = pos
	avatar_view.rotation = Vector3(deg_to_rad(pitch_deg), -heading, 0.0)
	if _avatar_cam != "":
		var fwd := Vector3(sin(heading), 0.0, -cos(heading))
		var right := Vector3(cos(heading), 0.0, sin(heading))
		if _avatar_cam == "side":
			camera.global_position = pos + right * 3.2 + Vector3(0.0, 1.0, 0.0)
		else:
			camera.global_position = pos - fwd * 3.0 + Vector3(0.0, 1.7, 0.0)
		camera.look_at(pos + Vector3(0.0, 0.95, 0.0), Vector3.UP)


## Équipement affiché (lot V7) : `look` de chaque identifiant (message `garage`), identifiants équipés
## (hello_ack puis `progression`).
var _look_of_id := {}
var _equipped_ids := {}


func _on_garage(items: Array) -> void:
	_look_of_id.clear()
	for it in items:
		if it is Dictionary:
			_look_of_id[it.get("id")] = it.get("look")
	_apply_equipment()
	menu_flow.on_garage(items)
	_refresh_menu()


## `xp_result` de fin de séance (lot V9) : bilan dans le résumé, bandeau « Niveau N ! » une seule fois.
const LEVEL_UP_S := 6.0


func _on_xp_result(msg: Dictionary) -> void:
	var text := menu_flow.on_xp_result(msg)
	if text != "":
		banner.show_message("level_up", text, LEVEL_UP_S)
	menu_view.summary.animate = _quality_name != "low"
	_refresh_menu()


## `progression` après equip, buy ou set_avatar : l'avatar et l'équipement affichés suivent, le catalogue
## est redemandé (états des pièces) et le Garage se met à jour.
func _on_progression(msg: Dictionary) -> void:
	var eq = msg.get("equipped")
	_equipped_ids = eq if eq is Dictionary else {}
	var prog := {}
	for key in ["level", "xp", "xp_next_level", "coins", "equipped", "avatar", "lives"]:
		if msg.has(key):
			prog[key] = msg[key]
	ipc.core_config["progression"] = prog
	_configure_avatar()
	_apply_equipment()
	menu_flow.on_progression(msg)
	ipc.request_garage()
	_refresh_menu()


func _apply_equipment() -> void:
	var looks := EquipmentMeshes.equip_looks(_equipped_ids, _look_of_id)
	if avatar_view != null:
		avatar_view.set_equipment(looks)
	if sound_player != null:
		sound_player.model.set_wheel_kind(EquipmentMeshes.wheel_sound(str(looks["wheels"])))


func _on_hello_ack(_ack: Dictionary) -> void:
	_configure_avatar()
	var prog = ipc.core_config.get("progression", {})
	menu_flow.on_hello_progression(prog)
	var eq = prog.get("equipped") if prog is Dictionary else null
	_equipped_ids = eq if eq is Dictionary else {}
	_apply_equipment()
	ipc.request_garage()
	# ipc.core_config garde ftp_w, gears_total et theme pour l'affichage. Core (re)démarré : listes
	# redemandées au prochain état affichant le menu. Modes de l'accueil : hello_ack.config.modes
	# (2.0 ; absent en 1.0).
	menu_flow.lists_needed()
	var ch := str(ipc.core_config.get("chart", "hidden"))
	if ch != chart_mode and ch in WorkoutChartView.MODES:
		chart_mode = ch
		_apply_chart_mode()
	menu_flow.menu.set_modes(ipc.core_config.get("modes"))
	menu_flow.rogue.configure(ipc.core_config.get("rogue"))
	menu_flow.set_versions(ipc.engine_version, ipc.core_version)


func _on_core_error(code: String, message: String) -> void:
	if world_menu_view != null and world_menu_view.visible:
		world_menu_view.vm.on_error(code, message)
		world_menu_view.update_display()
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
	if cmd_name in ["list_routes", "list_workouts", "list_imports"]:
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
	var previous_session_state := session_state
	if new_session_state != session_state:
		session_state = new_session_state
		# Rappel des commandes au départ et à la reprise ; effacé hors séance.
		if session_state == "RUNNING":
			banner.show_message("controls", HudViewModel.controls_text(state.get("erg", null) != null,
					str(state["erg"].get("kind", "workout")) if state.get("erg", null) is Dictionary else "workout"), CONTROLS_HINT_S)
		else:
			banner.clear_message("controls")
		# Une erreur reste au moins 5 s ; au-delà, elle reste tant que la séance est en ERROR.
		if banner.has_message("error"):
			banner.set_sticky("error", session_state == "ERROR")
	var route_id = state.get("route_id", null)
	if live_world.route != null:
		live_world.on_open_world(ipc.open_world)
	if world_menu_view != null and world_menu_view.visible and world_menu_view.vm.is_loading() \
			and session_state in ["READY", "RUNNING"] and str(route_id).begins_with(OW_PREFIX):
		world_menu_view.close()     # le monde est prêt : l'écran Prêt du menu prend le relais
		_refresh_menu()
	if (route_id == null or str(route_id) == "") and menu_flow.is_visible():
		route_id = DEMO_ROUTE_ID   # aucun parcours choisi : la démo tourne en fond des menus (lot N6)
	if route_id != _route_id_requested:
		_request_route(route_id)
	var running := session_state == "RUNNING"
	follow.push_frame(Time.get_ticks_usec(), float(state.get("s", 0.0)), float(state.get("v", 0.0)), running)
	ipc.test_log("state seq=%d s=%.3f session=%s" % [int(state.get("seq", 0)), float(state.get("s", 0.0)), session_state])

	if running and route != null:
		_give_cues(state)
	var in_session := running or session_state == "PAUSED"
	bots_model.push(state.get("bots", null) if in_session else null, Time.get_ticks_usec())
	bots_model.set_race(state if in_session else null)

	_feed_chart(state, running, previous_session_state)

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
		hud.update_segment(segment_hud.view(state, Time.get_ticks_msec() / 1000.0))
	if junction_view != null:
		junction_view.update_display(ipc.open_world if not ipc.open_world.is_empty() else null,
			get_viewport().get_visible_rect().size, hud.panel_center.get_global_rect().end.y)
	_show_bots(float(state.get("s", 0.0)), float(state.get("v", 0.0)))
	if living_decor != null:
		living_decor.ftp_w = float(ipc.core_config.get("ftp_w", 0.0))
	if living_world != null:
		# Vent du core (lot P16) : modèle du décor et indicateur du HUD, par rapport au cap de la route
		var wind_now_s := Time.get_ticks_msec() / 1000.0
		living_world.on_state(state, wind_now_s)
		var heading_deg: float = route.sample_heading_deg(route.wrap_s(float(state.get("s", 0.0)))) if route != null else 0.0
		if hud != null and hud.has_method("update_wind"):
			hud.update_wind(living_world.wind_hud(state, heading_deg, wind_now_s))

	rogue_host.ftp_w = float(ipc.core_config.get("ftp_w", 0.0))
	if rogue_host.update(state, self, [streamer, sun, living_decor, segment_markers], world_env, camera,
			_quality_name, float(Time.get_ticks_msec()) / 1000.0):
		ipc.request_rogue_resync()

	if sound_player != null and camera != null:
		var now_s := float(Time.get_ticks_msec()) / 1000.0
		sound_player.update_audio(state, now_s, camera.position)
	for jingle in event_sounds.on_state(state):
		_play_event(jingle)


## Taille des courbes (lot O14) : ERG à la place de l'histogramme, SIM dans son panneau.
func _apply_chart_mode() -> void:
	if erg_panel != null:
		erg_panel.set_chart(null, chart_mode)
	if chart_sim != null:
		chart_sim.set_mode(chart_mode)


## Courbes (lot O14) : une seconde de plus à chaque trame RUNNING ; remise à zéro au départ d'une
## séance (pas à la reprise après pause), profil de l'entraînement ERG en cours.
func _feed_chart(state: Dictionary, running: bool, previous_state: String) -> void:
	var erg = state.get("erg", null)
	var in_erg: bool = typeof(erg) == TYPE_DICTIONARY and not (erg as Dictionary).is_empty()
	if running and previous_state != "RUNNING" and previous_state != "PAUSED":
		chart_model.reset()
		_chart_workout = ""
		_chart_points = 0
	var name_now := str(erg.get("workout_name", "")) if in_erg else ""
	if running and name_now != _chart_workout:
		_chart_workout = name_now
		var prof: Array = erg_panel.profile_of(name_now) if (erg_panel != null and in_erg) else []
		if prof.is_empty():
			chart_model.clear_workout()
		else:
			chart_model.set_workout(prof, float(ipc.core_config.get("ftp_w", 0.0)), 0.0)
	if running:
		var target = null
		if in_erg and str(erg.get("block_type", "steady")) != "freeride":
			target = erg.get("target_w", null)
		chart_model.push(float(state.get("t", -1.0)), state.get("power", null), state.get("hr", null), state.get("cadence", null), target)
	var n: int = chart_model.point_count()
	var shown: bool = chart_mode != "hidden" and not in_erg and not menu_flow.is_visible() and (running or session_state == "PAUSED")
	if chart_sim != null:
		chart_sim.visible = shown
	if n != _chart_points:
		_chart_points = n
		if chart_sim != null:
			chart_sim.refresh()
		if erg_panel != null and erg_panel.chart != null:
			erg_panel.chart.refresh()


## Bots (lot O7) : encart du HUD et silhouettes sur la route, aux positions affichées à l'instant.
func _show_bots(rider_s: float, rider_v: float) -> void:
	var view: Array = bots_model.view(rider_s, rider_v, Time.get_ticks_usec())
	if hud != null and hud.has_method("update_bots"):
		hud.update_bots(view, bots_model.race())
	if bots_view != null:
		bots_view.update_view(view, route)


## Consignes d'essai atteintes : bandeau, bip et ligne « [essai] » dans le journal du lanceur, avec les
## relevés du moment (temps, puissance, cadence, FC, braquet, pente envoyée) : rien à chronométrer à la main.
## Un préavis (« Dans 1 min, prépare … ») laisse le temps de préparer le matériel.
func _give_cues(state: Dictionary) -> void:
	var s := float(state.get("s", 0.0))
	for c in _cues.update(s, float(state.get("t", -1.0))):
		var label := "Préavis %d/%d : %s" % [c["index"], c["count"], c["warn_text"]] if c["warn"] \
				else "Consigne %d/%d : %s" % [c["index"], c["count"], c["text"]]
		banner.show_message("cue", label, c["duration_s"])
		if c["beep"]:
			_play_tones(CUE_BEEP, ERG_BEEP_LEVEL)
		print("[essai] %s %d/%d à %.0f m, t = %.0f s, braquet %s, puissance %s W, cadence %s, FC %s, pente envoyée %s %% : %s" % [
				"préavis" if c["warn"] else "consigne", c["index"], c["count"], s, float(state.get("t", 0.0)),
				str(state.get("gear", "?")), str(state.get("power", "?")), str(state.get("cadence", "?")),
				str(state.get("hr", "?")), str(state.get("grade_sent", "?")),
				c["warn_text"] if c["warn"] else c["text"]])
		ipc.test_log("cue index=%d warn=%s s=%.1f" % [c["index"], str(c["warn"]), s])


func _exit_tree() -> void:
	if not _route_job.is_empty():
		WorkerThreadPool.wait_for_task_completion(_route_job["task"])
	_probe.close()
