extends Node3D

## Corps des ennemis du Cyber-Rogue (lot R12) : un volume de primitives Godot par archétype (train de trois
## voitures, moto lumineuse, drone pyramidal, chasseur en losange, essaim de cubes, chimère du boss), animé
## par la pose de enemy_model.gd, avec un flash de 0,1 s et un éclat de particules aux impacts. Couleurs et
## matériaux de la charte R17 (neon_catalog.gd), aucun modèle ni texture. Pas de calcul de jeu ici.

const Catalog := preload("res://scripts/rogue/neon_catalog.gd")
const Materials := preload("res://scripts/rogue/neon_materials.gd")
const Model := preload("res://scripts/rogue/enemy_model.gd")

const OBJECT_OF := {
	"diesel": "enemy_diesel", "puncheur": "enemy_puncher", "grimpeur": "enemy_climber",
	"sprinteur": "enemy_sprinter", "saboteur": "enemy_saboteur", "boss": "boss_chimera",
}
const CAR_LEN_M := 4.0
const CAR_GAP_M := 1.0
const FLASH_RADIUS_M := 1.2
const BURST_SMALL := 12
const BURST_BIG := 24
const SWARM_RADIUS_M := 2.5
const SCATTER_RADIUS_M := 9.0

var preset := "low"
var adapted := false
var archetype := ""
var body: Node3D
var flash: MeshInstance3D
var burst: CPUParticles3D
var swarm: MultiMeshInstance3D
var wall: MeshInstance3D
var charge_bar: MeshInstance3D
var lift_node: Node3D
var locks: Node3D
var shock: MeshInstance3D
var flash_left_s := 0.0
var _flash_scale := 1.0
var _time := 0.0
var _boss_effect := ""
var _tinted := false


func _ready() -> void:
	body = Node3D.new()
	body.name = "Body"
	add_child(body)
	flash = MeshInstance3D.new()
	flash.name = "Flash"
	var s := SphereMesh.new()
	s.radius = FLASH_RADIUS_M
	s.height = FLASH_RADIUS_M * 2.0
	flash.mesh = s
	flash.visible = false
	add_child(flash)
	burst = CPUParticles3D.new()
	burst.name = "Burst"
	burst.one_shot = true
	burst.emitting = false
	burst.explosiveness = 1.0
	burst.lifetime = 0.5
	burst.initial_velocity_min = 4.0
	burst.initial_velocity_max = 9.0
	burst.spread = 180.0
	burst.gravity = Vector3.ZERO
	var q := QuadMesh.new()
	q.size = Vector2(0.15, 0.15)
	burst.mesh = q
	add_child(burst)
	set_style(preset, adapted)


func set_style(new_preset: String, new_adapted: bool) -> void:
	preset = new_preset
	adapted = new_adapted
	if flash == null:
		return
	flash.material_override = Materials.glass("energy", 0.6, preset, adapted)
	burst.material_override = Materials.edge("energy", 2.0, preset, adapted)
	if archetype != "":
		var a := archetype
		archetype = ""
		set_archetype(a)


func _token(id: String) -> String:
	return String(Catalog.OBJECTS[id]["token"])


func _box(size: Vector3, pos: Vector3, token: String) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	var m := BoxMesh.new()
	m.size = size
	mi.mesh = m
	mi.position = pos
	mi.material_override = Materials.edge(token, 2.0, preset, adapted)
	return mi


## Construit le volume de l'archétype (sans effet si c'est déjà lui).
func set_archetype(new_archetype: String) -> void:
	if body == null or new_archetype == archetype:
		return
	archetype = new_archetype
	for c in body.get_children():
		c.queue_free()
	swarm = null
	wall = null
	charge_bar = null
	lift_node = null
	locks = null
	shock = null
	_tinted = false
	if not OBJECT_OF.has(archetype):
		return
	var tok := _token(OBJECT_OF[archetype])
	match archetype:
		"diesel":
			_build_train(tok, Vector3.ZERO)
		"puncheur":
			_build_bike(tok, Vector3.ZERO)
		"grimpeur":
			_build_drone(tok, Vector3.ZERO)
		"sprinteur":
			_build_fighter(tok, Vector3.ZERO)
		"saboteur":
			_build_swarm(tok)
		"boss":
			# Chimère : les cinq formes côte à côte ; les effets de phase (verrous, ondes, écarlate) viennent de boss_effect().
			_build_train(_token("enemy_diesel"), Vector3(-9.0, 0.0, 0.0))
			_build_bike(_token("enemy_puncher"), Vector3(-4.5, 0.0, 0.0))
			_build_drone(tok, Vector3(0.0, 0.0, 0.0))
			_build_fighter(_token("enemy_sprinter"), Vector3(4.5, 0.0, 0.0))
			_build_swarm(_token("enemy_saboteur"), Vector3(9.0, 0.0, 0.0))
			_build_boss_effects()


func _build_boss_effects() -> void:
	locks = Node3D.new()
	for i in 5:
		var a := TAU * float(i) / 5.0
		locks.add_child(_box(Vector3(0.5, 0.5, 0.5), Vector3(cos(a) * 3.0, 2.2, sin(a) * 3.0), "gold"))
	locks.visible = false
	body.add_child(locks)
	shock = MeshInstance3D.new()
	var t := TorusMesh.new()
	t.inner_radius = 0.9
	t.outer_radius = 1.0
	shock.mesh = t
	shock.material_override = Materials.edge("danger", 2.0, preset, adapted)
	shock.visible = false
	body.add_child(shock)


func _build_train(tok: String, at: Vector3) -> void:
	var root := Node3D.new()
	root.position = at
	for i in 3:
		root.add_child(_box(Vector3(2.0, 1.6, CAR_LEN_M), Vector3(0.0, 0.0, float(i) * (CAR_LEN_M + CAR_GAP_M)), tok))
	charge_bar = _box(Vector3(2.2, 0.15, 3.0 * CAR_LEN_M + 2.0 * CAR_GAP_M), Vector3(0.0, 1.0, CAR_LEN_M + CAR_GAP_M), "gold")
	charge_bar.visible = false
	root.add_child(charge_bar)
	body.add_child(root)


func _build_bike(tok: String, at: Vector3) -> void:
	var root := Node3D.new()
	root.position = at
	for z in [-1.4, 1.4]:
		var ring := MeshInstance3D.new()
		var t := TorusMesh.new()
		t.inner_radius = 0.5
		t.outer_radius = 0.7
		ring.mesh = t
		ring.rotation.z = PI * 0.5
		ring.position = Vector3(0.0, 0.0, z)
		ring.material_override = Materials.edge(tok, 2.0, preset, adapted)
		root.add_child(ring)
	root.add_child(_box(Vector3(0.5, 0.5, 2.4), Vector3(0.0, 0.3, 0.0), tok))
	wall = MeshInstance3D.new()
	var q := QuadMesh.new()
	q.size = Vector2(6.0, 2.0)
	wall.mesh = q
	wall.position = Vector3(0.0, 0.8, 4.0)
	wall.material_override = Materials.wall(tok, preset, adapted)
	wall.visible = false
	root.add_child(wall)
	body.add_child(root)


func _build_drone(tok: String, at: Vector3) -> void:
	lift_node = Node3D.new()
	lift_node.position = at
	var p := MeshInstance3D.new()
	var pm := PrismMesh.new()
	pm.size = Vector3(2.4, 2.4, 2.4)
	p.mesh = pm
	p.material_override = Materials.edge(tok, 2.0, preset, adapted)
	lift_node.add_child(p)
	body.add_child(lift_node)


func _build_fighter(tok: String, at: Vector3) -> void:
	var f := MeshInstance3D.new()
	var s := SphereMesh.new()
	s.radial_segments = 4
	s.rings = 2
	s.radius = 1.2
	s.height = 3.2
	f.mesh = s
	f.position = at
	f.material_override = Materials.edge(tok, 2.0, preset, adapted)
	body.add_child(f)


func _build_swarm(tok: String, at: Vector3 = Vector3.ZERO) -> void:
	swarm = MultiMeshInstance3D.new()
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	var cube := BoxMesh.new()
	cube.size = Vector3(0.6, 0.6, 0.6)
	mm.mesh = cube
	mm.instance_count = Model.SWARM_SIZE
	swarm.multimesh = mm
	swarm.position = at
	swarm.material_override = Materials.edge(tok, 2.0, preset, adapted)
	body.add_child(swarm)


## Impact reçu du modèle : flash de 0,1 s (plus gros pour un coup critique) et éclat de particules.
func impact(crit: bool, flash_s: float) -> void:
	if flash == null:
		return
	flash_left_s = flash_s
	_flash_scale = 2.0 if crit else 1.0
	burst.amount = BURST_BIG if crit else BURST_SMALL
	burst.restart()
	burst.emitting = true


## Applique la pose du modèle. `delta` : temps écoulé depuis l'appel précédent.
func apply(pose: Dictionary, delta: float) -> void:
	if body == null:
		return
	_time += delta
	var shown: bool = bool(pose.get("visible", false)) and float(pose.get("alpha", 0.0)) > 0.0
	visible = shown
	if not shown:
		return
	set_archetype(String(pose.get("archetype", "")))
	var alpha := float(pose.get("alpha", 1.0))
	body.scale = Vector3.ONE * alpha
	body.visible = not bool(pose.get("cloaked", false))      # Sprinteur : disparaît pendant les salves
	var jitter := Vector3.ZERO
	if bool(pose.get("glitch", false)):
		jitter = Vector3(sin(_time * 53.0), 0.0, cos(_time * 47.0)) * 0.15
	body.position = jitter
	if charge_bar != null:
		charge_bar.visible = bool(pose.get("charge", false))
	if wall != null:
		wall.visible = bool(pose.get("prelight", false))
	if lift_node != null:
		lift_node.position.y = float(pose.get("lift_m", 0.0))
	if swarm != null:
		_place_swarm(bool(pose.get("scatter", false)))
	_boss_effect = String(pose.get("boss_effect", ""))
	if archetype == "boss":
		body.rotation.y = sin(_time * 0.5) * 0.1
		locks.visible = _boss_effect == "locks"
		shock.visible = _boss_effect == "shockwaves"
		if shock.visible:
			var k := fmod(_time, 1.5) / 1.5          # une onde de choc toutes les 1,5 s, de 2 m à 14 m
			shock.scale = Vector3.ONE * lerpf(2.0, 14.0, k)
		if _boss_effect == "scarlet" and not _tinted:
			_tint_scarlet()
	flash_left_s = maxf(flash_left_s - delta, 0.0)
	flash.visible = flash_left_s > 0.0
	flash.scale = Vector3.ONE * _flash_scale


## Phase 3 : tous les volumes de la chimère passent au rouge `danger`.
func _tint_scarlet() -> void:
	_tinted = true
	var mat := Materials.edge("danger", 2.0, preset, adapted)
	for mi in body.find_children("*", "MeshInstance3D", true, false):
		mi.material_override = mat
	if swarm != null:
		swarm.material_override = mat


func boss_effect() -> String:
	return _boss_effect


func _place_swarm(scattered: bool) -> void:
	var mm := swarm.multimesh
	var radius := SCATTER_RADIUS_M if scattered else SWARM_RADIUS_M
	for i in mm.instance_count:
		var a := float(i) * 2.399963 + _time * (0.4 if scattered else 1.2)
		var r := radius * (0.35 + 0.65 * fmod(float(i) * 0.61803, 1.0))
		mm.set_instance_transform(i, Transform3D(Basis.IDENTITY, Vector3(cos(a) * r, sin(a * 0.7) * r * 0.4, sin(a) * r)))
