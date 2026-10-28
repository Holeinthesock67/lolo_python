extends RefCounted

## Clavier = Click, touche pour touche (lot O17, décision D6 ; tableau du clavier de la spécification
## générale §7.1, seule référence), sans nœud. Traduit l'appui et le relâchement d'une touche en événement
## du Click, avec les seuils du décodeur du core (zwift_click.PressClassifier) : court sous 0,5 s, long à
## 0,9 s ou plus ; entre les deux, PLUS_UNCLEAR ou MINUS_UNCLEAR pour + et −, rien pour A et Z. Y et les
## flèches n'ont qu'un événement, quelle que soit la durée. L'événement part au relâchement, comme au Click.
##
## Synonymes de l'appui long (claviers où il est malcommode) : Page haut (+ long), Page bas (− long),
## Maj+A et Entrée (A long), Maj+Z (Z long) ; Échap vaut Y. Les lettres sont lues comme imprimées sur la
## touche (`keycode`, AZERTY comme QWERTY). Aucune touche n'a d'autre rôle que celui de son bouton.
##
## L'appelant (main.gd) fait de l'événement ce qu'il ferait de celui du Click : en menu, menu_model.gd ;
## en séance, le core par `input_event`, qui le relaie à l'engine comme un appui du Click.
## Pas de class_name : charger par preload("res://scripts/key_map.gd").

const SHORT_MAX_S := 0.5
const LONG_MIN_S := 0.9

## Touche -> bouton du Click mesuré (appui court, long ou ambigu selon la durée).
const MEASURED := {
	KEY_PLUS: "PLUS", KEY_EQUAL: "PLUS", KEY_KP_ADD: "PLUS",
	KEY_MINUS: "MINUS", KEY_KP_SUBTRACT: "MINUS",
	KEY_A: "A", KEY_Z: "Z",
}
## Touche -> événement fixe, quelle que soit la durée (Y, flèches, synonymes de l'appui long).
const FIXED := {
	KEY_Y: "Y_SHORT", KEY_ESCAPE: "Y_SHORT",
	KEY_PAGEUP: "PLUS_LONG", KEY_PAGEDOWN: "MINUS_LONG",
	KEY_ENTER: "A_LONG", KEY_KP_ENTER: "A_LONG",
	KEY_LEFT: "LEFT_SHORT", KEY_RIGHT: "RIGHT_SHORT", KEY_UP: "UP_SHORT", KEY_DOWN: "DOWN_SHORT",
}
## Avec Maj : appui long de la lettre (Maj+A, Maj+Z).
const SHIFT_LONG := {KEY_A: "A_LONG", KEY_Z: "Z_LONG"}

var _down := {}   # touche enfoncée -> {t: instant de l'appui, shift: Maj tenue à l'appui}


## Vrai si la touche double un bouton du Click.
static func is_click_key(keycode: int) -> bool:
	return MEASURED.has(keycode) or FIXED.has(keycode)


## Événement d'un appui de durée `held_s` (secondes) sur `keycode`, Maj tenue ou non ; "" sans effet.
static func event_for(keycode: int, shift: bool, held_s: float) -> String:
	if FIXED.has(keycode):
		return FIXED[keycode]
	if shift and SHIFT_LONG.has(keycode):
		return SHIFT_LONG[keycode]
	if not MEASURED.has(keycode):
		return ""
	var button: String = MEASURED[keycode]
	if held_s < SHORT_MAX_S:
		return button + "_SHORT"
	if held_s >= LONG_MIN_S:
		return button + "_LONG"
	return button + "_UNCLEAR" if button in ["PLUS", "MINUS"] else ""


## Appui (hors répétition automatique) à l'instant `t_s`. Renvoie vrai si la touche double un bouton.
func press(keycode: int, shift: bool, t_s: float) -> bool:
	if not is_click_key(keycode):
		return false
	if not _down.has(keycode):
		_down[keycode] = {"t": t_s, "shift": shift}
	return true


## Relâchement à l'instant `t_s` : événement du Click, ou "" (touche étrangère, appui non vu, zone floue de A et Z).
func release(keycode: int, t_s: float) -> String:
	if not _down.has(keycode):
		return ""
	var d: Dictionary = _down[keycode]
	_down.erase(keycode)
	return event_for(keycode, bool(d["shift"]), maxf(0.0, t_s - float(d["t"])))


## Oublie les touches enfoncées (perte du focus de la fenêtre : leur relâchement ne viendra pas).
func reset() -> void:
	_down.clear()
