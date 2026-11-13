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
## Sous l'eau (lot SM1, `underwater` d'atmosphere_model.gd, fond marin `reef`) : le brouillard noie aussi le ciel
## (fog_sky_affect de 0 à 1), la surface de la mer vue d'en dessous suit la caméra au niveau 0
## (shaders/sea_ceiling.gdshader) et des bulles montent autour d'elle ; tout est caché hors de l'eau.
## Pas de class_name : charger par preload("res://scripts/atmosphere_view.gd").

const AtmosphereModel := preload("res://scripts/atmosphere_model.gd")
const RenderQuality := preload("res://scripts/render_quality.gd")
const ThemeRenderParams := preload("res://scripts/theme_render_params.gd")
const SkyClouds := preload("res://scripts/sky_clouds.gd")
const HeatHazeShader := preload("res://shaders/heat_haze.gdshader")
const SeaCeilingShader := preload("res://shaders/sea_ceiling.gdshader")

const PERIOD_S := 0.25
const FOG_EPS := 0.002       # écart de fog_end_factor qui justifie de reposer le brouillard
const COLOR_EPS := 0.002     # écart de couleur (par composante)
const HEAT_EPS := 0.01
const HORIZON_AHEAD_M := 5000.0
const NIGHT_AMBIENT_GAIN := 3.0   # lumière ambiante de la nuit (route lisible) : couleur × énergie de daylight_model × gain
const STAR_LEVELS := 4
const STAR_COUNT := 2200
## Sous l'eau (lot SM1)
const UNDER_EPS := 0.01            # part du fond marin sous laquelle la surface et les bulles sont cachées
const SEA_LEVEL_Y := 0.0           # niveau de la mer du format (aires `sea`, lot U3)
const CEILING_SIZE_M := 1200.0     # carré de la surface, au-delà du brouillard de l'eau
const BUBBLES := 96
const BUBBLE_BOX_M := Vector3(18.0, 2.0, 18.0)   # demi-côtés de la boîte d'émission, sous la caméra
const BUBBLE_BELOW_M := 5.0

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
var _ceiling: MeshInstance3D = null    # surface vue d'en dessous (lot SM1)
var _bubbles: GPUParticles3D = null
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
	_make_underwater()


## Surface vue d'en dessous et bulles (lot SM1), cachées jusqu'à ce que la caméra passe sous l'eau.
func _make_underwater() -> void:
	_ceiling = MeshInstance3D.new()
	_ceiling.name = "SeaCeiling"
	var plane := PlaneMesh.new()
	plane.size = Vector2(CEILING_SIZE_M, CEILING_SIZE_M)
	_ceiling.mesh = plane
	var mat := ShaderMaterial.new()
	mat.shader = SeaCeilingShader
	_ceiling.material_override = mat
	_ceiling.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_ceiling.visible = false
	add_child(_ceiling)
	_bubbles = GPUParticles3D.new()
	_bubbles.name = "Bubbles"
	_bubbles.amount = BUBBLES
	_bubbles.lifetime = 9.0
	_bubbles.preprocess = 9.0
	_bubbles.local_coords = false
	_bubbles.visibility_aabb = AABB(-BUBBLE_BOX_M - Vector3(4.0, 4.0, 4.0), (BUBBLE_BOX_M + Vector3(4.0, 20.0, 4.0)) * 2.0)
	var pm := ParticleProcessMaterial.new()
	pm.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_BOX
	pm.emission_box_extents = BUBBLE_BOX_M
	pm.direction = Vector3.UP
	pm.spread = 8.0
	pm.initial_velocity_min = 0.8
	pm.initial_velocity_max = 1.6
	pm.gravity = Vector3(0.0, 0.25, 0.0)
	pm.scale_min = 0.5
	pm.scale_max = 1.4
	_bubbles.process_material = pm
	var quad := QuadMesh.new()
	quad.size = Vector2(0.07, 0.07)
	var qm := StandardMaterial3D.new()
	qm.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	qm.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	qm.billboard_mode = BaseMaterial3D.BILLBOARD_PARTICLES
	qm.albedo_color = Color(0.9, 0.98, 1.0, 0.55)
	quad.material = qm
	_bubbles.draw_pass_1 = quad
	_bubbles.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_bubbles.emitting = false
	_bubbles.visible = false
	add_child(_bubbles)


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
	p["s"] = s
	return p


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
	if _ceiling != null and _ceiling.visible and camera != null:
		var c := camera.global_position
		_ceiling.global_position = Vector3(c.x, SEA_LEVEL_Y, c.z)
		_bubbles.global_position = Vector3(c.x, minf(c.y - BUBBLE_BELOW_M, SEA_LEVEL_Y - BUBBLE_BOX_M.y), c.z)
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
	if absf(float(a.get("underwater", 0.0)) - float(b.get("underwater", 0.0))) > COLOR_EPS:
		return true
	for k in ["light_energy_factor", "ambient_energy", "stars"]:
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
		# Sous l'eau (lot SM1) : le ciel, le soleil et les nuages se perdent dans l'eau
		var u := float(p.get("underwater", 0.0))
		if u > 0.0:
			environment.fog_sky_affect = lerpf(RenderQuality.FOG_SKY_AFFECT, 1.0, u)
			environment.volumetric_fog_sky_affect = environment.fog_sky_affect
		if living_decor != null:
			living_decor.set_fog_base(environment)
	if sun != null:
		sun.basis = Basis.looking_at(-(p["sun_direction"] as Vector3), Vector3.UP)
		sun.light_color = p["light_tint"]
		sun.light_energy = _sun_energy * float(p["light_energy_factor"])
	_apply_sky(p)
	_apply_underwater(p)
	if _haze_rect != null:
		var heat := float(p["heat_haze"])
		_haze_rect.visible = heat > 0.0
		(_haze_rect.material as ShaderMaterial).set_shader_parameter("strength", heat)


## Surface et bulles (lot SM1) : visibles avec le fond marin sous la caméra, à sa part ; couleurs de l'eau.
func _apply_underwater(p: Dictionary) -> void:
	if _ceiling == null:
		return
	var u := float(p.get("underwater", 0.0))
	var on := u > UNDER_EPS
	_ceiling.visible = on
	_bubbles.visible = on
	_bubbles.emitting = on
	if on:
		var mat := _ceiling.material_override as ShaderMaterial
		var water: Color = p["horizon_color"]
		mat.set_shader_parameter("strength", u)
		mat.set_shader_parameter("deep_color", water)
		mat.set_shader_parameter("bright_color", water.lerp(Color(0.85, 0.98, 1.0), 0.75))


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
		sm.set_shader_parameter("sky_top_color", SkyClouds.SKY_TOP * ((p["sky_top"] as Color) if on else Color.WHITE))
		if not sm.has_meta("base_horizon"):
			var h: Variant = sm.get_shader_parameter("sky_horizon_color")
			sm.set_meta("base_horizon", h if h != null else SkyClouds.SKY_HORIZON)
		sm.set_shader_parameter("sky_horizon_color",
			(sm.get_meta("base_horizon") as Color) * ((p["sky_horizon"] as Color) if on else Color.WHITE))
		if not sm.has_meta("base_cloud"):
			var c: Variant = sm.get_shader_parameter("cloud_color")
			sm.set_meta("base_cloud", c if c != null else Color(0.957, 0.969, 0.984))
		# Nuages éclairés comme l'horizon : orangés au coucher, sombres la nuit
		sm.set_shader_parameter("cloud_color",
			(sm.get_meta("base_cloud") as Color) * ((p["sky_horizon"] as Color) if on else Color.WHITE))
		sm.set_shader_parameter("stars", stars)
	elif mat is ProceduralSkyMaterial:   # ciel sans nuages (et moteur Compatibility) : couleurs seulement, sans étoiles
		var pm := mat as ProceduralSkyMaterial
		pm.sky_top_color = SkyClouds.SKY_TOP * ((p["sky_top"] as Color) if on else Color.WHITE)
		pm.sky_horizon_color = SkyClouds.SKY_HORIZON * ((p["sky_horizon"] as Color) if on else Color.WHITE)


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
		"underwater": float(current.get("underwater", 0.0)),
		"sea_ceiling": _ceiling != null and _ceiling.visible,
	}
