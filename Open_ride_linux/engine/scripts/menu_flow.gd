extends RefCounted

## Déroulé des menus au-dessus de la vue 3D (Lot N6), sans nœud : relie la navigation (menu_model.gd,
## K5), le catalogue (catalog_model.gd, N3), le bilan (summary_view_model.gd, N4) et l'état de séance
## reçu du core (contrat IPC v1.1).
##
## Règles :
## - menu visible dès qu'une trame `state` est reçue, sauf en RUNNING (contrat §4 : les événements
##   `input` ne servent alors qu'aux bips) ;
## - PAUSED ouvre l'écran de pause, FINISHED le bilan ; une séance terminée sans bilan (IDLE ou READY
##   après RUNNING ou PAUSED) ramène à l'accueil ;
## - les listes sont demandées au premier état reçu, même en RUNNING (`--autostart` : la liste des
##   entraînements donne au bandeau ERG les durées réelles de tous les blocs), puis à chaque « Nouvelle séance ».
##
## `on_state()` et `handle()` renvoient des actions à exécuter par main.gd : commandes du contrat
## (select_route, select_workout, start, resume, end_session), « list » (demander les deux listes) et
## « quit ». Pas de class_name : charger par preload("res://scripts/menu_flow.gd").
##
## Connexion au démarrage (lot N13) : au premier état hors séance, l'écran « Connexion des appareils »
## s'ouvre avant l'accueil. Il passe seul à l'accueil quand tout est relié depuis CONNECT_HOLD_S
## (trainer, boîtiers du Click, ceinture si configurée) ; « Passer » y va tout de suite, même avec un
## seul boîtier du Click (unilatéral) ou sans trainer. « Rechercher et appairer » ouvre l'écran
## « Appareils » (pairing_view_model.gd), aussi accessible depuis Réglages. Actions en plus pour main.gd :
## scan_devices, identify_click_plus, pair_devices (+ args) et relaunch (relancer OpenRide).

const MenuModel := preload("res://scripts/menu_model.gd")
const CatalogModel := preload("res://scripts/catalog_model.gd")
const SummaryViewModel := preload("res://scripts/summary_view_model.gd")
const DevicesViewModel := preload("res://scripts/devices_view_model.gd")
const PairingViewModel := preload("res://scripts/pairing_view_model.gd")

const SUMMARY := "summary"
const CONNECT := "connect"
const PAIRING := PairingViewModel.SCREEN
## Tout relié depuis ce temps (s) : passage seul à l'accueil, le temps de voir les appareils connectés.
const CONNECT_HOLD_S := 2.0

var menu = MenuModel.new()
var catalog = CatalogModel.new()
var summary_model = SummaryViewModel.new()
var session_state: String = ""
## Dernier bilan reçu (objet `summary` de la trame en FINISHED).
var summary: Dictionary = {}
## « Voir le bilan détaillé » : blocs ERG en plus des lignes.
var show_details := false
var _lists_requested := false
var devices_model = DevicesViewModel.new()
var pairing = PairingViewModel.new()
## Dernier objet `devices` reçu (une trame sur 30 le porte, contrat §3) : gardé jusqu'au suivant.
var devices: Dictionary = {}
## Écran de connexion déjà quitté (ou séance déjà en cours au premier état : --autostart, reprise).
var connect_done := false
var _all_ok_since := -1.0
## Noms des parcours de la dernière liste, par id (monde affiché à l'accueil).
var route_names := {}


func _init() -> void:
	summary_model.attach_to_menu(menu)
	menu.add_screen({"id": CONNECT, "title": "Connexion des appareils", "on_back": "", "items": []})
	menu.add_screen({"id": PAIRING, "title": "Appareils", "on_back": MenuModel.SETTINGS, "items": []})
	_refresh_pairing()


func is_visible() -> bool:
	return session_state != "" and session_state != "RUNNING"


## Trame `state` reçue ; renvoie les actions à exécuter (liste, éventuellement vide). `now_s` : horloge
## en secondes pour l'attente de l'écran de connexion (négatif : passage à l'accueil sans attente).
func on_state(state: Dictionary, now_s := -1.0) -> Array:
	var out: Array = []
	var st := str(state.get("session_state", ""))
	if state.get("devices") is Dictionary:
		devices = state["devices"]
	if session_state == "" and st != "" and not connect_done:
		if st in ["IDLE", "READY"]:
			menu.open_screen(CONNECT)
		else:
			connect_done = true
	if not connect_done and menu.current_screen() == CONNECT:
		_update_connect(with_devices(state), now_s)
	var rid = state.get("route_id", null)
	if rid != null and str(rid) != "" and str(rid) != menu.world_id:
		menu.set_world(str(rid), str(route_names.get(str(rid), rid)))
	if st == "FINISHED" and state.get("summary") is Dictionary:
		summary = state["summary"]
	if st != session_state:
		var prev := session_state
		session_state = st
		match st:
			"PAUSED":
				menu.open_pause()
			"FINISHED":
				show_details = false
				menu.open_screen(SUMMARY)
			"IDLE", "READY":
				if prev in ["RUNNING", "PAUSED"]:
					menu.reset()
	if st != "" and not _lists_requested:
		_lists_requested = true
		out.append({"action": "list"})
	return out


## Trame complétée du dernier objet `devices` reçu (affichage des appareils à chaque image).
func with_devices(state: Dictionary) -> Dictionary:
	if state.has("devices") or devices.is_empty():
		return state
	var out := state.duplicate()
	out["devices"] = devices
	return out


func _update_connect(state: Dictionary, now_s: float) -> void:
	var c: Dictionary = devices_model.connection(state)
	if c["all_ok"]:
		if _all_ok_since < 0.0:
			_all_ok_since = now_s
		if now_s < 0.0 or now_s - _all_ok_since >= CONNECT_HOLD_S:
			_leave_connect()
			return
	else:
		_all_ok_since = -1.0
	var label := "Continuer"
	var detail := ""
	if not c["all_ok"]:
		label = "Passer"
		if c["unilateral"] and c["trainer_ok"] and c["missing"].size() == 1:
			detail = "un seul boîtier du Click"
		else:
			detail = "sans " + ", ".join(c["missing"])
	menu.set_screen_items(CONNECT, [
		{"id": "continue", "label": label, "detail": detail},
		{"id": "pairing", "label": "Rechercher et appairer"},
		{"id": "quit", "label": "Quitter"}])


func _leave_connect() -> void:
	connect_done = true
	menu.reset()


func _refresh_pairing() -> void:
	menu.set_screen_items(PAIRING, pairing.menu_items())


## Message `scan_results` du core.
func on_scan_results(msg: Dictionary) -> void:
	var was_busy: bool = pairing.scanning or pairing.identifying
	pairing.on_scan_results(msg)
	_refresh_pairing()
	# Fin de recherche ou d'identification : le focus va à « Enregistrer » s'il y a quelque chose à écrire.
	if was_busy and not pairing.scanning and not pairing.identifying and menu.current_screen() == PAIRING:
		menu.focus_item("save")


## Erreur du core (codes de l'écran Appareils : busy, scan_failed, pairing_failed).
func on_error(code: String, text: String) -> void:
	if code in ["busy", "scan_failed", "pairing_failed"]:
		pairing.on_error(code, text)
		_refresh_pairing()


func on_command_acked(cmd_name: String) -> void:
	if cmd_name == "pair_devices":
		pairing.on_pair_acked()
		_refresh_pairing()


## Core relancé ou de nouveau joignable : listes redemandées au prochain état visible.
func lists_needed() -> void:
	_lists_requested = false


func set_routes(raw: Array) -> void:
	menu.set_items(MenuModel.ROUTES, catalog.route_items(raw))
	for r in raw:
		if r is Dictionary and str(r.get("id", "")) != "":
			route_names[str(r["id"])] = str(r.get("name", r["id"]))
	if menu.world_id != "" and route_names.has(menu.world_id):
		menu.set_world(menu.world_id, route_names[menu.world_id])


func set_workouts(raw: Array) -> void:
	menu.set_items(MenuModel.WORKOUTS, catalog.workout_items(raw))


## Liste indisponible (trois demandes sans réponse) : un élément désactivé qui le dit.
func list_failed(list_name: String) -> void:
	var screen := MenuModel.ROUTES if list_name == "routes" else MenuModel.WORKOUTS
	var label := "Liste des parcours indisponible" if list_name == "routes" else "Liste des entraînements indisponible"
	menu.set_items(screen, [{"id": "unavailable", "label": label, "enabled": false, "detail": "core sans réponse"}])


## Événement du Click ou du clavier (PLUS_SHORT…) ; renvoie l'action à exécuter ({} sinon).
func handle(event: String) -> Dictionary:
	if not is_visible():
		return {}
	var act: Dictionary = menu.handle(event)["action"]
	if act.get("action", "") == "item" and act.get("screen", "") == CONNECT:
		match str(act["id"]):
			"continue":
				_leave_connect()
			"pairing":
				return _open_pairing()
			"quit":
				menu.confirm("Quitter OpenRide ?", {"action": "quit"})
		return {}
	if act.get("action", "") == "item" and act.get("screen", "") == MenuModel.SETTINGS and str(act["id"]) == "devices":
		return _open_pairing()
	if act.get("action", "") == "item" and act.get("screen", "") == PAIRING:
		act = pairing.handle(str(act["id"]))
		match act.get("action", ""):
			"back":
				menu.handle("MINUS_LONG")
				act = {}
			"confirm_pair":
				menu.confirm(str(act["title"]), {"action": "pair_devices", "args": act["args"]})
				act = {}
		_refresh_pairing()
		return act
	if act.get("action", "") == "item" and act.get("screen", "") == SUMMARY:
		act = summary_model.handle_action(str(act["id"]), menu)
		match act.get("action", ""):
			"new_session":
				show_details = false
				summary = {}
				# Le core reste en FINISHED jusqu'au prochain select_route : le monde choisi est rechargé.
				if menu.world_id != "":
					return {"action": "list", "route_id": menu.world_id}
				return {"action": "list"}
			"details":
				show_details = not show_details
				return {}
	return act


## Écran « Appareils » par-dessus l'écran courant, recherche lancée tout de suite.
func _open_pairing() -> Dictionary:
	pairing.reset()
	var act: Dictionary = pairing.handle("scan")
	_refresh_pairing()
	menu.push_screen(PAIRING)
	return act


## État du menu ; `status` : ligne d'état sous le titre (écran Appareils : recherche, + reconnu, enregistré).
func state() -> Dictionary:
	var st: Dictionary = menu.state()
	st["status"] = pairing.message if st["screen"] == PAIRING else ""
	return st
