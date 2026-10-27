extends PanelContainer

## Bandeau des boutons en bas des menus (lot « présentation des menus », étape 1) : touches du Click
## dessinées en pastilles, appui long marqué d'un anneau, action principale (valider) en tête et en
## couleur de sélection, rappel du clavier à droite, coupé en dernier si la place manque. Ne décide rien :
## affiche button_help.gd. Pas de class_name : charger par preload("res://scripts/button_bar.gd").

const UiTheme := preload("res://scripts/ui_theme.gd")
const UiIcons := preload("res://scripts/ui_icons.gd")
const ButtonHelp := preload("res://scripts/button_help.gd")

var _row: HBoxContainer
var _screen := "-"
var keyboard_label: Label


func _init() -> void:
	name = "ButtonBar"
	add_theme_stylebox_override("panel", UiTheme.help_style())
	custom_minimum_size.y = UiTheme.HELP_H
	_row = HBoxContainer.new()
	_row.add_theme_constant_override("separation", 22)
	_row.alignment = BoxContainer.ALIGNMENT_BEGIN
	add_child(_row)


## Aide affichée en une ligne (tests graphiques).
func text() -> String:
	return ButtonHelp.text(_screen)


func update_display(screen: String) -> void:
	if screen == _screen:
		return
	_screen = screen
	for c in _row.get_children():
		_row.remove_child(c)
		c.queue_free()
	for e in ButtonHelp.entries(screen):
		var group := HBoxContainer.new()
		group.add_theme_constant_override("separation", 8)
		for k in e["keys"]:
			group.add_child(_keycap(str(k), bool(e["main"])))
		if e["hold"]:
			var ring := Control.new()
			ring.custom_minimum_size = Vector2(26, 26)
			ring.size_flags_vertical = Control.SIZE_SHRINK_CENTER
			ring.draw.connect(func() -> void: UiIcons.draw(ring, "hold", Rect2(Vector2.ZERO, ring.size), UiTheme.FOCUS, 3.0))
			group.add_child(ring)
		var words := ("maintenir : " if e["hold"] else "") + str(e["text"])
		var lbl := UiTheme.label(UiTheme.HELP_SIZE, UiTheme.TEXT if e["main"] else UiTheme.DIM, words)
		lbl.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		group.add_child(lbl)
		_row.add_child(group)
	keyboard_label = UiTheme.label(UiTheme.SMALL_SIZE, UiTheme.DIM, ButtonHelp.KEYBOARD)
	keyboard_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	keyboard_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	keyboard_label.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	keyboard_label.clip_text = true
	keyboard_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_row.add_child(keyboard_label)


func _keycap(letter: String, accent: bool) -> PanelContainer:
	var cap := PanelContainer.new()
	cap.add_theme_stylebox_override("panel", UiTheme.keycap_style(accent))
	cap.custom_minimum_size = Vector2(38, 38)
	cap.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	var l := UiTheme.label(20, UiTheme.FOCUS if accent else UiTheme.TEXT, letter)
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	l.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	cap.add_child(l)
	return cap
