extends SceneTree

## Tests unitaires sans écran du ciel, du brouillard et du soleil de la scène (`atmosphere_view.gd`, lot U17).
## Lancement : godot --headless --path engine --script res://tests/unit/test_atmosphere_view.gd

const AtmosphereView := preload("res://scripts/atmosphere_view.gd")
const BiomeModel := preload("res://scripts/biome_model.gd")
const ThemeLoader := preload("res://scripts/theme_loader.gd")
const ThemeRenderParams := preload("res://scripts/theme_render_params.gd")
const RenderQuality := preload("res://scripts/render_quality.gd")
const QualityPresets := preload("res://scripts/quality_presets.gd")


## Route droite vers le nord, 5 km, à 45° de latitude.
class StraightRoute:
	var n := 501
	var lat := PackedFloat64Array([45.0])
	func sample_point(s: float) -> Vector3:
		return Vector3(s, 0.0, 0.0)
	func wrap_s(s: float) -> float:
		return s


## Prairie avant x = 0, désert de sable après 1 km (passage linéaire), toujours actif.
class RampModel extends "res://scripts/biome_model.gd":
	func active() -> bool:
		return true
	func weights_at(x: float, _z: float) -> Dictionary:
		var t := clampf(x / 1000.0, 0.0, 1.0)
		if t <= 0.0:
			return {"temperate_grassland": 1.0}
		if t >= 1.0:
			return {"sand_desert": 1.0}
		return {"temperate_grassland": 1.0 - t, "sand_desert": t}


var _failures := 0
var _checked := 0
var _theme: Dictionary


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _view(quality: String) -> Array:
	var env := Environment.new()
	var sun := DirectionalLight3D.new()
	root.add_child(sun)
	var view = AtmosphereView.new()
	root.add_child(view)
	view.quality = quality
	view.setup(env, sun)
	return [view, env, sun]


func _forced(biome: String):
	var m = BiomeModel.new(_theme, null)
	m.set_forced(biome)
	return m


func _test_without_biomes() -> void:
	var v: Array = _view("medium")
	var view = v[0]
	var env: Environment = v[1]
	var sun: DirectionalLight3D = v[2]
	view.set_world(_theme, BiomeModel.new(_theme, null), StraightRoute.new(), true)
	var ref := Environment.new()
	RenderQuality.apply_fog(ref, "medium", true)
	_check(not view.test_info()["biomes"], "parcours sans couche biome : ciel du thème")
	_check(env.fog_light_color == RenderQuality.FOG_COLOR and is_equal_approx(env.fog_depth_end, ref.fog_depth_end)
		and is_equal_approx(env.fog_depth_begin, ref.fog_depth_begin), "sans biome : brouillard d'avant la série U")
	var sky := ThemeRenderParams.sky_params(_theme)
	_check(sun.basis.z.is_equal_approx(sky["sun_direction"]) and sun.light_color == Color.WHITE and sun.light_energy == 1.0,
		"sans biome : soleil du thème, blanc, force 1")
	_check(not view.test_info()["haze_visible"], "sans biome : pas de brume de chaleur")
	view.step(10.0, 500.0, null, {})
	_check(view.test_info()["updates"] == 1, "sans biome : rien n'est reposé en roulant")


func _test_forced_biomes() -> void:
	var v: Array = _view("high")
	var view = v[0]
	var env: Environment = v[1]
	var sun: DirectionalLight3D = v[2]
	view.set_world(_theme, _forced("jungle"), StraightRoute.new(), true)
	_check(is_equal_approx(env.fog_depth_end, QualityPresets.fog_end_m("high") * 0.6),
		"jungle : brouillard à 60 %% (%.0f m)" % env.fog_depth_end)
	_check(is_equal_approx(sun.light_energy, 0.75) and sun.light_color != Color.WHITE, "jungle : soleil plus faible et teinté")
	view.set_world(_theme, _forced("sand_desert"), StraightRoute.new(), true)
	_check(view.test_info()["haze_visible"], "désert en high : brume de chaleur affichée")
	view.set_quality("low")
	_check(not view.test_info()["haze_visible"], "désert passé en low : brume de chaleur cachée")
	_check(is_equal_approx(env.fog_depth_end, QualityPresets.fog_end_m("low")), "passage en low : brouillard du préréglage low")
	view.set_quality("medium")
	view.set_world(_theme, _forced("temperate_grassland"), StraightRoute.new(), true)
	var ref := Environment.new()
	var m = _forced("temperate_grassland")
	var p: Dictionary = m.params("temperate_grassland")["sky"]
	RenderQuality.apply_fog(ref, "medium", true, RenderQuality.FOG_COLOR.lerp(RenderQuality.HAZE_COLOR, float(p["haze"]) * 0.6))
	_check(env.fog_light_color.is_equal_approx(ref.fog_light_color) and is_equal_approx(env.fog_depth_end, ref.fog_depth_end)
		and sun.light_energy == 1.0, "prairie forcée : brouillard et soleil de la première partie de U17")


func _test_riding() -> void:
	var v: Array = _view("medium")
	var view = v[0]
	var env: Environment = v[1]
	view.set_world(_theme, RampModel.new(_theme, null), StraightRoute.new(), true)
	view.step(0.0, -1000.0, null, {})
	var start_updates: int = view.test_info()["updates"]
	for i in range(1, 8):
		view.step(i * 0.3, -1000.0, null, {})
	_check(view.test_info()["updates"] == start_updates, "à l'arrêt en prairie : brouillard posé une seule fois")
	_check(not view.test_info()["haze_visible"], "prairie : pas de brume de chaleur")
	var t := 3.0
	var s := -1000.0
	var before := env.fog_light_color
	while s < 2000.0:
		view.step(t, s, null, {})
		t += 0.3
		s += 3.0
	_check(view.test_info()["haze_visible"] and view.test_info()["heat_haze"] > 0.9, "arrivée au désert : brume de chaleur")
	_check(not env.fog_light_color.is_equal_approx(before), "arrivée au désert : horizon du désert")
	var updates: int = view.test_info()["updates"] - start_updates
	_check(updates > 5 and updates < 400, "passage de 3 km : %d brouillards posés (seulement quand ça change)" % updates)
	view.step(t + 1.0, 2000.0, null, {"rain": 0.8, "snow": 0.0, "fog_boost": 0.0})
	_check(not view.test_info()["haze_visible"], "pluie au désert : la brume de chaleur disparaît")


func _init() -> void:
	_theme = ThemeLoader.load_theme(ThemeLoader.DEFAULT_THEME_DIR)["theme"]
	_test_without_biomes()
	_test_forced_biomes()
	_test_riding()
	print("test_atmosphere_view : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
