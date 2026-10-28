extends Node3D

## Mur du Firewall (lot R10 §4.3) : mur translucide `danger` en travers du ruban, à `firewall_gap_m` derrière le
## joueur, qui pulse au contact (écart ≤ 0). Matériau `energy_wall` de la charte (R17).

const Materials := preload("res://scripts/rogue/neon_materials.gd")

const HEIGHT_M := 3.0
const WIDTH_M := 7.0
const PULSE_HZ := 1.5       # au plus 3 clignotements par seconde (charte §4.6)

var contact := false
var _mesh: MeshInstance3D
var _time := 0.0


func _ready() -> void:
	_mesh = MeshInstance3D.new()
	var quad := QuadMesh.new()
	quad.size = Vector2(WIDTH_M, HEIGHT_M)
	_mesh.mesh = quad
	_mesh.position.y = HEIGHT_M * 0.5
	add_child(_mesh)
	set_style("low", false)


func set_style(preset: String, adapted: bool) -> void:
	if _mesh != null:
		_mesh.material_override = Materials.wall("danger", preset, adapted)


## Place le mur à la distance `s_wall` de la salle, sur un ruban d'altitude `y`.
func place(s_wall: float, y: float, gap_m: float) -> void:
	position = Vector3(0.0, y, -s_wall)
	contact = gap_m <= 0.0


func _process(delta: float) -> void:
	_time += delta
	if _mesh == null:
		return
	var k := 1.0
	if contact:
		k = 1.0 + 0.2 * sin(_time * TAU * PULSE_HZ)
	_mesh.scale = Vector3(1.0, k, 1.0)
