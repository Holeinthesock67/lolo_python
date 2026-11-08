extends SceneTree

## Séance conseillée dans le menu (série CO, lot CO5) : ligne de l'accueil, écran du conseil (raison, lancer
## l'entraînement ou la course), détail du calcul, autre besoin, prochaine course, suggestion de la montre,
## réglages du conseil ; message `coach` fabriqué (aucune donnée réelle).
## Lancement : godot --headless --path engine --script res://tests/unit/test_coach_menu.gd

const MenuFlow := preload("res://scripts/menu_flow.gd")
const MenuModel := preload("res://scripts/menu_model.gd")
const Coach := preload("res://scripts/coach_view_model.gd")
const IpcClientScript := preload("res://scripts/ipc_client.gd")

const WORKOUT := {"id": "sweet_spot_3x10", "name": "Sweet Spot 3 × 10 min", "need": "intense", "dominant_zone": "Z4",
	"tss_estimate": 62, "duration_s": 3600}
const OTHER := {"id": "seuil_2x20", "name": "Seuil 2 × 20 min", "need": "intense", "dominant_zone": "Z4",
	"tss_estimate": 83, "duration_s": 3900}
const ROUTE := {"mode": "ride", "label": "Course contre des bots sur un parcours à montées longues", "route_id": "cote",
	"route_name": "Côte", "laps": 4, "duration_s": 3605, "bots": {"count": 4, "level_pct": 95, "tactics": "classic"},
	"survivor": null, "predicted_need_s": 1890, "reference_need_s": 1800, "ratio_pct": 105}
const DETAILS := {"objective": "endurance", "targets_pct": {"light": 80.0, "intense": 16.0, "anaerobic": 4.0},
	"shares_pct": {"light": 85.0, "intense": 9.0, "anaerobic": 6.0}, "deficits_pts": {"light": -5.0, "intense": 7.0, "anaerobic": -2.0},
	"sessions_28d": 14, "duration_28d_s": 41100.0, "ctl": 33.9, "atl": 28.4, "form": 4.4, "days_since_hard": 6,
	"hard_last_7d": 1, "ftp_w": 250.0, "ftp_test_date": "2026-10-28", "ftp_age_days": 10, "profile": null,
	"profile_weak": "intense", "races": [{"date": "2026-11-05", "kind": "survivor", "place": 3, "cause": "intense"}],
	"last_by_need": {"light": "2026-11-04", "intense": "2026-11-01", "anaerobic": null}, "plan": null,
	"next_race": null, "watch": null}
const MSG := {"type": "coach", "v": 1, "request_cmd_id": 3, "date": "2026-11-07", "need": "intense",
	"need_label": "aérobie intense", "rule": "R6", "reason": "9 % de ton temps en aérobie intense sur 4 semaines (cible 16 %).",
	"duration_s": 3600, "tss_estimate": 62, "notes": [], "alternatives": ["anaerobic"], "workout": WORKOUT,
	"other_workouts": [OTHER], "route": ROUTE, "details": DETAILS}
const SETTINGS := {"type": "settings", "items": [
	{"key": "coach.objectif", "label": "Conseil : objectif", "group": "ride", "type": "choice", "value": "endurance",
		"choices": ["endurance", "courses", "grimpeur"], "applies": "now"},
	{"key": "coach.temps_disponible_min", "label": "Conseil : temps disponible", "group": "ride", "type": "int",
		"value": 60, "min": 30, "max": 120, "step": 15, "unit": "min", "applies": "now"},
	{"key": "survivor.opponents", "label": "Survivant : adversaires", "group": "ride", "type": "int", "value": 6,
		"min": 2, "max": 11, "step": 1, "applies": "next_session"},
	{"key": "survivor.spacing_km", "label": "Survivant : écart des arches", "group": "ride", "type": "int", "value": 2,
		"min": 1, "max": 3, "step": 1, "unit": "km", "applies": "next_session"}]}

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _ids(st: Dictionary) -> Array:
	return st["items"].map(func(it): return str(it["id"]))


func _item(st: Dictionary, id: String) -> Dictionary:
	for it in st["items"]:
		if str(it["id"]) == id:
			return it
	return {}


func _flow():
	var f = MenuFlow.new()
	f.connect_done = true
	f.on_state({"session_state": "IDLE"})
	f.set_routes([{"id": "cote", "name": "Côte des vignes", "status": "ready", "length_m": 8000}])
	f.on_settings(SETTINGS.duplicate(true))
	return f


func _open(f) -> Dictionary:
	if not f.coach.loaded():
		f.on_coach(MSG)
	f.menu.reset()
	f.menu.focus_item("coach")
	return f.handle("A_LONG")


func _init() -> void:
	_test_home_and_screen()
	_test_launch_workout()
	_test_launch_race()
	_test_survivor_race()
	_test_detail_and_need()
	_test_race_and_watch_inputs()
	_test_settings_and_rest()
	_test_lost_reply()
	print("test_coach_menu : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)


func _test_home_and_screen() -> void:
	var f = _flow()
	var st: Dictionary = f.state()
	_check(not "coach" in _ids(st), "accueil : pas de ligne avant la réponse du core (%s)" % str(_ids(st)))
	f.on_coach(MSG)
	st = f.state()
	_check(st["items"][st["focus"]]["id"] == "world", "ligne arrivée pendant l'affichage : le focus reste sur Parcours")
	_check(_ids(st).slice(0, 2) == ["coach", "world"] and _item(st, "coach")["detail"] == "aérobie intense · 60 min",
		"accueil : « Séance conseillée » en tête, besoin et durée (%s)" % str(_ids(st)))
	f.menu.set_profile("Profil : Cycliste A", "OpenRide — Cycliste A")
	_check(_ids(f.state()).slice(0, 3) == ["profile", "coach", "world"], "sous la ligne du profil, comme la maquette")
	_check(_open(f) == {"action": "coach_command", "name": "get_coach", "args": {}}, "ouverture : get_coach demandé")
	st = f.state()
	_check(st["screen"] == Coach.SCREEN and st["status"] == Coach.LOADING, "en attente de la réponse")
	f.on_coach(MSG)
	st = f.state()
	_check(st["title"] == "Séance conseillée : aérobie intense" and st["status"].begins_with("Pourquoi : 9 %"),
		"titre et raison (%s | %s)" % [st["title"], st["status"]])
	_check(_ids(st) == ["coach_workout", "coach_race", "coach_other", "coach_need", "coach_watch", "coach_race_date",
		"set:coach.objectif", "set:coach.temps_disponible_min", "coach_detail"], "lignes de la maquette (%s)" % str(_ids(st)))
	_check(_item(st, "set:coach.objectif")["label"] == "Objectif" and _item(st, "set:coach.temps_disponible_min")["detail"] == "60 min",
		"réglages du profil sans « Conseil : »")
	_check(_item(st, "coach_other")["detail"] == "1 de plus" and _item(st, "coach_race")["detail"] == "60 min",
		"autre séance et durée de la course")
	_check(st["card"]["name"] == "Sweet Spot 3 × 10 min" and st["card"]["tiles"].size() == 3, "carte : entraînement conseillé")
	f.menu.focus_item("coach_race")
	st = f.state()
	_check(st["card"]["name"] == "Côte · 4 tours" and st["card"]["tiles"][2]["value"] == "105",
		"carte : course, tours et part dans le besoin (%s)" % str(st["card"]))


func _test_launch_workout() -> void:
	var f = _flow()
	_open(f)
	f.on_coach(MSG)
	f.menu.focus_item("coach_workout")
	var act: Dictionary = f.handle("A_LONG")
	_check(act == {"action": "select_workout", "workout_id": "sweet_spot_3x10"} and f.menu.current_screen() == MenuModel.ROUTES,
		"entraînement : ERG, parcours d'abord sans monde choisi (%s)" % str(act))
	f.handle("A_LONG")
	_check(f.menu.current_screen() == MenuModel.READY and f.menu.mode == "erg", "puis l'écran Prêt en ERG")
	f = _flow()
	f.menu.set_world("cote", "Côte des vignes")
	_open(f)
	f.on_coach(MSG)
	f.menu.focus_item("coach_other")
	f.handle("A_LONG")
	_check(f.menu.current_screen() == Coach.OTHER and _ids(f.state()) == ["w:sweet_spot_3x10", "w:seuil_2x20"],
		"autre séance : conseillé puis les autres")
	f.menu.focus_item("w:seuil_2x20")
	_check(f.handle("A_LONG") == {"action": "select_workout", "workout_id": "seuil_2x20"} and f.menu.current_screen() == MenuModel.READY,
		"autre séance lancée, monde déjà choisi : écran Prêt")


func _test_launch_race() -> void:
	var f = _flow()
	_open(f)
	f.on_coach(MSG)
	f.menu.focus_item("coach_race")
	var act: Dictionary = f.handle("A_LONG")
	_check(act["action"] == "sequence" and act["list"][0] == {"action": "select_route", "route_id": "cote"}
		and act["list"][1] == {"action": "select_workout", "workout_id": null}, "course : parcours du conseil, SIM")
	var st: Dictionary = f.state()
	_check(st["screen"] == MenuModel.READY and _ids(st) == ["start", "ghost"]
		and st["title"] == "Prêt : course conseillée — Côte des vignes" and _item(st, "start")["detail"] == "4 tours, environ 60 min",
		"écran Prêt de la course conseillée (%s | %s)" % [st["title"], str(_ids(st))])
	act = f.handle("A_LONG")
	var bots: Array = act["args"]["bots"]
	_check(act["action"] == "start" and bots.size() == 4 and bots[0] == {"kind": "profile", "profile": "rouleur", "level_pct": 95}
		and bots[1]["profile"] == "climber", "start : 4 bots à profil à 95 %% (tactique Y10) (%s)" % str(act))
	f.menu.reset()
	_check(f.menu.mode == "free", "nouvel accueil : mode remis")
	var light := MSG.duplicate(true)
	light["route"]["bots"] = {"count": 4, "level_pct": 65, "tactics": "none"}
	f.on_coach(light)
	_check(f.coach.race_bots(MenuModel.PELOTON_PROFILES)[0] == {"kind": "constant", "ftp_pct": 65},
		"sans tactique : bots à puissance constante")


func _test_survivor_race() -> void:
	var f = _flow()
	_open(f)
	var m := MSG.duplicate(true)
	m["need"] = "anaerobic"
	m["route"] = {"mode": "survivor", "label": "Dernier survivant, une arche par kilomètre", "route_id": "cote",
		"route_name": "Côte", "laps": 3, "duration_s": 3500, "bots": {"count": 0, "level_pct": 100, "tactics": "classic"},
		"survivor": {"opponents": 4, "spacing_km": 1}, "predicted_need_s": 300, "reference_need_s": 180, "ratio_pct": 167}
	f.on_coach(m)
	_check(_item(f.state(), "coach_race")["label"] == "Lancer le Dernier survivant", "libellé du Dernier survivant")
	f.menu.focus_item("coach_race")
	var act: Dictionary = f.handle("A_LONG")
	_check(act["list"].slice(2) == [{"action": "set_setting", "key": "survivor.opponents", "value": 4},
		{"action": "set_setting", "key": "survivor.spacing_km", "value": 1}], "réglages du mode au format (%s)" % str(act["list"]))
	var st: Dictionary = f.state()
	_check(f.menu.mode == "survivor" and st["screen"] == MenuModel.READY and _item(st, "set:survivor.opponents")["detail"] == "4",
		"écran Prêt du Dernier survivant, réglages visibles")


func _test_detail_and_need() -> void:
	var f = _flow()
	_open(f)
	f.on_coach(MSG)
	f.menu.focus_item("coach_detail")
	f.handle("A_LONG")
	var st: Dictionary = f.state()
	_check(st["screen"] == Coach.DETAIL and _item(st, "d_intense")["bar"] == 9 and _item(st, "d_hard")["detail"] == "il y a 6 j"
		and _item(st, "d_profile")["detail"] == "aérobie intense", "détail : barres, séance dure, profil")
	f.menu.focus_item("d_intense")
	st = f.state()
	_check(st["card"]["tiles"][2]["value"] == "7" and "Course : 05/11 Dernier survivant, 3e, lâché en montée." in st["card"]["lines"],
		"carte : retard et dernière course (%s)" % str(st["card"]))
	f.handle("Y_SHORT")
	f.menu.focus_item("coach_need")
	f.handle("A_LONG")
	st = f.state()
	_check(st["screen"] == Coach.NEED and st["items"][st["focus"]]["id"] == "need_intense"
		and _item(st, "need_intense")["detail"] == "conseillé", "autre besoin : focus sur le conseil du jour")
	f.menu.focus_item("need_anaerobic")
	var act: Dictionary = f.handle("A_LONG")
	_check(act == {"action": "coach_command", "name": "get_coach", "args": {"need": "anaerobic"}}
		and f.menu.current_screen() == Coach.SCREEN, "besoin choisi : get_coach {need}, retour au conseil")
	var ch := MSG.duplicate(true)
	ch["need"] = "anaerobic"
	ch["rule"] = "CH"
	ch["alternatives"] = ["intense"]
	f.on_coach(ch)
	_check(_item(f.state(), "coach_need")["detail"] == "Anaérobie", "besoin choisi rappelé")
	f.menu.focus_item("coach_need")
	f.handle("A_LONG")
	f.menu.focus_item("need_intense")
	_check(f.handle("A_LONG")["args"] == {}, "retour au besoin conseillé : conseil du jour")


func _test_race_and_watch_inputs() -> void:
	var f = _flow()
	_open(f)
	f.on_coach(MSG)
	f.menu.focus_item("coach_race_date")
	f.handle("A_LONG")
	var st: Dictionary = f.state()
	_check(st["screen"] == Coach.RACE and _item(st, "set:conseil.race_days")["detail"] == "sam. 14/11"
		and not _item(st, "race_clear")["enabled"], "prochaine course : dans 7 jours par défaut (%s)" % str(_item(st, "set:conseil.race_days")))
	f.menu.focus_item("set:conseil.race_days")
	f.handle("A_LONG")
	f.handle("MINUS_SHORT")
	f.handle("MINUS_SHORT")
	_check(_item(f.state(), "set:conseil.race_days")["detail"] == "◀ jeu. 12/11 ▶", "date modifiée en place")
	f.handle("A_LONG")
	f.menu.focus_item("set:conseil.race_kind")
	f.handle("A_LONG")
	f.handle("PLUS_SHORT")
	f.handle("A_LONG")
	f.menu.focus_item("race_save")
	var act: Dictionary = f.handle("A_LONG")
	_check(act == {"action": "coach_command", "name": "set_next_race", "args": {"date": "2026-11-12", "kind": "championnat"}},
		"Enregistrer : set_next_race (%s)" % str(act))
	var saved := MSG.duplicate(true)
	saved["rule"] = "R2"
	saved["details"]["next_race"] = {"date": "2026-11-12", "kind": "championnat"}
	f.on_coach(saved)
	st = f.state()
	_check(st["screen"] == Coach.SCREEN and _item(st, "coach_race_date")["detail"] == "jeu. 12/11", "réponse : retour au conseil")
	f.menu.focus_item("coach_watch")
	f.handle("A_LONG")
	f.menu.focus_item("set:conseil.watch_type")
	f.handle("A_LONG")
	for i in 2:
		f.handle("PLUS_SHORT")
	f.handle("A_LONG")
	f.menu.focus_item("set:conseil.watch_min")
	f.handle("A_LONG")
	f.handle("PLUS_LONG")
	f.handle("PLUS_LONG")
	f.handle("A_LONG")
	_check(_item(f.state(), "set:conseil.watch_type")["detail"] == "seuil" and _item(f.state(), "set:conseil.watch_min")["detail"] == "50 min",
		"montre : seuil, 50 min")
	f.menu.focus_item("watch_save")
	act = f.handle("A_LONG")
	_check(act["args"] == {"type": "seuil", "duration_min": 50}, "Enregistrer : set_watch_advice (%s)" % str(act))
	f.on_error("bad_args", "set_watch_advice : refusé")
	_check(f.state()["status"] == "Échec : set_watch_advice : refusé" and f.state()["status_error"], "erreur du core affichée")


func _test_settings_and_rest() -> void:
	var f = _flow()
	_open(f)
	f.on_coach(MSG)
	f.menu.focus_item("set:coach.temps_disponible_min")
	f.handle("A_LONG")
	f.handle("PLUS_SHORT")
	var act: Dictionary = f.handle("A_LONG")
	_check(act == {"action": "sequence", "list": [{"action": "set_setting", "key": "coach.temps_disponible_min", "value": 75},
		{"action": "coach_command", "name": "get_coach", "args": {}}]}, "temps disponible : réglage puis conseil recalculé (%s)" % str(act))
	var rest := MSG.duplicate(true)
	rest["need"] = "rest"
	rest["workout"] = null
	rest["route"] = null
	rest["other_workouts"] = []
	f.on_coach(rest)
	var st: Dictionary = f.state()
	_check(_ids(st)[0] == "rest" and not st["items"][0]["enabled"] and not _item(st, "coach_other")["enabled"],
		"repos : rien à lancer")
	_check(_item(f.state(), "coach_need")["enabled"], "repos : un autre besoin reste possible")


## Message `coach` perdu (grande trame UDP) : commande renvoyée toutes les 3 s, réponse à une demande remplacée
## ignorée, échec en rouge après 3 relances ; saisie refusée (bad_args) : pas de relance.
func _test_lost_reply() -> void:
	var c = IpcClientScript.new()   # sans _ready : aucun port ouvert, envois sans effet
	var got: Array = []
	var failed: Array = []
	c.coach_received.connect(func(m: Dictionary) -> void: got.append(m))
	c.list_failed.connect(func(n: String, _t: String) -> void: failed.append(n))
	var first: int = c.coach_command("get_coach", {"need": "anaerobic"})
	c._tick_coach(2.9)
	_check(c._pending_coach["cmd_ids"] == [first], "conseil : pas de relance avant 3 s")
	c._tick_coach(0.2)
	_check(c._pending_coach["cmd_ids"].size() == 2 and c._pending_coach["args"] == {"need": "anaerobic"},
		"conseil : même commande renvoyée après 3 s")
	var late := MSG.duplicate(true)
	late["request_cmd_id"] = first
	c._on_coach(late)
	_check(got.size() == 1 and c._pending_coach.is_empty(), "conseil : réponse à la première demande acceptée")
	var old: int = c.coach_command("get_coach")
	c.coach_command("set_next_race", {"date": "2026-11-14", "kind": "course"})
	var stale := MSG.duplicate(true)
	stale["request_cmd_id"] = old
	c._on_coach(stale)
	_check(got.size() == 1 and not c._pending_coach.is_empty(), "conseil : réponse à une demande remplacée ignorée")
	for i in 4:
		c._tick_coach(3.0)
	_check(failed == ["coach"] and c._pending_coach.is_empty(), "conseil : échec signalé après 3 relances")
	c.coach_command("set_watch_advice", {"type": "fond"})
	c._on_error("bad_args", "Conseil : type de séance inconnu")
	_check(c._pending_coach.is_empty(), "conseil : saisie refusée, pas de relance")
	var f = _flow()
	_open(f)
	f.list_failed("coach")
	var st: Dictionary = f.state()
	_check(st["status_error"] and str(st["status"]).contains("sans réponse"), "conseil sans réponse : ligne d'état en rouge")
	c.free()
