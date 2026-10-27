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
##
## Sous-menu ERG (lot N16, contrat v1.3, décision D4 : le core écrit les fichiers) : « Créer un
## entraînement » ouvre les paramètres d'intervalles (workout_builder.gd, modifiés sur l'écran de
## réglage) puis renvoie create_workout {args} ; « Importer un fichier » renvoie list_imports, la
## réponse `imports` arrive par set_import_candidates() et un choix renvoie import_workout {path}.
## Réponse `workout_saved` : on_workout_saved(), retour à la liste, focus sur le nouvel entraînement à
## son arrivée ; erreur du core (bad_args, busy, workout_invalid, workout_write_failed) sur la ligne d'état.

const MenuModel := preload("res://scripts/menu_model.gd")
const CatalogModel := preload("res://scripts/catalog_model.gd")
const SummaryViewModel := preload("res://scripts/summary_view_model.gd")
const DevicesViewModel := preload("res://scripts/devices_view_model.gd")
const PairingViewModel := preload("res://scripts/pairing_view_model.gd")
const SettingsViewModel := preload("res://scripts/settings_view_model.gd")
const WorkoutBuilder := preload("res://scripts/workout_builder.gd")

const SUMMARY := "summary"
const CONNECT := "connect"
const PAIRING := PairingViewModel.SCREEN
const SETTING_EDIT := SettingsViewModel.EDIT_SCREEN
const WORKOUT_CREATE := WorkoutBuilder.SCREEN
const WORKOUT_IMPORT := "workout_import"
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
var settings = SettingsViewModel.new()
## Versions de l'engine et du core pour la ligne « OpenRide X.Y.Z » des réglages (lots O2 et O4).
var engine_version := str(ProjectSettings.get_setting("application/config/version", "0.0.0"))
var core_version := ""
## Difficulté de la séance (trame d'état, lot Q1), pour le curseur de la pause.
var difficulty_pct := 50
## Dernier objet `devices` reçu (une trame sur 30 le porte, contrat §3) : gardé jusqu'au suivant.
var devices: Dictionary = {}
## Écran de connexion déjà quitté (ou séance déjà en cours au premier état : --autostart, reprise).
var connect_done := false
var _all_ok_since := -1.0
## Noms des parcours de la dernière liste, par id (monde affiché à l'accueil).
var route_names := {}
var builder = WorkoutBuilder.new()
## Fichiers proposés à l'import : [{path, file, source, imported}] (message `imports` du core).
var import_candidates: Array = []
## Ligne d'état de la liste des entraînements (créé, importé, erreur).
var workout_message := ""
var _focus_workout := ""
## Dernière demande au core (« create » ou « import ») et dernier request_cmd_id traité : le core
## répond à chaque copie renvoyée d'une commande, une seule réponse compte.
var _workout_request := ""
var _last_saved_cmd_id := -1


func _init() -> void:
	summary_model.attach_to_menu(menu)
	menu.add_screen({"id": CONNECT, "title": "Connexion des appareils", "on_back": "", "items": []})
	menu.add_screen({"id": PAIRING, "title": "Appareils", "on_back": MenuModel.SETTINGS, "items": []})
	menu.add_screen({"id": SETTING_EDIT, "title": "Réglage", "on_back": MenuModel.SETTINGS, "items": []})
	menu.add_screen({"id": WORKOUT_CREATE, "title": "Créer un entraînement", "on_back": MenuModel.WORKOUTS,
		"items": []})
	menu.add_screen({"id": WORKOUT_IMPORT, "title": "Importer un entraînement", "on_back": MenuModel.WORKOUTS,
		"items": []})
	_refresh_builder()
	_refresh_pairing()
	_refresh_settings()
	menu.set_pause_difficulty(SettingsViewModel.slider(difficulty_pct))


func is_visible() -> bool:
	return session_state != "" and session_state != "RUNNING"


## Trame `state` reçue ; renvoie les actions à exécuter (liste, éventuellement vide). `now_s` : horloge
## en secondes pour l'attente de l'écran de connexion (négatif : passage à l'accueil sans attente).
func on_state(state: Dictionary, now_s := -1.0) -> Array:
	var out: Array = []
	var st := str(state.get("session_state", ""))
	if state.get("devices") is Dictionary:
		devices = state["devices"]
	var diff = state.get("difficulty_pct", null)
	if (diff is int or diff is float) and int(diff) != difficulty_pct:
		difficulty_pct = int(diff)
		menu.set_pause_difficulty(SettingsViewModel.slider(difficulty_pct))
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


## Écran « Réglages » : Appareils (lot N13) puis les réglages reçus du core (lot O4).
func _refresh_settings() -> void:
	var items: Array = [{"id": "devices", "label": "Appareils : rechercher et appairer"}]
	items.append_array(settings.menu_items())
	if settings.items.is_empty():
		items.append({"id": "none", "label": "Réglages : en attente du core", "enabled": false})
	items.append(SettingsViewModel.version_item(engine_version, core_version))
	menu.set_screen_items(MenuModel.SETTINGS, items)


## Versions affichées en bas des réglages : engine (project.godot) et core (hello_ack.core_version).
func set_versions(engine_v: String, core_v: String) -> void:
	engine_version = engine_v
	core_version = core_v
	_refresh_settings()


## Message `settings` du core (liste, ou réponse à set_setting).
func on_settings(msg: Dictionary) -> void:
	settings.on_settings(msg)
	_refresh_settings()


## Message `scan_results` du core.
func on_scan_results(msg: Dictionary) -> void:
	var was_busy: bool = pairing.scanning or pairing.identifying
	pairing.on_scan_results(msg)
	_refresh_pairing()
	# Fin de recherche ou d'identification : le focus va à « Enregistrer » s'il y a quelque chose à écrire.
	if was_busy and not pairing.scanning and not pairing.identifying and menu.current_screen() == PAIRING:
		menu.focus_item("save")


## Erreur du core : écrans Créer / Importer un entraînement (bad_args, busy, workout_invalid,
## workout_write_failed), sinon écran Appareils (busy, scan_failed, pairing_failed).
func on_error(code: String, text: String) -> void:
	if menu.current_screen() in [WORKOUT_CREATE, WORKOUT_IMPORT] \
			and code in ["bad_args", "busy", "workout_invalid", "workout_write_failed"]:
		workout_failed("Échec : " + text)
		return
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
	if _focus_workout != "" and menu.current_screen() == MenuModel.WORKOUTS:
		menu.focus_item(_focus_workout)
		_focus_workout = ""


func _refresh_builder() -> void:
	menu.set_screen_items(WORKOUT_CREATE, builder.menu_items())


## Fichiers importables (message `imports` du core, réponse à list_imports).
func set_import_candidates(found: Array) -> void:
	import_candidates = found
	var items: Array = []
	for i in range(found.size()):
		var c: Dictionary = found[i]
		items.append({"id": "file:%d" % i, "label": str(c["file"]),
			"detail": str(c["source"]) + (", déjà importé" if c.get("imported", false) else "")})
	if items.is_empty():
		items.append({"id": "none", "label": "Aucun fichier .zwo, .erg ou .mrc", "enabled": false,
			"detail": "dans Téléchargements, Bureau ou ~/OpenRide/Import"})
	menu.set_screen_items(WORKOUT_IMPORT, items)


## Réponse `workout_saved` du core {request_cmd_id, workout_id, name, created} (`created` faux : fichier
## identique déjà présent) ; vrai si c'est une nouvelle réponse (main.gd redemande alors la liste).
func on_workout_saved(msg: Dictionary) -> bool:
	var rid := int(msg.get("request_cmd_id", -1))
	if rid >= 0 and rid == _last_saved_cmd_id:
		return false
	_last_saved_cmd_id = rid
	var name := str(msg.get("name", msg.get("workout_id", "")))
	var text := ("Importé : " if _workout_request == "import" else "Créé : ") + name
	if not msg.get("created", true):
		text += " (déjà présent)"
	workout_added(str(msg.get("workout_id", "")), text)
	return true


## Entraînement écrit dans le dossier (créé ou importé) : retour à la liste, focus dessus quand la
## nouvelle liste arrive.
func workout_added(workout_id: String, message: String) -> void:
	for i in range(4):
		if menu.current_screen() in [MenuModel.WORKOUTS, MenuModel.HOME]:
			break
		menu.handle("Y_SHORT")
	workout_message = message
	_focus_workout = workout_id


func workout_failed(message: String) -> void:
	workout_message = message


## Liste indisponible (trois demandes sans réponse) : un élément désactivé qui le dit.
func list_failed(list_name: String) -> void:
	if list_name == "imports":
		menu.set_screen_items(WORKOUT_IMPORT, [{"id": "none", "label": "Fichiers à importer indisponibles",
			"enabled": false, "detail": "core sans réponse"}])
		return
	var screen := MenuModel.ROUTES if list_name == "routes" else MenuModel.WORKOUTS
	var label := "Liste des parcours indisponible" if list_name == "routes" else "Liste des entraînements indisponible"
	menu.set_items(screen, [{"id": "unavailable", "label": label, "enabled": false, "detail": "core sans réponse"}])


## Événement du Click ou du clavier (PLUS_SHORT…) ; renvoie l'action à exécuter ({} sinon).
func handle(event: String) -> Dictionary:
	if not is_visible():
		return {}
	if menu.current_screen() == SETTING_EDIT:
		return _handle_edit(event)
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
	if act.get("action", "") == "item" and act.get("screen", "") == MenuModel.SETTINGS:
		var item_id := str(act["id"])
		if item_id == "devices":
			return _open_pairing()
		if item_id.begins_with("set:") and settings.begin(item_id.substr(4)):
			_open_edit()
		return {}
	if act.get("action", "") == "item" and act.get("screen", "") == MenuModel.WORKOUTS:
		workout_message = ""
		if str(act["id"]) == MenuModel.CREATE_WORKOUT_ID:
			_refresh_builder()
			menu.push_screen(WORKOUT_CREATE)
			return {}
		import_candidates = []
		menu.set_screen_items(WORKOUT_IMPORT, [{"id": "none", "label": "Recherche des fichiers…", "enabled": false}])
		menu.push_screen(WORKOUT_IMPORT)
		return {"action": "list_imports"}
	if act.get("action", "") == "item" and act.get("screen", "") == WORKOUT_CREATE:
		var item_id := str(act["id"])
		if item_id == "save":
			_workout_request = "create"
			return {"action": "create_workout", "args": builder.values.duplicate()}
		if item_id.begins_with("param:"):
			settings.begin_with(builder.edit_item(item_id.substr(6)))
			_open_edit()
		return {}
	if act.get("action", "") == "item" and act.get("screen", "") == WORKOUT_IMPORT:
		var idx := int(str(act["id"]).substr(5))
		if str(act["id"]).begins_with("file:") and idx < import_candidates.size():
			_workout_request = "import"
			return {"action": "import_workout", "path": import_candidates[idx]["path"]}
		return {}
	if act.get("action", "") == "item" and act.get("screen", "") == MenuModel.PAUSE:
		settings.begin_pause_difficulty(difficulty_pct)
		_open_edit()
		return {}
	if act.get("action", "") == "item" and act.get("screen", "") == PAIRING:
		act = pairing.handle(str(act["id"]))
		match act.get("action", ""):
			"back":
				menu.handle("Y_SHORT")
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


func _open_edit() -> void:
	menu.set_screen_items(SETTING_EDIT, settings.edit_items(), str(settings.editing.get("label", "Réglage")))
	menu.push_screen(SETTING_EDIT)


## Écran de modification (plan des boutons, spécification générale §7.1) : + / − court, A court et
## flèches gauche, droite changent la valeur d'un pas, + / − long de cinq pas ; A long enregistre,
## Y annule.
func _handle_edit(event: String) -> Dictionary:
	match event:
		"PLUS_SHORT", "MINUS_SHORT", "A_SHORT", "LEFT_SHORT", "RIGHT_SHORT", "PLUS_LONG", "MINUS_LONG":
			var dir := -1 if event in ["MINUS_SHORT", "LEFT_SHORT", "MINUS_LONG"] else 1
			for i in range(MenuModel.LONG_STEP if event.ends_with("_LONG") else 1):
				settings.step(dir)
			menu.set_screen_items(SETTING_EDIT, settings.edit_items())
		"A_LONG":
			var act: Dictionary = settings.commit()
			menu.handle("Y_SHORT")
			if act.get("action", "") == "set_difficulty":
				difficulty_pct = int(act["pct"])
				menu.set_pause_difficulty(SettingsViewModel.slider(difficulty_pct))
			if act.get("action", "") == "builder_set":
				builder.set_value(str(act["key"]), act["value"])
				_refresh_builder()
				return {}
			return act
		"Y_SHORT":
			settings.cancel()
			menu.handle("Y_SHORT")
	return {}


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
	st["status"] = ""
	if st["screen"] == PAIRING:
		st["status"] = pairing.message
	elif st["screen"] in [MenuModel.WORKOUTS, WORKOUT_CREATE, WORKOUT_IMPORT]:
		st["status"] = workout_message
	return st
