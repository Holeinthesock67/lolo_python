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

const MenuModel := preload("res://scripts/menu_model.gd")
const CatalogModel := preload("res://scripts/catalog_model.gd")
const SummaryViewModel := preload("res://scripts/summary_view_model.gd")

const SUMMARY := "summary"

var menu = MenuModel.new()
var catalog = CatalogModel.new()
var summary_model = SummaryViewModel.new()
var session_state: String = ""
## Dernier bilan reçu (objet `summary` de la trame en FINISHED).
var summary: Dictionary = {}
## « Voir le bilan détaillé » : blocs ERG en plus des lignes.
var show_details := false
var _lists_requested := false


func _init() -> void:
	summary_model.attach_to_menu(menu)


func is_visible() -> bool:
	return session_state != "" and session_state != "RUNNING"


## Trame `state` reçue ; renvoie les actions à exécuter (liste, éventuellement vide).
func on_state(state: Dictionary) -> Array:
	var out: Array = []
	var st := str(state.get("session_state", ""))
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


## Core relancé ou de nouveau joignable : listes redemandées au prochain état visible.
func lists_needed() -> void:
	_lists_requested = false


func set_routes(raw: Array) -> void:
	menu.set_items(MenuModel.ROUTES, catalog.route_items(raw))


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
	if act.get("action", "") == "item" and act.get("screen", "") == SUMMARY:
		act = summary_model.handle_action(str(act["id"]), menu)
		match act.get("action", ""):
			"new_session":
				show_details = false
				summary = {}
				return {"action": "list"}
			"details":
				show_details = not show_details
				return {}
	return act


func state() -> Dictionary:
	return menu.state()
