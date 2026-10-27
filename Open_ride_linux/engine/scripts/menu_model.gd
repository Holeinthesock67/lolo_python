extends RefCounted

## Navigation des menus au Click et au clavier (Lot K5, SRS §4.5 et §7, Contrat IPC v1 §4), sans nœud.
##
## Machine à états pure : écrans décrits par des données, focus, validation, retour et confirmation.
## Elle n'envoie rien : `handle()` renvoie l'état et, le cas échéant, une action à exécuter par
## l'appelant (commande IPC ou action interne à l'engine). L'affichage et les listes réelles (contrat
## IPC v1.1) restent au lot G. Pas de class_name : charger par preload("res://scripts/menu_model.gd").
##
## Entrées (mêmes noms que l'IPC) : PLUS_SHORT (suivant), MINUS_SHORT (précédent), PLUS_LONG (valider),
## MINUS_LONG (retour). Le clavier s'y ramène par key_to_event(). Tout autre événement est ignoré.
##
## Règles : le focus saute les éléments désactivés et boucle en fin de liste ; valider un élément
## désactivé ne fait rien ; une action destructrice (Abandonner, Quitter) passe par l'écran de
## confirmation, focus sur « Non » ; une liste vide affiche un élément désactivé et le retour reste possible.
##
## Actions renvoyées ({"action": nom, …}) : noms des commandes du contrat v1 quand elles existent
## (select_route + route_id, select_workout + workout_id, start, resume, end_session + save), sinon
## internes à l'engine (quit ; relaunch_sim et relaunch : relancer OpenRide en session simulée ou sur le
## vrai matériel). Une action ouvre au besoin l'écran suivant dans le même appel.
##
## Accueil (menu principal, demande du 26 octobre) : « Parcours : … » (choix du parcours, retour à
## l'accueil), « Session libre » (SIM, sans entraînement), « Session ERG » (choix de l'entraînement),
## « Session simulée » (OpenRide relancé sans matériel ; en session simulée : « Revenir au matériel
## réel »), « Réglages », « Quitter ». Sans monde choisi, les sessions passent d'abord par les parcours.
## Écrans ajoutés par add_screen() (bilan de fin du lot N4) : valider un élément renvoie
## {"action": "item", "screen": écran, "id": élément}, à traiter par l'appelant (menu_flow.gd, lot N6).

const EVENTS := ["PLUS_SHORT", "MINUS_SHORT", "PLUS_LONG", "MINUS_LONG"]

const HOME := "home"
const ROUTES := "routes"
const WORKOUTS := "workouts"
const READY := "ready"
const SETTINGS := "settings"
const CONFIRM := "confirm"
const PAUSE := "pause"

const NO_WORKOUT_ID := "_sim"
## Modes de séance de l'accueil, dans l'ordre d'affichage : {mode: libellé}. Filtrés par `modes`, la
## liste que le core annoncera dans hello_ack.config (2.0, PLAN_SERIE_R §6) ; absente : DEFAULT_MODES.
## Un nouveau mode (Cyber-Rogue) n'ajoute qu'une ligne ici.
const HOME_MODES := {"ride": "Session libre", "erg": "Session ERG"}
const DEFAULT_MODES := ["ride", "erg"]

var _screens: Dictionary = {}
var _stack: Array[String] = []      # écrans précédents, pour le retour
var _focus_stack: Array[int] = []   # focus de chacun, rendu au retour
var _screen: String = HOME
var _focus: int = 0
var _pending: Dictionary = {}       # action destructrice en attente de confirmation
var _confirm_back: String = ""      # écran où revenir après « Non »
var _confirm_focus: int = 0
var _workouts_return: String = ROUTES
## Parcours choisi : id et nom ; "" tant qu'aucun n'est choisi.
var world_id := ""
var world_name := ""
## Mode de la séance préparée : "free" (session libre, SIM) ou "erg".
var mode := "free"
## Engine lancé en session simulée (--sim-session) : l'accueil propose de revenir au matériel réel.
var sim_session := false
var _routes_return := HOME
## Modes annoncés par le core (set_modes) ; les modes inconnus de HOME_MODES sont ignorés.
var modes: Array = DEFAULT_MODES.duplicate()


func _init() -> void:
	_screens = {
		HOME: {"id": HOME, "title": "OpenRide", "on_back": "", "items": []},
		ROUTES: {"id": ROUTES, "title": "Parcours", "on_back": HOME, "items": []},
		WORKOUTS: {"id": WORKOUTS, "title": "Session ERG : entraînement", "on_back": HOME, "items": []},
		READY: {"id": READY, "title": "Prêt", "on_back": HOME, "items": []},
		SETTINGS: {"id": SETTINGS, "title": "Réglages", "on_back": HOME, "items": [
			_item("devices", "Appareils : rechercher et appairer")]},
		CONFIRM: {"id": CONFIRM, "title": "Confirmer", "on_back": "", "items": [
			_item("no", "Non"), _item("yes", "Oui")]},
		PAUSE: {"id": PAUSE, "title": "Pause", "on_back": "", "items": [
			_item("resume", "Reprendre"), _item("end_save", "Terminer et enregistrer"),
			_item("abandon", "Abandonner")]},
	}
	set_items(ROUTES, [])
	set_items(WORKOUTS, [])
	_refresh_home()
	reset()


func _refresh_home() -> void:
	var world := world_name if world_name != "" else "à choisir"
	var items := [_item("world", "Parcours : " + world)]
	for m in HOME_MODES:
		if m in modes:
			items.append(_item(m, HOME_MODES[m]))
	items.append_array([_item("sim", "Revenir au matériel réel" if sim_session else "Session simulée"),
		_item("settings", "Réglages"), _item("quit", "Quitter")])
	_screens[HOME]["items"] = items
	_screens[READY]["items"] = [
		_item("start", "Démarrer"),
		_item("workout", "Changer d'entraînement" if mode == "erg" else "Passer en session ERG"),
		_item("change_route", "Changer de parcours")]
	_screens[READY]["title"] = ("Prêt : session ERG" if mode == "erg" else "Prêt : session libre") \
		+ ("" if world_name == "" else " — " + world_name)


## Parcours choisi (ou connu par la trame d'état) ; met à jour l'accueil et l'écran Prêt.
func set_world(id: String, name: String) -> void:
	world_id = id
	world_name = name if name != "" else id
	_refresh_home()


## Modes annoncés par le core (hello_ack.config.modes) ; null ou absent : DEFAULT_MODES (1.0).
func set_modes(list) -> void:
	modes = list.duplicate() if list is Array else DEFAULT_MODES.duplicate()
	_refresh_home()


func set_sim_session(on: bool) -> void:
	sim_session = on
	_screens[HOME]["title"] = "OpenRide — session simulée" if on else "OpenRide"
	_refresh_home()


static func _item(id: String, label: String, enabled := true, detail := "") -> Dictionary:
	return {"id": id, "label": label, "enabled": enabled, "detail": detail}


## Touche du clavier vers événement du Click (mêmes touches que main.gd, plus Entrée et Échap).
static func key_to_event(keycode: int) -> String:
	match keycode:
		KEY_EQUAL, KEY_PLUS, KEY_KP_ADD, KEY_UP:
			return "PLUS_SHORT"
		KEY_MINUS, KEY_KP_SUBTRACT, KEY_DOWN:
			return "MINUS_SHORT"
		KEY_PAGEUP, KEY_ENTER, KEY_KP_ENTER:
			return "PLUS_LONG"
		KEY_PAGEDOWN, KEY_ESCAPE, KEY_BACKSPACE:
			return "MINUS_LONG"
	return ""


func reset() -> void:
	_stack.clear()
	_focus_stack.clear()
	_pending = {}
	_open(HOME, false)


## Remplace les éléments d'une liste (parcours ou entraînements) : [{id, label, enabled, detail}].
## Un élément sans `enabled` est actif ; un parcours « à compiler » ou un entraînement invalide arrive
## avec enabled = false et son `detail`. Liste vide : un élément désactivé « Aucun … ».
func set_items(screen_id: String, items: Array) -> void:
	if not _screens.has(screen_id) or not screen_id in [ROUTES, WORKOUTS]:
		return
	var clean := []
	if screen_id == WORKOUTS:
		clean.append(_item(NO_WORKOUT_ID, "Sans entraînement (SIM)"))
	for it in items:
		if typeof(it) != TYPE_DICTIONARY or str(it.get("id", "")) == "":
			continue
		clean.append(_item(str(it["id"]), str(it.get("label", it["id"])), bool(it.get("enabled", true)),
			str(it.get("detail", ""))))
	if screen_id == ROUTES and clean.is_empty():
		clean.append(_item("empty", "Aucun parcours", false))
	elif screen_id == WORKOUTS and clean.size() == 1:
		clean.append(_item("empty", "Aucun entraînement", false))
	var focused_id := ""
	if _screen == screen_id and _focus >= 0 and _focus < _screens[screen_id]["items"].size():
		focused_id = _screens[screen_id]["items"][_focus]["id"]
	_screens[screen_id]["items"] = clean
	if _screen == screen_id:
		_focus = _first_enabled_from(_index_of(focused_id), 1)


## Ouvre l'écran de pause (appelé quand la séance passe en pause).
func open_pause() -> Dictionary:
	_stack.clear()
	_focus_stack.clear()
	_pending = {}
	_open(PAUSE, false)
	return state()


## Ajoute ou remplace un écran {id, title, on_back, items} (bilan de fin, lot N4).
func add_screen(screen: Dictionary) -> void:
	var id := str(screen.get("id", ""))
	if id != "":
		_screens[id] = screen.duplicate(true)


## Ouvre un écran en vidant l'historique (bilan de fin de séance) ; écran inconnu : rien.
func open_screen(screen_id: String) -> Dictionary:
	if _screens.has(screen_id):
		_stack.clear()
		_focus_stack.clear()
		_pending = {}
		_open(screen_id, false)
	return state()


## Ouvre un écran par-dessus l'écran courant (retour possible) ; écran inconnu : rien.
func push_screen(screen_id: String) -> Dictionary:
	if _screens.has(screen_id):
		_open(screen_id)
	return state()


## Remplace le titre et les éléments d'un écran ajouté par add_screen() (connexion, appairage, lot N13) ;
## le focus reste sur le même élément s'il existe encore.
func set_screen_items(screen_id: String, items: Array, title := "") -> void:
	if not _screens.has(screen_id) or screen_id in [ROUTES, WORKOUTS, CONFIRM]:
		return
	var focused_id := ""
	if _screen == screen_id and _focus >= 0 and _focus < _screens[screen_id]["items"].size():
		focused_id = _screens[screen_id]["items"][_focus]["id"]
	var clean := []
	for it in items:
		clean.append(_item(str(it["id"]), str(it.get("label", it["id"])), bool(it.get("enabled", true)),
			str(it.get("detail", ""))))
	_screens[screen_id]["items"] = clean
	if title != "":
		_screens[screen_id]["title"] = title
	if _screen == screen_id:
		_focus = _first_enabled_from(_index_of(focused_id), 1)


## Met le focus sur un élément actif de l'écran courant ; faux s'il n'existe pas ou est désactivé.
func focus_item(item_id: String) -> bool:
	var items := _items()
	for i in range(items.size()):
		if items[i]["id"] == item_id and items[i]["enabled"]:
			_focus = i
			return true
	return false


func current_screen() -> String:
	return _screen


## Demande de confirmation d'une action destructrice (focus sur « Non »), depuis l'écran courant.
func confirm(title: String, action: Dictionary) -> Dictionary:
	_confirm(title, action)
	return state()


## État courant : écran, titre, index du focus (−1 si aucun élément actif), éléments.
func state(action: Dictionary = {}) -> Dictionary:
	var scr: Dictionary = _screens[_screen]
	return {"screen": _screen, "title": scr["title"], "focus": _focus, "items": scr["items"].duplicate(true),
		"action": action}


## Traite un événement ; renvoie state() avec l'action éventuelle ({} sinon).
func handle(event: String) -> Dictionary:
	match event:
		"PLUS_SHORT":
			_move(1)
		"MINUS_SHORT":
			_move(-1)
		"PLUS_LONG":
			return state(_validate())
		"MINUS_LONG":
			return state(_back())
	return state()


# --- navigation -------------------------------------------------------------------------------

func _items() -> Array:
	return _screens[_screen]["items"]


func _index_of(id: String) -> int:
	var items := _items()
	for i in range(items.size()):
		if items[i]["id"] == id:
			return i
	return 0


## Premier élément actif à partir de `start` dans le sens `dir` (boucle) ; −1 s'il n'y en a aucun.
func _first_enabled_from(start: int, dir: int) -> int:
	var items := _items()
	var n := items.size()
	for k in range(n):
		var i := posmod(start + dir * k, n)
		if items[i]["enabled"]:
			return i
	return -1


func _move(dir: int) -> void:
	if _focus < 0:
		return
	_focus = _first_enabled_from(_focus + dir, dir)


func _open(screen_id: String, push := true) -> void:
	if push and _screen != screen_id:
		_stack.append(_screen)
		_focus_stack.append(_focus)
	_screen = screen_id
	_focus = _first_enabled_from(0, 1)


func _back() -> Dictionary:
	match _screen:
		CONFIRM:
			_pending = {}
			_go_back_to(_confirm_back)
			return {}
		PAUSE:
			return {"action": "resume"}   # retour depuis la pause = Reprendre
		HOME:
			return {}
	if not _stack.is_empty():
		_screen = _stack.pop_back()
		var previous: int = _focus_stack.pop_back()
		_focus = _first_enabled_from(clampi(previous, 0, _items().size() - 1), 1)
	else:
		var target: String = _screens[_screen]["on_back"]
		if target != "":
			_screen = target
			_focus = _first_enabled_from(0, 1)
	return {}


## Va à `screen_id` : retour en arrière s'il est juste dessous, sinon à la place de l'écran courant.
func _go(screen_id: String) -> void:
	if not _stack.is_empty() and _stack[-1] == screen_id:
		_back()
		_focus = _first_enabled_from(0, 1)   # écran Prêt : focus sur « Démarrer »
	else:
		_replace_top(screen_id)


## Ouvre un écran à la place de l'écran courant : le retour mène à l'écran d'avant (accueil).
func _replace_top(screen_id: String) -> void:
	_screen = screen_id
	_focus = _first_enabled_from(0, 1)


## Nom du parcours sans la longueur ajoutée par le catalogue (« Vosges (32,0 km) » → « Vosges »).
static func _short_name(label: String) -> String:
	var i := label.rfind(" (")
	return label.substr(0, i) if i > 0 and label.ends_with(")") else label


## Retour de l'écran de confirmation : écran et focus d'origine.
func _go_back_to(screen_id: String) -> void:
	_screen = screen_id
	_focus = _first_enabled_from(clampi(_confirm_focus, 0, _items().size() - 1), 1)


func _confirm(title: String, action: Dictionary) -> void:
	_pending = action
	_confirm_back = _screen
	_confirm_focus = _focus
	_screens[CONFIRM]["title"] = title
	_screen = CONFIRM
	_focus = 0   # « Non » par défaut


func _validate() -> Dictionary:
	if _focus < 0 or not _items()[_focus]["enabled"]:
		return {}
	var id: String = _items()[_focus]["id"]
	match _screen:
		HOME:
			match id:
				"world":
					_routes_return = HOME
					_open(ROUTES)
				"ride":
					mode = "free"
					_refresh_home()
					if world_id == "":
						_routes_return = READY
						_open(ROUTES)
					else:
						_open(READY)
					return {"action": "select_workout", "workout_id": null}
				"erg":
					_workouts_return = HOME
					_open(WORKOUTS)
				"sim":
					if sim_session:
						_confirm("Revenir au matériel réel ? OpenRide redémarre", {"action": "relaunch"})
					else:
						_confirm("Session simulée ? OpenRide redémarre sans matériel", {"action": "relaunch_sim"})
				"settings":
					_open(SETTINGS)
				"quit":
					_confirm("Quitter OpenRide ?", {"action": "quit"})
		ROUTES:
			var label := id
			for it in _items():
				if it["id"] == id:
					label = str(it["label"])
			set_world(id, _short_name(label))
			if _routes_return == READY:
				_go(READY)
			else:
				_back()
			return {"action": "select_route", "route_id": id}
		WORKOUTS:
			var workout = null if id == NO_WORKOUT_ID else id
			mode = "free" if workout == null else "erg"
			_refresh_home()
			if _workouts_return == READY:
				_back()
			elif world_id == "":
				_routes_return = READY
				_replace_top(ROUTES)
			else:
				_go(READY)
			return {"action": "select_workout", "workout_id": workout}
		READY:
			match id:
				"start":
					return {"action": "start"}
				"workout":
					_workouts_return = READY
					_open(WORKOUTS)
				"change_route":
					_routes_return = READY
					_open(ROUTES)
		CONFIRM:
			var act := _pending
			_pending = {}
			if id == "yes" and act.get("action", "") == "end_session":
				reset()
			else:
				_go_back_to(_confirm_back)
			if id == "yes":
				return act
		PAUSE:
			match id:
				"resume":
					return {"action": "resume"}
				"end_save":
					reset()
					return {"action": "end_session", "save": true}
				"abandon":
					_confirm("Abandonner la séance ?", {"action": "end_session", "save": false})
		_:
			return {"action": "item", "screen": _screen, "id": id}
	return {}
