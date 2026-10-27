extends HBoxContainer

## État des appareils dans les menus (Lot N6 ; pastilles du lot « présentation des menus ») : une
## pastille par appareil (trainer, boîtiers du Click, ceinture) avec un point de la couleur du niveau,
## l'état écrit seulement quand il n'est pas « prêt », puis la pastille « prêt à rouler » à droite.
## Ne calcule rien : lit devices_view_model.gd (lot N5) ; couleurs du thème commun (ui_theme.gd).
## Pas de class_name : charger par preload("res://scripts/devices_view.gd").

const DevicesViewModel := preload("res://scripts/devices_view_model.gd")
const UiTheme := preload("res://scripts/ui_theme.gd")

const LEVEL_COLORS := {
	DevicesViewModel.LEVEL_OK: UiTheme.OK,
	DevicesViewModel.LEVEL_WARN: UiTheme.WARN,
	DevicesViewModel.LEVEL_ERROR: UiTheme.DANGER,
	DevicesViewModel.LEVEL_OFF: UiTheme.DIM,
}

var model = DevicesViewModel.new()
## Lignes « appareil : état » du dernier affichage, et raison de prêt (tests graphiques).
var _lines: Array[String] = []
var _chips: Array[PanelContainer] = []
var _spacer: Control
var ready_label: Label
var _ready_chip: PanelContainer
var _ready_styles := {true: UiTheme.chip_style(Color(UiTheme.OK, 0.5)), false: UiTheme.chip_style(Color(UiTheme.DANGER, 0.5))}


func _init() -> void:
	add_theme_constant_override("separation", 10)
	custom_minimum_size.y = UiTheme.CHIPS_H
	clip_contents = true
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	_spacer = Control.new()
	_spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	add_child(_spacer)
	_ready_chip = _chip()
	ready_label = _ready_chip.get_child(0).get_child(1)
	add_child(_ready_chip)


## Texte affiché, une ligne par appareil (tests graphiques).
func text() -> String:
	var parts: Array[String] = _lines.duplicate()
	if ready_label.text != "":
		parts.append(ready_label.text)
	return " | ".join(parts)


func update_display(state: Dictionary) -> void:
	var rows: Array = model.rows(state)
	while _chips.size() < rows.size():
		var c := _chip()
		add_child(c)
		move_child(c, _chips.size())
		_chips.append(c)
	_lines.clear()
	for i in range(_chips.size()):
		var c := _chips[i]
		c.visible = i < rows.size()
		if not c.visible:
			continue
		var r: Dictionary = rows[i]
		var level := str(r.get("level", ""))
		var line := "%s : %s" % [r.get("label", ""), r.get("status_text", "")]
		_lines.append(line)
		_set_chip(c, line if level != DevicesViewModel.LEVEL_OK else str(r.get("label", "")), LEVEL_COLORS.get(level, UiTheme.TEXT), level)
	var ready: Dictionary = model.ready_to_ride(state)
	var ok: bool = ready.get("ok", false)
	_set_chip(_ready_chip, str(ready.get("reason", "")), UiTheme.OK if ok else UiTheme.DANGER,
		DevicesViewModel.LEVEL_OK if ok else DevicesViewModel.LEVEL_ERROR)
	_ready_chip.add_theme_stylebox_override("panel", _ready_styles[ok])
	_ready_chip.visible = ready_label.text != ""


func _chip() -> PanelContainer:
	var c := PanelContainer.new()
	c.mouse_filter = Control.MOUSE_FILTER_IGNORE
	c.add_theme_stylebox_override("panel", UiTheme.chip_style())
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 8)
	c.add_child(row)
	var dot := Control.new()
	dot.custom_minimum_size = Vector2(12, 12)
	dot.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	dot.mouse_filter = Control.MOUSE_FILTER_IGNORE
	dot.draw.connect(func() -> void:
		var col: Color = dot.get_meta("color", UiTheme.DIM)
		var centre := dot.size / 2.0
		if dot.get_meta("filled", true):
			dot.draw_circle(centre, 5.5, col)
		else:
			dot.draw_arc(centre, 4.5, 0.0, TAU, 16, col, 2.0, true))
	row.add_child(dot)
	var l := UiTheme.label(UiTheme.CHIP_SIZE)
	l.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	row.add_child(l)
	return c


## Point plein sauf appareil absent (cercle vide) ; texte en couleur secondaire s'il est absent.
func _set_chip(c: PanelContainer, words: String, color: Color, level: String) -> void:
	var row: HBoxContainer = c.get_child(0)
	var dot: Control = row.get_child(0)
	var l: Label = row.get_child(1)
	l.text = words
	l.add_theme_color_override("font_color", UiTheme.DIM if level == DevicesViewModel.LEVEL_OFF else
		(color if c == _ready_chip else UiTheme.TEXT))
	dot.set_meta("color", color)
	dot.set_meta("filled", level != DevicesViewModel.LEVEL_OFF)
	dot.queue_redraw()
