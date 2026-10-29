extends Node3D

## Jauge d'abri au-dessus du bot qui t'abrite (maquette C validée le 29 octobre) : un arc tourné vers le haut,
## rempli selon l'abri, au-dessus du nom du bot (bots_view.gd) ; « 30 % » dessous en medium et high, halo en
## high. Un seul quad (draft_gauge.gdshader) et une étiquette pour toute la scène : la jauge suit le bot
## `draft_bot` du core, il n'y en a jamais deux. Ne décide rien : affiche la sortie de draft_gauge_model.gd.
## Pas de class_name : charger par preload("res://scripts/draft_gauge.gd").

const UiTheme := preload("res://scripts/ui_theme.gd")
const GaugeShader := preload("res://shaders/draft_gauge.gdshader")

const HEIGHT_M := 2.55        # au-dessus du nom du bot (bots_view.gd NAME_HEIGHT_M = 2,1)
const SIZE_M := Vector2(0.8, 0.5)
const TEXT_DROP_M := 0.12     # texte sous le haut de l'arc, au milieu

var _quad: MeshInstance3D
var _mat: ShaderMaterial
var _label: Label3D
var _view: Dictionary = {}


func _init() -> void:
	name = "DraftGauge"
	visible = false
	var mesh := QuadMesh.new()
	mesh.size = SIZE_M
	_mat = ShaderMaterial.new()
	_mat.shader = GaugeShader
	_mat.set_shader_parameter("size_m", SIZE_M)
	var c: Color = UiTheme.DRAFT
	_mat.set_shader_parameter("fill_color", Color(c.r, c.g, c.b, 1.0).lightened(0.15))
	_mat.render_priority = 1
	_quad = MeshInstance3D.new()
	_quad.mesh = mesh
	_quad.material_override = _mat
	_quad.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(_quad)
	_label = Label3D.new()
	_label.name = "Pct"
	_label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	_label.position = Vector3(0.0, -TEXT_DROP_M, 0.0)
	_label.font_size = 40
	_label.pixel_size = 0.004
	_label.outline_size = 10
	_label.modulate = UiTheme.TEXT
	_label.render_priority = 2
	add_child(_label)


## `view` : sortie de draft_gauge_model.gd ; `anchor` : position du bot dans le monde (bots_view.gd
## anchor_of()), null si le bot n'est pas affiché.
func update_view(view: Dictionary, anchor: Variant) -> void:
	_view = view
	if not bool(view.get("visible", false)) or not (anchor is Vector3):
		visible = false
		return
	global_position = anchor + Vector3.UP * HEIGHT_M
	_mat.set_shader_parameter("fill", float(view["fill"]))
	_mat.set_shader_parameter("glow", 1.0 if view["glow"] else 0.0)
	_label.text = str(view["text"])
	_label.visible = _label.text != ""
	visible = true


## Pour les tests graphiques : état affiché et point haut de l'arc dans l'image.
func test_info(camera: Camera3D) -> Dictionary:
	var out := {"visible": visible, "bot": str(_view.get("bot", "")), "fill": float(_view.get("fill", 0.0)),
		"text": _label.text if visible and _label.visible else "", "glow": bool(_view.get("glow", false)),
		"on_screen": false, "point": []}
	if visible and camera != null and not camera.is_position_behind(global_position):
		var pt := camera.unproject_position(global_position)
		out["point"] = [pt.x, pt.y]
		out["on_screen"] = camera.get_viewport().get_visible_rect().has_point(pt)
	return out
