extends RefCounted

## Mode d'affichage de la fenêtre de l'engine (réglage `render.display`, argument `--display=`).
##
##   windowed    fenêtre 1280 × 720 centrée (taille de project.godot), avec bordure
##   borderless  plein écran sans bordure : fenêtre de la taille de l'écran, le compositeur reste actif
##   fullscreen  plein écran exclusif : sous X11, la fenêtre contourne le compositeur
##               (_NET_WM_BYPASS_COMPOSITOR), ce qui retire une copie d'image et sa latence
##
## Les deux pleins écrans gardent la définition native de l'écran (jamais de changement de mode vidéo,
## jamais de mise à l'échelle du rendu 3D) ; l'interface suit par l'étirement `canvas_items` de
## project.godot. La synchronisation verticale n'est pas touchée. Le bureau n'a rien à restaurer à
## la sortie : seule la fenêtre de l'engine change.
## Sans argument, l'engine reste en fenêtre : les outils de test qui lancent Godot directement
## (visual_check, sim_bench, menu_bench, run_engine_tests) gardent leur taille forcée par `--resolution`.
## Au lancement, `--display` fait foi ; la liste `settings` du core ne change la fenêtre que si la valeur
## de `render.display` y change ensuite (choix au menu), jamais à sa première réception (main.gd).
## Le curseur de la souris est masqué en séance et visible dès qu'un menu est affiché (clic des menus).
## Pas de class_name : charger par preload("res://scripts/display_mode.gd").

const WINDOWED := "windowed"
const BORDERLESS := "borderless"
const FULLSCREEN := "fullscreen"
const VALID := [WINDOWED, BORDERLESS, FULLSCREEN]
const DEFAULT := WINDOWED
## Taille de la fenêtre au retour en mode fenêtré (project.godot, viewport_width et viewport_height).
const WINDOW_SIZE := Vector2i(1280, 720)


static func is_valid(name: String) -> bool:
	return name in VALID


## Mode de DisplayServer correspondant au nom du réglage.
static func window_mode(name: String) -> DisplayServer.WindowMode:
	match name:
		BORDERLESS:
			return DisplayServer.WINDOW_MODE_FULLSCREEN
		FULLSCREEN:
			return DisplayServer.WINDOW_MODE_EXCLUSIVE_FULLSCREEN
	return DisplayServer.WINDOW_MODE_WINDOWED


## Mode de la souris : visible quand un menu est affiché, masquée en séance.
static func mouse_mode(menu_shown: bool) -> Input.MouseMode:
	return Input.MOUSE_MODE_VISIBLE if menu_shown else Input.MOUSE_MODE_HIDDEN


## Applique le mode à la fenêtre principale ; rien sans écran (--headless) ni si le mode est déjà en place.
## Renvoie vrai si la fenêtre a changé.
static func apply(name: String) -> bool:
	if DisplayServer.get_name() == "headless":
		return false
	var mode := window_mode(name)
	if DisplayServer.window_get_mode() == mode:
		return false
	DisplayServer.window_set_mode(mode)
	if mode == DisplayServer.WINDOW_MODE_WINDOWED:
		var screen := DisplayServer.window_get_current_screen()
		var area := DisplayServer.screen_get_usable_rect(screen)
		var size := Vector2i(mini(WINDOW_SIZE.x, area.size.x), mini(WINDOW_SIZE.y, area.size.y))
		DisplayServer.window_set_size(size)
		DisplayServer.window_set_position(area.position + (area.size - size) / 2)
	return true
