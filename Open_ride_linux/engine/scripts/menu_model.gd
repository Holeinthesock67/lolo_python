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
## Bots (lot O7) : l'écran Prêt gagne « Bot : … » (A long change : aucun, 200, 250, 300 W, 90, 100,
## 110 % de la FTP) et « Fantôme de la dernière séance : non/oui » ; `start` les transmet dans l'argument
## `bots` (contrat 1.3) quand l'un des deux est choisi, sinon n'envoie rien. Un nouvel accueil les remet à zéro.
## Records (série T, lot T10) : l'écran Prêt finit par « Records du parcours », qui renvoie une action
## « item » de l'écran Prêt (écrans des records ouverts par menu_flow.gd).

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
## Modes de séance de l'accueil, dans l'ordre d'affichage : {mode: libellé}. Filtrés par `modes`, la
## liste que le core annoncera dans hello_ack.config (2.0, PLAN_SERIE_R §6) ; absente : DEFAULT_MODES.
## Un nouveau mode (Cyber-Rogue) n'ajoute qu'une ligne ici.
const HOME_MODES := {"ride": "Session libre", "erg": "Session ERG", "open_world": "Monde ouvert",
	"rogue": "Cyber-Rogue", "wtf": "Mode WTF"}
const DEFAULT_MODES := ["ride", "erg"]
## Fin de la liste des entraînements (sous-menu ERG, lot N16) : créer ou importer un entraînement.
const CREATE_WORKOUT_ID := "_create"
const IMPORT_WORKOUT_ID := "_import"
## Bot de l'écran Prêt (lot O7), dans l'ordre du cycle : libellé et élément de l'argument `bots` de `start`.
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
## Mode de la séance préparée : "free" (session libre, SIM), "erg", "rogue" ou "wtf" (mode « What the fuck »,
## SIM seulement, lot WTF3).
var mode := "free"
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
## Bot choisi (index de BOT_CHOICES) et fantôme demandé, pour la séance préparée (lot O7).
var bot_choice := 0
var ghost := false
## Cyber-Rogue (lot R13) : rappel des choix affiché sur l'écran Prêt quand `mode` vaut « rogue ».
var rogue_ready := ""
## Garage (lot V8) : l'accueil gagne « Garage » quand le core annonce une progression (set_garage).
var garage := false


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
			_item("abandon", "Abandonner"), _item("difficulty", "Difficulté")]},
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
	items.append_array([_item("plan", plan_label, true, plan_detail), _item("ftp", "Test de FTP"),
		_item("sim", "Revenir au matériel réel" if sim_session else "Session simulée")])
	if garage:
		items.append(_item("garage", "Garage"))
	items.append_array([_item("settings", "Réglages"), _item("quit", "Quitter")])
	_screens[HOME]["items"] = items
	if mode == "rogue":
		_screens[READY]["items"] = [_item("start", "Démarrer", true, rogue_ready),
			_item("rogue_change", "Changer les choix")]
		_screens[READY]["title"] = "Prêt : Cyber-Rogue"
		return
	if mode == "wtf":
		_screens[READY]["items"] = [_item("start", "Démarrer"), _item("wtf_rules", "Changer les règles"),
			_item("change_route", "Changer de parcours"), _item("bot", "Bot : " + BOT_CHOICES[bot_choice][0]),
			_item("ghost", "Fantôme de la dernière séance : " + ("oui" if ghost else "non"))]
		_screens[READY]["title"] = "Prêt : mode WTF" + ("" if world_name == "" else " — " + world_name)
		return
	_screens[READY]["items"] = [
		_item("start", "Démarrer"),
		_item("workout", "Changer d'entraînement" if mode == "erg" else "Passer en session ERG"),
		_item("change_route", "Changer de parcours"),
		_item("bot", "Bot : " + BOT_CHOICES[bot_choice][0]),
		_item("ghost", "Fantôme de la dernière séance : " + ("oui" if ghost else "non")),
		_item("records", "Records du parcours")]
	var what := "session ERG" if mode == "erg" else "session libre"
	if start_name != "":
		what = start_name
	_screens[READY]["title"] = "Prêt : " + what + ("" if world_name == "" else " — " + world_name)


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


func _clear_start() -> void:
	start_name = ""
	start_args = {}


## Arguments de `start` : séance préparée (plan_day, ftp_test) et bots choisis ({} si rien).
func _start_args() -> Dictionary:
	var out := start_args.duplicate()
	if mode == "wtf":
		out["mode"] = "wtf"
	var bots: Array = []
	if bot_choice > 0:
		bots.append(BOT_CHOICES[bot_choice][1].duplicate())
	if ghost:
		bots.append({"kind": "ghost"})
	if not bots.is_empty():
		out["bots"] = bots
	return out


## Lignes modifiables de l'écran de pause, après Reprendre, Terminer et Abandonner : difficulté (curseur
## du lot O4, commande set_difficulty) et, en session libre (lot O18), mode SIM / ERG / ERG cadence,
## puissance ou cadence cible (set_ride_mode). `rows` : rangées de SettingsViewModel.row() (valeur,
## curseur, mode édition en place) ; leur `id` est renvoyé par une action « item » de l'écran de pause.
## Le focus reste sur la même ligne quand la liste change.
func set_pause_rows(rows: Array) -> void:
	var items: Array = [_item("resume", "Reprendre"), _item("end_save", "Terminer et enregistrer"),
		_item("abandon", "Abandonner")]
	for row in rows:
		var it := _item(str(row["id"]), str(row["label"]), true, str(row.get("detail", "")))
		if row.has("bar"):
			it["bar"] = int(row["bar"])
		it["editing"] = bool(row.get("editing", false))
		items.append(it)
	var focused_id := ""
	if _screen == PAUSE and _focus >= 0 and _focus < _screens[PAUSE]["items"].size():
		focused_id = _screens[PAUSE]["items"][_focus]["id"]
	_screens[PAUSE]["items"] = items
	if _screen == PAUSE:
		_focus = _first_enabled_from(_index_of(focused_id), 1)


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
	bot_choice = 0
	ghost = false
	if mode in ["rogue", "wtf"]:
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
	if screen_id == ROUTES and clean.is_empty():
		clean.append(_item("empty", "Aucun parcours", false))
	elif screen_id == WORKOUTS:
		if clean.size() == 1:
			clean.append(_item("empty", "Aucun entraînement", false))
		clean.append(_item(CREATE_WORKOUT_ID, "Créer un entraînement (intervalles)"))
		clean.append(_item(IMPORT_WORKOUT_ID, "Importer un fichier (.zwo, .erg, .mrc)"))
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
				"plan", "ftp", "rogue", "garage", "wtf":
					return {"action": "item", "screen": HOME, "id": id}
		ROUTES:
			if id in [SORT_ROUTES_ID, FILTER_ROUTES_ID]:
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
			if id in [CREATE_WORKOUT_ID, IMPORT_WORKOUT_ID]:
				return {"action": "item", "screen": WORKOUTS, "id": id}
			var workout = null if id == NO_WORKOUT_ID else id
			mode = "free" if workout == null else "erg"
			_clear_start()
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
					var args := _start_args()
					if args.is_empty():
						return {"action": "start"}
					return {"action": "start", "args": args}
				"bot":
					bot_choice = (bot_choice + 1) % BOT_CHOICES.size()
					_refresh_home()
				"ghost":
					ghost = not ghost
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
				_:   # lignes modifiables (set_pause_rows) : modifiées en place par menu_flow.gd
					return {"action": "item", "screen": PAUSE, "id": id}
		_:
			return {"action": "item", "screen": _screen, "id": id}
	return {}
