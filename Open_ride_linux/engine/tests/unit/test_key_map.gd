extends SceneTree

## Tests sans écran du clavier = Click `key_map.gd` (lot O17) : chaque ligne du tableau du clavier de la
## spécification générale §7.1, les seuils d'appui et la zone floue.
## Lancement : godot --headless --path engine --script res://tests/unit/test_key_map.gd

const KeyMap := preload("res://scripts/key_map.gd")

const SHORT := 0.2
const UNCLEAR := 0.7
const LONG := 1.0

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


## Appui puis relâchement après `held_s` secondes : événement produit.
func _tap(km, keycode: int, held_s: float, shift := false) -> String:
	km.press(keycode, shift, 10.0)
	return km.release(keycode, 10.0 + held_s)


func _test_table() -> void:
	var km = KeyMap.new()
	# Ligne « + » : +, = et + du pavé numérique ; appui long aussi par Page haut.
	for k in [KEY_PLUS, KEY_EQUAL, KEY_KP_ADD]:
		_check(_tap(km, k, SHORT) == "PLUS_SHORT" and _tap(km, k, LONG) == "PLUS_LONG", "touche %d : + court et long" % k)
	_check(_tap(km, KEY_PAGEUP, SHORT) == "PLUS_LONG", "Page haut : + long, même bref")
	# Ligne « − ou B » : − et − du pavé numérique ; appui long aussi par Page bas.
	for k in [KEY_MINUS, KEY_KP_SUBTRACT]:
		_check(_tap(km, k, SHORT) == "MINUS_SHORT" and _tap(km, k, LONG) == "MINUS_LONG", "touche %d : − court et long" % k)
	_check(_tap(km, KEY_PAGEDOWN, SHORT) == "MINUS_LONG", "Page bas : − long, même bref")
	# Ligne A : A ; appui long aussi par Maj+A et Entrée.
	_check(_tap(km, KEY_A, SHORT) == "A_SHORT" and _tap(km, KEY_A, LONG) == "A_LONG", "A court et long")
	_check(_tap(km, KEY_A, SHORT, true) == "A_LONG", "Maj+A : A long")
	_check(_tap(km, KEY_ENTER, SHORT) == "A_LONG" and _tap(km, KEY_KP_ENTER, SHORT) == "A_LONG", "Entrée : A long (valider)")
	# Ligne Y : Y ; Échap vaut Y court ; pas d'appui long.
	_check(_tap(km, KEY_Y, SHORT) == "Y_SHORT" and _tap(km, KEY_Y, LONG) == "Y_SHORT", "Y : un seul événement")
	_check(_tap(km, KEY_ESCAPE, SHORT) == "Y_SHORT", "Échap : Y court")
	# Ligne Z : Z ; appui long aussi par Maj+Z.
	_check(_tap(km, KEY_Z, SHORT) == "Z_SHORT" and _tap(km, KEY_Z, LONG) == "Z_LONG", "Z court et long")
	_check(_tap(km, KEY_Z, SHORT, true) == "Z_LONG", "Maj+Z : Z long")
	# Ligne des flèches : flèches du clavier, un seul événement chacune.
	var arrows := {KEY_LEFT: "LEFT_SHORT", KEY_RIGHT: "RIGHT_SHORT", KEY_UP: "UP_SHORT", KEY_DOWN: "DOWN_SHORT"}
	var arrows_ok := true
	for k in arrows:
		arrows_ok = arrows_ok and _tap(km, k, SHORT) == arrows[k] and _tap(km, k, LONG) == arrows[k]
	_check(arrows_ok, "flèches : celles du Click ; haut et bas ne font plus le braquet")
	# Aucune autre touche : P, Espace, Tab, Retour arrière, B n'ont pas de rôle.
	var others_ok := true
	for k in [KEY_P, KEY_SPACE, KEY_TAB, KEY_BACKSPACE, KEY_B, KEY_Q]:
		others_ok = others_ok and not KeyMap.is_click_key(k) and _tap(km, k, SHORT) == ""
	_check(others_ok, "P, Espace, Tab, Retour arrière, B : aucune action")


func _test_thresholds() -> void:
	var km = KeyMap.new()
	_check(_tap(km, KEY_PLUS, 0.49) == "PLUS_SHORT", "0,49 s : court")
	_check(_tap(km, KEY_PLUS, 0.5) == "PLUS_UNCLEAR", "0,5 s : zone floue")
	_check(_tap(km, KEY_MINUS, 0.89) == "MINUS_UNCLEAR", "0,89 s : zone floue")
	_check(_tap(km, KEY_MINUS, 0.9) == "MINUS_LONG", "0,9 s : long")
	_check(_tap(km, KEY_A, UNCLEAR) == "" and _tap(km, KEY_Z, UNCLEAR) == "", "A et Z dans la zone floue : rien")
	# Maj lue à l'appui : la relâcher avant la lettre ne change rien.
	km.press(KEY_A, true, 1.0)
	_check(km.release(KEY_A, 1.1) == "A_LONG", "Maj tenue à l'appui : A long")
	# Relâchement sans appui vu (touche tapée dans la recherche, focus perdu) : rien.
	_check(km.release(KEY_PLUS, 2.0) == "", "relâchement sans appui : rien")
	km.press(KEY_PLUS, false, 3.0)
	km.reset()
	_check(km.release(KEY_PLUS, 3.1) == "", "après reset (perte du focus) : rien")
	# Un second appui sans relâchement (répétition non filtrée) garde l'instant du premier.
	km.press(KEY_PLUS, false, 4.0)
	km.press(KEY_PLUS, false, 4.8)
	_check(km.release(KEY_PLUS, 5.0) == "PLUS_LONG", "durée mesurée depuis le premier appui")
	_check(not km.press(KEY_SPACE, false, 6.0), "touche étrangère : press renvoie faux")


func _init() -> void:
	_test_table()
	_test_thresholds()
	print("test_key_map : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
