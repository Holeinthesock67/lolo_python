extends Node

## Ciel, brouillard et soleil de la scène principale (lot U17, suite de la série U) : seul endroit qui pose
## le brouillard de profondeur, la couleur de l'horizon et le soleil (direction, teinte, force).
## - Parcours sans biome (thème 1.x ou couche `biome` absente, sans `--biome=`) : ciel et brouillard du
##   thème (`ThemeRenderParams.sky_params`), comme avant la série U ;
## - avec biomes : atmosphère du biome sous la caméra (`atmosphere_model.gd`, lot U10), recalculée
##   toutes les PERIOD_S et posée seulement quand elle change ; brume de chaleur à l'écran
##   (`shaders/heat_haze.gdshader`), bande recalée sur l'horizon à chaque image.
## Après chaque brouillard posé, `living_decor.set_fog_base` : la brume de la météo (P17) s'y ajoute.
## Jour et nuit (lot P19, réglage « Jour et nuit ») : `set_cycle(light)` avec la sortie de
## `DaylightModel.evaluate` ; actif, le soleil suit l'heure (la lune le remplace la nuit, quand elle éclaire plus
## que lui), lumière, horizon et brouillard prennent les multiplicateurs de l'heure, la lumière ambiante descend
## vers la lumière minimale de la nuit, et le ciel s'éteint avec ses étoiles (ciel physique : étoiles en quatre
## niveaux ; ciel nuageux de P6 : `stars` et couleurs de `sky_clouds.gdshader`). Inactif : rendu d'aujourd'hui.
## Pas de class_name : charger par preload("res://scripts/atmosphere_view.gd").

const AtmosphereModel := preload("res://scripts/atmosphere_model.gd")
const RenderQuality := preload("res://scripts/render_quality.gd")
const ThemeRenderParams := preload("res://scripts/theme_render_params.gd")
const SkyClouds := preload("res://scripts/sky_clouds.gd")
const HeatHazeShader := preload("res://shaders/heat_haze.gdshader")

const PERIOD_S := 0.25
const FOG_EPS := 0.002       # écart de fog_end_factor qui justifie de reposer le brouillard
const COLOR_EPS := 0.002     # écart de couleur (par composante)
const HEAT_EPS := 0.01
const HORIZON_AHEAD_M := 5000.0
const NIGHT_AMBIENT_GAIN := 3.0   # lumière ambiante de la nuit (route lisible) : couleur × énergie de daylight_model × gain
const STAR_LEVELS := 4
const STAR_COUNT := 2200

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
var cycle := {}              # sortie de DaylightModel.evaluate (lot P19) ; vide ou inactive : soleil fixe
var _ambient_base := {}      # lumière ambiante de la scène avant le jour et la nuit
var fire_level := 0.0        # paysage en feu autour de la caméra (volcano_fx.gd), 0 à 1
var fire_color := Color("#ff6a20")
const FIRE_HORIZON := 0.55   # part de la lueur dans la brume de l'horizon quand tout brûle
const FIRE_LIGHT := 0.15     # part de la lueur dans la lumière du soleil
const FIRE_SKY := 0.7        # part de la lueur dans l'horizon du ciel (le haut du ciel s'assombrit de cendres)
const ASH_TOP := Color(0.55, 0.38, 0.32)
const SMOKE_CLOUD := Color(0.5, 0.42, 0.4)
static var _star_textures := []


func setup(env: Environment, sun_light: DirectionalLight3D) -> void:
	environment = env
	sun = sun_light
	if sun != null:
		_sun_energy = sun.light_energy
	if env != null:
		_ambient_base = {"contribution": env.ambient_light_sky_contribution, "color": env.ambient_light_color,
			"energy": env.ambient_light_energy, "source": env.ambient_light_source}
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
		_cycle_daylight()
	_at = -INF
	_apply(_params_at(0.0, {}))


## Jour et nuit (lot P19) : lumière de l'heure, posée tout de suite ; {} : retour au soleil fixe.
func set_cycle(light: Dictionary) -> void:
	cycle = light
	_cycle_daylight()
	_at = -INF
	_apply(_params_at(float(current.get("s", 0.0)), {}))


func cycle_active() -> bool:
	return bool(cycle.get("active", false))


## Heure et hauteur du soleil données au modèle d'atmosphère (brume de chaleur l'après-midi, soleil polaire).
func _cycle_daylight() -> void:
	if cycle_active():
		daylight["solar_hour"] = float(cycle["solar_hour"])
		daylight["sun_elevation_deg"] = float(cycle["sun_elevation_deg"])
	elif not _theme.is_empty():
		var lat := float(daylight.get("latitude_deg", NAN))
		daylight = AtmosphereModel.daylight_from_theme(_theme, lat)


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
	if cycle_active():
		_with_cycle(p)
	_with_fire(p)
	p["s"] = s
	return p


## Lueur d'un paysage en feu (démo « Volcan en flammes ») : brume rougie et lumière orangée, après l'heure.
func set_fire(level: float, color: Color) -> void:
	fire_level = clampf(level, 0.0, 1.0)
	fire_color = color


func _with_fire(p: Dictionary) -> void:
	if fire_level <= 0.0:
		return
	p["horizon_color"] = (p["horizon_color"] as Color).lerp(fire_color * 0.8, FIRE_HORIZON * fire_level)
	p["light_tint"] = (p["light_tint"] as Color).lerp(fire_color.lightened(0.4), FIRE_LIGHT * fire_level)
	p["fire"] = fire_level


## Multiplicateurs du ciel (haut, horizon, nuages) : ceux de l'heure, puis la lueur et la cendre du feu.
func _sky_mults(p: Dictionary) -> Array:
	var on := p.has("ambient_energy")
	var top: Color = (p["sky_top"] as Color) if on else Color.WHITE
	var hz: Color = (p["sky_horizon"] as Color) if on else Color.WHITE
	var cloud := hz
	var f := float(p.get("fire", 0.0))
	if f > 0.0:
		top = top.lerp(top * ASH_TOP, 0.6 * f)
		hz = hz.lerp(hz * fire_color * 1.5, FIRE_SKY * f)
		cloud = cloud.lerp(cloud * SMOKE_CLOUD, 0.7 * f)
	return [top, hz, cloud]


## Multiplicateurs de l'heure (DaylightModel.light) sur les paramètres du biome ou du thème.
func _with_cycle(p: Dictionary) -> void:
	var moon := float(cycle["moon_energy"]) > float(cycle["sun_energy"])
	p["sun_direction"] = cycle["moon_direction"] if moon else cycle["sun_direction"]
	p["light_tint"] = (p["light_tint"] as Color) * ((cycle["moon_color"] if moon else cycle["sun_color"]) as Color)
	p["light_energy_factor"] = float(p["light_energy_factor"]) * float(cycle["moon_energy"] if moon else cycle["sun_energy"])
	p["horizon_color"] = (p["horizon_color"] as Color) * (cycle["fog_color"] as Color)
	p["ambient_color"] = cycle["ambient_color"]
	p["ambient_energy"] = float(cycle["ambient_energy"])
	p["sky_top"] = cycle["sky_top"]
	p["sky_horizon"] = cycle["sky_horizon"]
	p["stars"] = float(cycle["stars"])


## Une fois par image en roulant, après le décor vivant (météo évaluée `weather_eval`).
func step(now_s: float, s_route: float, camera: Camera3D, weather_eval: Dictionary) -> void:
	if atmosphere == null and not cycle_active():
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
	for k in ["light_energy_factor", "ambient_energy", "stars", "fire"]:
		if absf(float(a.get(k, 1.0)) - float(b.get(k, 1.0))) > COLOR_EPS:
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
	_apply_sky(p)
	if _haze_rect != null:
		var heat := float(p["heat_haze"])
		_haze_rect.visible = heat > 0.0
		(_haze_rect.material as ShaderMaterial).set_shader_parameter("strength", heat)


## Lumière ambiante et ciel de l'heure (lot P19) ; sans jour et nuit, valeurs de la scène remises.
func _apply_sky(p: Dictionary) -> void:
	if environment == null:
		return
	var on := p.has("ambient_energy")
	if not _ambient_base.is_empty():
		if on:
			# Le ciel éclaire la scène autant qu'il est clair ; le reste vient de la lumière minimale de la nuit
			# Source « fond » : la part du ciel (ambient_light_sky_contribution) n'agit qu'avec elle ; la source
			# « ciel » de la scène ignorerait la lumière minimale de la nuit (route noire sous un ciel noir).
			environment.ambient_light_source = Environment.AMBIENT_SOURCE_BG
			var sky_lum := clampf((p["sky_top"] as Color).get_luminance(), 0.0, 1.0)
			environment.ambient_light_sky_contribution = float(_ambient_base["contribution"]) * sky_lum
			environment.ambient_light_color = (p["ambient_color"] as Color) * clampf(float(p["ambient_energy"]) * NIGHT_AMBIENT_GAIN, 0.0, 1.0)
		else:
			environment.ambient_light_source = int(_ambient_base["source"]) as Environment.AmbientSource
			environment.ambient_light_sky_contribution = float(_ambient_base["contribution"])
			environment.ambient_light_color = _ambient_base["color"]
	if environment.sky == null:
		return
	var mat := environment.sky.sky_material
	var stars := float(p.get("stars", 0.0)) if on else 0.0
	if mat is PhysicalSkyMaterial:
		(mat as PhysicalSkyMaterial).night_sky = star_texture(stars)
	elif SkyClouds.is_cloud_material(mat):
		# Ciel à nuages : couleurs du ciel de base (celles de sky_clouds.gd) multipliées par celles de l'heure.
		# (get_shader_parameter rend null pour un paramètre resté à sa valeur par défaut : test sur le shader.)
		var sm := mat as ShaderMaterial
		var mults := _sky_mults(p)
		sm.set_shader_parameter("sky_top_color", SkyClouds.SKY_TOP * (mults[0] as Color))
		if not sm.has_meta("base_horizon"):
			var h: Variant = sm.get_shader_parameter("sky_horizon_color")
			sm.set_meta("base_horizon", h if h != null else SkyClouds.SKY_HORIZON)
		sm.set_shader_parameter("sky_horizon_color", (sm.get_meta("base_horizon") as Color) * (mults[1] as Color))
		if not sm.has_meta("base_cloud"):
			var c: Variant = sm.get_shader_parameter("cloud_color")
			sm.set_meta("base_cloud", c if c != null else Color(0.957, 0.969, 0.984))
		# Nuages éclairés comme l'horizon : orangés au coucher, sombres la nuit
		sm.set_shader_parameter("cloud_color", (sm.get_meta("base_cloud") as Color) * (mults[2] as Color))
		sm.set_shader_parameter("stars", stars)
	elif mat is ProceduralSkyMaterial:   # ciel sans nuages (et moteur Compatibility) : couleurs seulement, sans étoiles
		var pm := mat as ProceduralSkyMaterial
		var mults := _sky_mults(p)
		pm.sky_top_color = SkyClouds.SKY_TOP * (mults[0] as Color)
		pm.sky_horizon_color = SkyClouds.SKY_HORIZON * (mults[1] as Color)


## Ciel étoilé du ciel physique, en STAR_LEVELS niveaux de clarté (le ciel physique l'ajoute sans pondération) :
## null de jour, puis de plus en plus d'étoiles visibles quand la nuit tombe.
static func star_texture(stars: float) -> Texture2D:
	var level := clampi(int(round(stars * STAR_LEVELS)), 0, STAR_LEVELS)
	if level == 0:
		return null
	if _star_textures.is_empty():
		var rng := RandomNumberGenerator.new()
		rng.seed = 20261108
		var pts := []
		for k in STAR_COUNT:
			pts.append([rng.randi_range(0, 2047), rng.randi_range(0, 511), rng.randf_range(0.25, 1.0)])
		for lv in range(1, STAR_LEVELS + 1):
			var img := Image.create(2048, 1024, false, Image.FORMAT_RGB8)
			for s in pts:
				# Points de 2 × 2 pixels : un seul pixel se perd au rééchantillonnage du ciel (lot P35)
				var b := minf(1.0, float(s[2]) * float(lv) / STAR_LEVELS * 1.6)
				for dx in range(2):
					for dy in range(2):
						img.set_pixel((int(s[0]) + dx) % 2048, mini(int(s[1]) + dy, 1023), Color(b, b, minf(1.0, b * 1.05)))
			_star_textures.append(ImageTexture.create_from_image(img))
	return _star_textures[level - 1]


## État pour les tests et le journal de test (`test_info` de main.gd).
func test_info() -> Dictionary:
	return {
		"biomes": atmosphere != null,
		"fog_end_factor": float(current.get("fog_end_factor", 1.0)),
		"heat_haze": float(current.get("heat_haze", 0.0)),
		"humidity": float(current.get("humidity", 0.0)),
		"haze_visible": _haze_rect != null and _haze_rect.visible,
		"updates": updates,
		"cycle": cycle_active(),
		"sun_energy": sun.light_energy if sun != null else 0.0,
		"stars": float(current.get("stars", 0.0)),
	}
