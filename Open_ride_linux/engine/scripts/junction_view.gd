extends Control

## Panneau du carrefour et ligne d'attribution (lot W12) : dessine ce que `junction_view_model.gd` décrit.
## Enfant du HUD ; ne reçoit pas la souris. Pas de class_name (charger par preload).

const UiTheme := preload("res://scripts/ui_theme.gd")
const JunctionViewModel := preload("res://scripts/junction_view_model.gd")
const HudView := preload("res://scripts/hud_view.gd")

const CHOSEN_COLOR := UiTheme.PICK
const DEFAULT_COLOR := UiTheme.JUNCTION_DEFAULT
const ARROW_COLOR := UiTheme.JUNCTION_ARROW
const ATTRIBUTION_COLOR := UiTheme.ATTRIBUTION

var vm := JunctionViewModel.new()
var panel: Panel
var title_label: Label
var cells_row: HBoxContainer
var attribution_label: Label
var _signature := ""


func _init() -> void:
	set_anchors_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	panel = Panel.new()
	var style := StyleBoxFlat.new()
	style.bg_color = UiTheme.PANEL_BG
	for corner in ["top_left", "top_right", "bottom_left", "bottom_right"]:
		style.set("corner_radius_" + corner, 8)
	panel.add_theme_stylebox_override("panel", style)
	panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	panel.visible = false
	add_child(panel)
	var box := VBoxContainer.new()
	box.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT, Control.PRESET_MODE_KEEP_SIZE, 8)
	box.mouse_filter = Control.MOUSE_FILTER_IGNORE
	panel.add_child(box)
	title_label = Label.new()
	title_label.add_theme_font_size_override("font_size", 20)
	title_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	box.add_child(title_label)
	cells_row = HBoxContainer.new()
	cells_row.alignment = BoxContainer.ALIGNMENT_CENTER
	cells_row.add_theme_constant_override("separation", 10)
	cells_row.size_flags_vertical = Control.SIZE_EXPAND_FILL
	box.add_child(cells_row)
	# Attribution des données : bas de l'écran, à droite, sous le profil d'altitude (qui s'arrête à 15 px du bord).
	attribution_label = Label.new()
	attribution_label.text = JunctionViewModel.ATTRIBUTION
	attribution_label.add_theme_font_size_override("font_size", 11)
	attribution_label.add_theme_color_override("font_color", ATTRIBUTION_COLOR)
	attribution_label.anchor_left = 1.0
	attribution_label.anchor_right = 1.0
	attribution_label.anchor_top = 1.0
	attribution_label.anchor_bottom = 1.0
	attribution_label.offset_left = -320.0
	attribution_label.offset_right = -8.0
	attribution_label.offset_top = -15.0
	attribution_label.offset_bottom = -1.0
	attribution_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	attribution_label.visible = false
	attribution_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(attribution_label)


## Met l'affichage à jour. `open_world` : champ de la trame (null hors monde ouvert) ; `center_bottom` :
## bas du panneau central du HUD ; `viewport` : taille de la fenêtre.
func update_display(open_world: Variant, viewport: Vector2, center_bottom: float) -> void:
	var in_open_world := typeof(open_world) == TYPE_DICTIONARY
	attribution_label.visible = in_open_world
	vm.update(open_world.get("next") if in_open_world else null)
	var v := vm.view()
	panel.visible = bool(v["visible"])
	if not panel.visible:
		_signature = ""
		return
	var rect := JunctionViewModel.layout_for(viewport, center_bottom)
	panel.position = rect.position
	panel.size = rect.size
	var sig := JSON.stringify(v)
	if sig == _signature:
		return
	_signature = sig
	title_label.text = str(v["title"])
	title_label.add_theme_color_override("font_color", CHOSEN_COLOR if v["locked"] else UiTheme.INK)
	for child in cells_row.get_children():
		cells_row.remove_child(child)
		child.free()
	for cell in v["branches"]:
		cells_row.add_child(_make_cell(cell))


func _make_cell(cell: Dictionary) -> Control:
	var holder := PanelContainer.new()
	holder.mouse_filter = Control.MOUSE_FILTER_IGNORE
	holder.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var style := StyleBoxFlat.new()
	style.bg_color = UiTheme.JUNCTION_TILE
	var border := 3 if cell["is_chosen"] else (1 if cell["is_default"] else 0)
	for side in ["left", "top", "right", "bottom"]:
		style.set("border_width_" + side, border)
	style.border_color = CHOSEN_COLOR if cell["is_chosen"] else DEFAULT_COLOR
	for corner in ["top_left", "top_right", "bottom_left", "bottom_right"]:
		style.set("corner_radius_" + corner, 6)
	holder.add_theme_stylebox_override("panel", style)
	if cell["greyed"]:
		holder.modulate = UiTheme.JUNCTION_DIM
	var col := VBoxContainer.new()
	col.mouse_filter = Control.MOUSE_FILTER_IGNORE
	col.alignment = BoxContainer.ALIGNMENT_CENTER
	holder.add_child(col)
	var arrow := Control.new()
	arrow.custom_minimum_size = Vector2(0.0, 40.0)
	arrow.mouse_filter = Control.MOUSE_FILTER_IGNORE
	arrow.draw.connect(_draw_arrow.bind(arrow, float(cell["arrow_deg"])))
	col.add_child(arrow)
	var label := Label.new()
	label.text = str(cell["label"])
	label.add_theme_font_size_override("font_size", 14)
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	label.clip_text = true
	col.add_child(label)
	var grade := Label.new()
	grade.text = str(cell["grade_text"])
	grade.add_theme_font_size_override("font_size", 18)
	grade.add_theme_color_override("font_color", HudView.GRADE_COLORS.get(cell["grade_class"], HudView.COLOR_FLAT))
	grade.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	col.add_child(grade)
	return holder


## Flèche vers le haut (tout droit) tournée de `angle_deg` vers la droite.
func _draw_arrow(canvas: Control, angle_deg: float) -> void:
	var c := canvas.size * 0.5
	var r := minf(canvas.size.y, 40.0) * 0.45
	var a := deg_to_rad(angle_deg)
	var dir := Vector2(sin(a), -cos(a))
	var side := Vector2(-dir.y, dir.x)
	var tip := c + dir * r
	var tail := c - dir * r
	canvas.draw_line(tail, tip - dir * r * 0.5, ARROW_COLOR, 4.0)
	canvas.draw_colored_polygon(PackedVector2Array([tip, tip - dir * r * 0.7 + side * r * 0.5,
		tip - dir * r * 0.7 - side * r * 0.5]), ARROW_COLOR)
