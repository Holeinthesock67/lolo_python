extends SceneTree

## Tests unitaires sans écran des particules de pluie et de neige `weather_particles.gd` (Lot P8).
## Lancement : godot --headless --path engine --script res://tests/unit/test_weather_particles.gd

const WeatherParticles := preload("res://scripts/weather_particles.gd")
const WeatherModel := preload("res://scripts/weather_model.gd")
const QualityPresets := preload("res://scripts/quality_presets.gd")
const PerfBudget := preload("res://tests/perf_budget.gd")

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _eval(kind: String, intensity: float, wind: Dictionary = {"dir": Vector3.ZERO, "strength": 0.0}) -> Dictionary:
	var w := WeatherModel.from_theme({"weather": {"kind": kind, "intensity": intensity}})
	return WeatherModel.evaluate(w, 500.0, 500.0, wind)


# Critère 4 : budget, nœud inactif à budget nul, boîte centrée sur la caméra
func _test_budget_and_follow() -> void:
	var zero = WeatherParticles.new()
	root.add_child(zero)
	zero.configure(0)
	zero.update(Vector3.ZERO, _eval("rain", 1.0))
	_check(zero.get_child_count() == 0 and not zero.is_active(), "budget nul : aucun enfant, nœud inactif")
	for preset in ["low", "medium", "high"]:
		var budget: int = QualityPresets.living(preset)["weather_particles"]
		var p = WeatherParticles.new()
		root.add_child(p)
		p.configure(budget)
		var worst := 0
		for intensity in [0.2, 0.5, 1.0]:
			for kind in ["rain", "snow"]:
				p.update(Vector3.ZERO, _eval(kind, intensity))
				worst = maxi(worst, p.get_active_count())
		_check(worst <= budget and worst > 0, "%s : au plus %d particules (budget %d)" % [preset, worst, budget])
		p.queue_free()
	var f = WeatherParticles.new()
	root.add_child(f)
	f.configure(600)
	var cam := Vector3(10.0, 300.0, -5.0)
	var ok := true
	for i in range(100):
		cam += Vector3(3.0, 0.1, -4.0)   # 500 m en 100 images
		f.update(cam, _eval("rain", 0.5))
		ok = ok and f.global_position.distance_to(cam) <= 1.0
	_check(ok and cam.distance_to(Vector3(10.0, 300.0, -5.0)) >= 500.0, "boîte centrée sur la caméra à 1 m près après 500 m")
	var rain: GPUParticles3D = f.get_emitter("rain")
	var mat := rain.process_material as ParticleProcessMaterial
	_check(not rain.local_coords and is_equal_approx(mat.emission_box_extents.x * 2.0, WeatherParticles.BOX_M),
		"particules dans le repère du monde, boîte de 40 m")
	_check(rain.emitting and not f.get_emitter("snow").emitting, "pluie seule : la neige n'émet pas")
	f.update(cam, _eval("clear", 0.0))
	_check(not f.is_active() and f.get_active_count() == 0, "temps clair : rien n'émet")
	f.queue_free()
	zero.queue_free()


# Critère 5 : vent du nord fort, particules poussées vers le sud (+z dans le repère de Godot)
func _test_wind() -> void:
	var north := {"dir": Vector3(0.0, 0.0, 1.0), "strength": 1.0}   # vient du nord, souffle vers le sud
	for kind in ["rain", "snow"]:
		var v := WeatherParticles.particle_velocity(kind, north)
		_check(v.z > 1.0 and absf(v.x) < 1e-4 and v.y < 0.0, "%s, vent du nord : vitesse latérale vers le sud (%.1f m/s)" % [kind, v.z])
	var p = WeatherParticles.new()
	root.add_child(p)
	p.configure(600)
	p.update(Vector3.ZERO, _eval("snow", 0.6, north))
	var mat := p.get_emitter("snow").process_material as ParticleProcessMaterial
	_check(mat.direction.z > 0.5, "neige : direction d'émission vers le sud")
	p.queue_free()


# Critère 6 : thème sans weather, aucun nœud actif
func _test_no_weather() -> void:
	var p = WeatherParticles.new()
	root.add_child(p)
	p.configure(QualityPresets.living("high")["weather_particles"])
	var e := WeatherModel.evaluate(WeatherModel.from_theme({"version": "1.0"}), 500.0, 500.0, {})
	p.update(Vector3.ZERO, e)
	var none_on := true
	for c in p.get_children():
		none_on = none_on and not (c as GPUParticles3D).emitting and not (c as GPUParticles3D).visible
	_check(none_on and not p.is_active(), "thème sans weather : aucun effet actif")
	var t0 := Time.get_ticks_usec()
	for i in range(5000):
		p.update(Vector3(i, 0, 0), _eval("rain", 0.5))
	var ms := (Time.get_ticks_usec() - t0) / 1000.0 / 5000.0
	_check(PerfBudget.check("weather_particles_frame", ms), "coût de update : %.4f ms par image" % ms)
	p.queue_free()


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	_test_budget_and_follow()
	_test_wind()
	_test_no_weather()
	print("test_weather_particles : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
