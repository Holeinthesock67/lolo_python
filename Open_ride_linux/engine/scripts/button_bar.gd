extends PanelContainer

## Bandeau des boutons en bas des menus (lot « présentation des menus », étape 1) : touches du Click
## dessinées en pastilles, appui long marqué d'un anneau, action principale (valider) en tête et en
## couleur de sélection, double légende (une ligne pour le Click, une pour le clavier). Ne décide rien :
## affiche button_help.gd. Pas de class_name : charger par preload("res://scripts/button_bar.gd").

const UiTheme := preload("res://scripts/ui_theme.gd")
const UiIcons := preload("res://scripts/ui_icons.gd")
const ButtonHelp := preload("res://scripts/button_help.gd")

var _rows: VBoxContainer
var _screen := "-"


func _init() -> void:
	name = "ButtonBar"
	add_theme_stylebox_override("panel", UiTheme.help_style())
	custom_minimum_size.y = UiTheme.HELP_H
	_rows = VBoxContainer.new()
	_rows.add_theme_constant_override("separation", 4)
	add_child(_rows)


## Aide affichée en une ligne (tests graphiques).
func text() -> String:
	return ButtonHelp.text(_screen)


func update_display(screen: String) -> void:
	if screen == _screen:
		return
	_screen = screen
	for c in _rows.get_children():
		_rows.remove_child(c)
		c.queue_free()
	_rows.add_child(_line(ButtonHelp.CLICK_TITLE, screen, false))
	_rows.add_child(_line(ButtonHelp.KEYBOARD_TITLE, screen, true))


## Une ligne de la double légende : titre, puis une pastille ou plus et l'action de chaque entrée. Ligne
## du Click : boutons du boîtier, appui long marqué d'un anneau ; ligne du clavier : touches (A maintenu
## = Entrée, B = « − », Y = Échap).
func _line(title: String, screen: String, keyboard: bool) -> HBoxContainer:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 22)
	var t := UiTheme.label(UiTheme.SMALL_SIZE, UiTheme.DIM, title)
	t.custom_minimum_size.x = 70
	t.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	row.add_child(t)
	for e in ButtonHelp.entries(screen):
		if (e["kb"] if keyboard else e["keys"]).is_empty():
			continue   # entrée de l'autre ligne seulement (menu du monde ouvert)
		var group := HBoxContainer.new()
		group.add_theme_constant_override("separation", 8)
		for k in (e["kb"] if keyboard else e["keys"]):
			group.add_child(_keycap(str(k), bool(e["main"])))
		if e["hold"] and not keyboard:
			var ring := Control.new()
			ring.custom_minimum_size = Vector2(22, 22)
			ring.size_flags_vertical = Control.SIZE_SHRINK_CENTER
			ring.draw.connect(func() -> void: UiIcons.draw(ring, "hold", Rect2(Vector2.ZERO, ring.size), UiTheme.FOCUS, 3.0))
			group.add_child(ring)
		var words := ("maintenir : " if e["hold"] and not keyboard else "") + str(e["text"])
		var lbl := UiTheme.label(UiTheme.HELP_SIZE, UiTheme.TEXT if e["main"] else UiTheme.DIM, words)
		lbl.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		group.add_child(lbl)
		row.add_child(group)
	return row


func _keycap(letter: String, accent: bool) -> PanelContainer:
	var cap := PanelContainer.new()
	cap.add_theme_stylebox_override("panel", UiTheme.keycap_style(accent))
	cap.custom_minimum_size = Vector2(30, 30)
	cap.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	var l := UiTheme.label(16, UiTheme.FOCUS if accent else UiTheme.TEXT, letter)
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	l.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	cap.add_child(l)
	return cap
