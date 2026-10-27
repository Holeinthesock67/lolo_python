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
##
## Plans, test de FTP et bibliothèque (lot O12, contrat 1.3) :
## - accueil : « Séance du jour » (nom, durée, TSS) quand le plan actif en a une, sinon « Plan : … » ou
##   « Choisir un plan » ; la séance du jour démarre par `start` avec plan_day ; l'écran « Plans »
##   (action list_plans à l'ouverture) montre le suivi du plan actif et la liste, l'écran d'un plan
##   le démarre (start_plan, remplacement confirmé) ou l'arrête (stop_plan, confirmé) ; réponse `plans`
##   par on_plans(), erreur plan_invalid sur la ligne d'état ;
## - « Test de FTP » : rampe ou 20 minutes, puis écran Prêt, `start` avec ftp_test ; au bilan,
##   « Accepter » (accept_ftp ; résultat douteux : confirmation puis accept_ftp avec force) ou « Garder » ;
## - parcours : tri et filtre par étiquette en cycle en fin de liste, fiche du parcours sur l'écran Prêt ;
## - bots (lot O7) : « Bot : … » et « Fantôme … » sur l'écran Prêt, `start` avec `bots` ; refus du
##   core (bot_invalid) sur la ligne d'état de l'écran Prêt ;
## - entraînements en watts (.erg, .mrc) : « watts fixes » et la puissance maximale.

const MenuModel := preload("res://scripts/menu_model.gd")
const CatalogModel := preload("res://scripts/catalog_model.gd")
const SummaryViewModel := preload("res://scripts/summary_view_model.gd")
const DevicesViewModel := preload("res://scripts/devices_view_model.gd")
const PairingViewModel := preload("res://scripts/pairing_view_model.gd")
const SettingsViewModel := preload("res://scripts/settings_view_model.gd")
const WorkoutBuilder := preload("res://scripts/workout_builder.gd")
const RecordsViewModel := preload("res://scripts/records_view_model.gd")

const SUMMARY := "summary"
const CONNECT := "connect"
const PAIRING := PairingViewModel.SCREEN
const SETTING_EDIT := SettingsViewModel.EDIT_SCREEN
const WORKOUT_CREATE := WorkoutBuilder.SCREEN
const WORKOUT_IMPORT := "workout_import"
const PLANS := "plans"
const PLAN := "plan"
const FTP_TEST := "ftp_test"
## Records du parcours (série T, lot T10) : liste des segments, puis table d'un segment.
const RECORDS := "records"
const RECORD_TABLE := "record_table"
## Tests de FTP proposés (lot O10) : id, libellé, explication courte, nom de la séance (écran Prêt).
const FTP_TESTS := [
	["ramp", "Rampe", "≈ 25 min : +20 W par minute jusqu'à ne plus tenir ; FTP = 75 % de la meilleure minute",
		"test de FTP (rampe)"],
	["20min", "20 minutes", "≈ 1 h avec l'échauffement : 20 min à fond, régulier ; FTP = 95 % de la moyenne",
		"test de FTP (20 min)"]]
const FTP_HINT := "Sur une boucle : l'arrivée d'un parcours arrête le test"
## Avertissements du test de FTP (summary.ftp_test.warnings), comme `openride-core ftp-test`.
const FTP_WARNINGS := {"too_short": "test trop court", "erratic_cadence": "cadence erratique",
	"trainer_dropout": "coupure du trainer pendant l'effort", "paused": "pause pendant l'effort"}
const SUMMARY_BASE_IDS := ["new_session", "details", "quit"]
## Ligne d'état de l'écran de pause selon `state.pause_reason` (contrat IPC) : le HUD est caché pendant
## un menu, la raison de la pause s'affiche donc sous le titre. Pause demandée (`user`) : rien.
const PAUSE_REASONS := {"user": "", "trainer_lost": "Trainer perdu : reconnexion en cours…",
	"engine_lost": "Affichage relancé : reprends quand tu veux", "core_restarted": "OpenRide a redémarré : séance retrouvée",
	"recording_failed": "Enregistrement impossible : la séance reste en mémoire",
	"world_data": "Route devant toi en cours de chargement : reprise automatique"}
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
## Dernière réponse `plans` du core ({} avant la première) ; plan affiché sur l'écran d'un plan.
var plans: Dictionary = {}
var _plan_shown := ""
## Ligne d'état des écrans des plans, et demande en cours (« start », « stop » ou "").
var plan_message := ""
var _plan_request := ""
## Liste brute des parcours (fiche de l'écran Prêt) ; tri et étiquette choisis dans la liste.
var routes_raw: Array = []
var route_sort := 0
var route_tag := ""
var _workouts_raw: Array = []
## Résultat du test de FTP du bilan (summary.ftp_test) tant qu'il reste à accepter ou garder ({} sinon).
var ftp_offer: Dictionary = {}
var summary_message := ""
## Ligne d'état de l'écran Prêt (bots refusés par le core, lot O7).
var ready_message := ""
var _ftp_pending := false
## Records (lot T10) : fichier relu à chaque ouverture ; segment et table affichés.
var records = RecordsViewModel.new()
var records_path := ""
var _record_segment := ""
var _record_bonus := false
## Raison de la dernière pause (`state.pause_reason`), "" hors pause.
var pause_reason := ""


func _init() -> void:
	summary_model.attach_to_menu(menu)
	menu.add_screen({"id": CONNECT, "title": "Connexion des appareils", "on_back": "", "items": []})
	menu.add_screen({"id": PAIRING, "title": "Appareils", "on_back": MenuModel.SETTINGS, "items": []})
	menu.add_screen({"id": SETTING_EDIT, "title": "Réglage", "on_back": MenuModel.SETTINGS, "items": []})
	menu.add_screen({"id": WORKOUT_CREATE, "title": "Créer un entraînement", "on_back": MenuModel.WORKOUTS,
		"items": []})
	menu.add_screen({"id": WORKOUT_IMPORT, "title": "Importer un entraînement", "on_back": MenuModel.WORKOUTS,
		"items": []})
	menu.add_screen({"id": PLANS, "title": "Plans d'entraînement", "on_back": MenuModel.HOME, "items": []})
	menu.add_screen({"id": PLAN, "title": "Plan", "on_back": PLANS, "items": []})
	var tests: Array = []
	for t in FTP_TESTS:
		tests.append({"id": t[0], "label": t[1], "detail": t[2]})
	menu.add_screen({"id": FTP_TEST, "title": "Test de FTP", "on_back": MenuModel.HOME, "items": []})
	menu.set_screen_items(FTP_TEST, tests)
	menu.add_screen({"id": RECORDS, "title": "Records", "on_back": MenuModel.READY, "items": []})
	menu.add_screen({"id": RECORD_TABLE, "title": "Records", "on_back": RECORDS, "items": []})
	_refresh_plans()
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
	pause_reason = "" if state.get("pause_reason") == null else str(state["pause_reason"])
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
				ftp_offer = summary["ftp_test"] if summary.get("ftp_test") is Dictionary else {}
				summary_message = _ftp_text(ftp_offer)
				_refresh_summary()
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


## Message `settings` du core (liste, ou réponse à set_setting et à accept_ftp).
func on_settings(msg: Dictionary) -> void:
	settings.on_settings(msg)
	_refresh_settings()
	if _ftp_pending:
		_ftp_pending = false
		summary_message = "FTP enregistrée : %s W" % str(settings.item("rider.ftp_w").get("value", ftp_offer.get("ftp_w")))
		ftp_offer = {}
		_refresh_summary()
	_refresh_workouts()


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
	if _ftp_pending and code in ["ftp_result_missing", "ftp_result_doubtful", "setting_invalid", "busy"]:
		_ftp_pending = false
		if code == "ftp_result_doubtful":
			menu.confirm("Résultat douteux : enregistrer %s W quand même ?" % str(ftp_offer.get("ftp_w")),
				{"action": "accept_ftp", "force": true})
		else:
			summary_message = "Échec : " + text
		return
	if code == "bot_invalid" and menu.current_screen() == MenuModel.READY:
		ready_message = "Échec : " + text
		return
	if _plan_request != "" and code in ["plan_invalid", "busy"]:
		_plan_request = ""
		plan_message = "Échec : " + text
		return
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
	routes_raw = raw
	var tags: Array = CatalogModel.route_tags(raw)
	if route_tag != "" and not route_tag in tags:
		route_tag = ""
	var items: Array = catalog.route_items(raw, CatalogModel.ROUTE_SORTS[route_sort][0], route_tag)
	if items.is_empty() and route_tag != "":
		items.append({"id": "empty", "label": "Aucun parcours « %s »" % route_tag, "enabled": false})
	if not raw.is_empty():
		items.append({"id": MenuModel.SORT_ROUTES_ID, "label": "Trier par : " + CatalogModel.ROUTE_SORTS[route_sort][1]})
		if not tags.is_empty():
			items.append({"id": MenuModel.FILTER_ROUTES_ID,
				"label": "Étiquette : " + (route_tag if route_tag != "" else "toutes")})
	menu.set_items(MenuModel.ROUTES, items)
	for r in raw:
		if r is Dictionary and str(r.get("id", "")) != "":
			route_names[str(r["id"])] = str(r.get("name", r["id"]))
	if menu.world_id != "" and route_names.has(menu.world_id):
		menu.set_world(menu.world_id, route_names[menu.world_id])


func set_workouts(raw: Array) -> void:
	_workouts_raw = raw
	menu.set_items(MenuModel.WORKOUTS, catalog.workout_items(raw, _ftp_w()))
	if _focus_workout != "" and menu.current_screen() == MenuModel.WORKOUTS:
		menu.focus_item(_focus_workout)
		_focus_workout = ""


## Liste des entraînements reconstruite (FTP du core changée : watts maximaux des fichiers en watts).
func _refresh_workouts() -> void:
	if not _workouts_raw.is_empty():
		menu.set_items(MenuModel.WORKOUTS, catalog.workout_items(_workouts_raw, _ftp_w()))


## FTP du core d'après les réglages (lot O4) ; 0 tant qu'ils ne sont pas reçus.
func _ftp_w() -> float:
	var ftp = settings.item("rider.ftp_w").get("value", null)
	return float(ftp) if ftp is int or ftp is float else 0.0


## Tri ou étiquette suivants de la liste des parcours (cycle au Click) ; le focus reste sur l'élément.
func _cycle_routes(item_id: String) -> void:
	if item_id == MenuModel.SORT_ROUTES_ID:
		route_sort = (route_sort + 1) % CatalogModel.ROUTE_SORTS.size()
	else:
		var tags: Array = [""] + CatalogModel.route_tags(routes_raw)
		route_tag = tags[(tags.find(route_tag) + 1) % tags.size()]
	set_routes(routes_raw)
	menu.focus_item(item_id)


## Fiche du parcours choisi (écran Prêt) : lignes de catalog_model.route_card(), vide sans fiche.
func route_card() -> Array:
	for r in routes_raw:
		if r is Dictionary and str(r.get("id", "")) == menu.world_id:
			return CatalogModel.route_card(r)
	return []


# --- plans et test de FTP (lot O12) -----------------------------------------------------------

## Réponse `plans` du core (list_plans, start_plan, stop_plan).
func on_plans(msg: Dictionary) -> void:
	plans = msg
	var active = msg.get("active", null)
	match _plan_request:
		"start":
			if active is Dictionary:
				plan_message = "Plan démarré : " + str(active.get("name", ""))
		"stop":
			if active == null:
				plan_message = "Plan arrêté"
	_plan_request = ""
	_refresh_plans()


## Séance que lance `start` avec plan_day ({} sans plan actif ou sans séance à faire).
func plan_day_session() -> Dictionary:
	var active = plans.get("active", null)
	if not (active is Dictionary) or active.get("plan_day", null) == null:
		return {}
	for key in ["today", "late"]:
		for d in active.get(key, []):
			if d is Dictionary and not d.get("done", false) and str(d.get("workout", "")) == str(active["plan_day"]):
				var out: Dictionary = d.duplicate()
				out["late"] = key == "late"
				return out
	return {}


static func _session_detail(d: Dictionary) -> String:
	var parts: Array[String] = ["%d min" % int(round(float(d.get("duration_s", 0.0)) / 60.0))]
	if d.get("tss", null) != null:
		parts.append("TSS %d" % int(round(float(d["tss"]))))
	if d.get("late", false):
		parts.append("en retard")
	return ", ".join(parts)


func _refresh_plans() -> void:
	var active = plans.get("active", null)
	var day := plan_day_session()
	if not day.is_empty():
		menu.set_plan_home("Séance du jour : " + str(day.get("name", "")), _session_detail(day))
	elif active is Dictionary:
		menu.set_plan_home("Plan : " + str(active.get("name", "")), _plan_progress(active))
	else:
		menu.set_plan_home("Choisir un plan")
	var items: Array = []
	if active is Dictionary:
		if not day.is_empty():
			items.append({"id": "today", "label": "Séance du jour : " + str(day.get("name", "")),
				"detail": _session_detail(day)})
		items.append({"id": "progress", "label": str(active.get("name", "")), "enabled": false,
			"detail": _plan_progress(active)})
		var nxt = active.get("next", null)
		if nxt is Dictionary:
			items.append({"id": "next", "label": "Prochaine : " + str(nxt.get("name", "")), "enabled": false,
				"detail": str(nxt.get("date", "")) + ", " + _session_detail(nxt)})
		items.append({"id": "stop", "label": "Arrêter le plan"})
	for p in plans.get("items", []):
		if not (p is Dictionary):
			continue
		var err = p.get("error", null)
		var detail := "%d semaines, %d séances" % [int(p.get("weeks", 0)), int(p.get("sessions", 0))]
		if p.get("active", false):
			detail += ", en cours"
		items.append({"id": "plan:" + str(p.get("id", "")), "label": str(p.get("name", p.get("id", ""))),
			"enabled": err == null, "detail": str(err) if err != null else detail})
	if plans.is_empty():
		items.append({"id": "none", "label": "Recherche des plans…", "enabled": false})
	elif plans.get("items", []).is_empty():
		items.append({"id": "none", "label": "Aucun plan", "enabled": false,
			"detail": "fichiers .toml dans ~/OpenRide/Plans"})
	menu.set_screen_items(PLANS, items)
	if _plan_shown != "":
		_refresh_plan_screen()


static func _plan_progress(active: Dictionary) -> String:
	if active.get("finished", false):
		return "terminé, %d %% fait" % int(round(float(active.get("done_pct", 0.0))))
	var week := "semaine %s / %d" % [str(active["week"]) if active.get("week", null) != null else "–",
		int(active.get("weeks", 0))]
	return "%s, %d %% fait (%d / %d)" % [week, int(round(float(active.get("done_pct", 0.0)))),
		int(active.get("done", 0)), int(active.get("total", 0))]


func _plan_entry(plan_id: String) -> Dictionary:
	for p in plans.get("items", []):
		if p is Dictionary and str(p.get("id", "")) == plan_id:
			return p
	return {}


func _refresh_plan_screen() -> void:
	var p := _plan_entry(_plan_shown)
	var active = plans.get("active", null)
	var is_active: bool = active is Dictionary and str(active.get("id", "")) == _plan_shown
	var items: Array = [{"id": "info", "label": "%d semaines, %d séances" % [int(p.get("weeks", 0)),
		int(p.get("sessions", 0))], "enabled": false}]
	if is_active:
		items.append({"id": "info_active", "label": "En cours", "enabled": false, "detail": _plan_progress(active)})
		items.append({"id": "stop", "label": "Arrêter ce plan"})
	else:
		items.append({"id": "start", "label": "Démarrer ce plan aujourd'hui"})
	menu.set_screen_items(PLAN, items, str(p.get("name", _plan_shown)))


## Texte du bilan d'un test de FTP : nouvelle FTP, ancienne, avertissements ; "" sans test.
static func _ftp_text(ftp: Dictionary) -> String:
	if ftp.is_empty():
		return ""
	var text := "Test de FTP : aucune FTP calculable"
	if ftp.get("ftp_w", null) != null:
		text = "Nouvelle FTP : %d W" % int(ftp["ftp_w"])
		if ftp.get("previous_ftp_w", null) != null:
			text += " (avant %d W)" % int(ftp["previous_ftp_w"])
	var warnings: Array[String] = []
	for w in ftp.get("warnings", []):
		warnings.append(str(FTP_WARNINGS.get(str(w), w)))
	if not warnings.is_empty():
		text += " ; " + ", ".join(warnings)
	return text


## Bilan : « Accepter » et « Garder » en tête tant qu'une FTP calculée reste à décider.
func _refresh_summary() -> void:
	var items: Array = []
	if ftp_offer.get("ftp_w", null) != null:
		items.append({"id": "accept_ftp", "label": "Accepter %d W" % int(ftp_offer["ftp_w"])})
		var prev = ftp_offer.get("previous_ftp_w", null)
		items.append({"id": "keep_ftp", "label": ("Garder %d W" % int(prev)) if prev != null else "Garder l'ancienne FTP"})
	for it in summary_model.menu_screen()["items"]:
		items.append(it)
	menu.set_screen_items(SUMMARY, items)


## Choix sur l'écran d'un plan, des plans ou du test de FTP ; renvoie l'action pour main.gd.
func _handle_plan_item(screen: String, item_id: String) -> Dictionary:
	if item_id == "today":
		var day := plan_day_session()
		menu.prepare_start("séance du jour (%s)" % str(day.get("name", "")), {"plan_day": true})
		return {}
	if item_id == "stop":
		var active = plans.get("active", null)
		var name := str(active.get("name", "")) if active is Dictionary else ""
		menu.confirm("Arrêter le plan %s ?" % name, {"action": "stop_plan"})
		return {}
	if screen == PLANS and item_id.begins_with("plan:"):
		_plan_shown = item_id.substr(5)
		_refresh_plan_screen()
		menu.push_screen(PLAN)
		return {}
	if screen == PLAN and item_id == "start":
		var active = plans.get("active", null)
		var act := {"action": "start_plan", "id": _plan_shown, "start_date": null}
		if active is Dictionary:
			menu.confirm("Remplacer le plan %s ?" % str(active.get("name", "")), act)
			return {}
		return _send_plan_request(act)
	return {}


## Commande start_plan ou stop_plan (après confirmation éventuelle) : retour à la liste des plans.
func _send_plan_request(act: Dictionary) -> Dictionary:
	_plan_request = "start" if act["action"] == "start_plan" else "stop"
	plan_message = "Démarrage du plan…" if _plan_request == "start" else "Arrêt du plan…"
	if menu.current_screen() == PLAN:
		menu.handle("Y_SHORT")
	return act


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
	ready_message = ""
	if menu.current_screen() == SETTING_EDIT:
		return _handle_edit(event)
	if menu.current_screen() == RECORD_TABLE and event == "A_SHORT":   # A court : bascule de table (T10)
		_handle_records(RECORD_TABLE, "toggle")
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
	match act.get("action", ""):
		"start_plan", "stop_plan":
			return _send_plan_request(act)
		"accept_ftp":
			_ftp_pending = true
			summary_message = "Enregistrement de la FTP…"
			return act
	if act.get("action", "") == "item" and act.get("screen", "") == MenuModel.HOME:
		if str(act["id"]) == "ftp":
			menu.push_screen(FTP_TEST)
			return {}
		if not plan_day_session().is_empty():
			return _handle_plan_item(PLANS, "today")
		plan_message = ""
		menu.push_screen(PLANS)
		return {"action": "list_plans"}
	if act.get("action", "") == "item" and act.get("screen", "") == MenuModel.ROUTES:
		_cycle_routes(str(act["id"]))
		return {}
	if act.get("action", "") == "item" and act.get("screen", "") in [PLANS, PLAN]:
		return _handle_plan_item(str(act["screen"]), str(act["id"]))
	if act.get("action", "") == "item" and act.get("screen", "") == FTP_TEST:
		for t in FTP_TESTS:
			if t[0] == str(act["id"]):
				menu.prepare_start(t[3], {"ftp_test": t[0]})
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
	if act.get("action", "") == "item" and act.get("screen", "") in [MenuModel.READY, RECORDS, RECORD_TABLE]:
		_handle_records(str(act["screen"]), str(act["id"]))
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
		match str(act["id"]):
			"accept_ftp":
				_ftp_pending = true
				summary_message = "Enregistrement de la FTP…"
				return {"action": "accept_ftp", "force": false}
			"keep_ftp":
				var prev = ftp_offer.get("previous_ftp_w", null)
				summary_message = ("FTP gardée : %d W" % int(prev)) if prev != null else "FTP gardée"
				ftp_offer = {}
				_refresh_summary()
				return {}
		act = summary_model.handle_action(str(act["id"]), menu)
		match act.get("action", ""):
			"new_session":
				show_details = false
				summary = {}
				ftp_offer = {}
				summary_message = ""
				_refresh_summary()
				# Le core reste en FINISHED jusqu'au prochain select_route : le monde choisi est rechargé.
				if menu.world_id != "":
					return {"action": "list", "route_id": menu.world_id}
				return {"action": "list"}
			"details":
				show_details = not show_details
				return {}
	return act


## Écrans des records (lot T10) : « Records du parcours » (écran Prêt) relit le fichier et liste les
## segments ; un segment ouvre sa table « sans bonus » ; « A : voir les temps avec bonus » bascule.
func _handle_records(screen: String, item_id: String) -> void:
	if screen == MenuModel.READY and item_id == "records":
		records.load_file(records_path)
		var title: String = "Records : " + (menu.world_name if menu.world_name != "" else menu.world_id)
		menu.set_screen_items(RECORDS, records.segment_items(menu.world_id), title)
		menu.push_screen(RECORDS)
	elif screen == RECORDS and item_id.begins_with("seg:"):
		_record_segment = item_id.substr(4)
		_record_bonus = false
		_refresh_record_table()
		menu.push_screen(RECORD_TABLE)
	elif screen == RECORD_TABLE and item_id == "toggle":
		_record_bonus = not _record_bonus
		_refresh_record_table()
		menu.focus_item("toggle")


func _refresh_record_table() -> void:
	menu.set_screen_items(RECORD_TABLE, records.table_items(menu.world_id, _record_segment, _record_bonus),
		records.table_title(_record_segment, _record_bonus))


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
	elif st["screen"] in [PLANS, PLAN]:
		st["status"] = plan_message
	elif st["screen"] == FTP_TEST:
		st["status"] = FTP_HINT
	elif st["screen"] == SUMMARY:
		st["status"] = summary_message
	elif st["screen"] == MenuModel.READY:
		st["status"] = ready_message
	elif st["screen"] == MenuModel.PAUSE:
		st["status"] = str(PAUSE_REASONS.get(pause_reason, pause_reason))
	st["card"] = route_card() if st["screen"] == MenuModel.READY else []
	return st
