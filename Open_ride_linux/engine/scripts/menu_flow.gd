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
## - « Test de FTP » : la rampe (seul test depuis le lot O19), puis écran Prêt, `start` avec ftp_test ; au bilan,
##   « Accepter » (accept_ftp ; résultat douteux : confirmation puis accept_ftp avec force) ou « Garder » ;
## - parcours : tri et filtre par étiquette en cycle en fin de liste, fiche du parcours sur l'écran Prêt ;
##   puis « Ajouter un parcours » et « Comment ça marche ? » (lot O22) : leur carte et l'écran « Aide
##   parcours » (route_help.gd) expliquent où déposer une trace et le monde ouvert ;
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
const RouteHelp := preload("res://scripts/route_help.gd")
const RecordsViewModel := preload("res://scripts/records_view_model.gd")
const RogueMenuModel := preload("res://scripts/rogue/rogue_menu_model.gd")
const GarageViewModel := preload("res://scripts/garage_view_model.gd")
const ProgressViewModel := preload("res://scripts/progress_view_model.gd")
const ProfilesViewModel := preload("res://scripts/profiles_view_model.gd")

const SUMMARY := "summary"
const CONNECT := "connect"
const PAIRING := PairingViewModel.SCREEN
const SETTING_EDIT := SettingsViewModel.EDIT_SCREEN
## Sous-écran de « Réglages » (Cycliste, Séance, Graphisme, Son, Vent) ; titre et éléments du groupe ouvert.
const SETTINGS_GROUP := "settings_group"
const WORKOUT_CREATE := WorkoutBuilder.SCREEN
const WORKOUT_IMPORT := "workout_import"
const ROUTE_HELP := RouteHelp.SCREEN
## Lignes de la liste des parcours dont la carte est un sujet de l'aide des parcours (lot O22).
const ROUTE_HELP_TOPICS := {MenuModel.ADD_ROUTE_ID: "add", MenuModel.HELP_ROUTES_ID: "choose"}
const PLANS := "plans"
const PLAN := "plan"
const FTP_TEST := "ftp_test"
## Records du parcours (série T, lot T10) : liste des segments, puis table d'un segment.
const RECORDS := "records"
const RECORD_TABLE := "record_table"
## Tests de FTP proposés (lot O10) : id, libellé, explication courte, nom de la séance (écran Prêt).
const FTP_TESTS := [
	["ramp", "Rampe", "≈ 25 min : +20 W par minute jusqu'à ne plus tenir ; FTP = 75 % de la meilleure minute",
		"test de FTP (rampe)"]]
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
## Chiffres de la séance en cours pour la carte de la pause : durée (t), distance (s) de la dernière trame et
## moyenne de la puissance mesurée en roulant (le core n'envoie pas de moyenne dans la trame d'état).
var _run_t := NAN
var _run_s := NAN
var _power_sum := 0.0
var _power_n := 0
## Dernier bilan reçu (objet `summary` de la trame en FINISHED).
var summary: Dictionary = {}
## « Voir le bilan détaillé » : blocs ERG en plus des lignes.
var show_details := false
var _lists_requested := false
var devices_model = DevicesViewModel.new()
var pairing = PairingViewModel.new()
var settings = SettingsViewModel.new()
## Groupe du sous-écran de « Réglages » ouvert en dernier ("" : aucun).
var settings_group := ""
## Versions de l'engine et du core pour la ligne « OpenRide X.Y.Z » des réglages (lots O2 et O4).
var engine_version := str(ProjectSettings.get_setting("application/config/version", "0.0.0"))
var core_version := ""
## Difficulté de la séance (trame d'état, lot Q1), pour le curseur de la pause.
var difficulty_pct := 50
## Mode d'une session libre (lot O18, ride_mode_of()) : "sim", "erg", "cadence" ; "" hors session libre
## (entraînement, run) : la pause n'a alors pas les lignes du mode. Cibles en cours pour ses lignes.
var ride_mode := ""
var erg_target_w := 0
var cadence_target_rpm := 0
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
var rogue = RogueMenuModel.new()
## `start_run` accusé par le core depuis le dernier lancement : l'écran d'attente peut céder la place à Prêt.
var _rogue_acked := false
## Garage (lot V8) : catalogue, progression et brouillon de l'avatar.
var garage = GarageViewModel.new()
## Bilan de progression de la séance (lot V9) : dernier message `xp_result` ({} sans), et qu'il a déjà été annoncé.
var progress = ProgressViewModel.new()
var xp_result: Dictionary = {}
var _xp_announced := false
var records_path := ""
var _record_segment := ""
var _record_bonus := false
## Raison de la dernière pause (`state.pause_reason`), "" hors pause.
var pause_reason := ""
## Profils de joueurs (série MJ, lot MJ8) : « Qui roule ? », nom du profil, gestion.
var profiles = ProfilesViewModel.new()


func _init() -> void:
	summary_model.attach_to_menu(menu)
	menu.add_screen({"id": CONNECT, "title": "Connexion des appareils", "on_back": "", "items": []})
	menu.add_screen({"id": PAIRING, "title": "Appareils", "on_back": MenuModel.SETTINGS, "items": []})
	menu.add_screen({"id": SETTINGS_GROUP, "title": "Réglages", "on_back": MenuModel.SETTINGS, "items": []})
	menu.add_screen({"id": SETTING_EDIT, "title": "Réglage", "on_back": MenuModel.SETTINGS, "items": []})
	menu.add_screen({"id": WORKOUT_CREATE, "title": "Créer un entraînement", "on_back": MenuModel.WORKOUTS,
		"items": []})
	menu.add_screen({"id": WORKOUT_IMPORT, "title": "Importer un entraînement", "on_back": MenuModel.WORKOUTS,
		"items": []})
	menu.add_screen({"id": ROUTE_HELP, "title": RouteHelp.TITLE, "on_back": MenuModel.ROUTES,
		"items": RouteHelp.items()})
	menu.add_screen({"id": PLANS, "title": "Plans d'entraînement", "on_back": MenuModel.HOME, "items": []})
	menu.add_screen({"id": PLAN, "title": "Plan", "on_back": PLANS, "items": []})
	menu.add_screen({"id": FTP_TEST, "title": "Test de FTP", "on_back": MenuModel.HOME, "items": []})
	_refresh_ftp_test()
	menu.add_screen({"id": RECORDS, "title": "Records", "on_back": MenuModel.READY, "items": []})
	menu.add_screen({"id": RECORD_TABLE, "title": "Records", "on_back": RECORDS, "items": []})
	menu.add_screen({"id": RogueMenuModel.SCREEN, "title": "Départ Cyber-Rogue", "on_back": MenuModel.HOME, "items": []})
	menu.add_screen({"id": RogueMenuModel.LOADING, "title": "Composition de la run…", "on_back": "", "items": []})
	menu.set_screen_items(RogueMenuModel.LOADING, [{"id": "wait", "label": "Composition de la run…", "enabled": false}])
	menu.add_screen({"id": GarageViewModel.SCREEN, "title": "Garage", "on_back": MenuModel.HOME, "items": []})
	for screen in [GarageViewModel.BIKE, GarageViewModel.OUTFIT, GarageViewModel.AVATAR]:
		menu.add_screen({"id": screen, "title": "Garage", "on_back": GarageViewModel.SCREEN, "items": []})
	menu.add_screen({"id": ProfilesViewModel.SCREEN, "title": "Qui roule ?", "on_back": MenuModel.HOME, "items": []})
	menu.add_screen({"id": ProfilesViewModel.NAME, "title": "Nom du profil", "on_back": ProfilesViewModel.SCREEN,
		"items": []})
	menu.add_screen({"id": ProfilesViewModel.MANAGE_LIST, "title": "Gérer un profil",
		"on_back": ProfilesViewModel.SCREEN, "items": []})
	menu.add_screen({"id": ProfilesViewModel.MANAGE, "title": "Gérer", "on_back": ProfilesViewModel.MANAGE_LIST,
		"items": []})
	_refresh_plans()
	_refresh_builder()
	_refresh_pairing()
	_refresh_settings()
	_refresh_pause_rows()


func is_visible() -> bool:
	return session_state != "" and session_state != "RUNNING"


## Trame `state` reçue ; renvoie les actions à exécuter (liste, éventuellement vide). `now_s` : horloge
## en secondes pour l'attente de l'écran de connexion (négatif : passage à l'accueil sans attente).
func _track_run(st: String, state: Dictionary) -> void:
	if st in ["IDLE", "READY"]:
		_run_t = NAN
		_run_s = NAN
		_power_sum = 0.0
		_power_n = 0
		return
	var t = state.get("t", null)
	var s = state.get("s", null)
	if (t is int or t is float) and not is_nan(_run_t) and float(t) + 1.0 < _run_t:   # nouvelle séance : le temps repart de zéro
		_power_sum = 0.0
		_power_n = 0
	if t is int or t is float:
		_run_t = float(t)
	if s is int or s is float:
		_run_s = float(s)
	var p = state.get("power", null)
	if st == "RUNNING" and (p is int or p is float) and float(p) >= 0.0 and float(p) < 3000.0:
		_power_sum += float(p)
		_power_n += 1


func on_state(state: Dictionary, now_s := -1.0) -> Array:
	var out: Array = []
	var st := str(state.get("session_state", ""))
	pause_reason = "" if state.get("pause_reason") == null else str(state["pause_reason"])
	_track_run(st, state)
	if state.get("devices") is Dictionary:
		devices = state["devices"]
	var diff = state.get("difficulty_pct", null)
	var pause_changed := false
	if (diff is int or diff is float) and int(diff) != difficulty_pct:
		difficulty_pct = int(diff)
		pause_changed = true
	var erg = state.get("erg", null)
	var rm: String = ride_mode_of(state)
	var tw: int = int(round(float(erg.get("target_w", 0)))) if erg is Dictionary else 0
	var cad: int = int(erg.get("cadence_target_rpm", 0)) if erg is Dictionary else 0
	if rm != ride_mode or tw != erg_target_w or cad != cadence_target_rpm:
		ride_mode = rm
		erg_target_w = tw
		cadence_target_rpm = cad
		pause_changed = true
	if pause_changed:
		_refresh_pause_rows()
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
		if st != "FINISHED":
			xp_result = {}
			_xp_announced = false
	# Run composée (lot R13) : `start_run` accusé par la trame qui suit son traitement. Le core passe de
	# READY à LOADING puis READY dans la même commande : l'état seul ne dit pas qu'une nouvelle run est prête.
	if _rogue_acked and st == "READY" and menu.current_screen() == RogueMenuModel.LOADING:
		_rogue_acked = false
		menu.set_rogue_ready(rogue.ready_text())
		menu.open_screen(MenuModel.READY)
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
	if profiles.should_ask():   # au moins deux profils joueur : « Qui roule ? » d'abord (plan MJ §3.1)
		profiles.asked = true
		_refresh_profiles()
		menu.push_screen(ProfilesViewModel.SCREEN)


func _refresh_pairing() -> void:
	menu.set_screen_items(PAIRING, pairing.menu_items())


## Écran « Réglages » : Appareils (lot N13), puis un sous-écran par groupe des réglages reçus du core
## (lot O4) ; le sous-écran ouvert est mis à jour avec la liste.
func _refresh_settings() -> void:
	var items: Array = [{"id": "devices", "label": "Appareils : rechercher et appairer"}]
	items.append_array(settings.group_items())
	if settings.items.is_empty():
		items.append({"id": "none", "label": "Réglages : en attente du core", "enabled": false})
	items.append(SettingsViewModel.version_item(engine_version, core_version))
	menu.set_screen_items(MenuModel.SETTINGS, items)
	_refresh_ftp_test()   # la rampe suit la FTP
	if settings_group != "":
		menu.set_screen_items(SETTINGS_GROUP, settings.menu_items(settings_group),
			SettingsViewModel.crumb(settings_group))


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
	if code in ["run_invalid", "item_locked", "busy"] and menu.current_screen() == RogueMenuModel.LOADING:
		rogue.message = "Échec : " + text
		_refresh_rogue()
		menu.open_screen(RogueMenuModel.SCREEN)
		return
	if menu.current_screen() in GarageViewModel.SCREENS and garage.on_error(code, text):
		_refresh_garage()
		return
	if menu.current_screen() in ProfilesViewModel.SCREENS and profiles.on_error(code, text):
		_refresh_profiles()
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
	if cmd_name == "start_run":
		_rogue_acked = true
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


## Terrain (`terrain` de `routes`, contrat 1.4) du parcours choisi, null sans parcours ou sans terrain.
func _route_terrain():
	for r in routes_raw:
		if r is Dictionary and menu.world_id != "" and str(r.get("id", "")) == menu.world_id:
			return r.get("terrain")
	return null


## Carte de détail de l'écran (lot « présentation des menus », étape 2), {} sans carte : fiche du
## parcours choisi (Prêt), du parcours ou de l'entraînement sous le focus (listes), aperçu de
## l'entraînement en création, en-tête du bilan (le bilan lui-même vient de `summary`). Fiches de
## catalog_model.gd (route_sheet, workout_sheet).
func card(st: Dictionary) -> Dictionary:
	var focus := int(st.get("focus", -1))
	var focused := str(st["items"][focus]["id"]) if focus >= 0 and focus < st["items"].size() else ""
	var screen := str(st["screen"])
	if screen == MenuModel.READY:
		return _sheet(routes_raw, menu.world_id, func(r): return CatalogModel.route_sheet(r))
	if screen == MenuModel.ROUTES:
		if focused in ROUTE_HELP_TOPICS:
			return RouteHelp.sheet(ROUTE_HELP_TOPICS[focused])
		return _sheet(routes_raw, focused, func(r): return CatalogModel.route_sheet(r))
	if screen == ROUTE_HELP:
		return RouteHelp.sheet(focused.substr(5)) if focused.begins_with("help:") else {}
	if screen == MenuModel.WORKOUTS:
		return _sheet(_workouts_raw, focused, func(w): return CatalogModel.workout_sheet(w, _ftp_w()))
	if screen == PLANS:
		return _plan_card(focused)
	if screen == PLAN:
		return _plan_card("plan:" + _plan_shown)
	if screen == FTP_TEST:
		for t in FTP_TESTS:
			if t[0] == focused:
				return CatalogModel.ftp_test_sheet(t[0], t[1], t[2], _ftp_w())
		return {}
	if screen == PAIRING:
		return pairing.sheet(focused)
	if screen == SETTINGS_GROUP:
		return settings.sheet(focused.substr(4)) if focused.begins_with("set:") else {}
	if screen == WORKOUT_CREATE:
		var blocks: Array = builder.profile()
		return CatalogModel.workout_sheet({"id": builder.workout_id(), "name": builder.workout_name(),
			"duration_s": builder.duration_s(), "block_count": blocks.size(), "profile": blocks}).merged({"title": "Aperçu"}, true)
	if screen == MenuModel.PAUSE:
		return CatalogModel.pause_sheet(_run_t, _run_s, _power_sum / _power_n if _power_n > 0 else -1.0)
	if screen == SUMMARY:
		return {"title": "Bilan de la séance"}
	if screen == RECORDS:
		return records.sheet_segment(menu.world_id, focused.substr(4)) if focused.begins_with("seg:") else {}
	if screen == RECORD_TABLE:
		if focused.begins_with("row:"):
			return records.sheet_row(menu.world_id, _record_segment, _record_bonus, int(focused.substr(4)))
		return records.sheet_segment(menu.world_id, _record_segment)
	if screen == SETTING_EDIT and str(settings.editing.get("key", "")).begins_with(GarageViewModel.KEY_PREFIX):
		return garage.sheet(GarageViewModel.AVATAR, "")
	if screen in GarageViewModel.SCREENS:
		return garage.sheet(screen, focused)
	return {}


func _sheet(raw: Array, id: String, make: Callable) -> Dictionary:
	for r in raw:
		if r is Dictionary and id != "" and str(r.get("id", "")) == id:
			return make.call(r)
	return {}


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


## Écran « Test de FTP » : une entrée par test, durée à droite (elle suit la FTP pour la rampe),
## explication dans la carte de détail.
func _refresh_ftp_test() -> void:
	var tests: Array = []
	for t in FTP_TESTS:
		tests.append({"id": t[0], "label": t[1],
			"detail": "≈ " + CatalogModel._format_fr_duration(CatalogModel.blocks_duration(CatalogModel.ftp_test_blocks(t[0], _ftp_w())))})
	menu.set_screen_items(FTP_TEST, tests)


## Profil [durée, début, fin] d'une séance de plan : test de FTP (blocs du core) ou entraînement de la liste.
func _session_blocks(workout_id: String) -> Array:
	if workout_id.begins_with("ftp_test:"):
		return CatalogModel.ftp_test_blocks(workout_id.substr(9), _ftp_w())
	for w in _workouts_raw:
		if w is Dictionary and str(w.get("id", "")) == workout_id and w.get("profile") is Array:
			return w["profile"]
	return []


func _plan_card(id: String) -> Dictionary:
	var active = plans.get("active", null)
	if id == "today" and not plan_day_session().is_empty():
		var day := plan_day_session()
		return CatalogModel.plan_day_sheet(day, _session_blocks(str(day.get("workout", ""))))
	if id == "stop" and active is Dictionary:
		return CatalogModel.active_plan_sheet(active)
	if id.begins_with("plan:"):
		var p := _plan_entry(id.substr(5))
		return CatalogModel.plan_sheet(p, active) if not p.is_empty() else {}
	return {}


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
	return CatalogModel.active_progress(active)


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


## Message `xp_result` (répété par le core) : gardé pour le bloc « Progression » ; renvoie le texte du bandeau
## « Niveau N ! » la première fois qu'un passage de niveau est annoncé, sinon "".
func on_xp_result(msg: Dictionary) -> String:
	if session_state != "FINISHED" or (_xp_announced and xp_result.is_empty()):
		return ""
	xp_result = msg
	_refresh_summary()
	if _xp_announced:
		return ""
	_xp_announced = true
	return str(progress_view().get("level_up", ""))


## Bloc « Progression » du bilan ({} sans `xp_result`).
func progress_view() -> Dictionary:
	var names := {}
	for it in garage.items:
		names[str(it["id"])] = {"name": it.get("name", it["id"]), "slot": it.get("slot", "")}
	return progress.view(xp_result, summary, names)


## Bilan : « Accepter » et « Garder » en tête tant qu'une FTP calculée reste à décider.
func _refresh_summary() -> void:
	var items: Array = []
	if ftp_offer.get("ftp_w", null) != null:
		items.append({"id": "accept_ftp", "label": "Accepter %d W" % int(ftp_offer["ftp_w"])})
		var prev = ftp_offer.get("previous_ftp_w", null)
		items.append({"id": "keep_ftp", "label": ("Garder %d W" % int(prev)) if prev != null else "Garder l'ancienne FTP"})
	for it in summary_model.menu_screen()["items"]:
		items.append(it)
		if it["id"] == "details" and garage.enabled and bool(progress_view().get("garage", false)):
			items.append({"id": "garage", "label": "Aller au Garage", "detail": "une pièce est devenue achetable"})
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
	if not settings.editing.is_empty():
		if menu.current_screen() in [SETTING_EDIT, MenuModel.PAUSE, SETTINGS_GROUP, WORKOUT_CREATE]:
			return _handle_edit(event)
		settings.cancel()   # menu quitté pendant un réglage (séance lancée, perte du core…)
	if menu.current_screen() == ProfilesViewModel.NAME:
		return _handle_name(event)
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
		"start_run":   # confirmation du premier lancement acceptée (lot R13) : l'avertissement n'est plus redemandé
			rogue.mark_warned()
			return _launch_rogue(act)
		"start_plan", "stop_plan":
			return _send_plan_request(act)
		"accept_ftp":
			_ftp_pending = true
			summary_message = "Enregistrement de la FTP…"
			return act
	if act.get("action", "") == "item" and act.get("screen", "") == MenuModel.HOME and str(act["id"]) == "rogue":
		_refresh_rogue()
		menu.push_screen(RogueMenuModel.SCREEN)
		return {}
	if act.get("action", "") == "item" and act.get("screen", "") == RogueMenuModel.SCREEN:
		return _handle_rogue(str(act["id"]))
	if act.get("action", "") == "item" and act.get("screen", "") == MenuModel.READY and str(act["id"]) == "rogue_change":
		_refresh_rogue()
		menu.open_screen(RogueMenuModel.SCREEN)
		return {}
	if act.get("action", "") == "item" and act.get("screen", "") in ProfilesViewModel.SCREENS:
		return _handle_profiles(str(act["screen"]), str(act["id"]))
	if act.get("action", "") == "item" and act.get("screen", "") == MenuModel.HOME:
		if str(act["id"]) == "profile":
			profiles.message = ""
			_refresh_profiles()
			menu.push_screen(ProfilesViewModel.SCREEN)
			return {"action": "list_profiles"}
		if str(act["id"]) == "garage":
			garage.message = ""
			_refresh_garage()
			menu.push_screen(GarageViewModel.SCREEN)
			return {"action": "list_garage"}
		if str(act["id"]) == "ftp":
			menu.push_screen(FTP_TEST)
			return {}
		if not plan_day_session().is_empty():
			return _handle_plan_item(PLANS, "today")
		plan_message = ""
		menu.push_screen(PLANS)
		return {"action": "list_plans"}
	if act.get("action", "") == "item" and act.get("screen", "") in GarageViewModel.SCREENS:
		return _handle_garage(str(act["screen"]), str(act["id"]))
	if act.get("action", "") == "item" and act.get("screen", "") == MenuModel.ROUTES:
		if str(act["id"]) in ROUTE_HELP_TOPICS:
			menu.push_screen(ROUTE_HELP)
			menu.focus_item("help:" + str(ROUTE_HELP_TOPICS[act["id"]]))
			return {}
		_cycle_routes(str(act["id"]))
		return {}
	if act.get("action", "") == "item" and act.get("screen", "") == ROUTE_HELP:
		return {}   # un sujet d'aide ne fait rien : son explication est dans la carte
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
		if item_id.begins_with("group:"):
			settings_group = item_id.substr(6)
			_refresh_settings()
			menu.push_screen(SETTINGS_GROUP)
		return {}
	if act.get("action", "") == "item" and act.get("screen", "") == SETTINGS_GROUP:
		var item_id := str(act["id"])
		if item_id.begins_with("set:") and settings.begin(item_id.substr(4)):
			_refresh_edit()
		if item_id == SettingsViewModel.RELAUNCH:
			return {"action": "relaunch"}   # lot O26 : décor vivant ou relief changés
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
			_refresh_edit()
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
		var key: String = SettingsViewModel.PAUSE_PREFIX + str(act["id"])
		settings.begin_pause(key, _pause_value(key))
		_refresh_pause_rows()
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
		if str(act["id"]) == "garage":
			garage.message = ""
			_refresh_garage()
			menu.push_screen(GarageViewModel.SCREEN)
			return {"action": "list_garage"}
		act = summary_model.handle_action(str(act["id"]), menu)
		match act.get("action", ""):
			"new_session":
				show_details = false
				xp_result = {}
				_xp_announced = true   # les copies du bilan encore envoyées par le core ne rouvrent rien
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


## Écran de départ du Cyber-Rogue (lot R13) : les trois premiers éléments font défiler leur valeur, « Lancer »
## demande confirmation au premier lancement (efforts au-delà de 140 % de la FTP possibles) puis envoie `start_run`.
func _refresh_rogue() -> void:
	menu.set_screen_items(RogueMenuModel.SCREEN, rogue.items())


func _handle_rogue(item_id: String) -> Dictionary:
	if item_id != "launch":
		rogue.cycle(item_id)
		_refresh_rogue()
		return {}
	var act := {"action": "start_run", "args": rogue.start_args()}
	if rogue.needs_warning():
		menu.confirm(RogueMenuModel.WARNING, act)
		return {}
	return _launch_rogue(act)


func _launch_rogue(act: Dictionary) -> Dictionary:
	_rogue_acked = false
	menu.open_screen(RogueMenuModel.LOADING)
	return act


## Garage (lot V8) : écrans reconstruits d'après le brouillon et le catalogue.
func _refresh_garage() -> void:
	for screen in GarageViewModel.SCREENS:
		menu.set_screen_items(screen, garage.screen_items(screen), garage.title(screen))


func _handle_garage(screen: String, item_id: String) -> Dictionary:
	var act := {}
	if screen == GarageViewModel.SCREEN:
		garage.message = ""
		match item_id:
			"bike":
				menu.push_screen(GarageViewModel.BIKE)
			"outfit":
				menu.push_screen(GarageViewModel.OUTFIT)
			"avatar":
				menu.push_screen(GarageViewModel.AVATAR)
	elif screen == GarageViewModel.AVATAR:
		if item_id.begins_with("field:"):
			settings.begin_with(garage.edit_item(item_id.substr(6)))
			menu.set_screen_items(SETTING_EDIT, settings.edit_items(), str(settings.editing.get("label", "Réglage")))
			menu.push_screen(SETTING_EDIT)
		elif item_id == "save":
			act = garage.save()
			if not act.is_empty():
				garage.message = "Enregistrement…"
		elif item_id == "cancel":
			garage.cancel()
	else:
		var todo: Dictionary = garage.activate(item_id)
		match todo.get("action", ""):
			"equip":
				act = todo
			"confirm_buy":
				menu.confirm(str(todo["title"]), {"action": "buy", "item_id": todo["item_id"]})
	_refresh_garage()
	return act


# --- profils de joueurs (série MJ, lot MJ8) ----------------------------------------------------

func _refresh_profiles() -> void:
	menu.set_profile(profiles.home_label(), profiles.home_title())
	menu.set_screen_items(ProfilesViewModel.SCREEN, profiles.who_items(), "Qui roule ?")
	menu.set_screen_items(ProfilesViewModel.MANAGE_LIST, profiles.manage_list_items(), "Gérer un profil")
	menu.set_screen_items(ProfilesViewModel.MANAGE, profiles.manage_items(), profiles.manage_title())
	menu.set_screen_items(ProfilesViewModel.NAME, profiles.grid_items(), profiles.name_title())


func _handle_profiles(screen: String, item_id: String) -> Dictionary:
	var act := {}
	match screen:
		ProfilesViewModel.SCREEN:
			if item_id == "new":
				profiles.begin_create()
				_open_name()
			elif item_id == "manage":
				menu.push_screen(ProfilesViewModel.MANAGE_LIST)
			elif item_id.begins_with("p:"):
				var id := item_id.substr(2)
				if id == profiles.active:
					menu.reset()   # profil déjà en cours : retour à l'accueil
				else:
					profiles.message = "Changement de profil…"
					act = {"action": "select_profile", "id": id}
		ProfilesViewModel.MANAGE_LIST:
			profiles.manage_id = item_id.substr(2)
			_refresh_profiles()
			menu.push_screen(ProfilesViewModel.MANAGE)
		ProfilesViewModel.MANAGE:
			if item_id == "rename":
				profiles.begin_rename(profiles.manage_id)
				_open_name()
			elif item_id == "delete":
				menu.confirm(profiles.delete_question(), {"action": "delete_profile", "id": profiles.manage_id})
	_refresh_profiles()
	return act


func _open_name() -> void:
	_refresh_profiles()
	menu.push_screen(ProfilesViewModel.NAME)
	menu.focus_item("c:0")


## Saisie du nom (maquette E) : Z écrit la lettre, Y efface (nom vide : retour), A maintenu valide,
## + et − maintenus sautent d'une ligne de la grille.
func _handle_name(event: String) -> Dictionary:
	var act := {}
	match event:
		"Z_SHORT":
			act = profiles.press_cell(_focused_id())
		"A_LONG":
			act = profiles.validate()
		"Y_SHORT":
			if not profiles.backspace():
				menu.handle("Y_SHORT")
		"PLUS_LONG", "MINUS_LONG":
			_move_grid(ProfilesViewModel.GRID_COLUMNS * (1 if event == "PLUS_LONG" else -1))
		_:
			menu.handle(event)
	_refresh_profiles()
	return act


func _focused_id() -> String:
	var st: Dictionary = menu.state()
	var i := int(st["focus"])
	return str(st["items"][i]["id"]) if i >= 0 and i < st["items"].size() else ""


func _move_grid(step: int) -> void:
	var st: Dictionary = menu.state()
	var n: int = st["items"].size()
	menu.focus_item(str(st["items"][clampi(int(st["focus"]) + step, 0, n - 1)]["id"]))


## Événement d'un clic sur un élément : écrire la lettre sur la grille du nom, valider ailleurs.
func click_event() -> String:
	return "Z_SHORT" if menu.current_screen() == ProfilesViewModel.NAME else "A_LONG"


## Saisie du nom au clavier : vrai si la touche a servi (lettre, chiffre, espace, tiret, Entrée, Retour arrière).
func name_key(ch: String, enter: bool, backspace: bool) -> Dictionary:
	if menu.current_screen() != ProfilesViewModel.NAME:
		return {"used": false}
	var act := {}
	var used := true
	if enter:
		act = profiles.validate()
	elif backspace:
		profiles.backspace()
	else:
		used = profiles.type_text(ch)
	_refresh_profiles()
	return {"used": used, "action": act}


func on_profiles(msg: Dictionary) -> void:
	var waiting: bool = profiles.message == "Enregistrement…"
	profiles.on_profiles(msg)
	if waiting and menu.current_screen() == ProfilesViewModel.NAME and profiles.name_mode == "rename":
		menu.open_screen(ProfilesViewModel.SCREEN)   # renommé : retour à la liste
	elif menu.current_screen() == ProfilesViewModel.MANAGE and profiles._find(profiles.manage_id).is_empty():
		menu.open_screen(ProfilesViewModel.SCREEN)   # supprimé
	_refresh_profiles()


## `hello_ack.config.profile` (démarrage ou changement de profil) : accueil du nouveau profil.
func on_hello_profile(block) -> void:
	var changed: bool = profiles.on_hello(block)
	if changed and menu.current_screen() in ProfilesViewModel.SCREENS:
		menu.reset()
	_refresh_profiles()


## Garage : `garage` du core (liste complète), `progression` (après chaque réussite) et hello_ack.
func on_garage(list: Array) -> void:
	garage.on_garage(list)
	_refresh_garage()


func on_progression(msg: Dictionary) -> void:
	garage.on_progression(msg)
	if garage.message == "Enregistrement…":
		garage.message = "Enregistré"
	_refresh_garage()


func on_hello_progression(progression) -> void:
	garage.on_hello(progression)
	menu.set_garage(garage.enabled)
	_refresh_garage()


## Aperçu 3D du Garage pour l'état de menu `st` ({} hors Garage) : réglages de l'avatar et `look` choisis.
func garage_preview(st: Dictionary) -> Dictionary:
	var screen := str(st["screen"])
	var focus := int(st.get("focus", -1))
	var focused := str(st["items"][focus]["id"]) if focus >= 0 and focus < st["items"].size() else ""
	if screen == SETTING_EDIT and str(settings.editing.get("key", "")).begins_with(GarageViewModel.KEY_PREFIX):
		return garage.preview(GarageViewModel.AVATAR, "", settings.editing)
	if screen in GarageViewModel.SCREENS:
		return garage.preview(screen, focused)
	return {}


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


## Réglage en cours de modification : la rangée de la liste ouverte (Réglages, Créer un entraînement)
## passe en mode édition ; la difficulté de la pause se règle de même dans sa rangée. Seuls les champs
## de l'avatar du Garage gardent leur écran.
## Mode d'une session libre d'après une trame `state` (lot O18) : "sim" sans objet `erg`, "erg" ou
## "cadence" selon `erg.kind` ; "" pendant un entraînement (`kind` absent ou `workout`) ou une run.
static func ride_mode_of(state: Dictionary) -> String:
	if str(state.get("mode", "")) == "ROGUE":
		return ""
	var erg = state.get("erg", null)
	if not erg is Dictionary:
		return "sim"
	match str(erg.get("kind", "workout")):
		"free":
			return "erg"
		"cadence":
			return "cadence"
	return ""


## Valeur en cours d'une ligne de la pause (clé « pause.… »).
func _pause_value(key: String):
	if key == SettingsViewModel.PAUSE_RIDE_MODE:
		return ride_mode
	if key == SettingsViewModel.PAUSE_TARGET_W:
		return erg_target_w
	if key == SettingsViewModel.PAUSE_CADENCE:
		return cadence_target_rpm
	return difficulty_pct


## Lignes modifiables de la pause : difficulté ; en session libre, mode, puis puissance cible (ERG) ou
## cadence cible (ERG cadence). La ligne en cours de modification passe en mode édition.
func _refresh_pause_rows() -> void:
	var keys := [SettingsViewModel.PAUSE_DIFFICULTY]
	if ride_mode != "":
		keys.append(SettingsViewModel.PAUSE_RIDE_MODE)
	if ride_mode == "erg":
		keys.append(SettingsViewModel.PAUSE_TARGET_W)
	elif ride_mode == "cadence":
		keys.append(SettingsViewModel.PAUSE_CADENCE)
	var rows: Array = []
	for key in keys:
		var it: Dictionary = SettingsViewModel.pause_item(key, _pause_value(key))
		var ed: Dictionary = settings.editing if str(settings.editing.get("key", "")) == key else {}
		rows.append(SettingsViewModel.row(key.substr(SettingsViewModel.PAUSE_PREFIX.length()), it, ed))
	menu.set_pause_rows(rows)


func _refresh_edit() -> void:
	match menu.current_screen():
		SETTING_EDIT:
			menu.set_screen_items(SETTING_EDIT, settings.edit_items())
		MenuModel.PAUSE:
			_refresh_pause_rows()
		WORKOUT_CREATE:
			menu.set_screen_items(WORKOUT_CREATE, builder.menu_items(str(settings.editing.get("key", "")),
				settings.editing.get("value", 0)))
		_:
			_refresh_settings()


## Modification d'un réglage (plan des boutons, spécification générale §7.1) : + / B court, A court et
## flèches gauche, droite changent la valeur d'un pas, + / B long de cinq pas ; A maintenu enregistre,
## Y annule et rend la valeur d'avant.
func _handle_edit(event: String) -> Dictionary:
	match event:
		"PLUS_SHORT", "MINUS_SHORT", "A_SHORT", "LEFT_SHORT", "RIGHT_SHORT", "PLUS_LONG", "MINUS_LONG":
			var dir := -1 if event in ["MINUS_SHORT", "LEFT_SHORT", "MINUS_LONG"] else 1
			for i in range(MenuModel.LONG_STEP if event.ends_with("_LONG") else 1):
				settings.step(dir)
			_refresh_edit()
		"A_LONG":
			var act: Dictionary = settings.commit()
			if menu.current_screen() == SETTING_EDIT:
				menu.handle("Y_SHORT")
			if act.get("action", "") == "set_difficulty":
				difficulty_pct = int(act["pct"])
			if act.get("action", "") == "set_ride_mode":   # affiché tout de suite, la trame suivante confirme
				ride_mode = str(act["args"]["mode"])
			if act.get("action", "") == "garage_set":
				garage.set_field(str(act["key"]), int(act["value"]))
				_refresh_garage()
				return {}
			if act.get("action", "") == "builder_set":
				builder.set_value(str(act["key"]), act["value"])
				_refresh_builder()
				return {}
			_refresh_edit()
			return act
		"Y_SHORT":
			settings.cancel()
			if menu.current_screen() == SETTING_EDIT:
				menu.handle("Y_SHORT")
			else:
				_refresh_edit()
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
	st["status_error"] = false
	if st["screen"] == PAIRING:
		st["status"] = pairing.message
		st["status_error"] = pairing.message_error
	elif st["screen"] in [MenuModel.WORKOUTS, WORKOUT_CREATE, WORKOUT_IMPORT]:
		st["status"] = workout_message
	elif st["screen"] in [PLANS, PLAN]:
		st["status"] = plan_message
	elif st["screen"] == FTP_TEST:
		st["status"] = FTP_HINT
	elif st["screen"] == SUMMARY:
		st["status"] = summary_message
	elif st["screen"] == MenuModel.READY:
		st["status"] = ready_message if ready_message != "" else garage.route_advice(_route_terrain())
	elif st["screen"] in GarageViewModel.SCREENS:
		st["status"] = garage.message
	elif st["screen"] in ProfilesViewModel.SCREENS:
		st["status"] = profiles.message
		st["status_error"] = profiles.message.begins_with("Nom refusé") or profiles.message.begins_with("Nom vide")
	if st["screen"] == ProfilesViewModel.NAME:
		st["grid"] = {"columns": ProfilesViewModel.GRID_COLUMNS, "text": profiles.name_text}
	elif st["screen"] == MenuModel.PAUSE:
		st["status"] = str(PAUSE_REASONS.get(pause_reason, pause_reason))
	st["card"] = card(st)
	st["preview"] = garage_preview(st)
	st["progress"] = progress_view() if st["screen"] == SUMMARY else {}
	st["editing"] = not settings.editing.is_empty()
	return st
