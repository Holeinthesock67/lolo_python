extends Node3D

## Planche de démonstration de la charte du Cyber-Rogue (lot R17 §4.8) : chaque objet du catalogue côte à
## côte (volumes sombres à arêtes lumineuses), les effets rejouables à la touche, les trois préréglages.
## Touches : 1, 2, 3 = préréglage low, medium, high ; E = effet suivant ; A = couleurs adaptées.
## Les maillages sont des primitives Godot : aucun modèle ni texture (invariant A9).

const Palette := preload("res://scripts/rogue/neon_palette.gd")
const Materials := preload("res://scripts/rogue/neon_materials.gd")
const Catalog := preload("res://scripts/rogue/neon_catalog.gd")
const RogueEnvironment := preload("res://scripts/rogue/rogue_environment.gd")

const COLUMNS := 6
const SPACING := 4.0

var preset := "low"
var adapted := false
var effect_index := -1
var objects: Dictionary = {}          # id -> Node3D
var _env: Environment
var _flash: MeshInstance3D
var _flash_tween: Tween


func _ready() -> void:
	_env = Environment.new()
	var we := WorldEnvironment.new()
	we.environment = _env
	add_child(we)
	var cam := Camera3D.new()
	cam.position = Vector3(10.0, 7.0, 16.0)
	add_child(cam)
	cam.look_at_from_position(cam.position, Vector3(10.0, 0.5, 0.0))
	var floor_mesh := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size = Vector2(400.0, 400.0)
	floor_mesh.mesh = plane
	floor_mesh.position = Vector3(10.0, 0.0, 0.0)
	floor_mesh.name = "Grid"
	add_child(floor_mesh)
	_flash = MeshInstance3D.new()
	_flash.mesh = SphereMesh.new()
	_flash.position = Vector3(10.0, 4.0, 4.0)
	_flash.scale = Vector3.ZERO
	_flash.name = "Flash"
	add_child(_flash)
	_build_objects()
	set_preset(preset)


func _build_objects() -> void:
	var i := 0
	for id in Catalog.object_ids():
		var spec: Dictionary = Catalog.OBJECTS[id]
		var node := Node3D.new()
		node.name = id
		node.position = Vector3((i % COLUMNS) * SPACING, 0.0, -floori(float(i) / COLUMNS) * SPACING)
		var mi := MeshInstance3D.new()
		mi.mesh = _mesh_for(spec["shape"])
		mi.position.y = 1.0
		mi.name = "Body"
		node.add_child(mi)
		var label := Label3D.new()
		label.text = id
		label.font_size = 24
		label.position = Vector3(0.0, 2.6, 0.0)
		label.modulate = Palette.color("neutral")
		label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
		node.add_child(label)
		add_child(node)
		objects[id] = node
		i += 1


static func _mesh_for(shape: String) -> Mesh:
	match shape:
		"wheel":
			var m := CylinderMesh.new()
			m.top_radius = 0.6
			m.bottom_radius = 0.6
			m.height = 0.2
			return m
		"ring":
			var t := TorusMesh.new()
			t.inner_radius = 0.7
			t.outer_radius = 1.0
			return t
		"diamond":
			var s := SphereMesh.new()
			s.radial_segments = 4
			s.rings = 2
			s.radius = 0.8
			s.height = 1.6
			return s
		"arch", "gate":
			var g := BoxMesh.new()
			g.size = Vector3(2.0, 2.0, 0.2)
			return g
		"slab":
			var sl := BoxMesh.new()
			sl.size = Vector3(2.0, 0.1, 2.0)
			return sl
		"wall":
			var w := QuadMesh.new()
			w.size = Vector2(3.0, 1.6)
			return w
		"ribbon":
			var r := BoxMesh.new()
			r.size = Vector3(3.0, 0.1, 0.5)
			return r
		"card":
			var c := QuadMesh.new()
			c.size = Vector2(1.4, 2.0)
			return c
		"rock":
			var p := PrismMesh.new()
			p.size = Vector3(1.4, 1.4, 1.4)
			return p
	var b := BoxMesh.new()
	b.size = Vector3(1.4, 1.4, 1.4)
	return b


func set_adapted(value: bool) -> void:
	adapted = value
	_apply_materials()


func set_preset(preset_name: String) -> void:
	preset = preset_name if RogueEnvironment.PRESETS.has(preset_name) else "low"
	RogueEnvironment.apply(_env, preset)
	_apply_materials()


func _apply_materials() -> void:
	get_node("Grid").material_override = Materials.grid(preset, adapted)
	for id in objects:
		var spec: Dictionary = Catalog.OBJECTS[id]
		var body: MeshInstance3D = objects[id].get_node("Body")
		match spec["shape"]:
			"wall":
				body.material_override = Materials.wall(spec["token"], preset, adapted)
			"card", "gate":
				body.material_override = Materials.hologram(spec["token"], preset, adapted)
			_:
				body.material_override = Materials.edge(spec["token"], 2.0, preset, adapted)
	var flash_mat := Materials.wall(Catalog.EFFECTS.values()[maxi(effect_index, 0)]["token"], preset, adapted)
	_flash.material_override = flash_mat


## Rejoue un effet du catalogue : la sphère de démonstration s'allume dans la couleur de l'effet pendant sa
## durée (0,5 s pour les effets continus), sans dépasser son plafond de clignotements.
func play_effect(id: String) -> void:
	assert(Catalog.EFFECTS.has(id), "effet inconnu : %s" % id)
	var spec: Dictionary = Catalog.EFFECTS[id]
	_flash.material_override = Materials.wall(spec["token"], preset, adapted)
	if _flash_tween:
		_flash_tween.kill()
	_flash.scale = Vector3.ONE
	_flash_tween = create_tween()
	_flash_tween.tween_property(_flash, "scale", Vector3.ZERO, maxf(spec["duration_s"], 0.5))


func _unhandled_key_input(event: InputEvent) -> void:
	if not (event is InputEventKey and event.pressed and not event.echo):
		return
	match event.keycode:
		KEY_1: set_preset("low")
		KEY_2: set_preset("medium")
		KEY_3: set_preset("high")
		KEY_A: set_adapted(not adapted)
		KEY_E:
			effect_index = (effect_index + 1) % Catalog.effect_ids().size()
			play_effect(Catalog.effect_ids()[effect_index])
