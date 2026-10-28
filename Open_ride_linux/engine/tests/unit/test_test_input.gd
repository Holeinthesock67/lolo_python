extends SceneTree

## Tests sans écran des entrées simulées du robot des menus (`test_input.gd`) : chaque touche du tableau du
## clavier (spécification générale §7.1) donne, par key_map.gd, l'événement de son bouton ; gestes de la souris ;
## état des menus lu par le banc (identifiants, focus, lignes).
## Lancement : godot --headless --path engine --script res://tests/unit/test_test_input.gd

const TestInput := preload("res://scripts/test_input.gd")
const KeyMap := preload("res://scripts/key_map.gd")

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


## Appui puis relâchement de la touche nommée, tenue `held_s` secondes, lu par key_map.gd comme main.gd.
func _tap(name: String, held_s: float, shift := false) -> String:
	var km = KeyMap.new()
	var down := TestInput.key_event(name, true, shift)
	var up := TestInput.key_event(name, false, shift)
	if down == null or up == null or not down.pressed or up.pressed:
		return "?"
	km.press(down.keycode, down.shift_pressed, 1.0)
	return km.release(up.keycode, 1.0 + held_s)


func _test_keys() -> void:
	var table := {
		["+", 0.15]: "PLUS_SHORT", ["+", 1.1]: "PLUS_LONG", ["+", 0.7]: "PLUS_UNCLEAR", ["=", 0.15]: "PLUS_SHORT",
		["Pavé+", 0.15]: "PLUS_SHORT", ["-", 0.15]: "MINUS_SHORT", ["-", 1.1]: "MINUS_LONG", ["Pavé-", 0.15]: "MINUS_SHORT",
		["PageHaut", 0.15]: "PLUS_LONG", ["PageBas", 0.15]: "MINUS_LONG", ["A", 0.15]: "A_SHORT", ["A", 1.1]: "A_LONG",
		["Entrée", 0.15]: "A_LONG", ["PavéEntrée", 0.15]: "A_LONG", ["Y", 0.15]: "Y_SHORT", ["Échap", 0.15]: "Y_SHORT",
		["Z", 0.15]: "Z_SHORT", ["Z", 1.1]: "Z_LONG", ["Gauche", 0.15]: "LEFT_SHORT", ["Droite", 0.15]: "RIGHT_SHORT",
		["Haut", 0.15]: "UP_SHORT", ["Bas", 0.15]: "DOWN_SHORT", ["P", 0.15]: "", ["Espace", 0.15]: "",
	}
	for k in table:
		var got := _tap(k[0], k[1])
		_check(got == table[k], "touche « %s » tenue %.2f s : %s (reçu « %s »)" % [k[0], k[1], table[k], got])
	_check(_tap("A", 0.15, true) == "A_LONG" and _tap("Z", 0.15, true) == "Z_LONG", "Maj+A et Maj+Z : appuis longs")
	_check(TestInput.key_event("Inconnue", true) == null, "touche inconnue : null")
	_check(TestInput.keycode_of("Escape") == KEY_ESCAPE, "nom de Godot accepté (Escape)")
	var a := TestInput.key_event("A", true)
	_check(a.unicode == "a".unicode_at(0) and TestInput.key_event("A", true, true).unicode == "A".unicode_at(0),
		"lettre : caractère tapé (minuscule, majuscule avec Maj), comme un vrai clavier")


func _test_mouse() -> void:
	var pos := Vector2(320, 200)
	var click := TestInput.mouse_events("left", pos)
	_check(click.size() == 3 and click[0] is InputEventMouseMotion, "clic gauche : survol, appui, relâchement")
	var down := click[1] as InputEventMouseButton
	var up := click[2] as InputEventMouseButton
	_check(down.pressed and not up.pressed and down.button_index == MOUSE_BUTTON_LEFT and down.position == pos,
		"clic gauche au point demandé")
	_check((TestInput.mouse_events("right", pos)[1] as InputEventMouseButton).button_index == MOUSE_BUTTON_RIGHT, "clic droit")
	_check((TestInput.mouse_events("wheel_down", pos)[1] as InputEventMouseButton).button_index == MOUSE_BUTTON_WHEEL_DOWN
		and (TestInput.mouse_events("wheel_up", pos)[1] as InputEventMouseButton).button_index == MOUSE_BUTTON_WHEEL_UP, "molette")
	_check(TestInput.mouse_events("move", pos).size() == 1, "survol seul")
	_check(TestInput.mouse_events("triple", pos).is_empty(), "geste inconnu : rien")


func _test_snapshot() -> void:
	var st := {"screen": "home", "title": "OpenRide", "focus": 1, "status": "", "editing": false,
		"items": [{"id": "world", "label": "Parcours : demo", "enabled": true, "detail": ""},
			{"id": "ride", "label": "Session libre", "enabled": true, "detail": "SIM"},
			{"id": "version", "label": "OpenRide", "enabled": false, "detail": ""}]}
	var snap := TestInput.menu_snapshot(st, [{"id": "ride", "focused": true, "rect": [0, 0, 10, 10]}], {"tag": "t1"})
	_check(snap["screen"] == "home" and snap["focus_id"] == "ride" and snap["tag"] == "t1", "écran, focus et étiquette")
	_check(snap["items"].size() == 3 and snap["items"][2]["enabled"] == false and snap["items"][1]["detail"] == "SIM",
		"éléments : identifiant, libellé, détail, actif")
	_check(snap["rows"][0]["id"] == "ride", "lignes affichées")
	st["focus"] = -1
	_check(TestInput.menu_snapshot(st, [], {})["focus_id"] == "", "aucun focus : identifiant vide")


func _init() -> void:
	_test_keys()
	_test_mouse()
	_test_snapshot()
	print("test_test_input : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
