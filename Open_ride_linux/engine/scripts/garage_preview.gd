extends SubViewportContainer

## Aperçu 3D du Garage (lot V8) : l'avatar équipé tourne lentement dans sa propre petite scène, à droite
## du menu (dans la carte de détail). `show_preview({settings, looks})` (garage_view_model.gd preview) ne
## reconstruit l'avatar que si les réglages ont changé ; les pièces suivent le focus de la liste.
## Ne tourne que visible. Pas de class_name : charger par preload("res://scripts/garage_preview.gd").

const AvatarView := preload("res://scripts/avatar_view.gd")

const HEIGHT_PX := 240
const TURN_RAD_PER_S := 0.7
const PEDAL_RAD_PER_S := 1.4

var viewport: SubViewport
var avatar: Node3D
var _cam: Camera3D
var _settings: Dictionary = {}
var _angle := 0.0
var _crank := 0.0


func _init() -> void:
	name = "GaragePreview"
	custom_minimum_size = Vector2(0, HEIGHT_PX)
	stretch = true
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	visible = false
	viewport = SubViewport.new()
	viewport.own_world_3d = true
	viewport.transparent_bg = true
	viewport.render_target_update_mode = SubViewport.UPDATE_WHEN_VISIBLE
	add_child(viewport)
	var env := Environment.new()
	env.background_mode = Environment.BG_CLEAR_COLOR
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.85, 0.88, 0.95)
	env.ambient_light_energy = 0.7
	var we := WorldEnvironment.new()
	we.environment = env
	viewport.add_child(we)
	var sun := DirectionalLight3D.new()
	sun.rotation = Vector3(deg_to_rad(-40.0), deg_to_rad(35.0), 0.0)
	sun.light_energy = 1.1
	viewport.add_child(sun)
	_cam = Camera3D.new()
	_cam.fov = 38.0
	viewport.add_child(_cam)
	avatar = AvatarView.new()
	viewport.add_child(avatar)
	avatar.set_visible_for_view("preview")
	visibility_changed.connect(func() -> void: set_process(is_visible_in_tree()))
	set_process(false)


func _ready() -> void:
	_cam.position = Vector3(0.0, 1.05, 3.4)
	_cam.look_at(Vector3(0.0, 0.82, 0.0), Vector3.UP)


## Réglages de l'avatar et pièces à montrer ({} : rien à changer).
func show_preview(p: Dictionary) -> void:
	if p.is_empty():
		return
	var settings: Dictionary = p["settings"]
	if settings != _settings:
		_settings = settings.duplicate()
		avatar.configure(_settings, 0)
		avatar.set_visible_for_view("preview")
	avatar.set_equipment(p["looks"])


func _process(delta: float) -> void:
	_angle = fposmod(_angle + TURN_RAD_PER_S * delta, TAU)
	_crank = fposmod(_crank + PEDAL_RAD_PER_S * delta, TAU)
	avatar.rotation.y = _angle
	avatar.apply_pose(_crank, false)


## Pour les tests : avatar affiché (look, triangles) et angle.
func test_info() -> Dictionary:
	var info: Dictionary = avatar.test_info()
	info["angle"] = _angle
	info["shown"] = is_visible_in_tree()
	return info
