extends SceneTree

## Tests unitaires sans écran du ciel nuageux `sky_clouds.gd` (Lot P6).
## Lancement : godot --headless --path engine --script res://tests/unit/test_sky_clouds.gd

const PerfBudget := preload("res://tests/perf_budget.gd")
const SkyClouds := preload("res://scripts/sky_clouds.gd")
const ThemeRenderParams := preload("res://scripts/theme_render_params.gd")
const QualityPresets := preload("res://scripts/quality_presets.gd")
const TerrainShader := preload("res://shaders/terrain.gdshader")

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _params(coverage: float) -> Dictionary:
	var p := ThemeRenderParams.cloud_params({})
	p["coverage"] = coverage
	return p


# Critère 4 : clouds = "off" (ou couverture nulle) rend le matériau actuel, sans le changer
func _test_off_keeps_current() -> void:
	var current := PhysicalSkyMaterial.new()
	_check(SkyClouds.build_material(_params(0.5), "off", current) == current, "off : matériau actuel rendu tel quel")
	_check(SkyClouds.build_material(_params(0.0), "layered", current) == current, "couverture 0 : matériau actuel")
	var living_off: String = QualityPresets.living("high", false)["clouds"]
	_check(SkyClouds.build_material(_params(0.5), living_off, current) == current, "décor vivant coupé : matériau actuel")
	var fallback = SkyClouds.build_material(_params(0.5), "off")
	_check(fallback is ProceduralSkyMaterial and fallback.sky_top_color == SkyClouds.SKY_TOP,
		"off sans matériau : ciel procédural actuel (Compatibility)")


func _test_presets() -> void:
	var low = SkyClouds.build_material(_params(0.5), QualityPresets.living("low")["clouds"])
	var high = SkyClouds.build_material(_params(0.5), QualityPresets.living("high")["clouds"])
	_check(SkyClouds.is_cloud_material(low) and not bool(low.get_shader_parameter("layered")),
		"low : une couche de nuages")
	_check(SkyClouds.is_cloud_material(high) and bool(high.get_shader_parameter("layered")),
		"high : deux couches")
	_check(is_equal_approx(float(low.get_shader_parameter("coverage")), 0.5)
		and is_equal_approx(float(low.get_shader_parameter("altitude_m")), 2000.0), "couverture et altitude transmises")
	var fog := Color(0.8, 0.7, 0.6)
	var tinted = SkyClouds.build_material(_params(0.5), "flat", null, fog)
	_check(tinted.get_shader_parameter("sky_horizon_color") == fog
		and low.get_shader_parameter("sky_horizon_color") == SkyClouds.SKY_HORIZON,
		"horizon du ciel nuageux = couleur du brouillard passée (par défaut, celle du ciel actuel)")
	_check(not SkyClouds.terrain_shadow_params(low, "flat")["cloud_shadow_enabled"],
		"ombre des nuages coupée en low et medium")
	var sh := SkyClouds.terrain_shadow_params(high, "layered")
	_check(sh["cloud_shadow_enabled"] and is_equal_approx(sh["cloud_shadow_coverage"], 0.5),
		"ombre des nuages en high, même couverture")
	var defaults := {}
	for u in TerrainShader.get_shader_uniform_list():
		defaults[u["name"]] = true
	var mat := ShaderMaterial.new()
	mat.shader = TerrainShader
	_check(defaults.has("cloud_shadow_enabled") and mat.get_shader_parameter("cloud_shadow_enabled") == null,
		"terrain.gdshader : ombre derrière un uniform bool faux par défaut")


# Défilement : vers où souffle le vent, proportionnel à la force et au facteur de vitesse
func _test_update() -> void:
	var p := _params(0.5)
	p["speed_factor"] = 2.0
	var m = SkyClouds.build_material(p, "flat")
	var wind := {"dir": Vector3(1, 0, 0), "strength": 0.5, "gust": 0.0, "phase": 0.0}
	SkyClouds.update(m, wind, 2.0)
	var off: Vector2 = m.get_shader_parameter("cloud_offset")
	var expected := 0.5 * (60.0 / 3.6) * 2.0 * 2.0
	_check(is_equal_approx(off.x, -expected) and is_zero_approx(off.y),
		"2 s de vent d'ouest : décalage de %.1f m (attendu %.1f m)" % [-off.x, expected])
	SkyClouds.update(m, {"dir": Vector3.ZERO, "strength": 0.0}, 5.0)
	_check(m.get_shader_parameter("cloud_offset") == off, "vent nul : nuages immobiles")
	var current := ProceduralSkyMaterial.new()
	SkyClouds.update(current, wind, 1.0)   # sans effet, sans erreur
	_check(true, "update sur un autre matériau : sans effet")
	var cost := PerfBudget.frame_cost(func(): SkyClouds.update(m, wind), 2000, 50)
	_check(PerfBudget.check("sky_clouds_frame", cost["median_ms"]), "coût de update : %.4f ms par image" % cost["median_ms"])


func _init() -> void:
	_test_off_keeps_current()
	_test_presets()
	_test_update()
	print("test_sky_clouds : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
