extends Node3D

## Scène principale du moteur Godot : affiche la polyligne de la route, la caméra subjective et le HUD.

@onready var ipc: IpcClient = $IpcClient
@onready var camera: Camera3D = $Camera3D
@onready var polyline_instance: MeshInstance3D = $RouteMesh
@onready var hud_power: Label = $HUD/Margin/VBox/PowerLabel
@onready var hud_speed: Label = $HUD/Margin/VBox/SpeedLabel
@onready var hud_cadence: Label = $HUD/Margin/VBox/CadenceLabel
@onready var hud_grade: Label = $HUD/Margin/VBox/GradeLabel
@onready var hud_distance: Label = $HUD/Margin/VBox/DistanceLabel

var route: RouteData
var current_s: float = 0.0
var target_s: float = 0.0


func _ready() -> void:
	ipc.state_received.connect(_on_state_received)
	
	# Charger la route de démonstration factice
	var demo_path := "res://demo/demo.world/route.json"
	route = RouteData.load_from_file(demo_path)
	if route:
		_build_route_mesh()


func _process(delta: float) -> void:
	# Interpolation fluide de la position s entre les mises à jour UDP
	current_s = lerpf(current_s, target_s, clampf(delta * 10.0, 0.0, 1.0))
	
	if route:
		var pos := route.sample_point(current_s)
		# Caméra subjective placée à 1.4 m de hauteur (hauteur des yeux du cycliste)
		camera.global_position = pos + Vector3(0.0, 1.4, 0.0)
		
		# Orienter la caméra selon le cap de la route
		var heading := route.sample_heading(current_s)
		# Dans Godot : -Z est le nord. La rotation Y s'applique sur le cap horaire.
		camera.rotation.y = -heading


func _build_route_mesh() -> void:
	var im := ImmediateMesh.new()
	var mat := StandardMaterial3D.new()
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.albedo_color = Color(0.2, 0.7, 1.0, 1.0) # Bleu lumineux pour la polyligne du Spike 0
	
	im.surface_begin(Mesh.PRIMITIVE_LINE_STRIP, mat)
	for i in range(route.n):
		im.surface_add_vertex(Vector3(route.x[i], route.alt_m[i], route.z[i]))
	im.surface_end()
	
	polyline_instance.mesh = im


func _on_state_received(state: Dictionary) -> void:
	target_s = float(state.get("s", 0.0))
	
	var p := float(state.get("power", 0.0))
	var p3s := float(state.get("power_3s", p))
	var v_kmh := float(state.get("v", 0.0)) * 3.6
	var cad := float(state.get("cadence", 0.0))
	var grade := float(state.get("grade", 0.0))
	var dist_km := float(state.get("s", 0.0)) / 1000.0
	var gear := int(state.get("gear", 12))
	var gears_tot := int(state.get("gears_total", 24))
	
	hud_power.text = "PUISSANCE: %d W (3s: %d W)" % [int(round(p)), int(round(p3s))]
	hud_speed.text = "VITESSE: %.1f km/h  [Braquet: %d/%d]" % [v_kmh, gear, gears_tot]
	hud_cadence.text = "CADENCE: %d rpm" % int(round(cad))
	hud_grade.text = "PENTE: %.1f %%" % grade
	hud_distance.text = "DISTANCE: %.2f km" % dist_km
