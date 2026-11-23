extends Node3D

## Éoliennes des points `wind_turbine` (Lot P12, Format .world v1.2 §8), construites par code.
## Pas de class_name : charger par preload("res://scripts/wind_turbines.gd").
##
## - `set_points(points)` : points d'intérêt du parcours chargé (les autres sortes sont ignorées) ;
##   `height_m` est la hauteur du moyeu (DEFAULT_HEIGHT_M sans valeur), les pales mesurent
##   BLADE_RATIO × la hauteur.
## - `update(wind, cam_pos, dt_s)` une fois par image, avec l'évaluation de wind_model.gd
##   (`{dir, strength, gust}`, vent au sol, à 10 m) : chaque rotor suit le vent à hauteur de SON moyeu
##   (`hub_kmh`, loi de puissance d'exposant SHEAR_ALPHA = 1/7 : ×1,39 à 100 m), à
##   `5 + 12 × force au moyeu` tr/min ; il démarre à CUT_IN_KMH (10 km/h au moyeu) et ne s'arrête que
##   sous CUT_OUT_KMH (8 km/h), pour ne pas repartir à chaque rafale ; sa vitesse suit la cible au premier
##   ordre de constante SPIN_TAU_S (inertie du rotor, sans à-coup). Sens horaire vu de face, comme les
##   vraies éoliennes. Lot EO1 (21/11) : le vent du thème par défaut (8 km/h au sol) fait tourner les rotors ;
##   nacelle face au vent (le rotor regarde d'où vient le vent), lissée au premier ordre de constante
##   YAW_TAU_S et limitée à YAW_MAX_DEG_S, donc sans à-coup ; par vent nul, elle garde son cap.
## Au plus MAX_ACTIVE éoliennes affichées, les plus proches de la caméra, retriées tous les
## RESELECT_M ; leurs nœuds sont créés au démarrage. Au-delà de LOD_DISTANCE_M, mât et nacelle passent
## à un maillage simplifié (portée de visibilité des MeshInstance3D).

const MAX_ACTIVE := 20
const DEFAULT_HEIGHT_M := 100.0
const BLADE_RATIO := 0.45
const RPM_BASE := 5.0
const RPM_PER_STRENGTH := 12.0
const CUT_IN_KMH := 10.0         # au moyeu
const CUT_OUT_KMH := 8.0         # au moyeu : arrêt (hystérésis, lot EO1)
const SHEAR_ALPHA := 1.0 / 7.0   # loi de puissance du vent avec la hauteur (lot EO1)
const SHEAR_REF_M := 10.0        # hauteur du vent du jeu (Open-Meteo : vent à 10 m)
const SPIN_TAU_S := 6.0          # inertie du rotor (lot EO1)
const STRENGTH_FULL_KMH := 60.0
const YAW_TAU_S := 10.0
const YAW_MAX_DEG_S := 3.0
const LOD_DISTANCE_M := 2000.0
const RESELECT_M := 50.0
const COLOR := Color(0.92, 0.93, 0.94)
const PropShader := preload("res://shaders/props.gdshader")
const RoadsideProps := preload("res://scripts/roadside_props.gd")
## Matières de props.gdshader (lot Y8 étape 4) : joints des tronçons et porte du mât, capot, pales usées.
const KIND_TOWER := 3
const KIND_NACELLE := 4
const KIND_BLADE := 5

var _points: Array = []          # {pos, height, shear, yaw, rotor, omega (rad/s), running}
var _slots: Array = []           # {root, nacelle, rotor, point: int}
var _last_select := Vector3(INF, INF, INF)
var _dirty := true
var _meshes: Array = []   # gardés ici : les maillages partagés survivent aux nœuds qui les affichent
var _mats: Array = []     # mât, nacelle, pale
var last_update_usec := 0


## Facteur du vent au moyeu de hauteur `height_m` par rapport au vent du jeu (10 m), jamais sous 1.
static func shear_factor(height_m: float) -> float:
	return pow(maxf(height_m, SHEAR_REF_M) / SHEAR_REF_M, SHEAR_ALPHA)


## Vent au moyeu (km/h) pour la force au sol `strength` (0 à 1, 1 = 60 km/h) et un moyeu à `height_m`.
static func hub_kmh(strength: float, height_m: float) -> float:
	return maxf(strength, 0.0) * STRENGTH_FULL_KMH * shear_factor(height_m)


## Rotor en marche après ce pas : démarre à CUT_IN_KMH, s'arrête sous CUT_OUT_KMH (vent au moyeu).
static func is_running(hub: float, was_running: bool) -> bool:
	return hub >= CUT_OUT_KMH if was_running else hub >= CUT_IN_KMH


## Vitesse cible du rotor (tr/min) pour un vent au moyeu de `hub` km/h, rotor en marche ou non.
static func rotor_rpm(hub: float, running: bool = true) -> float:
	if not running:
		return 0.0
	return RPM_BASE + RPM_PER_STRENGTH * clampf(hub / STRENGTH_FULL_KMH, 0.0, 1.0)


## Cap de la nacelle (rad autour de y, rotor vers -z local) pour un vent qui souffle vers `dir`.
static func facing_yaw(dir: Vector3) -> float:
	# Le rotor regarde d'où vient le vent : -z local tourné vers -dir.
	return atan2(dir.x, dir.z)


## Un pas de lissage du cap : premier ordre (YAW_TAU_S) limité à YAW_MAX_DEG_S.
static func step_yaw(current: float, target: float, dt_s: float) -> float:
	var delta := wrapf(target - current, -PI, PI)
	var step := delta * (1.0 - exp(-dt_s / YAW_TAU_S))
	var max_step := deg_to_rad(YAW_MAX_DEG_S) * dt_s
	return current + clampf(step, -max_step, max_step)



## Maillage d'une primitive converti en ArrayMesh (le serveur de rendu factice du mode sans écran ne
## sait pas compter les surfaces d'une PrimitiveMesh).
static func _baked(pm: PrimitiveMesh) -> ArrayMesh:
	var am := ArrayMesh.new()
	am.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, pm.get_mesh_arrays())
	return am

func _init() -> void:
	var mats := []
	for k in [KIND_TOWER, KIND_NACELLE, KIND_BLADE]:
		var m := ShaderMaterial.new()
		m.shader = PropShader
		m.set_shader_parameter("kind", k)
		m.set_shader_parameter("base_color", COLOR)
		mats.append(m)
	_mats = mats
	var tower_near := CylinderMesh.new()
	tower_near.top_radius = 0.012
	tower_near.bottom_radius = 0.022
	tower_near.height = 1.0
	tower_near.radial_segments = 16
	tower_near.rings = 1
	var tower_far := tower_near.duplicate() as CylinderMesh
	tower_far.radial_segments = 6
	var nacelle_mesh := BoxMesh.new()
	nacelle_mesh.size = Vector3(0.035, 0.035, 0.1)
	var blade_mesh := BoxMesh.new()
	blade_mesh.size = Vector3(0.018, BLADE_RATIO, 0.006)
	_meshes = [_baked(tower_near), _baked(tower_far), _baked(nacelle_mesh), _baked(blade_mesh)]
	(_mats[0] as ShaderMaterial).set_shader_parameter("size_m", Vector3(0.044, 1.0, 0.044))
	(_mats[1] as ShaderMaterial).set_shader_parameter("size_m", nacelle_mesh.size)
	(_mats[2] as ShaderMaterial).set_shader_parameter("size_m", blade_mesh.size)
	var lods := [[_meshes[0], 0.0, LOD_DISTANCE_M], [_meshes[1], LOD_DISTANCE_M, 0.0]]
	var nacelle_am: ArrayMesh = _meshes[2]
	var blade_am: ArrayMesh = _meshes[3]
	for i in range(MAX_ACTIVE):
		var root := Node3D.new()
		root.name = "Turbine_%d" % i
		root.visible = false
		add_child(root)
		for lod in lods:
			var t := MeshInstance3D.new()
			t.mesh = lod[0]
			t.material_override = _mats[0]
			t.position = Vector3(0.0, 0.5, 0.0)
			t.visibility_range_begin = lod[1]
			t.visibility_range_end = lod[2]
			root.add_child(t)
		var nacelle := Node3D.new()
		nacelle.position = Vector3(0.0, 1.0, 0.0)
		root.add_child(nacelle)
		var body := MeshInstance3D.new()
		body.mesh = nacelle_am
		body.material_override = _mats[1]
		body.position = Vector3(0.0, 0.0, 0.02)
		nacelle.add_child(body)
		var rotor := Node3D.new()
		rotor.position = Vector3(0.0, 0.0, -0.035)
		nacelle.add_child(rotor)
		for b in range(3):
			var arm := Node3D.new()
			arm.rotation = Vector3(0.0, 0.0, TAU * b / 3.0)
			rotor.add_child(arm)
			var blade := MeshInstance3D.new()
			blade.mesh = blade_am
			blade.material_override = _mats[2]
			blade.position = Vector3(0.0, BLADE_RATIO * 0.5, 0.0)
			arm.add_child(blade)
		_slots.append({"root": root, "nacelle": nacelle, "rotor": rotor, "point": -1})


## Faux relief des joints selon le préréglage (RoadsideProps.RELIEF : coupé en low).
func set_preset(preset_name: String) -> void:
	for m in _mats:
		(m as ShaderMaterial).set_shader_parameter("relief", float(RoadsideProps.RELIEF.get(preset_name, 1.0)))


func set_points(points: Array) -> void:
	_points.clear()
	for p in points:
		if typeof(p) != TYPE_DICTIONARY or str(p.get("kind", "")) != "wind_turbine":
			continue
		var h := float(p.get("height_m", DEFAULT_HEIGHT_M))
		if not is_finite(h) or h <= 0.0:
			h = DEFAULT_HEIGHT_M
		_points.append({"pos": Vector3(float(p["x"]), float(p["y"]), float(p["z"])), "height": h,
			"shear": shear_factor(h), "yaw": 0.0, "rotor": float(hash(str(p.get("id", ""))) % 360) * PI / 180.0,
			"omega": 0.0, "running": false})
	_dirty = true


func active_count() -> int:
	var n := 0
	for s in _slots:
		if s["root"].visible:
			n += 1
	return n


## Cap lissé (rad), angle (rad), vitesse (tr/min) et marche du rotor de l'éolienne `i` de set_points (tests).
func turbine_state(i: int) -> Dictionary:
	var p: Dictionary = _points[i]
	return {"yaw": p["yaw"], "rotor": p["rotor"], "rpm": float(p["omega"]) * 60.0 / TAU, "running": p["running"]}


## Scène figée des tests graphiques : rotors posés sur leur régime établi pour `wind`, sans inertie.
func settle(wind: Dictionary) -> void:
	var ground_kmh := maxf(float(wind.get("strength", 0.0)), 0.0) * STRENGTH_FULL_KMH
	for p in _points:
		var hub := ground_kmh * float(p["shear"])
		p["running"] = is_running(hub, false)
		p["omega"] = rotor_rpm(hub, p["running"]) * TAU / 60.0


func _select(cam_pos: Vector3) -> void:
	var order := []
	for i in range(_points.size()):
		order.append([(_points[i]["pos"] as Vector3).distance_squared_to(cam_pos), i])
	order.sort_custom(func(a, b): return a[0] < b[0] or (a[0] == b[0] and a[1] < b[1]))
	for j in range(MAX_ACTIVE):
		var s: Dictionary = _slots[j]
		var root: Node3D = s["root"]
		if j < order.size():
			var p: Dictionary = _points[order[j][1]]
			s["point"] = order[j][1]
			root.position = p["pos"]
			root.scale = Vector3.ONE * float(p["height"])
			root.visible = true
		else:
			s["point"] = -1
			root.visible = false
	_last_select = cam_pos
	_dirty = false


func update(wind: Dictionary, cam_pos: Vector3, dt_s: float) -> void:
	var t0 := Time.get_ticks_usec()
	if _dirty or cam_pos.distance_to(_last_select) > RESELECT_M:
		_select(cam_pos)
	var strength := float(wind.get("strength", 0.0))
	var dir: Vector3 = wind.get("dir", Vector3.ZERO)
	var has_dir := Vector2(dir.x, dir.z).length() > 1e-3
	var target := facing_yaw(dir)
	var ground_kmh := maxf(strength, 0.0) * STRENGTH_FULL_KMH
	var k_spin := 1.0 - exp(-maxf(dt_s, 0.0) / SPIN_TAU_S)
	# Toutes les éoliennes du parcours suivent le vent, même hors de l'écran : pas de saut au retour.
	for p in _points:
		if has_dir:
			p["yaw"] = step_yaw(float(p["yaw"]), target, dt_s)
		var hub := ground_kmh * float(p["shear"])
		var running := is_running(hub, bool(p["running"]))
		p["running"] = running
		var omega := float(p["omega"])
		omega += (rotor_rpm(hub, running) * TAU / 60.0 - omega) * k_spin
		p["omega"] = omega
		p["rotor"] = fposmod(float(p["rotor"]) + omega * dt_s, TAU)
	for s in _slots:
		var i: int = s["point"]
		if i < 0:
			continue
		(s["nacelle"] as Node3D).rotation = Vector3(0.0, float(_points[i]["yaw"]), 0.0)
		(s["rotor"] as Node3D).rotation = Vector3(0.0, 0.0, float(_points[i]["rotor"]))
	last_update_usec = Time.get_ticks_usec() - t0
