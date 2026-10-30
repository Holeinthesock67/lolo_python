extends Node3D

## Pluie et neige autour de la caméra (Lot P8), nœud autonome. Pas de class_name : charger par
## preload("res://scripts/weather_particles.gd"). Branché par P17 dans main.gd.
##
## - Un seul GPUParticles3D par effet (pluie, neige), dans une boîte de `BOX_M` mètres centrée sur la
##   caméra : `update(camera_position, weather_eval)` déplace le nœud sur la caméra à chaque image.
##   Les particules vivent dans le repère du monde (`local_coords` faux) : elles ne sont pas « collées »
##   à l'écran quand la caméra avance.
## - Nombre de particules borné par `configure(budget)` (`living(preset).weather_particles`) ;
##   budget nul : aucun enfant, nœud inactif. L'intensité règle `amount_ratio`, sans relancer l'effet.
## - Vitesse des particules : chute + vent du modèle P4 (`wind_dir` vers où souffle le vent).
## - Maillages et matériaux dessinés par code, sans image externe.
## - Poussière (lot U22, option « gravel ») : `update_dust(rider_pos, back, speed_mps, surface)` fait lever
##   quelques grains derrière la roue sur `dirt` et `gravel`, par temps sec seulement (ni pluie ni neige au
##   dernier `update`), au-dessus de `DUST_MIN_MPS`. `dust_amount(budget)` grains (budget / `DUST_SHARE`, au
##   moins `DUST_MIN_AMOUNT`), pris sur le budget de la météo (`living(preset).weather_particles`) : pluie,
##   neige et poussière restent sous ce budget.

const BOX_M := 40.0
const RAIN_FALL_MPS := 7.0
const SNOW_FALL_MPS := 1.2
const WIND_MAX_MPS := 60.0 / 3.6
const RAIN_WIND_SHARE := 0.6      # la pluie, lourde, suit moins le vent que la neige
const SNOW_WIND_SHARE := 0.9
const DUST_SURFACES := ["gravel", "dirt"]
const DUST_SHARE := 25
const DUST_MIN_AMOUNT := 8
const DUST_MIN_MPS := 2.0
const DUST_LIFETIME_S := 1.6

var _budget := 0
var _rain: GPUParticles3D = null
var _snow: GPUParticles3D = null
var _dust: GPUParticles3D = null
var _dry := true


func configure(budget: int) -> void:
	_budget = maxi(budget, 0)
	for c in get_children():
		c.queue_free()
		remove_child(c)
	_rain = null
	_snow = null
	_dust = null
	if _budget == 0:
		set_process(false)
		visible = false
		return
	_rain = _make_emitter("Pluie", _rain_mesh(), RAIN_FALL_MPS)
	_snow = _make_emitter("Neige", _snow_mesh(), SNOW_FALL_MPS)
	_dust = _make_dust()
	visible = true


func get_budget() -> int:
	return _budget


func is_active() -> bool:
	return _budget > 0 and ((_rain != null and _rain.emitting) or (_snow != null and _snow.emitting)
			or (_dust != null and _dust.emitting))


## Particules visibles au plus (amount × amount_ratio des effets qui émettent).
func get_active_count() -> int:
	var n := 0
	for p in [_rain, _snow, _dust]:
		if p != null and p.emitting:
			n += int(round(p.amount * p.amount_ratio))
	return n


func get_emitter(kind: String) -> GPUParticles3D:
	if kind == "dust":
		return _dust
	return _rain if kind == "rain" else _snow


## Une fois par image : suit la caméra et applique la météo de weather_model.evaluate().
func update(camera_position: Vector3, weather_eval: Dictionary) -> void:
	global_position = camera_position
	if _budget == 0:
		return
	_dry = float(weather_eval.get("rain", 0.0)) <= 0.001 and float(weather_eval.get("snow", 0.0)) <= 0.001
	var wind := {"dir": weather_eval.get("wind_dir", Vector3.ZERO), "strength": weather_eval.get("wind_strength", 0.0)}
	_apply(_rain, float(weather_eval.get("rain", 0.0)), particle_velocity("rain", wind))
	_apply(_snow, float(weather_eval.get("snow", 0.0)), particle_velocity("snow", wind))


## Une fois par image, après `update` : poussière derrière la roue arrière (`rider_pos` au sol, `back` vers
## l'arrière du vélo), plus dense avec la vitesse ; rien sur le bitume, sous la pluie ou la neige.
func update_dust(rider_pos: Vector3, back: Vector3, speed_mps: float, surface: String) -> void:
	if _dust == null:
		return
	var on := dust_wanted(surface, speed_mps, _dry)
	_dust.emitting = on
	_dust.visible = on
	if not on:
		return
	_dust.global_position = rider_pos + back.normalized() * 0.5 + Vector3.UP * 0.05
	_dust.amount_ratio = clampf(speed_mps / 10.0, 0.2, 1.0)
	var mat := _dust.process_material as ParticleProcessMaterial
	mat.direction = (back.normalized() + Vector3.UP * 0.6).normalized()
	mat.initial_velocity_min = 0.3 * speed_mps
	mat.initial_velocity_max = 0.5 * speed_mps


static func dust_amount(budget: int) -> int:
	return mini(budget / 2, maxi(DUST_MIN_AMOUNT, budget / DUST_SHARE))


static func dust_wanted(surface: String, speed_mps: float, dry: bool) -> bool:
	return dry and speed_mps >= DUST_MIN_MPS and surface in DUST_SURFACES


## Vitesse d'une particule (m/s, repère de Godot) : chute verticale et part du vent horizontal.
static func particle_velocity(kind: String, wind_eval: Dictionary) -> Vector3:
	var dir: Vector3 = wind_eval.get("dir", Vector3.ZERO)
	var horiz := Vector3(dir.x, 0.0, dir.z)
	if horiz.length() > 1e-4:
		horiz = horiz.normalized()
	var speed := clampf(float(wind_eval.get("strength", 0.0)), 0.0, 1.0) * WIND_MAX_MPS
	if kind == "rain":
		return horiz * speed * RAIN_WIND_SHARE + Vector3(0.0, -RAIN_FALL_MPS, 0.0)
	return horiz * speed * SNOW_WIND_SHARE + Vector3(0.0, -SNOW_FALL_MPS, 0.0)


func _apply(p: GPUParticles3D, intensity: float, velocity: Vector3) -> void:
	if p == null:
		return
	var on := intensity > 0.001
	p.emitting = on
	p.visible = on
	if not on:
		return
	p.amount_ratio = clampf(intensity, 0.0, 1.0)
	var mat := p.process_material as ParticleProcessMaterial
	var speed := velocity.length()
	mat.direction = velocity / speed if speed > 1e-4 else Vector3.DOWN
	mat.initial_velocity_min = speed
	mat.initial_velocity_max = speed * 1.1
	# Durée de vie : traverser la boîte, avec la pente due au vent
	p.lifetime = clampf(BOX_M / maxf(absf(velocity.y), 0.5), 1.0, 40.0)


func _make_emitter(node_name: String, mesh: Mesh, fall_mps: float) -> GPUParticles3D:
	var p := GPUParticles3D.new()
	p.name = node_name
	p.amount = _budget - dust_amount(_budget)   # la poussière prend sa part du même budget
	p.amount_ratio = 0.0
	p.local_coords = false
	p.emitting = false
	p.visible = false
	p.lifetime = BOX_M / fall_mps
	p.preprocess = 0.0
	p.visibility_aabb = AABB(Vector3.ONE * (-BOX_M), Vector3.ONE * BOX_M * 2.0)
	p.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	var mat := ParticleProcessMaterial.new()
	mat.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_BOX
	mat.emission_box_extents = Vector3(BOX_M * 0.5, BOX_M * 0.5, BOX_M * 0.5)
	mat.gravity = Vector3.ZERO
	mat.direction = Vector3.DOWN
	mat.spread = 3.0 if fall_mps > 3.0 else 25.0
	mat.initial_velocity_min = fall_mps
	mat.initial_velocity_max = fall_mps * 1.1
	p.process_material = mat
	p.draw_pass_1 = mesh
	add_child(p)
	return p


## Poussière : petits carrés beiges qui montent, ralentissent et retombent en 1,6 s ; nombre borné par le budget.
func _make_dust() -> GPUParticles3D:
	var p := GPUParticles3D.new()
	p.name = "Poussiere"
	p.amount = dust_amount(_budget)
	p.amount_ratio = 0.0
	p.local_coords = false
	p.emitting = false
	p.visible = false
	p.lifetime = DUST_LIFETIME_S
	p.visibility_aabb = AABB(Vector3.ONE * -6.0, Vector3.ONE * 12.0)
	p.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	var mat := ParticleProcessMaterial.new()
	mat.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_BOX
	mat.emission_box_extents = Vector3(0.15, 0.02, 0.15)
	mat.gravity = Vector3(0.0, -1.5, 0.0)
	mat.damping_min = 1.5
	mat.damping_max = 2.5
	mat.spread = 35.0
	mat.scale_min = 0.6
	mat.scale_max = 1.6
	p.process_material = mat
	var q := QuadMesh.new()
	q.size = Vector2(0.08, 0.08)
	var m := StandardMaterial3D.new()
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.albedo_color = Color(0.72, 0.64, 0.5, 0.35)
	m.billboard_mode = BaseMaterial3D.BILLBOARD_PARTICLES
	q.material = m
	p.draw_pass_1 = q
	add_child(p)
	return p


## Goutte : trait fin et allongé, orienté vers la caméra autour de l'axe vertical.
static func _rain_mesh() -> QuadMesh:
	var q := QuadMesh.new()
	q.size = Vector2(0.015, 0.45)
	var m := StandardMaterial3D.new()
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.albedo_color = Color(0.78, 0.83, 0.9, 0.35)
	m.billboard_mode = BaseMaterial3D.BILLBOARD_FIXED_Y
	m.billboard_keep_scale = true
	q.material = m
	return q


## Flocon : petit carré blanc face à la caméra.
static func _snow_mesh() -> QuadMesh:
	var q := QuadMesh.new()
	q.size = Vector2(0.06, 0.06)
	var m := StandardMaterial3D.new()
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.albedo_color = Color(1.0, 1.0, 1.0, 0.85)
	m.billboard_mode = BaseMaterial3D.BILLBOARD_PARTICLES
	q.material = m
	return q
