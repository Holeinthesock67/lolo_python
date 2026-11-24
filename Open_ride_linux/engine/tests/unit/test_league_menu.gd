extends SceneTree

## Ligue d'hiver au menu (série CH, lot CH4a, maquettes CH0 01 à 03) : ligne de l'accueil après la séance
## conseillée, écran de la ligue (classement, « Toi » écrit et encadré), écran Prêt d'une manche sur une boucle
## (`start` {mode race, league}), saison à commencer, encart du bilan. Message `league` au format de
## league.status() (rivaux et équipes fictifs, FTP fictive 250 W).
## Lancement : godot --headless --path engine --script res://tests/unit/test_league_menu.gd

const MenuFlow := preload("res://scripts/menu_flow.gd")
const MenuModel := preload("res://scripts/menu_model.gd")
const League := preload("res://scripts/league_view_model.gd")
const Summary := preload("res://scripts/summary_view_model.gd")
const DetailCard := preload("res://scripts/detail_card.gd")

const NAMES := ["Fabien Lacroix", "Gaël Perrin", "Hugo Marchal", "Nils Pujol", "Oscar Lemaire", "Pierre Vasseur",
	"Simon Barral", "Théo Valette", "Toi", "Victor Chauvin", "Yann Mercier", "Zacharie Brun"]
const STYLES := ["Grimpeur", "Sprinteur", "Rouleur", "Diesel", "Rouleur", "Rouleur", "Grimpeur", "Diesel", "",
	"Sprinteur", "Grimpeur", "Sprinteur"]

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


static func _standings() -> Array:
	var out: Array = []
	for i in range(NAMES.size()):
		var me: bool = NAMES[i] == "Toi"
		out.append({"place": i + 1, "id": "me" if me else "r%d" % i, "name": NAMES[i],
			"style": null if me else STYLES[i], "team": null if me else "Équipe %d" % i,
			"color": null if me else "#7fc4d9", "points": 0.0, "ran": 0, "wins": 0, "me": me})
	return out


static func _msg(done := false, playable := true, closed = null) -> Dictionary:
	return {"type": "league", "v": 1, "request_cmd_id": 4, "season": {"number": 1, "start": "2026-11-23",
		"end": "2027-01-17", "weeks": 8, "week": 1, "paused": false, "closed": closed,
		"home_line": "9e · manche 1/8 : Course en tours, à courir cette semaine",
		"round": {"index": 0, "mode": "race", "event": null, "title": "Course en tours, circuit vallonné",
			"short": "Course en tours", "decides": "rouleurs", "terrain": "boucle", "done": done, "open": not done,
			"playable": playable and not done},
		"classic_day": null, "trophy": null, "standings": _standings()}}


func _ids(st: Dictionary) -> Array:
	return st["items"].map(func(it): return str(it["id"]))


func _item(st: Dictionary, id: String) -> Dictionary:
	for it in st["items"]:
		if str(it["id"]) == id:
			return it
	return {}


func _init() -> void:
	_test_model()
	_test_flow()
	_test_grand_prix_loop()
	_test_card()
	_test_summary()
	print("test_league_menu : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)


func _test_model() -> void:
	var m = League.new()
	_check(m.home_detail() == "", "accueil : rien avant la réponse du core")
	m.on_league({"type": "league", "v": 1, "request_cmd_id": 1, "season": null})
	_check(m.home_detail() == "8 semaines contre 11 rivaux" and m.items()[0]["id"] == League.NEW_ID
		and m.items()[0]["label"] == "Commencer la saison 1", "sans saison : la commencer")
	m.on_league(_msg())
	var it: Dictionary = m.items()[0]
	_check(it["id"] == League.RUN_ID and it["label"] == "Courir la manche 1 : Course en tours" and it["enabled"],
		"manche de la semaine à courir (%s)" % it["label"])
	_check(m.title() == "Ligue d'hiver · saison 1 · semaine 1 sur 8", "titre (%s)" % m.title())
	var rows: Array = League.table_rows(_msg()["season"]["standings"], 250.0)
	_check(rows.size() == 12 and rows[8]["name"] == "Toi" and rows[8]["me"] and rows[8]["style"] == "FTP 250 W"
		and rows[0]["style"] == "grimpeur" and rows[0]["points"] == "0 pts" and rows[0]["ran"] == "0/8",
		"tableau : « Toi » et la FTP, caractère et équipe écrits")
	_check(m.ready({"route_type": "loop"})["enabled"] and m.ready({"route_type": "loop"})["detail"].begins_with("manche 1 sur 8"),
		"Prêt : boucle acceptée")
	_check(not m.ready({"route_type": "open"})["enabled"] and "boucle" in m.ready({"route_type": "open"})["detail"],
		"Prêt : parcours en ligne refusé, expliqué")
	m.on_league(_msg(true))
	_check(not m.items()[0]["enabled"] and m.items()[0]["label"] == "Manche 1 faite" and m.items()[0]["detail"] == "prochaine lundi"
		and not m.ready({"route_type": "loop"})["enabled"], "manche courue : grisée, prochaine lundi")
	m.on_league(_msg())
	m.weekday = 6
	_check("À courir avant dimanche soir : encore 2 jours." in m.sheet(250.0)["lines"], "samedi : 2 jours écrits")
	m.weekday = 0
	_check("À courir avant dimanche soir : dernier jour." in m.sheet(250.0)["lines"], "dimanche : dernier jour")
	m.weekday = 2
	_check("À courir avant dimanche soir." in m.sheet(250.0)["lines"], "mardi : sans compte des jours")
	m.on_league(_msg(false, false))
	_check(m.items()[0]["detail"] == "pas encore jouable dans cette version", "mode pas encore jouable : expliqué")
	m.on_league(_msg(false, true, "fin"))
	_check(m.items()[0]["id"] == League.NEW_ID and m.items()[0]["label"] == "Commencer la saison 2",
		"saison finie : la suivante")


func _test_flow() -> void:
	var f = MenuFlow.new()
	f.connect_done = true
	f.on_state({"session_state": "IDLE"})
	f.set_routes([{"id": "ligne", "name": "Col en ligne", "status": "ready", "length_m": 12000, "route_type": "open"},
		{"id": "boucle", "name": "Boucle des Prés", "status": "ready", "length_m": 4000, "route_type": "loop"}])
	_check(not "league" in _ids(f.state()), "accueil : pas de ligne avant la réponse du core")
	f.on_league(_msg())
	var st: Dictionary = f.state()
	_check("league" in _ids(st) and _ids(st).find("league") == _ids(st).find("world") - 1
		and _item(st, "league")["detail"].begins_with("9e · manche 1/8"), "accueil : « Ligue d'hiver » avant le parcours")
	f.menu.coach_detail = "Endurance · 1 h"
	f.menu.set_coach_home("Endurance · 1 h")
	st = f.state()
	_check(_ids(st).find("league") == _ids(st).find("coach") + 1, "accueil : après « Séance conseillée »")
	f.menu.focus_item("league")
	_check(f.handle("A_LONG") == {"action": "league_status"}, "ouvrir : league_status demandé")
	st = f.state()
	_check(st["screen"] == League.SCREEN and _ids(st) == [League.RUN_ID] and st["title"].begins_with("Ligue d'hiver · saison 1"),
		"écran de la ligue")
	var card: Dictionary = f.card(st)
	_check(card.get("table", []).size() == 12 and str(card.get("title", "")).begins_with("Classement général"),
		"fiche : classement des 12")
	var act: Dictionary = f.handle("A_LONG")
	st = f.state()
	_check(act.get("action") == "sequence" and act["list"][0] == {"action": "select_route", "route_id": "boucle"}
		and act["list"][1] == {"action": "select_workout", "workout_id": null}, "manche : boucle choisie, sans ERG")
	_check(st["screen"] == MenuModel.READY and st["title"] == "Prêt : Ligue d'hiver — Boucle des Prés"
		and _ids(st) == ["start", "change_route"] and _item(st, "start")["enabled"], "écran Prêt de la manche")
	act = f.handle("A_LONG")
	_check(act == {"action": "start", "args": {"mode": "race", "league": true}}, "Démarrer : course de la ligue (%s)" % act)
	f.menu.reset()
	_check(f.menu.mode == "free", "retour à l'accueil : mode libre")
	# Saison finie : « Commencer la saison 2 » demande league_new.
	f.on_league(_msg(false, true, "fin"))
	f.menu.focus_item("league")
	f.handle("A_LONG")
	_check(f.handle("A_LONG") == {"action": "league_new"} and f.state()["status"] == "Création de la saison…",
		"nouvelle saison : league_new")
	f.on_error("bad_args", "Ligue d'hiver : une saison est déjà en cours.")
	_check(f.state()["status"].begins_with("Échec") and f.state()["status_error"], "refus du core sur la ligne d'état")


## Sans boucle libre (cas des contenus de départ : parcours libres en ligne), la manche prend le premier circuit du
## Grand Prix et « Changer de parcours » ouvre la liste du Grand Prix.
func _test_grand_prix_loop() -> void:
	var f = MenuFlow.new()
	f.connect_done = true
	f.menu.set_modes(["ride", "erg", "grandprix", "race"])
	f.menu.set_mode_routes({"track": "velodrome", "grandprix": "grandprix"})
	f.set_routes([{"id": "demo", "name": "Col du lacet", "status": "ready", "length_m": 5000.0, "route_type": "point_to_point"},
		{"id": "vignes", "name": "Route des Vignes", "status": "ready", "length_m": 6000.0, "route_type": "point_to_point",
			"library": {"tags": ["grandprix"]}},
		{"id": "demo-circuit", "name": "Circuit des Prés", "status": "ready", "length_m": 3000.0, "route_type": "loop",
			"library": {"tags": ["grandprix"]}}])
	f.on_state({"session_state": "IDLE"})
	f.on_league(_msg())
	f.menu.focus_item("league")
	f.handle("A_LONG")
	var act: Dictionary = f.handle("A_LONG")
	var st: Dictionary = f.state()
	_check(act.get("list", [{}])[0] == {"action": "select_route", "route_id": "demo-circuit"} and st["screen"] == MenuModel.READY
		and st["title"] == "Prêt : Ligue d'hiver — Circuit des Prés" and _item(st, "start")["enabled"],
		"sans boucle libre : circuit du Grand Prix (%s)" % st["title"])
	f.menu.focus_item("change_route")
	f.handle("A_LONG")
	st = f.state()
	# Lot GPL1 : un parcours de mode est une boucle ; la trace en ligne étiquetée « grandprix » reste libre, hors de
	# la liste du Grand Prix (Démarrer grisé sur un parcours en ligne : vérifié plus haut par LeagueViewModel.ready)
	_check(st["screen"] == MenuModel.ROUTES and "demo-circuit" in _ids(st) and not "demo" in _ids(st)
		and not "vignes" in _ids(st), "Changer de parcours : liste du Grand Prix, boucles seulement (%s)" % str(_ids(st)))


func _test_card() -> void:
	var c = DetailCard.new()
	var m = League.new()
	m.on_league(_msg())
	c.update_display(m.sheet(250.0))
	var t: String = c.text()
	_check(c.table_box.visible and c.table_box.get_child_count() == 12 and "9 Toi FTP 250 W 0 pts 0/8 (toi)" in t and "1 Fabien Lacroix grimpeur 0 pts 0/8" in t,
		"carte : tableau des 12, ligne du cycliste écrite")
	c.update_display({"title": "Autre"})
	_check(not c.table_box.visible, "carte sans tableau : rien")
	c.free()


func _test_summary() -> void:
	var lg := {"round": 1, "of_rounds": 8, "title": "Course en tours", "place": 3, "of": 12, "points": 16,
		"general_before": 9, "general_after": 3, "moved": "gagne 6 places", "easy": false,
		"rows": [{"place": 1, "name": "Fabien Lacroix", "points": 25.0, "me": false},
			{"place": 3, "name": "Toi", "points": 16.0, "me": true}]}
	var lines: Array = League.summary_lines({"league": lg})
	_check(lines[0]["value"] == "manche 1 sur 8" and lines[1]["value"] == "3e sur 12 · +16 points"
		and lines[2]["value"] == "3e, gagne 6 places" and lines[4]["label"] == "3 Toi", "bilan : manche, général, classement")
	var s = Summary.new()
	var ml: Array = s.mode_lines({"league": lg})
	_check(ml.size() >= 5 and ml[0]["label"] == "Ligue d'hiver", "bilan : lignes du mode")
	_check(League.summary_lines({}).is_empty(), "séance hors ligue : rien")
