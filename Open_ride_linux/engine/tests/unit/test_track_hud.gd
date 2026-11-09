extends SceneTree

## Tests sans écran du HUD des épreuves de piste (série VD, lot VD9) : objet `track` de la trame `state`
## (contrat 1.7) traduit en bandeau, tours, liste, poursuite, chrono, derny, bandeaux du milieu, tableau
## d'affichage de la salle, sons (cloche, pistolet, public) et lignes du bilan ; vue sans plantage.
## Cas des maquettes VD8 : course aux points, cloche, élimination (dernier), poursuite, kilomètre, keirin,
## américaine, heure, omnium.
## Lancement : godot --headless --path engine --script res://tests/unit/test_track_hud.gd

const Model := preload("res://scripts/track/track_hud_model.gd")
const View := preload("res://scripts/track/track_view.gd")
const SummaryViewModel := preload("res://scripts/summary_view_model.gd")
const EventSounds := preload("res://scripts/event_sounds_model.gd")
const VelodromeHall := preload("res://scripts/velodrome_hall.gd")

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


const BOTS := [{"id": "b1", "name": "Bastien"}, {"id": "b2", "name": "Léa"}, {"id": "b3", "name": "Marco"},
	{"id": "b4", "name": "Hugo"}, {"id": "b5", "name": "Inès"}]


func _st(tr: Dictionary) -> Dictionary:
	return {"session_state": "RUNNING", "s": 100.0, "bots": BOTS, "track": tr}


func _points() -> Dictionary:
	return {"event": "points", "t_s": 412.0, "lap": 23, "laps": 40, "laps_to_go": 17, "bell": false,
		"ranking": ["b1", "me", "b2", "b3"], "points": [14, 11, 8, 5], "eliminated": [], "finished": false,
		"laps_up": 0, "my_lap": 23, "next_sprint_lap": 25}


func _run() -> void:
	var m = Model.new()
	_check(not m.view({"session_state": "RUNNING"})["visible"], "sans objet track : rien")

	# Course aux points (maquette 1)
	var v: Dictionary = m.view(_st(_points()))
	_check(v["visible"] and v["banner"]["title"] == "Course aux points · 40 tours", "points : titre (%s)" % v["banner"]["title"])
	_check(v["banner"]["sub"] == "Sprint dans 2 tours · 5, 3, 2, 1 pts", "points : prochain sprint (%s)" % v["banner"]["sub"])
	_check(v["laps"]["value"] == "23 / 40" and v["laps"]["extra"] == "17 tours" and absf(v["laps"]["bar"] - 0.575) < 0.001, "points : tours")
	var rows: Array = v["list"]["rows"]
	_check(v["list"]["title"] == "POINTS" and rows.size() == 4, "points : liste de 4")
	_check(rows[0]["name"] == "Bastien" and rows[0]["value"] == "14" and rows[1]["name"] == "Toi" and rows[1]["kind"] == "me",
		"points : Toi surligné en 2e (%s)" % str(rows[1]))
	_check(v["pursuit"].is_empty() and v["chrono"].is_empty() and v["pacer"].is_empty() and v["center"].is_empty(), "points : pas d'autre bloc")

	# Cloche du dernier tour
	var bell := _points()
	bell.merge({"lap": 40, "laps_to_go": 1, "bell": true, "next_sprint_lap": 40}, true)
	v = m.view(_st(bell))
	_check(v["banner"]["bell"] and v["banner"]["sub"] == "DERNIER TOUR" and v["banner"]["color"] == Model.GOLD_BG, "cloche : bandeau doré")
	_check(v["laps"]["extra"] == "cloche", "cloche : bloc des tours")

	# Sons : pistolet au départ, cloche une fois, public avant le sprint
	var s = Model.new()
	var p0 := _points()
	p0.merge({"t_s": 0.2, "lap": 1, "next_sprint_lap": 10}, true)
	_check(s.sounds(_st(p0)) == ["track_gun"], "pistolet au départ")
	_check(s.sounds(_st(p0)) == [], "pistolet une seule fois")
	var p1 := _points()
	p1.merge({"lap": 10, "next_sprint_lap": 10}, true)
	_check(s.sounds(_st(p1)) == ["track_crowd"], "public au tour du sprint")
	_check(s.sounds(_st(p1)) == [], "public une fois par sprint")
	_check(s.sounds(_st(bell)) == ["track_bell", "track_crowd"], "cloche et public au dernier tour (%s)" % str(s.sounds(_st(bell))))
	_check(s.sounds(_st(bell)) == [], "cloche une seule fois")
	var late = Model.new()
	_check(late.sounds(_st(_points())) == [], "épreuve reprise en cours : pas de pistolet")
	_check(s.sounds({}) == [], "hors épreuve : rien")
	for j in ["track_bell", "track_gun", "track_crowd"]:
		_check(EventSounds.JINGLES.has(j), "%s déclaré" % j)
	_check(str(EventSounds.JINGLES["track_bell"]) != str(EventSounds.JINGLES["jingle_lap"]), "cloche différente de la ligne")

	# Élimination : le cycliste est dernier (maquette 4)
	var el := {"event": "elimination", "t_s": 200.0, "lap": 6, "laps": 24, "laps_to_go": 18, "bell": true,
		"ranking": ["b1", "b2", "b3", "me", "b4", "b5"], "points": null, "eliminated": ["b5", "b4"], "finished": false,
		"to_elim_m": 180.0, "gap_last_s": 0.4, "last": "me", "alive": 4}
	v = m.view(_st(el))
	_check(v["banner"]["color"] == Model.RED and v["banner"]["sub"] == "ÉLIMINATION À CE TOUR", "élimination : bandeau rouge")
	_check(v["laps"]["label"] == "ENCORE EN COURSE" and v["laps"]["value"] == "4" and v["laps"]["extra"] == "4 sur 6", "élimination : encore en course")
	rows = v["list"]["rows"]
	_check(v["list"]["title"] == "ORDRE DE COURSE" and rows.size() == 6, "élimination : ordre de course et sortis")
	_check(rows[3]["name"] == "Toi" and rows[3]["value"] == "dernier", "élimination : Toi dernier")
	_check(rows[4]["kind"] == "out" and rows[4]["name"] == "Hugo" and rows[5]["name"] == "Inès", "élimination : sortis grisés, le dernier sorti en premier")
	_check(v["center"]["title"] == "DERNIER !" and v["center"]["sub"] == "Remonte Marco avant la ligne (0,4 s)", "élimination : bandeau DERNIER (%s)" % str(v["center"]))
	el["last"] = "b3"
	v = m.view(_st(el))
	_check(v["center"].is_empty() and v["list"]["rows"][2]["kind"] == "danger", "élimination : un bot dernier en rouge")

	# Poursuite (maquette 5)
	var pu := {"event": "pursuit", "t_s": 150.0, "lap": 9, "laps": 16, "laps_to_go": 8, "bell": false,
		"ranking": ["me", "b1"], "points": null, "eliminated": [], "finished": false,
		"d_m": 2125.0, "to_go_m": 1875.0, "gap_m": 12.0, "gap_s": 0.84, "lead": null}
	v = m.view(_st(pu))
	_check(v["pursuit"]["gap_text"] == "−0,84 s" and v["pursuit"]["good"], "poursuite : avance en vert (%s)" % v["pursuit"]["gap_text"])
	_check(v["pursuit"]["left"] == "encore 1,88 km", "poursuite : distance restante (%s)" % v["pursuit"]["left"])
	_check(absf(v["pursuit"]["me_frac"] - 0.5) < 0.001 and absf(v["pursuit"]["opp_frac"] - 0.952) < 0.001, "poursuite : places sur l'anneau")
	_check(v["list"].is_empty(), "poursuite : pas de liste")
	pu["gap_s"] = -1.2
	_check(m.view(_st(pu))["pursuit"]["gap_text"] == "+1,20 s" and not m.view(_st(pu))["pursuit"]["good"], "poursuite : retard en rouge")

	# Kilomètre et 200 m lancé
	var ki := {"event": "kilo", "t_s": 40.0, "lap": 3, "laps": 4, "laps_to_go": 2, "bell": false, "ranking": ["me"],
		"points": null, "eliminated": [], "finished": false, "d_m": 610.0, "to_go_m": 390.0, "timed": true, "time_s": 41.253}
	v = m.view(_st(ki))
	_check(v["chrono"]["big"] == "41,253" and v["chrono"]["line"] == "passage 610 m", "kilomètre : chrono (%s)" % str(v["chrono"]))
	_check(v["laps"]["extra"] == "390 m", "kilomètre : distance restante")
	var fl := ki.duplicate()
	fl.merge({"event": "flying_200", "d_m": 300.0, "timed": false, "time_s": null}, true)
	v = m.view(_st(fl))
	_check(v["chrono"]["big"] == "élan" and v["chrono"]["line"] == "chrono dans 130 m", "200 m lancé : élan (%s)" % str(v["chrono"]))
	_check(Model.chrono_text(61.5) == "1:01,500", "chrono au-delà d'une minute")

	# Keirin (maquette 7)
	var ke := {"event": "keirin", "t_s": 60.0, "lap": 3, "laps": 8, "laps_to_go": 6, "bell": false,
		"ranking": ["b1", "me", "b2"], "points": null, "eliminated": [], "finished": false,
		"pacer": {"s": 900.0, "v": 11.11, "on": true}}
	v = m.view(_st(ke))
	_check(v["pacer"]["text"] == "s'écarte dans 3 tours" and v["pacer"]["speed"] == "40 km/h", "keirin : derny (%s)" % str(v["pacer"]))
	_check(v["list"]["title"] == "DERRIÈRE LE DERNY", "keirin : liste derrière le derny")
	_check(v["list"]["rows"][0]["value"] == "derny", "keirin : le premier est derrière le derny")
	var kst := _st(ke)
	kst["lane_m"] = 0.65
	var with_p: Array = Model.bots_with_pacer(kst)
	_check(with_p.size() == BOTS.size() + 1 and with_p[-1]["id"] == Model.PACER_ID and with_p[-1]["name"] == "Derny"
		and is_equal_approx(float(with_p[-1]["s"]), 900.0) and is_equal_approx(float(with_p[-1]["lane_m"]), 0.65), "keirin : le derny roule avec les bots")
	_check(BOTS.size() == 5, "bots de la trame non modifiés")
	ke["pacer"]["on"] = false
	_check(Model.bots_with_pacer(_st(ke)) == BOTS, "derny parti : bots tels quels")
	_check(Model.bots_with_pacer(_st(_points())) == BOTS, "hors keirin : bots tels quels")
	v = m.view(_st(ke))
	_check(v["pacer"]["text"] == "parti : sprint !" and v["banner"]["sub"] == "Derny parti : sprint !", "keirin : derny parti")

	# Américaine : équipes, relais
	var ma := {"event": "madison", "t_s": 300.0, "lap": 12, "laps": 40, "laps_to_go": 28, "bell": false,
		"ranking": ["t2", "home", "t3"], "points": [5, 3, 0], "eliminated": [], "finished": false,
		"next_sprint_lap": 20, "racers": {"home": "b1", "t2": "b2", "t3": "b3"}}
	v = m.view(_st(ma))
	_check(v["list"]["title"] == "ÉQUIPES · POINTS" and v["list"]["rows"][1]["name"] == "Ton équipe" and v["list"]["rows"][1]["kind"] == "me",
		"américaine : Ton équipe")
	_check(v["center"]["title"] == "AU REPOS EN HAUT" and v["center"]["sub"].begins_with("Bastien court"), "américaine : au repos (%s)" % str(v["center"]))
	ma["racers"]["home"] = "me"
	_check(m.view(_st(ma))["center"].is_empty(), "américaine : en course, pas de bandeau")

	# Vitesse par équipes : seuls les sortis de ton équipe sont listés
	var ts := {"event": "team_sprint", "t_s": 30.0, "lap": 3, "laps": 3, "laps_to_go": 1, "bell": true,
		"ranking": ["home", "t2"], "points": null, "eliminated": [], "finished": false, "d_m": 500.0, "to_go_m": 250.0,
		"gap_m": 6.0, "gap_s": 0.44, "lead": "me", "order": ["me", "b1", "b2"]}
	var tm = Model.new()
	tm.view(_st(ts))
	ts.merge({"eliminated": ["b4", "me", "b5"], "order": ["b2"], "lead": "b2"}, true)
	rows = tm.view(_st(ts))["list"]["rows"]
	_check(rows.size() == 2 and rows[0]["name"] == "Léa" and rows[0]["value"] == "en tête" and rows[1]["name"] == "Toi" and rows[1]["kind"] == "out",
		"vitesse par équipes : Toi sorti, pas l'autre équipe (%s)" % str(rows))

	# Heure, séance libre, omnium
	var ho := {"event": "hour", "t_s": 1800.0, "lap": 101, "laps": null, "laps_to_go": null, "bell": false, "ranking": ["me"],
		"points": null, "eliminated": [], "finished": false, "d_m": 25123.0, "time_left_s": 1800.0, "avg_kmh": 50.25}
	v = m.view(_st(ho))
	_check(v["laps"]["value"] == "100" and v["laps"]["extra"] == "30:00 restant" and absf(v["laps"]["bar"] - 0.5) < 0.001, "heure : tours et temps")
	_check(v["chrono"]["big"] == "25,123 km" and v["banner"]["sub"].begins_with("Moyenne 50,2"), "heure : distance et moyenne (%s)" % v["banner"]["sub"])
	var fr := {"event": "free", "t_s": 100.0, "lap": 5, "laps": null, "laps_to_go": null, "bell": false, "ranking": ["me"],
		"points": null, "eliminated": [], "finished": false, "last_lap_s": 19.87, "best_lap_s": 19.5}
	v = m.view(_st(fr))
	_check(v["laps"]["value"] == "4" and v["laps"]["extra"] == "meilleur 19,50 s" and v["banner"]["sub"] == "Dernier tour 19,87 s", "séance libre")
	var om := el.duplicate(true)
	om.merge({"event": "omnium", "sub": "elimination", "sub_index": 3, "subs": 4, "neutral": false, "last": "me", "points": [40, 36, 34, 30, 0, 0]}, true)
	v = m.view(_st(om))
	_check(v["banner"]["title"] == "Omnium · Élimination (3 / 4)" and v["center"]["title"] == "DERNIER !", "omnium : sous-épreuve élimination (%s)" % v["banner"]["title"])

	# Tableau d'affichage de la salle
	var board: String = m.board_text(_st(_points()))
	var lines := board.split("\n")
	_check(lines[0] == "COURSE AUX POINTS · 40 TOURS" and lines[1] == "TOURS 23 / 40" and lines[3] == "2. TOI 11", "tableau : texte (%s)" % board.replace("\n", " | "))
	_check(lines.size() <= Model.BOARD_LINES, "tableau : 8 lignes au plus")
	_check(m.board_text({}) == VelodromeHall.SCOREBOARD_IDLE, "tableau hors épreuve")
	var fs: int = VelodromeHall.scoreboard_font_size(board)
	_check(fs >= 16 and fs < VelodromeHall.SCOREBOARD_FONT_MAX, "tableau : lettres réduites pour 6 lignes (%d)" % fs)
	_check(VelodromeHall.scoreboard_font_size(VelodromeHall.SCOREBOARD_IDLE) >= 80, "tableau : texte d'attente en grand")
	var hall = VelodromeHall.new()
	var lbl := Label3D.new()
	lbl.name = "ScoreboardText0"
	hall.add_child(lbl)
	hall.set_scoreboard(board)
	_check(hall.scoreboard_text() == board and lbl.font_size == fs, "tableau : texte posé sur la face")
	hall.free()

	# Bilan
	var summ := {"event": "kilo", "place": 1, "of": 1, "ranking": ["me"], "names": {}, "elapsed_s": 70.0,
		"laps": [22.1, 16.0, 16.2, 16.5], "best_lap_s": 16.0, "finished": true, "points": null, "record": null,
		"record_rank": 1, "time_s": 70.812}
	var sl: Array = Model.summary_lines(summ)
	_check(sl[0]["label"] == "Kilomètre · départ arrêté" and sl[0]["value"] == "terminé", "bilan : épreuve seule")
	_check(sl[1]["value"] == "1:10,812" and sl[3]["value"] == "16,00 s (tour 2)" and sl[4]["value"] == "nouveau record !", "bilan : temps, meilleur tour, record (%s)" % str(sl))
	var race := {"event": "scratch", "place": 2, "of": 6, "ranking": ["b1", "me"], "names": {"b1": "Bastien"}, "laps": [],
		"best_lap_s": null, "finished": true, "points": null, "record": null, "record_rank": null}
	sl = Model.summary_lines(race)
	_check(sl[0]["value"] == "2e sur 6" and sl[-1]["value"] == "Bastien", "bilan : place et vainqueur (%s)" % str(sl))
	var all_lines: Array = SummaryViewModel.new().lines({"track": race})
	var found := false
	for l in all_lines:
		found = found or str(l.get("label", "")) == "Scratch"
	_check(found, "bilan : lignes de la piste dans le bilan")
	_check(Model.lap_rows(summ)[1]["best"] and not Model.lap_rows(summ)[0]["best"], "bilan : meilleur tour marqué")

	# Vue : construite et remplie sans erreur
	var view = View.new()
	get_root().add_child(view)
	for st in [_points(), bell, el, pu, ki, ke, ma, ho, om]:
		view.update_view(m.view(_st(st)))
	view.update_view(m.view(_st(_points())))
	var info: Dictionary = view.test_info()
	_check(info["visible"] and info["banner"] == "Course aux points · 40 tours" and info["laps"] == "23 / 40", "vue : bandeau et tours")
	_check(info["list"].size() == 4 and str(info["list"][1]) == "Toi" and info["list_title"] == "POINTS", "vue : liste (%s)" % str(info["list"]))
	view.update_view(m.view(_st(bell)))
	_check(view.test_info()["bell"], "vue : cloches au dernier tour")
	view.update_view(m.view(_st(pu)))
	_check(view.test_info()["pursuit"] != "" and view.test_info()["list"].is_empty(), "vue : poursuite")
	view.update_view({"visible": false})
	_check(not view.test_info()["visible"], "vue cachée hors du mode")
	view.queue_free()
	_check(View.ring_point(0.0, 20.0, 10.0) == Vector2(0, 10) and View.ring_point(0.5, 20.0, 10.0).is_equal_approx(Vector2(0, -10)), "anneau : A en bas, B en haut")

	print("test_track_hud : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
