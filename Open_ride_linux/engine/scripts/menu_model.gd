extends RefCounted

## Navigation des menus au Click et au clavier (Lot K5, SRS §4.5 et §7, Contrat IPC v1 §4), sans nœud.
##
## Machine à états pure : écrans décrits par des données, focus, validation, retour et confirmation.
## Elle n'envoie rien : `handle()` renvoie l'état et, le cas échéant, une action à exécuter par
## l'appelant (commande IPC ou action interne à l'engine). L'affichage et les listes réelles (contrat
## IPC v1.1) restent au lot G. Pas de class_name : charger par preload("res://scripts/menu_model.gd").
##
## Entrées (mêmes noms que l'IPC, plan des boutons de la spécification générale §7.1) : PLUS_SHORT et
## RIGHT_SHORT et A_SHORT (suivant), MINUS_SHORT et LEFT_SHORT (précédent), PLUS_LONG et MINUS_LONG
## (cinq éléments plus loin, plus haut, bornés à la liste), A_LONG (valider), Y_SHORT (écran précédent ;
## sur l'écran de pause, reprendre). Z, flèches haut et bas : rien dans un menu. Le clavier produit les
## mêmes événements, touche pour touche (key_map.gd, lot O17). Tout autre événement est ignoré.
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
## « Session ERG » ouvre la liste des entraînements, qui finit par « Créer un entraînement » et
## « Importer un fichier » (lot N16, traités par menu_flow.gd).
## Écrans ajoutés par add_screen() (bilan de fin du lot N4) : valider un élément renvoie
## {"action": "item", "screen": écran, "id": élément}, à traiter par l'appelant (menu_flow.gd, lot N6).
##
## Plans et test de FTP (lot O12) : l'accueil gagne « Séance du jour » ou « Choisir un plan » (libellé
## donné par set_plan_home()) et « Test de FTP » ; les deux renvoient une action « item » de l'accueil.
## prepare_start() prépare une séance démarrée avec des arguments de `start` (plan_day, ftp_test) :
## écran Prêt, en passant par les parcours sans monde choisi ; choisir un entraînement ou la session
## libre l'annule. La liste des parcours finit par le tri et le filtre par étiquette (SORT_ROUTES_ID,
## FILTER_ROUTES_ID), traités par menu_flow.gd.
##
## Bots (lots O7 et O35) : l'écran Prêt gagne « Bot 1 : … » (A long change : aucun, 200, 250, 300 W, 90,
## 100, 110 % de la FTP, profils) et « Fantôme de la dernière séance : non/oui » ; `start` les transmet dans
## l'argument `bots` (contrat 1.3) quand l'un d'eux est choisi, sinon n'envoie rien. Jusqu'à MAX_BOTS bots
## (lot O35, la limite du core) : la ligne « Bot n+1 : aucun » n'apparaît que quand « Bot n » est choisi ;
## remettre un bot à « aucun » le retire et remonte les suivants. Un nouvel accueil les remet à zéro.
## Peloton (lot PL1, 3.0) : sous le fantôme, « Peloton : aucun » (A long : 4, 8, 11 bots) ajoute des bots à profil
## (rouleur, grimpeur, sprinteur, diesel, en cycle) au niveau des bots du réglage `bots.level_pct` (élément
## `{kind: "profile", profile}` sans `level_pct`), après les bots choisis un par un, sans dépasser
## MAX_RIDER_BOTS bots en tout (la limite du core).
## Records (série T, lot T10) : l'écran Prêt finit par « Records du parcours », qui renvoie une action
## « item » de l'écran Prêt (écrans des records ouverts par menu_flow.gd).
##
## Vélodrome (série VD, lot VD10) : sur une piste (`track_ids`, parcours d'étiquette « velodrome » posés par
## menu_flow.gd) et en session libre ou ERG, l'écran Prêt devient celui du vélodrome : « Lancer : épreuve »,
## « Épreuve : … » (A long : épreuve suivante), un réglage par ligne (« Tours : 40 », A long : valeur suivante),
## valeurs et défauts du core (`hello_ack.config.track`, set_track_events), « Changer d'entraînement » ou
## « Passer en session ERG » en séance libre seulement (la seule épreuve qui accepte l'ERG), « Changer de
## parcours ». `start` part avec `mode` « track » et `track` = {event, réglages}. Passer à une autre épreuve en
## ERG revient en SIM (sans entraînement). Les choix restent jusqu'à la fermeture de l'engine.
##
## Séance conseillée (série CO, lot CO5) : « Séance conseillée » en tête de l'accueil, sous le profil, quand le core a
## répondu à get_coach (set_coach_home()) ; elle renvoie une action « item » de l'accueil (écrans de menu_flow.gd).
## choose_workout() prépare un entraînement (liste des entraînements, entraînement conseillé) ; prepare_coach_race()
## prépare la course conseillée (`mode` « coach » : écran Prêt avec « Démarrer » et le fantôme, bots du format).
##
## Derniers choix du profil (lot O32, hello_ack.config.last_choices, set_last_choices()) : un nouvel accueil
## remet le bot et le fantôme de la dernière séance au lieu de « aucun » ; la liste des entraînements s'ouvre
## sur le dernier entraînement choisi, celle des parcours sur le parcours en cours (rechargé par le core).

const EVENTS := ["PLUS_SHORT", "MINUS_SHORT", "PLUS_LONG", "MINUS_LONG", "A_SHORT", "A_LONG", "Y_SHORT",
	"LEFT_SHORT", "RIGHT_SHORT"]
## Éléments sautés par un appui long sur + ou −.
const LONG_STEP := 5

const HOME := "home"
const ROUTES := "routes"
const WORKOUTS := "workouts"
const READY := "ready"
const SETTINGS := "settings"
const CONFIRM := "confirm"
const PAUSE := "pause"

const NO_WORKOUT_ID := "_sim"
const TrackNames := preload("res://scripts/track/track_names.gd")
const TRACK_EVENT_ID := "track_event"
const TRACK_OPTION_PREFIX := "track:"
## Modes de séance de l'accueil, dans l'ordre d'affichage : {mode: libellé}. Filtrés par `modes`, la
## liste que le core annoncera dans hello_ack.config (2.0, PLAN_SERIE_R §6) ; absente : DEFAULT_MODES.
## Un nouveau mode (Cyber-Rogue) n'ajoute qu'une ligne ici.
const HOME_MODES := {"ride": "Session libre", "erg": "Session ERG", "open_world": "Monde ouvert",
	"rogue": "Cyber-Rogue", "wtf": "Mode WTF", "survivor": "Dernier survivant"}
const DEFAULT_MODES := ["ride", "erg"]
## Ligne d'explication d'un mode de l'accueil (lot O22), à droite de son libellé.
const HOME_DETAILS := {"open_world": "route créée en roulant", "survivor": "à chaque arche, le dernier sort"}
## Fin de la liste des entraînements (sous-menu ERG, lot N16) : créer ou importer un entraînement.
const CREATE_WORKOUT_ID := "_create"
const IMPORT_WORKOUT_ID := "_import"
## Dernière ligne de la liste : « Comment ça marche ? » ouvre l'aide du sous-menu ERG (workout_help.gd).
## « Saisir du QWKcode (clavier) » ouvre la saisie du QWKcode de GoldenCheetah (qwk_editor.gd, lot O21).
const QWK_WORKOUT_ID := "_qwk"
const HELP_WORKOUT_ID := "_help"
## Lignes « Bot n » de l'écran Prêt, fantôme en plus (lot O35).
const MAX_BOTS := 4
## Bots en tout, peloton compris, fantôme en plus (lot PL1) : MAX_CONSTANT_BOTS du core (bots.py).
const MAX_RIDER_BOTS := 11
## Tailles du peloton (lot PL1), dans l'ordre du cycle, et profils de ses bots, en cycle.
const PELOTON_CHOICES := [0, 4, 8, 11]
const PELOTON_PROFILES := ["rouleur", "climber", "sprinter", "diesel"]
## Bots de l'écran Prêt (lots O7 et O35), dans l'ordre du cycle : libellé et élément de l'argument `bots` de `start`.
## Bots à profil (lots T12 et T13) : chaque profil à 90, 100 et 110 % de ta FTP, calibré par le core.
const BOT_CHOICES := [["aucun", {}], ["200 W", {"kind": "constant", "power_w": 200}],
	["250 W", {"kind": "constant", "power_w": 250}], ["300 W", {"kind": "constant", "power_w": 300}],
	["90 % de la FTP", {"kind": "constant", "ftp_pct": 90}], ["100 % de la FTP", {"kind": "constant", "ftp_pct": 100}],
	["110 % de la FTP", {"kind": "constant", "ftp_pct": 110}],
	["Grimpeur 90 %", {"kind": "profile", "profile": "climber", "level_pct": 90}], ["Grimpeur 100 %", {"kind": "profile", "profile": "climber", "level_pct": 100}], ["Grimpeur 110 %", {"kind": "profile", "profile": "climber", "level_pct": 110}],
	["Rouleur 90 %", {"kind": "profile", "profile": "rouleur", "level_pct": 90}], ["Rouleur 100 %", {"kind": "profile", "profile": "rouleur", "level_pct": 100}], ["Rouleur 110 %", {"kind": "profile", "profile": "rouleur", "level_pct": 110}],
	["Sprinteur 90 %", {"kind": "profile", "profile": "sprinter", "level_pct": 90}], ["Sprinteur 100 %", {"kind": "profile", "profile": "sprinter", "level_pct": 100}], ["Sprinteur 110 %", {"kind": "profile", "profile": "sprinter", "level_pct": 110}],
	["Diesel 90 %", {"kind": "profile", "profile": "diesel", "level_pct": 90}], ["Diesel 100 %", {"kind": "profile", "profile": "diesel", "level_pct": 100}], ["Diesel 110 %", {"kind": "profile", "profile": "diesel", "level_pct": 110}]]
## Fin de la liste des parcours (bibliothèque, lot O12) : tri et filtre par étiquette, en cycle.
const SORT_ROUTES_ID := "_sort"
const FILTER_ROUTES_ID := "_filter"
## Fin de la liste des parcours (lot O22) : « Ajouter un parcours » (sa carte explique l'ajout, A
## maintenu ouvre l'écran « Importer une trace », lot O23) et « Comment ça marche ? » (aide des parcours,
## route_help.gd).
const ADD_ROUTE_ID := "_add_route"
const HELP_ROUTES_ID := "_route_help"

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
## Mode de la séance préparée : "free" (session libre, SIM), "erg", "rogue", "wtf" (mode « What the fuck »,
## SIM seulement, lot WTF3) ou "survivor" (Dernier survivant, SIM seulement, lot DS7).
var mode := "free"
## Écran Prêt du Dernier survivant (lot DS7), posé par menu_flow.gd : rangées des réglages du mode
## (SettingsViewModel.row, ids « set:clé ») et ligne « Lancer » ({enabled, detail} : « 4 arches sur 8 km », ou
## parcours trop court).
var survivor_rows: Array = []
var survivor_launch := {"enabled": true, "detail": ""}
## Vélodrome (lot VD10) : parcours qui sont des pistes, épreuves du core (épreuve → réglage → [défaut, valeurs]),
## épreuve choisie et valeurs choisies par épreuve.
var track_ids: Array = []
var track_events: Dictionary = {}
var track_event := "free"
var track_values: Dictionary = {}
## Engine lancé en session simulée (--sim-session) : l'accueil propose de revenir au matériel réel.
var sim_session := false
var _routes_return := HOME
## Modes annoncés par le core (set_modes) ; les modes inconnus de HOME_MODES sont ignorés.
var modes: Array = DEFAULT_MODES.duplicate()
## Écran Prêt du Cyber-Rogue (lot R13) : `mode` « rogue » et rappel des choix (objectif, durée, W').
func set_rogue_ready(text: String) -> void:
	mode = "rogue"
	rogue_ready = text
	_clear_start()
	_refresh_home()


## Entrée des plans de l'accueil (lot O12) : « Séance du jour » avec un plan actif, sinon « Choisir un plan ».
var plan_label := "Choisir un plan"
var plan_detail := ""
## Séance préparée par prepare_start() : nom affiché sur l'écran Prêt et arguments de `start` ({} sinon).
var start_name := ""
var start_args: Dictionary = {}
## Bots choisis (index de BOT_CHOICES, jamais 0, au plus MAX_BOTS, dans l'ordre des lignes) et fantôme
## demandé, pour la séance préparée (lots O7 et O35).
var bot_choices: Array[int] = []
var ghost := false
## Taille du peloton choisie (une valeur de PELOTON_CHOICES, lot PL1) ; celle de la dernière séance.
var peloton := 0
var last_peloton := 0
## Écran de pause (lot N18) : lignes modifiables reçues de menu_flow (set_pause_rows), bots modifiés depuis
## l'ouverture de la pause (envoyés par `set_bots` avant `resume`).
var _pause_rows: Array = []
var pause_bots_changed := false
## Derniers choix du profil (lot O32) : bots et fantôme remis par reset(), entraînement mis sous le focus.
var last_bots: Array[int] = []
var last_ghost := false
var last_workout := ""
## Cyber-Rogue (lot R13) : rappel des choix affiché sur l'écran Prêt quand `mode` vaut « rogue ».
var rogue_ready := ""
## Garage (lot V8) : l'accueil gagne « Garage » quand le core annonce une progression (set_garage).
var garage := false
## Profil de joueur (série MJ, lot MJ8) : ligne « Profil : … » en tête de l'accueil ("" : aucune) et
## titre de l'accueil (« OpenRide — Cycliste A »).
var profile_label := ""
var home_title := "OpenRide"
## Séance interrompue d'un lancement précédent (lot O34) : ligne en tête de l'accueil ("" : aucune).
var interrupted_label := ""
var interrupted_detail := ""
## Séance conseillée (série CO, lot CO5) : détail de la ligne « Séance conseillée » de l'accueil (besoin et durée) ;
## "" tant que le core n'a pas répondu à get_coach : pas de ligne (comme la séance interrompue).
var coach_detail := ""
## Course conseillée (lot CO5) : `mode` « coach », rappel du format affiché sur l'écran Prêt.
var coach_ready := ""


func set_coach_home(detail: String) -> void:
	coach_detail = detail
	_refresh_home()


func set_interrupted(label: String, detail: String) -> void:
	interrupted_label = label
	interrupted_detail = detail
	_refresh_home()


func set_profile(label: String, title: String) -> void:
	profile_label = label
	home_title = title
	_refresh_home()


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
		PAUSE: {"id": PAUSE, "title": "Pause", "on_back": "", "items": []},
	}
	_pause_rows = [{"id": "difficulty", "label": "Difficulté"}]   # remplacées par menu_flow (set_pause_rows)
	_refresh_pause()
	set_items(ROUTES, [])
	set_items(WORKOUTS, [])
	_refresh_home()
	reset()


func _refresh_home() -> void:
	var world := world_name if world_name != "" else "à choisir"
	var items := [_item("world", "Parcours : " + world)]
	if coach_detail != "":
		items.push_front(_item("coach", "Séance conseillée", true, coach_detail))
	if profile_label != "":
		items.push_front(_item("profile", profile_label))
	if interrupted_label != "":
		items.push_front(_item("interrupted", interrupted_label, true, interrupted_detail))
	_screens[HOME]["title"] = home_title
	for m in HOME_MODES:
		if m in modes:
			items.append(_item(m, HOME_MODES[m], true, str(HOME_DETAILS.get(m, ""))))
	items.append_array([_item("plan", plan_label, true, plan_detail), _item("ftp", "Test de FTP"),
		_item("history", "Historique", true, "séances, semaines, tests de FTP"),
		_item("sim", "Revenir au matériel réel" if sim_session else "Session simulée")])
	if garage:
		items.append(_item("garage", "Garage"))
	items.append_array([_item("settings", "Réglages"), _item("quit", "Quitter")])
	# Ligne ajoutée ou retirée pendant l'affichage (séance conseillée arrivée après l'accueil, lot CO5) : le focus
	# reste sur le même élément, comme pour une liste qui change (set_screen_items).
	var focused_id := ""
	if _screen == HOME and _focus >= 0 and _focus < _screens[HOME]["items"].size():
		focused_id = _screens[HOME]["items"][_focus]["id"]
	_screens[HOME]["items"] = items
	if focused_id != "":
		_focus = _first_enabled_from(_index_of(focused_id), 1)
	if mode == "rogue":
		_screens[READY]["items"] = [_item("start", "Démarrer", true, rogue_ready),
			_item("rogue_change", "Changer les choix")]
		_screens[READY]["title"] = "Prêt : Cyber-Rogue"
		return
	if mode == "coach":
		_screens[READY]["items"] = [_item("start", "Démarrer", true, coach_ready), _item("ghost",
			"Fantôme de la dernière séance : " + ("oui" if ghost else "non"))]
		_screens[READY]["title"] = "Prêt : " + start_name + ("" if world_name == "" else " — " + world_name)
		return
	if mode == "survivor":
		_screens[READY]["items"] = [_item("start", "Lancer", bool(survivor_launch.get("enabled", true)),
			str(survivor_launch.get("detail", ""))), _item("change_route", "Changer de parcours")] + survivor_rows
		_screens[READY]["title"] = "Prêt : Dernier survivant" + ("" if world_name == "" else " — " + world_name)
		return
	if is_track():
		_screens[READY]["items"] = _track_items()
		_screens[READY]["title"] = "Prêt : " + (world_name if world_name != "" else "vélodrome")
		return
	if mode == "wtf":
		_screens[READY]["items"] = [_item("start", "Démarrer"), _item("wtf_rules", "Changer les règles"),
			_item("change_route", "Changer de parcours")] + _bot_items() \
			+ [_item("ghost", "Fantôme de la dernière séance : " + ("oui" if ghost else "non")), _peloton_item()]
		_screens[READY]["title"] = "Prêt : mode WTF" + ("" if world_name == "" else " — " + world_name)
		return
	_screens[READY]["items"] = [
		_item("start", "Démarrer"),
		_item("workout", "Changer d'entraînement" if mode == "erg" else "Passer en session ERG"),
		_item("change_route", "Changer de parcours"),
	] + _bot_items() + [
		_item("ghost", "Fantôme de la dernière séance : " + ("oui" if ghost else "non")),
		_peloton_item(),
		_item("records", "Records du parcours")]
	var what := "session ERG" if mode == "erg" else "session libre"
	if start_name != "":
		what = start_name
	_screens[READY]["title"] = "Prêt : " + what + ("" if world_name == "" else " — " + world_name)


## Écran Prêt du vélodrome : piste choisie, session libre ou ERG, épreuves reçues du core.
func is_track() -> bool:
	return world_id in track_ids and mode in ["free", "erg"] and not track_events.is_empty()


## Épreuves et réglages du core (hello_ack.config.track) ; null ou absent : pas d'écran Prêt du vélodrome.
func set_track_events(block) -> void:
	track_events = block["events"] if block is Dictionary and block.get("events") is Dictionary else {}
	if not track_events.has(track_event):
		track_event = "free" if track_events.has("free") else ("" if track_events.is_empty() else str(track_events.keys()[0]))
	_refresh_home()


## Parcours qui sont des pistes (étiquette « velodrome » de la fiche), posés à chaque liste des parcours.
func set_track_ids(ids: Array) -> void:
	track_ids = ids.duplicate()
	_refresh_home()


## Valeur choisie d'un réglage de l'épreuve choisie (défaut du core sinon).
func track_value(option_id: String):
	var opts: Dictionary = track_events.get(track_event, {})
	var chosen: Dictionary = track_values.get(track_event, {})
	if chosen.has(option_id):
		return chosen[option_id]
	return opts[option_id][0] if opts.has(option_id) else null


func _track_items() -> Array:
	var name := TrackNames.event_name(track_event)
	var erg_note := " en ERG" if mode == "erg" else ""
	var items := [_item("start", "Lancer : " + name + erg_note),
		_item(TRACK_EVENT_ID, "Épreuve : " + name)]
	var opts: Dictionary = track_events.get(track_event, {})
	for o in opts:
		items.append(_item(TRACK_OPTION_PREFIX + str(o), "%s : %s" % [TrackNames.option_name(track_event, str(o)),
			TrackNames.value_text(str(o), track_value(str(o)))]))
	if track_event == "free":
		items.append(_item("workout", "Changer d'entraînement" if mode == "erg" else "Passer en session ERG"))
	items.append(_item("change_route", "Changer de parcours"))
	return items


## A long sur « Épreuve » : épreuve suivante ; quitter la séance libre en ERG revient en SIM.
func _cycle_track_event() -> Dictionary:
	var ids: Array = track_events.keys()
	track_event = str(ids[(ids.find(track_event) + 1) % ids.size()])
	var out := {}
	if mode == "erg" and track_event != "free":
		mode = "free"
		out = {"action": "select_workout", "workout_id": null}
	_refresh_home()
	return out


## A long sur un réglage : valeur suivante parmi celles du core.
func _cycle_track_option(option_id: String) -> void:
	var opts: Dictionary = track_events.get(track_event, {})
	if not opts.has(option_id):
		return
	var values: Array = opts[option_id][1]
	var v = track_value(option_id)
	var i := values.find(v)
	if not track_values.has(track_event):
		track_values[track_event] = {}
	track_values[track_event][option_id] = values[(i + 1) % values.size()]
	_refresh_home()


## Parcours choisi (ou connu par la trame d'état) ; met à jour l'accueil et l'écran Prêt.
func set_world(id: String, name: String) -> void:
	world_id = id
	world_name = name if name != "" else id
	_refresh_home()


## « Garage » à l'accueil (lot V8) : vrai quand hello_ack.config porte une `progression`.
func set_garage(on: bool) -> void:
	garage = on
	_refresh_home()


## Modes annoncés par le core (hello_ack.config.modes) ; null ou absent : DEFAULT_MODES (1.0).
func set_modes(list) -> void:
	modes = list.duplicate() if list is Array else DEFAULT_MODES.duplicate()
	_refresh_home()


## Entrée des plans de l'accueil (lot O12) : libellé et détail (nom, durée, TSS de la séance du jour).
func set_plan_home(label: String, detail := "") -> void:
	plan_label = label
	plan_detail = detail
	_refresh_home()


## Prépare une séance démarrée avec `args` (`start` : plan_day ou ftp_test, lot O12) et ouvre l'écran
## Prêt, ou les parcours d'abord sans monde choisi ; `name` s'affiche dans le titre de l'écran Prêt.
func prepare_start(name: String, args: Dictionary) -> Dictionary:
	start_name = name
	start_args = args.duplicate()
	mode = "erg"
	_refresh_home()
	if world_id == "":
		_routes_return = READY
		_open(ROUTES)
	else:
		_open(READY)
	return state()


## Course conseillée (série CO, lot CO5) : session libre en SIM sur le parcours du conseil, déjà choisi, avec
## les bots du format (`args` de `start`) ; l'écran Prêt ne garde que « Démarrer » et le fantôme.
func prepare_coach_race(name: String, args: Dictionary, ready_text: String) -> Dictionary:
	start_name = name
	start_args = args.duplicate(true)
	coach_ready = ready_text
	mode = "coach"
	bot_choices = []
	peloton = 0
	ghost = false
	_refresh_home()
	_open(READY)
	return state()


## Entraînement choisi (liste des entraînements, ou séance conseillée, lot CO5) : séance ERG, écran Prêt, ou les
## parcours d'abord sans monde choisi ; `workout` null : session libre. Renvoie l'action `select_workout`.
func choose_workout(workout) -> Dictionary:
	mode = "free" if workout == null else "erg"
	if workout != null:
		last_workout = str(workout)   # noté aussi par le core (lot O32)
	_clear_start()
	_refresh_home()
	if _screen == WORKOUTS and _workouts_return == READY:
		_back()
	elif world_id == "":
		_routes_return = READY
		if _screen == WORKOUTS:
			_replace_top(ROUTES)
		else:
			_open(ROUTES)
	elif _screen == WORKOUTS:
		_go(READY)
	else:
		_open(READY)
	return {"action": "select_workout", "workout_id": workout}


## Séance du mode WTF (lot WTF3) : session libre en SIM avec `mode` « wtf » au `start` ; ouvre l'écran
## Prêt, ou les parcours d'abord sans monde choisi.
func prepare_wtf() -> Dictionary:
	_clear_start()
	mode = "wtf"
	_refresh_home()
	if world_id == "":
		_routes_return = READY
		_open(ROUTES)
	else:
		_open(READY)
	return state()


## Séance du Dernier survivant (lot DS7) : SIM, `mode` « survivor » au `start`, adversaires composés par le core
## d'après les réglages `survivor.*` ; ouvre l'écran Prêt, ou les parcours d'abord sans monde choisi.
func prepare_survivor() -> Dictionary:
	_clear_start()
	mode = "survivor"
	_refresh_home()
	if world_id == "":
		_routes_return = READY
		_open(ROUTES)
	else:
		_open(READY)
	return state()


## Réglages et ligne « Lancer » de l'écran Prêt du Dernier survivant (menu_flow.gd).
func set_survivor_ready(rows: Array, launch: Dictionary) -> void:
	survivor_rows = []
	for it in rows:   # lignes de réglage (SettingsViewModel.row) remises au format des éléments du menu
		var e := _item(str(it["id"]), str(it.get("label", it["id"])), bool(it.get("enabled", true)), str(it.get("detail", "")))
		for k in ["bar", "editing"]:
			if it.has(k):
				e[k] = it[k]
		survivor_rows.append(e)
	survivor_launch = launch
	if mode == "survivor":
		_refresh_home()
		# « Lancer » grisé (parcours trop court) : le focus n'y reste pas, il passe à la ligne active suivante
		if _screen == READY and (_focus < 0 or _focus >= _items().size() or not _items()[_focus]["enabled"]):
			_focus = _first_enabled_from(maxi(_focus, 0), 1)


func _clear_start() -> void:
	start_name = ""
	start_args = {}


## Arguments de `start` : séance préparée (plan_day, ftp_test) et bots choisis ({} si rien).
func _start_args() -> Dictionary:
	var out := start_args.duplicate()
	if mode == "survivor":   # le core compose le plateau : pas d'argument `bots`
		return {"mode": "survivor"}
	if is_track():   # vélodrome (lot VD10) : le core compose aussi le plateau
		var choice := {"event": track_event}
		for o in track_events.get(track_event, {}):
			var v = track_value(str(o))
			choice[str(o)] = int(v) if v is float and is_equal_approx(v, round(v)) else v   # 20 et non 20.0
		return {"mode": "track", "track": choice}
	if mode == "coach" and ghost:   # bots du format de la course conseillée, fantôme en plus (lot CO5)
		out["bots"] = (out.get("bots", []) as Array) + [{"kind": "ghost"}]
	if mode == "coach":
		return out
	if mode == "wtf":
		out["mode"] = "wtf"
	var bots := _bots_list()
	if not bots.is_empty():
		out["bots"] = bots
	return out


## Liste `bots` des lignes « Bot n », du peloton et du fantôme (argument de `start` et de `set_bots`).
func _bots_list() -> Array:
	var bots: Array = []
	for c in bot_choices:
		bots.append(BOT_CHOICES[c][1].duplicate())
	for i in range(peloton_size()):
		bots.append({"kind": "profile", "profile": PELOTON_PROFILES[i % PELOTON_PROFILES.size()]})
	if ghost:
		bots.append({"kind": "ghost"})
	return bots


## Lignes modifiables de l'écran de pause, après Reprendre, Terminer et Abandonner : difficulté (curseur
## du lot O4, commande set_difficulty) et, en session libre (lot O18), mode SIM / ERG / ERG cadence,
## puissance ou cadence cible (set_ride_mode). `rows` : rangées de SettingsViewModel.row() (valeur,
## curseur, mode édition en place) ; leur `id` est renvoyé par une action « item » de l'écran de pause.
## Le focus reste sur la même ligne quand la liste change.
## Lot N18 : puis, en séance libre, ERG ou WTF, les lignes des bots de l'écran Prêt (« Bot 1 » à « Bot n »,
## fantôme, peloton), modifiées de la même façon (A) et appliquées à la reprise.
func set_pause_rows(rows: Array) -> void:
	_pause_rows = rows.duplicate()
	_refresh_pause()


## Bots modifiables sur l'écran de pause (lot N18) : pas en Cyber-Rogue ni en Dernier survivant, où le core
## compose le plateau.
func pause_bots_shown() -> bool:
	return mode in ["free", "erg", "wtf"]


func _refresh_pause() -> void:
	var items: Array = [_item("resume", "Reprendre"), _item("end_save", "Terminer et enregistrer"),
		_item("abandon", "Abandonner")]
	for row in _pause_rows:
		var it := _item(str(row["id"]), str(row["label"]), true, str(row.get("detail", "")))
		if row.has("bar"):
			it["bar"] = int(row["bar"])
		it["editing"] = bool(row.get("editing", false))
		items.append(it)
	if pause_bots_shown():
		items.append_array(_bot_items())
		items.append_array([_item("ghost", "Fantôme de la dernière séance : " + ("oui" if ghost else "non")),
			_peloton_item()])
	var focused_id := ""
	if _screen == PAUSE and _focus >= 0 and _focus < _screens[PAUSE]["items"].size():
		focused_id = _screens[PAUSE]["items"][_focus]["id"]
	_screens[PAUSE]["items"] = items
	if _screen == PAUSE:
		_focus = _first_enabled_from(_index_of(focused_id), 1)


## Derniers choix du profil (`hello_ack.config.last_choices`, lot O32 ; null ou absent : aucun). Un bot
## inconnu de BOT_CHOICES (ligne de commande, ancienne liste) est sauté ; MAX_BOTS bots au plus (lot O35).
func set_last_choices(choices) -> void:
	var c: Dictionary = choices if choices is Dictionary else {}
	last_workout = str(c["workout_id"]) if c.get("workout_id") is String else ""
	last_bots = []
	last_ghost = false
	var in_peloton := 0
	var bots = c.get("bots", [])
	for b in (bots if bots is Array else []):
		if b is Dictionary and str(b.get("kind", "")) == "ghost":
			last_ghost = true
		elif b is Dictionary and _is_peloton_bot(b):
			in_peloton += 1
		elif b is Dictionary and last_bots.size() < MAX_BOTS and bot_index(b) > 0:
			last_bots.append(bot_index(b))
	last_peloton = 0
	for n in PELOTON_CHOICES:   # la plus petite taille qui donne ce nombre de bots (11 coupé à 7 après 4 bots)
		if last_peloton == 0 and in_peloton > 0 and mini(int(n), MAX_RIDER_BOTS - last_bots.size()) >= in_peloton:
			last_peloton = int(n)
	bot_choices = last_bots.duplicate()
	ghost = last_ghost
	peloton = last_peloton
	_refresh_home()


## Index de BOT_CHOICES d'un élément de `bots` (nombres du JSON comparés en valeur), 0 s'il est inconnu.
static func bot_index(bot: Dictionary) -> int:
	for i in range(1, BOT_CHOICES.size()):
		var ref: Dictionary = BOT_CHOICES[i][1]
		if ref.size() != bot.size():
			continue
		var same := true
		for k in ref:
			var v = bot.get(k)
			if ref[k] is String:
				same = same and v is String and v == ref[k]
			else:
				same = same and (v is int or v is float) and is_equal_approx(float(v), float(ref[k]))
		if same:
			return i
	return 0


## Bot du peloton (lot PL1) : bot à profil sans `level_pct` (les bots choisis un par un en ont toujours un).
static func _is_peloton_bot(b: Dictionary) -> bool:
	return str(b.get("kind", "")) == "profile" and not b.has("level_pct") and PELOTON_PROFILES.has(str(b.get("profile", "")))


## Bots du peloton envoyés à `start` : la taille choisie, sans dépasser MAX_RIDER_BOTS avec les bots choisis un par un.
func peloton_size() -> int:
	return clampi(peloton, 0, maxi(MAX_RIDER_BOTS - bot_choices.size(), 0))


## Ligne « Peloton : … » de l'écran Prêt (lot PL1).
func _peloton_item() -> Dictionary:
	var n := peloton_size()
	var label := "Peloton : " + ("aucun" if n == 0 else "%d bots" % n)
	return _item("peloton", label, true, "" if n == 0 else "rouleurs, grimpeurs, sprinteurs, diesels")


## A long sur « Bot n » (lot O35) : choix suivant de BOT_CHOICES ; « aucun » retire le bot, les suivants
## remontent d'une ligne. La ligne vide (après le dernier bot) en ajoute un.
## Lignes « Bot 1 » à « Bot n+1 » de l'écran Prêt (lot O35, séance libre, ERG et mode WTF) : une ligne vide
## sous le dernier bot choisi, au plus MAX_BOTS.
func _bot_items() -> Array:
	var out: Array = []
	for i in range(mini(bot_choices.size() + 1, MAX_BOTS)):
		var label: String = BOT_CHOICES[bot_choices[i]][0] if i < bot_choices.size() else BOT_CHOICES[0][0]
		out.append(_item("bot%d" % (i + 1), "Bot %d : %s" % [i + 1, label]))
	return out


## Reprise depuis la pause (Reprendre ou Y) ; lot N18 : bots changés envoyés par `set_bots` avant `resume`,
## et gardés comme derniers choix (le core les note aussi).
func _resume_action() -> Dictionary:
	if not pause_bots_changed:
		return {"action": "resume"}
	pause_bots_changed = false
	last_bots = bot_choices.duplicate()
	last_ghost = ghost
	last_peloton = peloton
	return {"action": "resume", "bots": _bots_list()}


func _cycle_bot(i: int) -> void:
	var next := (bot_choices[i] if i < bot_choices.size() else 0) + 1
	next %= BOT_CHOICES.size()
	if i >= bot_choices.size():
		bot_choices.append(next)
	elif next == 0:
		bot_choices.remove_at(i)
	else:
		bot_choices[i] = next
	_refresh_home()
	_refresh_pause()


func set_sim_session(on: bool) -> void:
	sim_session = on
	_screens[HOME]["title"] = "OpenRide — session simulée" if on else "OpenRide"
	_refresh_home()


static func _item(id: String, label: String, enabled := true, detail := "") -> Dictionary:
	return {"id": id, "label": label, "enabled": enabled, "detail": detail}


func reset() -> void:
	_stack.clear()
	_focus_stack.clear()
	_pending = {}
	_clear_start()
	bot_choices = last_bots.duplicate()
	ghost = last_ghost
	peloton = last_peloton
	if mode in ["rogue", "wtf", "survivor", "coach"]:
		mode = "free"
	_refresh_home()
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
	if screen_id == ROUTES:
		if clean.is_empty():
			clean.append(_item("empty", "Aucun parcours", false, "« Ajouter un parcours » importe une trace"))
		clean.append(_item(ADD_ROUTE_ID, "Ajouter un parcours"))
		clean.append(_item(HELP_ROUTES_ID, "Comment ça marche ?"))
	elif screen_id == WORKOUTS:
		if clean.size() == 1:
			clean.append(_item("empty", "Aucun entraînement", false))
		clean.append(_item(CREATE_WORKOUT_ID, "Créer un entraînement (intervalles)"))
		clean.append(_item(QWK_WORKOUT_ID, "Saisir du QWKcode (clavier)"))
		clean.append(_item(IMPORT_WORKOUT_ID, "Importer un fichier"))
		clean.append(_item(HELP_WORKOUT_ID, "Comment ça marche ?"))
	var focused_id := ""
	if _screen == screen_id and _focus >= 0 and _focus < _screens[screen_id]["items"].size():
		focused_id = _screens[screen_id]["items"][_focus]["id"]
	# Liste des parcours arrivée pendant l'affichage d'une liste vide : le focus, posé faute de mieux sur
	# l'aide de fin de liste (lot O22), passe au premier parcours.
	if screen_id == ROUTES and focused_id in [ADD_ROUTE_ID, HELP_ROUTES_ID] \
			and _screens[screen_id]["items"].all(func(it): return not it["enabled"] or it["id"] in [ADD_ROUTE_ID, HELP_ROUTES_ID]):
		focused_id = ""
	_screens[screen_id]["items"] = clean
	if _screen == screen_id:
		_focus = _first_enabled_from(_index_of(focused_id), 1)


## Ouvre l'écran de pause (appelé quand la séance passe en pause).
func open_pause() -> Dictionary:
	_stack.clear()
	_focus_stack.clear()
	_pending = {}
	pause_bots_changed = false
	_refresh_pause()
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
		var e := _item(str(it["id"]), str(it.get("label", it["id"])), bool(it.get("enabled", true)),
			str(it.get("detail", "")))
		for k in ["bar", "editing"]:   # affichage seulement : curseur (0 à 100) et valeur en cours de réglage
			if it.has(k):
				e[k] = it[k]
		clean.append(e)
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
		"PLUS_SHORT", "RIGHT_SHORT", "A_SHORT":
			_move(1)
		"MINUS_SHORT", "LEFT_SHORT":
			_move(-1)
		"PLUS_LONG":
			_jump(LONG_STEP)
		"MINUS_LONG":
			_jump(-LONG_STEP)
		"A_LONG":
			return state(_validate())
		"Y_SHORT":
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


## Grand pas : `steps` éléments actifs plus loin (négatif : plus haut), sans boucler ; s'arrête au
## dernier (premier) élément actif.
func _jump(steps: int) -> void:
	if _focus < 0:
		return
	var items := _items()
	var dir := signi(steps)
	var left := absi(steps)
	var i := _focus + dir
	while left > 0 and i >= 0 and i < items.size():
		if items[i]["enabled"]:
			_focus = i
			left -= 1
		i += dir


func _open(screen_id: String, push := true) -> void:
	if push and _screen != screen_id:
		_stack.append(_screen)
		_focus_stack.append(_focus)
	_screen = screen_id
	_focus = _first_enabled_from(0, 1)
	if screen_id == WORKOUTS and last_workout != "":   # lot O32 : dernier entraînement, parcours en cours
		focus_item(last_workout)
	elif screen_id == ROUTES and world_id != "":
		focus_item(world_id)


func _back() -> Dictionary:
	match _screen:
		CONFIRM:
			_pending = {}
			_go_back_to(_confirm_back)
			return {}
		PAUSE:
			return _resume_action()   # retour depuis la pause = Reprendre
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
					_clear_start()
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
				"open_world":
					return {"action": "open_world_menu"}
				"sim":
					if sim_session:
						_confirm("Revenir au matériel réel ? OpenRide redémarre", {"action": "relaunch"})
					else:
						_confirm("Session simulée ? OpenRide redémarre sans matériel", {"action": "relaunch_sim"})
				"settings":
					_open(SETTINGS)
				"quit":
					_confirm("Quitter OpenRide ?", {"action": "quit"})
				"plan", "ftp", "history", "rogue", "garage", "profile", "wtf", "survivor", "interrupted", "coach":
					return {"action": "item", "screen": HOME, "id": id}
		ROUTES:
			if id in [SORT_ROUTES_ID, FILTER_ROUTES_ID, ADD_ROUTE_ID, HELP_ROUTES_ID]:
				return {"action": "item", "screen": ROUTES, "id": id}
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
			if id in [CREATE_WORKOUT_ID, IMPORT_WORKOUT_ID, QWK_WORKOUT_ID, HELP_WORKOUT_ID]:
				return {"action": "item", "screen": WORKOUTS, "id": id}
			return choose_workout(null if id == NO_WORKOUT_ID else id)
		READY:
			match id:
				"start":
					if not mode in ["rogue", "survivor", "coach"]:   # bots de la séance notés aussi par le core (lot O32)
						last_bots = bot_choices.duplicate()
						last_ghost = ghost
						last_peloton = peloton
					var args := _start_args()
					if args.is_empty():
						return {"action": "start"}
					return {"action": "start", "args": args}
				"bot1", "bot2", "bot3", "bot4":
					_cycle_bot(int(id.substr(3)) - 1)
				TRACK_EVENT_ID:
					return _cycle_track_event()
				"ghost":
					ghost = not ghost
					_refresh_home()
				"peloton":
					peloton = PELOTON_CHOICES[(PELOTON_CHOICES.find(peloton) + 1) % PELOTON_CHOICES.size()]
					_refresh_home()
				"workout":
					_workouts_return = READY
					_open(WORKOUTS)
				"change_route":
					_routes_return = READY
					_open(ROUTES)
				"rogue_change", "wtf_rules":
					return {"action": "item", "screen": READY, "id": id}
				"records":   # écran « Records » (série T, lot T10), traité par menu_flow.gd
					return {"action": "item", "screen": READY, "id": id}
				_:   # réglages du Dernier survivant (« set:clé », lot DS7) : modifiés en place par menu_flow.gd
					if id.begins_with(TRACK_OPTION_PREFIX):
						_cycle_track_option(id.substr(TRACK_OPTION_PREFIX.length()))
					elif id.begins_with("set:"):
						return {"action": "item", "screen": READY, "id": id}
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
					return _resume_action()
				"bot1", "bot2", "bot3", "bot4":
					if pause_bots_shown():
						_cycle_bot(int(id.substr(3)) - 1)
						pause_bots_changed = true
				"ghost":
					if pause_bots_shown():
						ghost = not ghost
						pause_bots_changed = true
						_refresh_home()
						_refresh_pause()
				"peloton":
					if pause_bots_shown():
						peloton = PELOTON_CHOICES[(PELOTON_CHOICES.find(peloton) + 1) % PELOTON_CHOICES.size()]
						pause_bots_changed = true
						_refresh_home()
						_refresh_pause()
				"end_save":
					reset()
					return {"action": "end_session", "save": true}
				"abandon":
					_confirm("Abandonner la séance ?", {"action": "end_session", "save": false})
				_:   # lignes modifiables (set_pause_rows) : modifiées en place par menu_flow.gd
					return {"action": "item", "screen": PAUSE, "id": id}
		_:
			return {"action": "item", "screen": _screen, "id": id}
	return {}
