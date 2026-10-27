extends Node3D

## Décor vivant, première vague (Lot P16) : branche dans la scène principale le vent (P4), les arbres et
## l'herbe au vent (P5), les nuages (P6) et les fonds sonores (P9). Pas de class_name : charger par
## preload("res://scripts/living_world.gd"). Créé par main.gd.
##
## - `configure(preset, enabled, theme, environment, sound_player, osm_streamer, tree_renderer)` :
##   budgets `living(preset, enabled)`, vent décoratif du thème, matériaux des arbres, ciel de P6 à la
##   place du ciel actuel, réglages d'ambiance du thème. `enabled` faux (`[render] living = false`) :
##   rien de tout cela, rendu et sons de la 1.0 (le vent du core reste affiché dans le HUD).
## - `set_route(route, road_width_m)` : touffes d'herbe le long du nouveau parcours.
## - `on_state(state, now_s)` à chaque trame ; `wind_hud(state, heading_deg, now_s)` : indicateur du HUD.
## - `step(now_s, dt_s, cam_pos, cam_s, rider_v, heading_deg, alt_m, paused)` une fois par image :
##   paramètres globaux du vent, vent apparent de l'herbe, défilement des nuages (et leur ombre sur le
##   terrain en `high`), fonds d'ambiance et cloches ; le voisinage sonore (part de forêt et de bâti, eau
##   la plus proche) n'est recalculé qu'au plus toutes les NEIGH_PERIOD_S, à partir des contours des
##   tronçons OSM déjà chargés (osm_streamer.gd `layer_shapes`) à moins de AmbienceModel.RADIUS_M.

const WindModel := preload("res://scripts/wind_model.gd")
const WindViewModel := preload("res://scripts/wind_view_model.gd")
const TreeRenderer := preload("res://scripts/tree_renderer.gd")
const GrassTufts := preload("res://scripts/grass_tufts.gd")
const SkyClouds := preload("res://scripts/sky_clouds.gd")
const ThemeRenderParams := preload("res://scripts/theme_render_params.gd")
const QualityPresets := preload("res://scripts/quality_presets.gd")
const AmbienceModel := preload("res://scripts/ambience_model.gd")

const NEIGH_PERIOD_S := 0.5

var wind = WindModel.new()
var wind_view = WindViewModel.new()
var enabled := true
var preset := "low"
var living: Dictionary = {}
var grass: Node3D = null
var sky_material: Material = null
var terrain_material: Material = null
var sound_player = null
var osm_streamer = null
var neigh: Dictionary = {}
var neigh_updates := 0               # voisinages recalculés (tests)
var last_wind: Dictionary = {}
var rain := 0.0                      # pluie de la météo (P8), posée par living_decor.gd (P17)
var _neigh_at := -INF
var _shapes_version := -1
var _shapes: Dictionary = {"forests": [], "buildings": [], "waters": []}
var _route = null


func configure(preset_name: String, living_enabled: bool, theme: Dictionary, environment: Environment = null,
		p_sound_player = null, p_osm_streamer = null, tree_renderer = null) -> void:
	preset = preset_name
	enabled = living_enabled
	living = QualityPresets.living(preset, enabled)
	sound_player = p_sound_player
	osm_streamer = p_osm_streamer
	wind.reset()
	var theme_wind: Variant = theme.get("wind", {})
	wind.set_theme_wind(theme_wind if enabled and typeof(theme_wind) == TYPE_DICTIONARY else {})
	if tree_renderer != null:
		tree_renderer.set_preset(preset, enabled)
	if environment != null and environment.sky != null:
		var mat := SkyClouds.build_material(ThemeRenderParams.cloud_params(theme), str(living.get("clouds", "off")),
			environment.sky.sky_material)
		environment.sky.sky_material = mat
		sky_material = mat
	if sound_player != null:
		sound_player.ambience.set_theme(theme)
	if grass == null:
		grass = GrassTufts.new()
		grass.name = "GrassTufts"
		add_child(grass)
	if _route != null:
		set_route(_route)


func set_route(route, road_width_m: float = 6.0) -> void:
	_route = route
	if grass != null:
		grass.configure(int(living.get("grass_tufts", 0)) if enabled else 0, route, road_width_m)
		grass.exclusions = _exclusions()
	_neigh_at = -INF


func on_state(state: Dictionary, now_s: float) -> void:
	wind.on_state(state, now_s)


func wind_hud(state: Dictionary, heading_deg: float, now_s: float) -> Dictionary:
	return wind_view.view(state, heading_deg, now_s)


func step(now_s: float, dt_s: float, cam_pos: Vector3, cam_s: float, rider_v: float, heading_deg: float,
		alt_m: float = 0.0, paused: bool = false) -> Dictionary:
	last_wind = wind.evaluate(now_s)
	if not enabled:
		return last_wind
	_refresh_shapes()
	TreeRenderer.apply_wind(last_wind)
	if grass != null:
		grass.set_apparent_wind(wind.apparent(rider_v, heading_deg))
		grass.update(cam_s)
	SkyClouds.update(sky_material, last_wind, dt_s)
	if terrain_material is ShaderMaterial:
		var shadow := SkyClouds.terrain_shadow_params(sky_material, str(living.get("clouds", "off")))
		for key in shadow:
			(terrain_material as ShaderMaterial).set_shader_parameter(key, shadow[key])
	if sound_player != null:
		if now_s - _neigh_at >= NEIGH_PERIOD_S:
			_neigh_at = now_s
			neigh = describe_near(cam_pos)
		neigh["alt_m"] = alt_m
		neigh["wind_strength"] = float(last_wind.get("strength", 0.0))
		neigh["paused"] = paused
		neigh["rain"] = rain
		sound_player.update_ambience(neigh, now_s)
		sound_player.update_bells(NAN, now_s)
	return last_wind


## Voisinage sonore autour de `p` : seuls les contours dont le rectangle touche le cercle d'écoute.
func describe_near(p: Vector3) -> Dictionary:
	_refresh_shapes()
	neigh_updates += 1
	var r := AmbienceModel.RADIUS_M
	var q := Vector2(p.x, p.z)
	var area := Rect2(q - Vector2(r, r), Vector2(2.0 * r, 2.0 * r))
	var forests := []
	for f in _shapes["forests"]:
		if (f["rect"] as Rect2).intersects(area, true):
			forests.append(f["points"])
	var buildings := []
	for b in _shapes["buildings"]:
		if (b["rect"] as Rect2).intersects(area, true):
			buildings.append(b["points"])
	var waters := []
	for w in _shapes["waters"]:
		# Eau : gain jusqu'à 100 m, au-delà la plus proche ne compte plus
		if (w["rect"] as Rect2).grow(100.0).has_point(q):
			waters.append(w)
	return AmbienceModel.describe(q, forests, buildings, waters)


func _refresh_shapes() -> void:
	if osm_streamer == null or not osm_streamer.has_method("layer_shapes"):
		return
	if int(osm_streamer.shapes_version) == _shapes_version:
		return
	_shapes_version = int(osm_streamer.shapes_version)
	_shapes = osm_streamer.layer_shapes()
	if grass != null:
		grass.exclusions = _exclusions()


## Bâtiments et plans d'eau : pas de touffe d'herbe dedans.
func _exclusions() -> Array:
	var out := []
	for b in _shapes["buildings"]:
		out.append(b["points"])
	for w in _shapes["waters"]:
		if bool(w.get("area", false)):
			out.append(w["points"])
	return out
