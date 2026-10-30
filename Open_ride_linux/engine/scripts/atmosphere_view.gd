extends Node

## Ciel, brouillard et soleil de la scène principale (lot U17, suite de la série U) : seul endroit qui pose
## le brouillard de profondeur, la couleur de l'horizon et le soleil (direction, teinte, force).
## - Parcours sans biome (thème 1.x ou couche `biome` absente, sans `--biome=`) : ciel et brouillard du
##   thème (`ThemeRenderParams.sky_params`), comme avant la série U ;
## - avec biomes : atmosphère du biome sous la caméra (`atmosphere_model.gd`, lot U10), recalculée
##   toutes les PERIOD_S et posée seulement quand elle change ; brume de chaleur à l'écran
##   (`shaders/heat_haze.gdshader`), bande recalée sur l'horizon à chaque image.
## Après chaque brouillard posé, `living_decor.set_fog_base` : la brume de la météo (P17) s'y ajoute.
## Pas de class_name : charger par preload("res://scripts/atmosphere_view.gd").

const AtmosphereModel := preload("res://scripts/atmosphere_model.gd")
const RenderQuality := preload("res://scripts/render_quality.gd")
const ThemeRenderParams := preload("res://scripts/theme_render_params.gd")
const HeatHazeShader := preload("res://shaders/heat_haze.gdshader")

const PERIOD_S := 0.25
const FOG_EPS := 0.002       # écart de fog_end_factor qui justifie de reposer le brouillard
const COLOR_EPS := 0.002     # écart de couleur (par composante)
const HEAT_EPS := 0.01
const HORIZON_AHEAD_M := 5000.0

var environment: Environment
var sun: DirectionalLight3D
var living_decor = null
var quality := "low"
var has_terrain := false
var atmosphere = null        # AtmosphereModel, null sans biomes
var daylight := {}
var current := {}            # paramètres posés en dernier
var updates := 0             # brouillards posés (tests)
var _theme := {}
var _sun_energy := 1.0
var _at := -INF
var _haze_rect: ColorRect = null


func setup(env: Environment, sun_light: DirectionalLight3D) -> void:
	environment = env
	sun = sun_light
	if sun != null:
		_sun_energy = sun.light_energy
	var layer := CanvasLayer.new()
	layer.name = "HeatHazeLayer"
	layer.layer = -1        # sous le HUD et les menus
	_haze_rect = ColorRect.new()
	_haze_rect.name = "HeatHaze"
	_haze_rect.set_anchors_preset(Control.PRESET_FULL_RECT)
	_haze_rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var mat := ShaderMaterial.new()
	mat.shader = HeatHazeShader
	_haze_rect.material = mat
	_haze_rect.visible = false
	layer.add_child(_haze_rect)
	add_child(layer)


## Thème, modèle de biome et parcours chargés (changement de thème ou de parcours) : atmosphère du départ.
func set_world(theme: Dictionary, biome_model, route, terrain: bool) -> void:
	_theme = theme
	has_terrain = terrain
	atmosphere = null
	if biome_model != null and biome_model.active() and route != null and route.n > 0:
		atmosphere = AtmosphereModel.new(biome_model, func(s: float) -> Vector2:
			var p: Vector3 = route.sample_point(route.wrap_s(s))
			return Vector2(p.x, p.z))
		daylight = AtmosphereModel.daylight_from_theme(theme, route.lat[0] if route.lat.size() > 0 else NAN)
	_at = -INF
	_apply(_params_at(0.0, {}))


## Préréglage changé dans les réglages : brouillard du nouveau préréglage, brume de chaleur selon `heat_haze`.
func set_quality(name: String) -> void:
	quality = name
	_apply(_params_at(float(current.get("s", 0.0)), {}))


func _params_at(s: float, weather: Dictionary) -> Dictionary:
	var p: Dictionary
	if atmosphere != null:
		p = atmosphere.at(s, daylight, weather, quality)
	else:
		var sky := ThemeRenderParams.sky_params(_theme)
		p = {"fog_density": sky["fog_density"], "fog_end_factor": 1.0, "horizon_color": RenderQuality.FOG_COLOR,
			"light_tint": Color.WHITE, "light_energy_factor": 1.0, "heat_haze": 0.0, "sun_direction": sky["sun_direction"]}
	p["s"] = s
	return p


## Une fois par image en roulant, après le décor vivant (météo évaluée `weather_eval`).
func step(now_s: float, s_route: float, camera: Camera3D, weather_eval: Dictionary) -> void:
	if atmosphere == null:
		return
	if now_s - _at >= PERIOD_S:
		_at = now_s
		var p := _params_at(s_route, weather_eval)
		if _differs(p, current):
			_apply(p)
		else:
			current["s"] = s_route
	if _haze_rect.visible and camera != null:
		var ahead := -camera.global_transform.basis.z
		ahead.y = 0.0
		var y := -1.0
		if ahead.length_squared() > 1e-6:
			var far_pt := camera.global_position + ahead.normalized() * HORIZON_AHEAD_M
			if not camera.is_position_behind(far_pt):
				y = camera.unproject_position(far_pt).y / maxf(get_viewport().get_visible_rect().size.y, 1.0)
		(_haze_rect.material as ShaderMaterial).set_shader_parameter("horizon_y", y)


static func _differs(a: Dictionary, b: Dictionary) -> bool:
	if b.is_empty():
		return true
	if absf(float(a["fog_end_factor"]) - float(b["fog_end_factor"])) > FOG_EPS:
		return true
	if absf(float(a["heat_haze"]) - float(b["heat_haze"])) > HEAT_EPS:
		return true
	for k in ["horizon_color", "light_tint"]:
		var ca: Color = a[k]
		var cb: Color = b[k]
		if maxf(maxf(absf(ca.r - cb.r), absf(ca.g - cb.g)), absf(ca.b - cb.b)) > COLOR_EPS:
			return true
	return not (a["sun_direction"] as Vector3).is_equal_approx(b["sun_direction"])


func _apply(p: Dictionary) -> void:
	current = p
	updates += 1
	if environment != null:
		RenderQuality.apply_fog(environment, quality, has_terrain, p["horizon_color"], float(p["fog_density"]),
			float(p["fog_end_factor"]))
		if living_decor != null:
			living_decor.set_fog_base(environment)
	if sun != null:
		sun.basis = Basis.looking_at(-(p["sun_direction"] as Vector3), Vector3.UP)
		sun.light_color = p["light_tint"]
		sun.light_energy = _sun_energy * float(p["light_energy_factor"])
	if _haze_rect != null:
		var heat := float(p["heat_haze"])
		_haze_rect.visible = heat > 0.0
		(_haze_rect.material as ShaderMaterial).set_shader_parameter("strength", heat)


## État pour les tests et le journal de test (`test_info` de main.gd).
func test_info() -> Dictionary:
	return {
		"biomes": atmosphere != null,
		"fog_end_factor": float(current.get("fog_end_factor", 1.0)),
		"heat_haze": float(current.get("heat_haze", 0.0)),
		"humidity": float(current.get("humidity", 0.0)),
		"haze_visible": _haze_rect != null and _haze_rect.visible,
		"updates": updates,
	}
