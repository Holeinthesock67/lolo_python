extends Node3D

## Affichage de road_traffic_model.gd (Lot P25) : un MultiMeshInstance3D par sorte de véhicule (caisse et
## roues fixes de vehicle_mesh.gd `build_full`, shaders/vehicle.gdshader en mode `instanced`), sans ombre ;
## couleur d'instance = peinture, INSTANCE_CUSTOM.x = phares. Pas de class_name : charger par
## preload("res://scripts/road_traffic_renderer.gd").
##
## - `setup(model)`, `set_budget(n)` (cases de chaque MultiMesh), `set_lights(on)`.
## - `update()` une fois par image, après `model.update`.
## Tous les nœuds sont créés à l'initialisation ; aucun n'est créé ensuite.

const VehicleMesh := preload("res://scripts/vehicle_mesh.gd")
const VehicleShader := preload("res://shaders/vehicle.gdshader")
const RoadTrafficModel := preload("res://scripts/road_traffic_model.gd")

const KINDS := ["car_a", "car_b", "van", "truck", "bus", "moto", "tractor", "tractor_field"]
const VISIBILITY_END_M := RoadTrafficModel.RANGE_M + 100.0

var model = null
var lights := false
var _mmi: Dictionary = {}          # sorte -> MultiMeshInstance3D
var _capacity := 0


func _init() -> void:
	for kind in KINDS:
		var mm := MultiMesh.new()
		mm.transform_format = MultiMesh.TRANSFORM_3D
		mm.use_colors = true
		mm.use_custom_data = true
		mm.mesh = VehicleMesh.build_full(kind)
		mm.instance_count = 0
		var mat := ShaderMaterial.new()
		mat.shader = VehicleShader
		mat.set_shader_parameter("instanced", true)
		mat.set_shader_parameter("second", VehicleMesh.second(kind))
		var mmi := MultiMeshInstance3D.new()
		mmi.name = "Distant_%s" % kind
		mmi.multimesh = mm
		mmi.material_override = mat
		mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		mmi.visibility_range_end = VISIBILITY_END_M
		add_child(mmi)
		_mmi[kind] = mmi


func setup(road_traffic_model) -> void:
	model = road_traffic_model


func set_budget(n: int) -> void:
	_capacity = maxi(0, n)
	for kind in KINDS:
		var mm: MultiMesh = _mmi[kind].multimesh
		mm.instance_count = _capacity
		mm.visible_instance_count = 0


func set_lights(on: bool) -> void:
	lights = on


## Données d'instance de chaque véhicule : x = phares.
func instance_custom() -> Color:
	return Color(1.0 if lights else 0.0, 0.0, 0.0, 0.0)


func visible_count() -> int:
	var n := 0
	for kind in KINDS:
		n += maxi(0, _mmi[kind].multimesh.visible_instance_count)
	return n


func count_of(kind: String) -> int:
	return maxi(0, _mmi[kind].multimesh.visible_instance_count) if _mmi.has(kind) else 0


func update() -> void:
	var used := {}
	for kind in KINDS:
		used[kind] = 0
	var vs: Array = model.vehicles if model != null else []
	var custom := instance_custom()
	for v in vs:
		var kind: String = v["kind"]
		if not _mmi.has(kind) or int(used[kind]) >= _capacity:
			continue
		var mm: MultiMesh = _mmi[kind].multimesh
		var i: int = used[kind]
		mm.set_instance_transform(i, v["xform"])
		mm.set_instance_color(i, VehicleMesh.paint(kind, int(v["color"])))
		mm.set_instance_custom_data(i, custom)
		used[kind] = i + 1
	for kind in KINDS:
		_mmi[kind].multimesh.visible_instance_count = used[kind]
