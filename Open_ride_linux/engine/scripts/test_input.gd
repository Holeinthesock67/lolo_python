extends RefCounted

## Entrées simulées et état des menus pour le banc des menus (`engine/tests/menu_robot.py`), sans nœud.
##
## Le banc envoie, en mode test (`--test-mode`), des messages `_test` : « key » (appui ou relâchement d'une
## touche), « mouse » (clic, clic droit, molette, survol) et « menu_state ». main.gd fabrique ici les
## événements de Godot et les injecte par Input.parse_input_event : ils suivent alors le même chemin qu'une
## vraie touche ou une vraie souris (_unhandled_input et key_map.gd, gui_input de menu_view.gd), durée
## d'appui comprise. Les touches portent les noms de KEYS (ceux du tableau du clavier de la spécification
## générale §7.1), sinon le nom de Godot (OS.find_keycode_from_string).
## Pas de class_name : charger par preload("res://scripts/test_input.gd").

## Nom de touche du banc -> code de touche de Godot.
const KEYS := {
	"A": KEY_A, "Z": KEY_Z, "Y": KEY_Y, "B": KEY_B, "P": KEY_P, "Espace": KEY_SPACE,
	"+": KEY_PLUS, "=": KEY_EQUAL, "Pavé+": KEY_KP_ADD, "-": KEY_MINUS, "Pavé-": KEY_KP_SUBTRACT,
	"PageHaut": KEY_PAGEUP, "PageBas": KEY_PAGEDOWN, "Entrée": KEY_ENTER, "PavéEntrée": KEY_KP_ENTER,
	"Échap": KEY_ESCAPE, "Gauche": KEY_LEFT, "Droite": KEY_RIGHT, "Haut": KEY_UP, "Bas": KEY_DOWN,
}
## Gestes de la souris -> bouton de Godot (« move » : survol seul).
const MOUSE_BUTTONS := {"left": MOUSE_BUTTON_LEFT, "right": MOUSE_BUTTON_RIGHT,
	"wheel_up": MOUSE_BUTTON_WHEEL_UP, "wheel_down": MOUSE_BUTTON_WHEEL_DOWN, "move": MOUSE_BUTTON_NONE}


## Code de touche d'un nom (KEYS, sinon nom de Godot) ; KEY_NONE si inconnu.
static func keycode_of(name: String) -> int:
	if KEYS.has(name):
		return KEYS[name]
	return OS.find_keycode_from_string(name)


## Appui ou relâchement de la touche `name` ; null si le nom est inconnu.
static func key_event(name: String, pressed: bool, shift := false) -> InputEventKey:
	var code := keycode_of(name)
	if code == KEY_NONE:
		return null
	var ev := InputEventKey.new()
	ev.keycode = code
	ev.physical_keycode = code
	ev.pressed = pressed
	ev.shift_pressed = shift
	if pressed and code >= KEY_SPACE and code < 127:
		ev.unicode = code if shift else String.chr(code).to_lower().unicode_at(0)
	return ev


## Événements d'un geste de la souris en `pos` (pixels de la fenêtre) : survol, puis appui et relâchement
## du bouton ; [] si le geste est inconnu.
static func mouse_events(kind: String, pos: Vector2) -> Array:
	if not MOUSE_BUTTONS.has(kind):
		return []
	var move := InputEventMouseMotion.new()
	move.position = pos
	move.global_position = pos
	var out: Array = [move]
	if kind == "move":
		return out
	for pressed in [true, false]:
		var b := InputEventMouseButton.new()
		b.button_index = MOUSE_BUTTONS[kind]
		b.pressed = pressed
		b.position = pos
		b.global_position = pos
		b.button_mask = MOUSE_BUTTON_MASK_LEFT if kind == "left" and pressed else 0
		if kind.begins_with("wheel"):
			b.factor = 1.0
		out.append(b)
	return out


## État des menus pour le banc : écran, titre, élément du focus, éléments (id, libellé, détail, actif), lignes
## affichées avec leur rectangle en pixels de la fenêtre (`rows` : [{id, rect, focused}]) et `extra`.
static func menu_snapshot(st: Dictionary, rows: Array, extra: Dictionary) -> Dictionary:
	var items: Array = []
	for it in st.get("items", []):
		var e := {"id": str(it.get("id", "")), "label": str(it.get("label", "")),
			"detail": str(it.get("detail", "")), "enabled": bool(it.get("enabled", true))}
		if it.has("editing"):
			e["editing"] = it["editing"]
		items.append(e)
	var focus := int(st.get("focus", -1))
	var out := {"screen": str(st.get("screen", "")), "title": str(st.get("title", "")), "focus": focus,
		"focus_id": items[focus]["id"] if focus >= 0 and focus < items.size() else "",
		"items": items, "status": str(st.get("status", "")), "editing": bool(st.get("editing", false)),
		"rows": rows}
	out.merge(extra)
	return out
