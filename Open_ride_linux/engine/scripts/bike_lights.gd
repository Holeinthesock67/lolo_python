extends Node3D

## Éclairage du vélo du joueur (lot P35) : un vrai projecteur blanc devant le vélo (SpotLight3D, sans ombre),
## qui éclaire la route la nuit, et une petite lueur rouge derrière (OmniLight3D de courte portée). Le phare
## et le feu dessinés sur le vélo sont ceux de avatar_view.gd (NightLights.bike_lamps_mesh) ; ce nœud ne porte
## que les lumières, pour rester allumé en vue subjective où l'avatar est caché.
## - `place(pos, basis)` une fois par image : posé comme l'avatar ; énergie selon NightLights.current, éteint
##   (nœuds cachés, aucun coût de rendu) de jour et quand le jour et la nuit est coupé.
## Pas de class_name : charger par preload("res://scripts/bike_lights.gd").

const NightLights := preload("res://scripts/night_lights.gd")

const SPOT_ENERGY := 6.0
const SPOT_RANGE_M := 45.0
const SPOT_ANGLE_DEG := 26.0
const SPOT_PITCH_DEG := -6.0     # vers la route, devant
const REAR_ENERGY := 0.12
const REAR_RANGE_M := 1.6

var spot: SpotLight3D
var rear: OmniLight3D


func _init() -> void:
	name = "BikeLights"
	spot = SpotLight3D.new()
	spot.name = "Headlight"
	spot.light_color = NightLights.FRONT_COLOR
	spot.spot_range = SPOT_RANGE_M
	spot.spot_angle = SPOT_ANGLE_DEG
	spot.spot_angle_attenuation = 0.8
	spot.spot_attenuation = 1.2
	spot.shadow_enabled = false
	spot.position = NightLights.BIKE_FRONT_LAMP + Vector3(0.0, 0.0, -0.04)
	spot.rotation = Vector3(deg_to_rad(SPOT_PITCH_DEG), 0.0, 0.0)
	add_child(spot)
	rear = OmniLight3D.new()
	rear.name = "Taillight"
	rear.light_color = NightLights.REAR_COLOR
	rear.omni_range = REAR_RANGE_M
	rear.shadow_enabled = false
	rear.position = NightLights.BIKE_REAR_LAMP + Vector3(0.0, 0.0, 0.05)
	add_child(rear)
	_set_level(0.0)


func place(pos: Vector3, rot: Vector3) -> void:
	_set_level(NightLights.current)
	if not visible:
		return
	position = pos
	rotation = rot


func _set_level(g: float) -> void:
	visible = g > 0.0
	spot.light_energy = SPOT_ENERGY * g
	rear.light_energy = REAR_ENERGY * g
