extends MeshInstance3D

## Lune du ciel de nuit (lot P35, demande du 13 novembre : « Pas d'étoiles ou de lune ? ») : un disque face à la
## caméra (moon.gdshader), loin devant le décor, dans la direction de la lune de daylight_model.gd, avec sa
## phase réelle ; il paraît avec les étoiles et ne dépend pas du ciel utilisé (ciel physique ou à nuages).
## - `update(cam_pos, cycle)` une fois par image : `cycle` = dernier état de atmosphere_view.gd (vide ou
##   inactif : cachée, aucun coût).
## Pas de class_name : charger par preload("res://scripts/moon_view.gd").

const MoonShader := preload("res://shaders/moon.gdshader")
const DIST_M := 1800.0
const DIAMETER_DEG := 3.0      # six fois la vraie lune : lisible à l'écran
const MIN_STARS := 0.05

var _mat: ShaderMaterial


func _init() -> void:
	name = "Moon"
	var q := QuadMesh.new()
	var d := 2.0 * DIST_M * tan(deg_to_rad(DIAMETER_DEG * 0.5)) * 1.6   # avec le halo
	q.size = Vector2(d, d)
	mesh = q
	_mat = ShaderMaterial.new()
	_mat.shader = MoonShader
	material_override = _mat
	cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	extra_cull_margin = 16384.0
	visible = false


func update(cam_pos: Vector3, cycle: Dictionary) -> void:
	var stars := float(cycle.get("stars", 0.0)) if bool(cycle.get("active", false)) else 0.0
	var illum := float(cycle.get("moon_illumination", 0.0))
	visible = stars > MIN_STARS and illum > 0.02
	if not visible:
		return
	var dir: Vector3 = cycle.get("moon_direction", Vector3.UP)
	position = cam_pos + dir.normalized() * DIST_M   # enfant de la scène principale, à l'origine
	_mat.set_shader_parameter("illum", illum)
	_mat.set_shader_parameter("opacity", clampf(stars * 1.5, 0.0, 1.0))
