extends SceneTree

## Tests sans écran du menu du vélodrome (série VD, lot VD10) : filtre « Vélodrome » et pistes de la liste des
## parcours (catalog_model.gd), écran Prêt du vélodrome (menu_model.gd) : épreuve, réglages du core
## (`hello_ack.config.track`), séance libre en ERG, arguments de `start`, retour à l'écran Prêt habituel hors piste.
## Lancement : godot --headless --path engine --script res://tests/unit/test_track_menu.gd

const MenuModel := preload("res://scripts/menu_model.gd")
const CatalogModel := preload("res://scripts/catalog_model.gd")
const TrackNames := preload("res://scripts/track/track_names.gd")

## Forme de `track.menu_options()` du core (extrait, dans l'ordre du registre).
const TRACK := {"events": {
	"free": {"opponents": [5, [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]], "bot_tactics": ["full", ["none", "simple", "full"]]},
	"pursuit": {"opponents": [1, [0, 1]], "distance_m": [4000, [3000, 4000]], "bot_tactics": ["full", ["none", "simple", "full"]]},
	"kilo": {"opponents": [0, [0]]},
	"points": {"opponents": [7, [3, 4, 5, 6, 7, 8, 9, 10, 11]], "laps": [40.0, [20.0, 30.0, 40.0, 60.0]],
		"bot_tactics": ["full", ["none", "simple", "full"]]},
	"team_sprint": {"opponents": [1, [0, 1]], "place": [1, [1, 2, 3]], "bot_tactics": ["full", ["none", "simple", "full"]]}}}
const ROUTES := [
	{"id": "demo", "name": "Démo", "status": "ready", "length_m": 4000.0, "library": {"tags": ["demo"]}},
	{"id": "velodrome-250", "name": "Vélodrome 250 m", "status": "ready", "length_m": 250.0, "route_type": "loop",
		"library": {"description": "Piste couverte de 250 m en bois, virages relevés à 42° et lignes droites à 12°.",
			"tags": ["velodrome"]}}]

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _init() -> void:
	call_deferred("_run")


func _labels(st: Dictionary) -> Array:
	return st["items"].map(func(it): return str(it["label"]))


func _press(m, id: String) -> Dictionary:
	_check(m.focus_item(id), "élément %s présent" % id)
	return m.handle("A_LONG")


func _run() -> void:
	# Liste des parcours
	_check(CatalogModel.track_route_ids(ROUTES) == ["velodrome-250"], "pistes de la liste")
	_check(CatalogModel.route_tags(ROUTES) == ["demo", "velodrome"] and CatalogModel.tag_label("velodrome") == "Vélodrome",
		"filtre « Vélodrome »")
	var cat = CatalogModel.new()
	var only: Array = cat.route_items(ROUTES, "nom", "velodrome")
	_check(only.size() == 1 and only[0]["id"] == "velodrome-250" and only[0]["detail"] == "Vélodrome", "liste filtrée (%s)" % str(only))
	var sheet: Dictionary = CatalogModel.route_sheet(ROUTES[1])
	_check(str(sheet["lines"][-1]).begins_with("Vélodrome — Piste couverte de 250 m en bois"), "fiche de la piste (%s)" % str(sheet["lines"]))

	# Écran Prêt du vélodrome
	var m = MenuModel.new()
	m.set_track_events(TRACK)
	m.set_track_ids(CatalogModel.track_route_ids(ROUTES))
	m.set_world("velodrome-250", "Vélodrome 250 m")
	_check(m.is_track(), "piste choisie en session libre : écran Prêt du vélodrome")
	var st: Dictionary = m.open_screen(MenuModel.READY)
	_check(st["title"] == "Prêt : Vélodrome 250 m", "titre (%s)" % st["title"])
	_check(_labels(st) == ["Lancer : Séance libre", "Épreuve : Séance libre", "Adversaires : 5", "Tactique des bots : complète",
		"Passer en session ERG", "Changer de parcours"], "séance libre par défaut (%s)" % str(_labels(st)))
	st = _press(m, "start")
	_check(st["action"] == {"action": "start", "args": {"mode": "track", "track": {"event": "free", "opponents": 5, "bot_tactics": "full"}}},
		"start de la séance libre (%s)" % str(st["action"]))
	m.open_screen(MenuModel.READY)
	st = _press(m, MenuModel.TRACK_EVENT_ID)
	_check(st["action"].is_empty() and _labels(st)[1] == "Épreuve : Poursuite individuelle", "épreuve suivante")
	_check(st["items"][_focus(st)]["id"] == MenuModel.TRACK_EVENT_ID, "focus gardé sur l'épreuve")
	_check(_labels(st).has("Distance : 4 km") and not _labels(st).has("Passer en session ERG"), "réglages de la poursuite, pas d'ERG")
	st = _press(m, "track:distance_m")
	_check(_labels(st).has("Distance : 3 km"), "distance suivante")
	_press(m, MenuModel.TRACK_EVENT_ID)
	_press(m, MenuModel.TRACK_EVENT_ID)
	st = _press(m, "track:laps")
	_check(_labels(st)[1] == "Épreuve : Course aux points" and _labels(st).has("Tours : 60"), "points : tours suivants (%s)" % str(_labels(st)))
	st = _press(m, "track:laps")
	_check(_labels(st).has("Tours : 20"), "les valeurs bouclent")
	st = _press(m, "track:bot_tactics")
	_check(_labels(st).has("Tactique des bots : aucune"), "tactique suivante")
	st = _press(m, "start")
	_check(st["action"]["args"] == {"mode": "track", "track": {"event": "points", "opponents": 7, "laps": 20, "bot_tactics": "none"}},
		"start de la course aux points (%s)" % str(st["action"]))
	_check(typeof(st["action"]["args"]["track"]["laps"]) == TYPE_INT and typeof(st["action"]["args"]["track"]["opponents"]) == TYPE_INT,
		"nombres entiers envoyés au core (20 et non 20.0)")
	m.open_screen(MenuModel.READY)
	st = _press(m, MenuModel.TRACK_EVENT_ID)
	_check(_labels(st).has("Adversaires : aucun") or _labels(st).has("Équipes adverses : 1"), "équipes adverses (%s)" % str(_labels(st)))
	_check(_labels(st).has("Ta place dans l'équipe : 1er"), "place dans l'équipe")
	st = _press(m, MenuModel.TRACK_EVENT_ID)
	_check(_labels(st)[1] == "Épreuve : Séance libre" and _labels(st).has("Adversaires : 5"), "retour à la séance libre")
	_press(m, MenuModel.TRACK_EVENT_ID)
	_press(m, MenuModel.TRACK_EVENT_ID)
	st = _press(m, MenuModel.TRACK_EVENT_ID)
	_check(_labels(st).has("Tours : 20") and _labels(st).has("Tactique des bots : aucune"), "choix gardés par épreuve (%s)" % str(_labels(st)))

	# Séance libre en ERG, puis autre épreuve : retour en SIM
	var e = MenuModel.new()
	e.set_track_events(TRACK)
	e.set_track_ids(["velodrome-250"])
	e.mode = "erg"
	e.set_world("velodrome-250", "Vélodrome 250 m")
	st = e.open_screen(MenuModel.READY)
	_check(_labels(st)[0] == "Lancer : Séance libre en ERG" and _labels(st).has("Changer d'entraînement"), "séance libre en ERG")
	st = _press(e, MenuModel.TRACK_EVENT_ID)
	_check(st["action"] == {"action": "select_workout", "workout_id": null} and e.mode == "free", "autre épreuve : retour en SIM")

	# Hors piste, sans épreuves du core, autres modes : écran Prêt habituel
	var n = MenuModel.new()
	n.set_track_events(TRACK)
	n.set_track_ids(["velodrome-250"])
	n.set_world("demo", "Démo")
	_check(not n.is_track() and _labels(n.open_screen(MenuModel.READY))[0] == "Démarrer", "parcours routier : écran habituel")
	var o = MenuModel.new()
	o.set_track_ids(["velodrome-250"])
	o.set_world("velodrome-250", "Vélodrome 250 m")
	_check(not o.is_track(), "core sans épreuves de piste : écran habituel")
	o.set_track_events(null)
	_check(o.track_events.is_empty(), "épreuves absentes")

	# Noms
	_check(TrackNames.value_text("relay_laps", 0.5) == "½ tour" and TrackNames.value_text("relay_laps", 1.0) == "1 tour", "relais")
	_check(TrackNames.option_name("madison", "opponents") == "Équipes adverses" and TrackNames.option_name("points", "opponents") == "Adversaires",
		"adversaires ou équipes")

	print("test_track_menu : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)


func _focus(st: Dictionary) -> int:
	return int(st["focus"])
