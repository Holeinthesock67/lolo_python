extends SceneTree

## Tests sans écran de la souris dans les menus `menu_view.gd` : clic gauche sur un élément,
## clic droit et molette sur le panneau.
## Lancement : godot --headless --path engine --script res://tests/unit/test_menu_view_mouse.gd

const MenuView := preload("res://scripts/menu_view.gd")

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _click(button: MouseButton) -> InputEventMouseButton:
	var e := InputEventMouseButton.new()
	e.button_index = button
	e.pressed = true
	return e


func _initialize() -> void:
	var v = MenuView.new()
	root.add_child(v)
	var items := []
	for i in range(12):
		items.append({"id": "it%d" % i, "label": "Élément %d" % i, "enabled": true})
	var menu := {"screen": "routes", "title": "Parcours", "focus": 7, "items": items}
	v.update_display(menu, {}, {}, false)
	var clicked: Array[String] = []
	var events: Array[String] = []
	v.item_clicked.connect(func(id: String) -> void: clicked.append(id))
	v.mouse_event.connect(func(ev: String) -> void: events.append(ev))
	# Focus sur le 8e élément : la fenêtre de 9 éléments (MAX_VISIBLE_ITEMS) commence au 4e (it3).
	v._item_panels[0].gui_input.emit(_click(MOUSE_BUTTON_LEFT))
	v._item_panels[4].gui_input.emit(_click(MOUSE_BUTTON_LEFT))
	_check(clicked == ["it3", "it7"], "clic gauche : identifiant de l'élément affiché, fenêtre décalée comprise")
	var release := _click(MOUSE_BUTTON_LEFT)
	release.pressed = false
	v._item_panels[1].gui_input.emit(release)
	_check(clicked.size() == 2, "relâchement du bouton : rien")
	v.gui_input.emit(_click(MOUSE_BUTTON_RIGHT))
	v.gui_input.emit(_click(MOUSE_BUTTON_WHEEL_UP))
	v.gui_input.emit(_click(MOUSE_BUTTON_WHEEL_DOWN))
	v.gui_input.emit(_click(MOUSE_BUTTON_LEFT))
	_check(events == ["Y_SHORT", "MINUS_SHORT", "PLUS_SHORT"],
		"clic droit = retour, molette haut = précédent, molette bas = suivant, clic gauche hors élément : rien")
	_check(v.button_bar.visible and v.hint_text().begins_with("A maintenir : Valider") and v.hint_text().contains("Y : Retour"),
		"aide visible sur la liste : A maintenu pour valider, Y pour revenir (%s)" % v.hint_text())
	v.update_display({"screen": "home", "title": "OpenRide", "focus": 0, "items": items}, {}, {}, false)
	_check(v.button_bar.visible and v.devices.visible and not v.hint_text().contains("Y :"),
		"accueil : aide visible avec les appareils, sans Y (rien à quitter)")
	v.update_display({"screen": "pause", "title": "Pause", "focus": 0, "items": items}, {}, {}, false)
	_check(v.hint_text().contains("Y : Reprendre"), "pause : Y pour reprendre")
	print("test_menu_view_mouse : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
