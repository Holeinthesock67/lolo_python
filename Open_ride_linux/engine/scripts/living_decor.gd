extends Node3D

## Décor vivant (Lot P17, première vague) : branche dans la scène principale la météo légère (P8), les
## animaux (P11), les éoliennes, les drapeaux et l'eau qui scintille (P12), les véhicules croisés (P13),
## les panneaux, bornes et marquages (P14), les spectateurs (P15) et les passants (P21). Deuxième vague
## (P22 à P29, intégrée par P27) : oiseaux de campagne (P23) et animaux selon le terrain (P24) dans
## fauna_renderer.gd ; circulation des routes voisines et tracteurs des champs (P25, road_traffic_model.gd)
## et phares de tous les véhicules par brume, pluie ou soleil bas (traffic_model.gd `headlights`) ; avions
## de ligne, hélicoptère, parapentes au-dessus des montées et montgolfières (P26, sky_traffic_model.gd),
## variés selon le biome, et paramoteurs des pays plats (P31) ;
## cyclistes du décor sur la route, qui laissent la place aux bots (P28, road_cyclists_model.gd) ; bateaux
## des lacs et des cours d'eau, feux allumés avec les phares (P29, boat_model.gd). Pas de class_name :
## charger par preload("res://scripts/living_decor.gd"). Créé par main.gd, à côté de living_world.gd
## (P16), dont il reprend le vent évalué.
##
## - `configure(preset, enabled, theme, environment, sound_player, world_streamer)` : budgets
##   `living(preset, enabled)`, météo du thème, marquages de la route et eau qui scintille, animaux placés
##   par les tâches de fond d'osm_streamer.gd. `enabled` faux (`[render] living = false`) : rien de tout
##   cela, rendu et sons de la 1.0.
## - `set_route(route, world_dir, road_width_m)` : une tâche de fond lit les couches OSM de tout le parcours
##   (bâtiments, eau, points d'intérêt), prend les montées (couche `segments`, sinon détection), prépare
##   les objets du bord de route, les chiffres peints, les spectateurs et les passants ; `step` applique
##   le résultat dès qu'il est prêt
##   (éoliennes, drapeaux, circulation, panneaux des tronçons déjà chargés).
## - `set_fog_base(env)` après chaque `RenderQuality.apply_fog` : brouillard de référence de la brume.
## - `step(now_s, dt_s, cam_pos, cam_s, rider_v, alt_m, paused, wind_eval, state, beep_active)` une fois
##   par image (sauf core non joignable : décor figé) : météo (particules, brume au plus toutes les
##   FOG_PERIOD_S, chaussée mouillée, pluie dans l'ambiance), oiseaux et animaux, éoliennes et drapeaux,
##   reflets de l'eau ; puis, une fois le parcours préparé, dans cet ordre (lot P27) : cyclistes du décor,
##   véhicules de la route, véhicules lointains, ciel et bateaux (figés en pause), spectateurs (clameur
##   selon la puissance et les bots doublés) et passants. La météo évaluée (`weather_eval`), le vent
##   (`wind_eval`) et les bots de `state` sont lus une seule fois par image et passés à chacun ;
##   `wave2_us` / `wave2_frames` : temps moyen des lots P23 à P26, P28 et P29 (enveloppe de P27).
## Panneaux et animaux suivent les tronçons d'osm_streamer.gd (`chunk_loaded` / `chunk_freed`) : au plus
## un nœud par panneau ou borne, quelques-uns par tronçon ; aucun autre nœud n'est créé après `configure`.

const QualityPresets := preload("res://scripts/quality_presets.gd")
const RenderQuality := preload("res://scripts/render_quality.gd")
const OsmLayers := preload("res://scripts/osm_layers.gd")
const RoadBuilder := preload("res://scripts/road_builder.gd")
const WeatherModel := preload("res://scripts/weather_model.gd")
const WeatherParticles := preload("res://scripts/weather_particles.gd")
const FaunaRenderer := preload("res://scripts/fauna_renderer.gd")
const WindTurbines := preload("res://scripts/wind_turbines.gd")
const Flags := preload("res://scripts/flags.gd")
const WaterMesh := preload("res://scripts/water_mesh.gd")
const TrafficModel := preload("res://scripts/traffic_model.gd")
const TrafficRenderer := preload("res://scripts/traffic_renderer.gd")
const RoadTrafficModel := preload("res://scripts/road_traffic_model.gd")
const RoadTrafficRenderer := preload("res://scripts/road_traffic_renderer.gd")
const RoadCyclistsModel := preload("res://scripts/road_cyclists_model.gd")
const RoadCyclistsRenderer := preload("res://scripts/road_cyclists_renderer.gd")
const ThemeRenderParams := preload("res://scripts/theme_render_params.gd")
const SkyTrafficModel := preload("res://scripts/sky_traffic_model.gd")
const SkyTrafficRenderer := preload("res://scripts/sky_traffic_renderer.gd")
const BoatModel := preload("res://scripts/boat_model.gd")
const BoatRenderer := preload("res://scripts/boat_renderer.gd")
const ClimbDetector := preload("res://scripts/climb_detector.gd")
const SegmentMarkersModel := preload("res://scripts/segment_markers_model.gd")
const RoadsideModel := preload("res://scripts/roadside_model.gd")
const RoadsideProps := preload("res://scripts/roadside_props.gd")
const CrowdModel := preload("res://scripts/crowd_model.gd")
const CrowdRenderer := preload("res://scripts/crowd_renderer.gd")
const PassersbyModel := preload("res://scripts/passersby_model.gd")

const FOG_PERIOD_S := 0.5
const SOUND_POLL_S := 0.25          # relevé des sons du décor qui démarrent (P30)
const VALLEY_WINDOW_M := 2000.0     # altitude de vallée : moyenne de la route à ± 2 km
const CHUNK_M := 1000.0

var enabled := true
var preset := "low"
var living: Dictionary = {}
var theme: Dictionary = {}
var weather: Dictionary = {}
var weather_eval: Dictionary = {}
var sound_player = null
var world_streamer = null
var osm_streamer = null
var environment: Environment = null
var living_world = null             # living_world.gd (P16) : pluie dans l'ambiance

var particles: Node3D = null
var fauna: Node3D = null
var turbines: Node3D = null
var flags: Node3D = null
var traffic = TrafficModel.new()
var traffic_view: Node3D = null
var road_traffic = RoadTrafficModel.new()
var road_traffic_view: Node3D = null
var cyclists = RoadCyclistsModel.new()
var cyclists_view: Node3D = null
var headlights := false
var sky = SkyTrafficModel.new()
var sky_view: Node3D = null
var boats = BoatModel.new()
var boats_view: Node3D = null
var props: Node3D = null
var crowd = CrowdModel.new()
var crowd_view: Node3D = null
var passersby = PassersbyModel.new()
var passersby_view: Node3D = null

var climbs: Array = []
var pois: Array = []
var roadside_items: Array = []
var prepared := false               # résultat de la tâche de fond appliqué
var fog_updates := 0                # brouillard recalculé (tests)
var last_cheer := 0.0
var ftp_w := 0.0                    # FTP du core (hello_ack), pour la clameur des spectateurs
var last_event: Dictionary = {}
var wave2_us := 0                   # temps cumulé des lots P23 à P26, P28 et P29 dans `step` (P27, enveloppe)
var wave2_frames := 0
var sounds_heard: Dictionary = {}   # nom du son (sound_player.gd) -> départs relevés depuis `configure` (P30)
var _audio: Array = []              # lecteurs 3D du décor, tous créés par _build_nodes
var _audio_was_playing: Array = []
var _sound_at := -INF

var _route = null
var _road_width_m := RoadBuilder.ROAD_WIDTH_M
var _job: Dictionary = {}
var _generation := 0
var _loaded_chunks: Dictionary = {}  # k -> true (tronçons OSM affichés)
var _fog_base := Vector2(-1.0, -1.0)
var _fog_vol_base := 0.0
var _fog_at := -INF
var _fog_boost := 0.0
var _valley_alt := 0.0
var _valley_at_s := -INF
var _sun_elevation_deg := 45.0


func configure(preset_name: String, living_enabled: bool, p_theme: Dictionary, p_environment: Environment = null,
		p_sound_player = null, p_world_streamer = null) -> void:
	preset = preset_name
	enabled = living_enabled
	living = QualityPresets.living(preset, enabled)
	theme = p_theme
	sound_player = p_sound_player
	world_streamer = p_world_streamer
	weather = WeatherModel.from_theme(theme) if enabled else WeatherModel.clear()
	weather_eval = {}
	sounds_heard = {}
	set_fog_base(p_environment)
	if particles == null:
		_build_nodes()
	particles.configure(int(living.get("weather_particles", 0)))
	fauna.set_preset(preset, enabled)
	fauna.setup_sound(sound_player)
	crowd_view.set_preset(preset, enabled)
	passersby_view.set_preset(preset, enabled)
	traffic.set_budget(int(living.get("vehicles", 0)))
	road_traffic.set_budget(int(living.get("distant_vehicles", 0)))
	road_traffic_view.set_budget(int(living.get("distant_vehicles", 0)))
	cyclists.set_budget(int(living.get("cyclists", 0)))
	sky.set_budget(int(living.get("aircraft", 0)))
	boats.set_budget(int(living.get("boats", 0)))
	_sun_elevation_deg = float(ThemeRenderParams.sky_params(theme)["sun_elevation_deg"])
	turbines.visible = enabled
	flags.visible = enabled
	if world_streamer != null:
		if world_streamer.has_method("set_road_markings"):
			world_streamer.set_road_markings(enabled)
		var osm = world_streamer.get("osm_streamer")
		if osm != null and osm != osm_streamer:
			osm_streamer = osm
			osm_streamer.chunk_loaded.connect(_on_chunk_loaded)
			osm_streamer.chunk_freed.connect(_on_chunk_freed)
	if osm_streamer != null:
		osm_streamer.fauna_enabled = enabled and int(living.get("animals", 0)) + int(living.get("birds", 0)) > 0
		osm_streamer.traffic_enabled = enabled and int(living.get("distant_vehicles", 0)) > 0
		osm_streamer.boats_enabled = enabled and int(living.get("boats", 0)) > 0
		osm_streamer.set_water_shimmer(enabled and bool(living.get("water_shimmer", false)))


func _build_nodes() -> void:
	particles = WeatherParticles.new()
	particles.name = "WeatherParticles"
	add_child(particles)
	fauna = FaunaRenderer.new()
	fauna.name = "Fauna"
	add_child(fauna)
	turbines = WindTurbines.new()
	turbines.name = "WindTurbines"
	add_child(turbines)
	flags = Flags.new()
	flags.name = "Flags"
	add_child(flags)
	traffic_view = TrafficRenderer.new()
	traffic_view.name = "Traffic"
	add_child(traffic_view)
	traffic_view.setup(traffic, sound_player)
	road_traffic_view = RoadTrafficRenderer.new()
	road_traffic_view.name = "RoadTraffic"
	add_child(road_traffic_view)
	road_traffic_view.setup(road_traffic)
	cyclists_view = RoadCyclistsRenderer.new()
	cyclists_view.name = "RoadCyclists"
	add_child(cyclists_view)
	cyclists_view.setup(cyclists, sound_player)
	sky_view = SkyTrafficRenderer.new()
	sky_view.name = "SkyTraffic"
	add_child(sky_view)
	sky_view.setup(sky, sound_player)
	boats_view = BoatRenderer.new()
	boats_view.name = "Boats"
	add_child(boats_view)
	boats_view.setup(boats, sound_player)
	props = RoadsideProps.new()
	props.name = "RoadsideProps"
	add_child(props)
	crowd_view = CrowdRenderer.new()
	crowd_view.name = "Spectators"
	add_child(crowd_view)
	crowd_view.setup(crowd, sound_player)
	passersby_view = CrowdRenderer.new("passersby")
	passersby_view.name = "Passersby"
	add_child(passersby_view)
	passersby_view.setup_passersby(passersby, sound_player)
	_audio = find_children("*", "AudioStreamPlayer3D", true, false)
	_audio_was_playing.resize(_audio.size())
	_audio_was_playing.fill(false)


## Départs des sons du décor, relevés toutes les SOUND_POLL_S (lecteur qui passe à `playing`) : tests
## automatiques des sons (lot P30), sans toucher aux lots qui les jouent.
func _poll_sounds(now_s: float) -> void:
	if now_s - _sound_at < SOUND_POLL_S or sound_player == null:
		return
	_sound_at = now_s
	for i in range(_audio.size()):
		var a: AudioStreamPlayer3D = _audio[i]
		var on := a.playing
		if on and not _audio_was_playing[i]:
			var kind: String = sound_player.kind_of(a.stream)
			if kind != "":
				sounds_heard[kind] = int(sounds_heard.get(kind, 0)) + 1
		_audio_was_playing[i] = on


## Nouveau parcours : préparation en tâche de fond (voir l'en-tête). `world_dir` vide : pas de couche OSM.
func set_route(route, world_dir: String = "", road_width_m: float = RoadBuilder.ROAD_WIDTH_M) -> void:
	_wait_job()
	_generation += 1
	_route = route
	_road_width_m = road_width_m
	props.road_width_m = road_width_m
	prepared = false
	climbs = []
	pois = []
	roadside_items = []
	traffic.configure(null, theme, [], 0)
	cyclists.configure(null, [], [], 0)
	sky.configure(null, theme, [], 0)
	crowd.configure(null, [])
	passersby.configure(null)
	turbines.set_points([])
	flags.set_points([])
	for k in _loaded_chunks.keys():
		props.remove_chunk(k)
	_valley_at_s = -INF
	if world_streamer != null and world_streamer.has_method("set_road_marks"):
		world_streamer.set_road_marks({})
	if route == null or not enabled:
		return
	var layers: Array = osm_streamer.layers_present.duplicate() if osm_streamer != null and not world_dir.is_empty() else []
	var job := {"gen": _generation, "route": route, "world_dir": world_dir, "layers": layers,
		"road_width_m": road_width_m, "crowd_all_climbs": false, "result": {}}
	job["task"] = WorkerThreadPool.add_task(_prepare_job.bind(job), false, "décor du parcours")
	_job = job


## Tâche de fond, sans toucher à la scène : modèles purs (RefCounted) et listes.
static func _prepare_job(job: Dictionary) -> void:
	var r = job["route"]
	var w_dir: String = job["world_dir"]
	var layers: Array = job["layers"]
	var buildings := []
	var water := {"lines": [], "areas": []}
	var all_pois := []
	var n := int(ceil(float(r.length_m) / CHUNK_M))
	for k in range(maxi(1, n)):
		if layers.has("buildings"):
			var b := OsmLayers.load_chunk(w_dir, "buildings", k)
			if b.get("ok", false):
				buildings.append_array(b.get("items", []))
		if layers.has("water"):
			var w := OsmLayers.load_chunk(w_dir, "water", k)
			if w.get("ok", false):
				water["lines"].append_array(w.get("lines", []))
				water["areas"].append_array(w.get("areas", []))
		if layers.has("poi"):
			var p := OsmLayers.load_chunk(w_dir, "poi", k)
			if p.get("ok", false):
				all_pois.append_array(p.get("items", []))
	var road_w: float = job["road_width_m"]
	var found: Array = climbs_of(r)
	var cm = CrowdModel.new()
	cm.configure(r, found, water, bool(job["crowd_all_climbs"]), 0, road_w)
	var pm = PassersbyModel.new()
	pm.configure(r, buildings, water, 0, road_w, PassersbyModel.crowd_zones(found, bool(job["crowd_all_climbs"])))
	var marks := {}
	for m in RoadsideModel.paint_marks(found):
		var k := int(floor(float(m["s"]) / CHUNK_M))
		if not marks.has(k):
			marks[k] = []
		marks[k].append(m)
	job["result"] = {
		"climbs": found, "pois": all_pois, "crowd": cm, "passersby": pm, "marks": marks,
		"items": RoadsideModel.items(r, found, all_pois, water),
	}


## Montées du parcours : celles de la couche `segments` quand elle existe (lot T8, une seule source avec
## le chronométrage du core), sinon celles de climb_detector.gd (P14).
static func climbs_of(r) -> Array:
	if r.get("segments_present") == true:
		return SegmentMarkersModel.climbs(r, r.segments)
	return ClimbDetector.detect(r)


func _wait_job() -> void:
	if not _job.is_empty():
		WorkerThreadPool.wait_for_task_completion(_job["task"])
		_job = {}


## Attend la tâche de fond et applique son résultat (tests, chargement initial).
func flush() -> void:
	_poll_job(true)


func _poll_job(wait: bool = false) -> void:
	if _job.is_empty() or (not wait and not WorkerThreadPool.is_task_completed(_job["task"])):
		return
	var job := _job
	_job = {}
	WorkerThreadPool.wait_for_task_completion(job["task"])
	if int(job["gen"]) != _generation:
		return
	var res: Dictionary = job["result"]
	climbs = res["climbs"]
	pois = res["pois"]
	roadside_items = res["items"]
	crowd = res["crowd"]
	crowd_view.setup(crowd, sound_player)
	passersby = res["passersby"]
	passersby_view.setup_passersby(passersby, sound_player)
	traffic.configure(_route, theme, pois, int(living.get("vehicles", 0)))
	cyclists.configure(_route, climbs, pois, int(living.get("cyclists", 0)), 0, _road_width_m, traffic)
	sky.biome_model = _active_biome_model()
	sky.configure(_route, theme, climbs, int(living.get("aircraft", 0)))
	turbines.set_points(pois)
	flags.set_points(pois)
	if world_streamer != null and world_streamer.has_method("set_road_marks"):
		world_streamer.set_road_marks(res["marks"])
	for k in _loaded_chunks:
		props.add_chunk(_route, k, RoadsideModel.for_chunk(roadside_items, k))
	prepared = true


## Modèle de biome du parcours quand il suit des biomes (couche ou forçage, lot U5), sinon null (lot P31).
func _active_biome_model():
	var model = world_streamer.get("biome_model") if world_streamer != null else null
	return model if model != null and model.active() else null


func _on_chunk_loaded(k: int, extras: Dictionary) -> void:
	_loaded_chunks[k] = true
	if not enabled:
		return
	var groups: Array = extras.get("fauna", [])
	if not groups.is_empty():
		fauna.set_chunk(k, groups)
	road_traffic.set_chunk(k, extras.get("traffic", []))
	boats.set_chunk(k, extras.get("boats", []))
	if prepared:
		props.add_chunk(_route, k, RoadsideModel.for_chunk(roadside_items, k))


func _on_chunk_freed(k: int) -> void:
	_loaded_chunks.erase(k)
	fauna.remove_chunk(k)
	road_traffic.remove_chunk(k)
	boats.remove_chunk(k)
	props.remove_chunk(k)


## Brouillard de référence (RenderQuality.apply_fog) : la brume le rapproche.
func set_fog_base(env: Environment) -> void:
	if env == null:
		return
	environment = env
	_fog_base = Vector2(env.fog_depth_begin, env.fog_depth_end)
	_fog_vol_base = env.volumetric_fog_density if env.volumetric_fog_enabled else 0.0
	_fog_at = -INF


## Altitude moyenne de la route à ± VALLEY_WINDOW_M de `s` (9 points), recalculée tous les 100 m.
func _valley_alt_at(s: float) -> float:
	if _route == null:
		return 0.0
	if absf(s - _valley_at_s) < 100.0:
		return _valley_alt
	_valley_at_s = s
	var total := 0.0
	for i in range(9):
		var q: float = _route.wrap_s(clampf(s + (i - 4) * VALLEY_WINDOW_M / 4.0, 0.0, _route.length_m))
		total += float(_route.sample(q)["alt_m"])
	_valley_alt = total / 9.0
	return _valley_alt


func step(now_s: float, dt_s: float, cam_pos: Vector3, cam_s: float, rider_v: float, alt_m: float,
		paused: bool, wind_eval: Dictionary, state: Dictionary = {}, beep_active: bool = false) -> void:
	_poll_job()
	if not enabled or _route == null:
		return
	var rider_pos := cam_pos - Vector3(0.0, 1.4, 0.0)
	# Météo (P8)
	weather_eval = WeatherModel.evaluate(weather, alt_m, _valley_alt_at(cam_s), wind_eval)
	particles.update(cam_pos, weather_eval)
	if world_streamer != null and world_streamer.has_method("set_road_wetness"):
		world_streamer.set_road_wetness(float(weather_eval.get("wetness", 0.0)))
	if living_world != null:
		living_world.rain = float(weather_eval.get("rain", 0.0))
	if environment != null and _fog_base.y > 0.0 and now_s - _fog_at >= FOG_PERIOD_S:
		_fog_at = now_s
		var boost := float(weather_eval.get("fog_boost", 0.0))
		if absf(boost - _fog_boost) > 0.01 or fog_updates == 0:
			_fog_boost = boost
			RenderQuality.apply_weather_fog(environment, _fog_base, boost, _fog_vol_base)
			fog_updates += 1
	# Oiseaux et animaux (P11, P22 à P24), éoliennes, drapeaux et eau (P12)
	var t_fauna := Time.get_ticks_usec()
	fauna.update(cam_pos, rider_pos, now_s)
	wave2_us += Time.get_ticks_usec() - t_fauna
	wave2_frames += 1
	turbines.update(wind_eval, cam_pos, dt_s)
	flags.update(wind_eval, dt_s)
	if osm_streamer != null:
		WaterMesh.update_shimmer(osm_streamer.water_material(), wind_eval, dt_s)
	if not prepared:
		return
	# Bots de l'état du core, lus une fois : cyclistes du décor (P28) et spectateurs (P15)
	var bots: Array = []
	var bots_s := []
	var bots_raw = state.get("bots", [])
	if typeof(bots_raw) == TYPE_ARRAY:
		bots = bots_raw
		for b in bots:
			if typeof(b) == TYPE_DICTIONARY and typeof(b.get("s")) in [TYPE_INT, TYPE_FLOAT]:
				bots_s.append(float(b["s"]))
	var t_wave2 := Time.get_ticks_usec()
	# Cyclistes du décor (P28), figés en pause, qui laissent la place aux bots
	cyclists.update(cam_s, rider_v, dt_s, paused, bots_s)
	cyclists_view.update(dt_s, paused)
	# Véhicules de la route (P13), puis routes voisines et champs (P25), figés en pause ; phares (P25)
	headlights = TrafficModel.headlights(weather_eval, _sun_elevation_deg)
	traffic.update(cam_s, rider_v, dt_s, paused)
	traffic_view.set_lights(headlights)
	traffic_view.update()
	road_traffic.update(cam_pos, dt_s, paused)
	road_traffic_view.set_lights(headlights)
	road_traffic_view.update()
	# Ciel (P26), figé en pause
	sky.update(cam_pos, dt_s, wind_eval, weather_eval, paused)
	sky_view.update()
	# Bateaux (P29), figés en pause, feux avec les phares
	boats.update(cam_pos, dt_s, wind_eval, weather_eval, paused)
	boats_view.set_lights(headlights)
	boats_view.update()
	wave2_us += Time.get_ticks_usec() - t_wave2
	# Spectateurs (P15) et passants (P21)
	crowd.update(rider_pos, cam_s, now_s)
	if not bots.is_empty():
		crowd.observe_bots(cam_s, bots, now_s)
	var power := float(state["power"]) if typeof(state.get("power")) in [TYPE_INT, TYPE_FLOAT] else NAN
	last_cheer = crowd.cheer(cam_s, now_s, power, ftp_w if ftp_w > 0.0 else NAN)
	crowd_view.update(cam_pos, now_s, last_cheer)
	last_event = passersby.update(rider_pos, cam_s, now_s, beep_active)
	passersby_view.update_passersby(cam_pos, cam_s, now_s, last_event)
	_poll_sounds(now_s)


## Météo imposée (mode test des tests graphiques) : même forme que `weather` du thème 1.2.
func set_weather(w: Dictionary) -> void:
	weather = WeatherModel.from_theme({"weather": w, "terrain": theme.get("terrain", {})}) if enabled else WeatherModel.clear()


## Somme des positions de ce qui se fige en pause (véhicules de la route et lointains, cyclistes du décor,
## ciel, bateaux), arrondie au centimètre : deux valeurs égales en pause = rien n'a bougé (lot P30).
func frozen_signature() -> float:
	var sig := 0.0
	for v in traffic.vehicles:
		sig += float(v["s"])
	for g in cyclists.groups:
		sig += float(g["s"])
	for list in [road_traffic.vehicles, sky.craft, boats.boats]:
		for o in list:
			var p: Vector3 = (o["xform"] as Transform3D).origin
			sig += p.x + p.y + p.z
	return snappedf(sig, 0.01)


## Animaux au sol affichés (P11, P24), pour test_info.
func _animal_count() -> int:
	var n := 0
	if fauna != null:
		for sp in FaunaRenderer.GROUND_SPECIES:
			n += fauna.visible_count(sp)
	return n


## État du décor pour les captures des tests graphiques : nombres affichés, météo, et le panneau le plus
## proche devant la caméra (texte, distance, hauteur des lettres à l'écran en pixels de l'image).
func test_info(cam: Camera3D) -> Dictionary:
	var out := {
		"enabled": enabled, "prepared": prepared, "props": props.prop_count() if props != null else 0,
		"spectators": crowd_view.visible_count() if crowd_view != null else 0,
		"passersby": passersby_view.visible_count() if passersby_view != null else 0,
		"vehicles": traffic_view.visible_count() if traffic_view != null else 0,
		"distant_vehicles": road_traffic_view.visible_count() if road_traffic_view != null else 0,
		"cyclists": cyclists_view.visible_count() if cyclists_view != null else 0,
		"headlights": headlights,
		"birds": fauna.visible_count("bird") if fauna != null else 0,
		"animals": _animal_count(),
		"aircraft": sky_view.visible_count() if sky_view != null else 0,
		"boats": boats_view.visible_count() if boats_view != null else 0,
		"particles": particles.get_active_count() if particles != null else 0,
		"rain": float(weather_eval.get("rain", 0.0)), "wetness": float(weather_eval.get("wetness", 0.0)),
		"fog_boost": float(weather_eval.get("fog_boost", 0.0)),
		"sounds": sounds_heard.duplicate(),
		"frozen_sig": frozen_signature(),
		"sign": {},
	}
	if cam == null or props == null:
		return out
	var fwd := -cam.global_transform.basis.z
	var best: Node3D = null
	var best_d := INF
	for n in props.get_children():
		var nd := n as Node3D
		if nd == null or not nd.has_meta("label"):
			continue
		var rel := nd.global_position - cam.global_position
		var d := rel.dot(fwd)
		if d > 5.0 and d < best_d and not cam.is_position_behind(nd.global_position):
			best_d = d
			best = nd
	if best != null:
		var label: Label3D = best.get_meta("label")
		var h := RoadsideProps.letter_height_m(best)
		var p0 := cam.unproject_position(label.global_position)
		var p1 := cam.unproject_position(label.global_position + Vector3(0.0, h, 0.0))
		var px := absf(p1.y - p0.y)
		var vh := maxf(1.0, cam.get_viewport().get_visible_rect().size.y)
		out["sign"] = {"text": label.text, "dist_m": best_d, "letter_px": px, "letter_px_720": px * 720.0 / vh}
	return out


func _exit_tree() -> void:
	_wait_job()
