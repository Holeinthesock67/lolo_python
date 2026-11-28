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
	_check(v["pursuit"].is_empty() and v["chrono"].is_empty() and v["pacer"].is_empty(), "points : pas d'autre bloc")
	_check(m.consigne(_st(_points()))["action"].begins_with("Sprint") and m.consigne(_st(_points()))["detail"].begins_with("Objectif : marquer le plus de points"),
		"points : consigne du prochain sprint (%s)" % str(m.consigne(_st(_points()))))

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
	var c: Dictionary = m.consigne(_st(el))
	_check(c["action"] == "Passe Marco avant la ligne : 0,4 s" and c["chips"] == ["pédale plus fort"]
		and c["detail"] == "Objectif : être le dernier en course · Pourquoi : le dernier sur la ligne est éliminé",
		"élimination : consigne commune, passer le coureur devant (%s)" % str(c))
	_check(not v.has("center"), "plus de bandeau du milieu propre à la piste (lot RT1)")
	el["last"] = "b3"
	v = m.view(_st(el))
	_check(v["list"]["rows"][2]["kind"] == "danger", "élimination : un bot dernier en rouge")
	_check(m.consigne(_st(el))["action"] == "Ne sois pas dernier sur la ligne · dans 180 m", "élimination : consigne hors danger")

	# Révision 1.33 (essai du 21 novembre) : tours entre deux éliminations, écarts aux voisins, victoire
	el.merge({"every_laps": 4, "bell": false, "ahead": {"id": "b3", "gap_s": 1.24}, "behind": {"id": "b4", "gap_s": -0.8}}, true)
	v = m.view(_st(el))
	_check(v["banner"]["sub"].begins_with("Le dernier sort tous les 4 tours"), "élimination : tous les 4 tours (%s)" % v["banner"]["sub"])
	_check(v["gaps"]["ahead"]["name"] == "Marco" and v["gaps"]["ahead"]["text"] == "+1,2 s", "écart devant (%s)" % str(v["gaps"]))
	_check(v["gaps"]["behind"]["name"] == "Hugo" and v["gaps"]["behind"]["text"] == "−0,8 s", "écart derrière")
	el.merge({"ahead": null}, true)
	_check(not m.view(_st(el))["gaps"].has("ahead"), "en tête : pas d'écart devant")
	el.merge({"behind": null}, true)
	_check(m.view(_st(el))["gaps"].is_empty(), "sans voisin : pas de bloc des écarts")
	var win := {"event": "elimination", "t_s": 900.0, "lap": 28, "laps": 28, "laps_to_go": 1, "bell": false,
		"ranking": ["me", "b1", "b2"], "points": null, "eliminated": ["b2", "b1"], "finished": true,
		"to_elim_m": null, "gap_last_s": null, "last": "me", "alive": 1, "every_laps": 4, "ahead": null, "behind": null}
	v = m.view(_st(win))
	_check(v["banner"]["sub"] == "Épreuve terminée", "victoire : bandeau de l'épreuve terminé")
	_check(m.consigne(_st(win)).is_empty(), "victoire : plus de consigne du mode (consigne de fin commune)")
	_check(v["list"]["rows"][0]["name"] == "Toi" and v["list"]["rows"][0]["value"] == "" and v["list"]["rows"][0]["kind"] == "me",
		"victoire : Toi premier, plus « dernier » (%s)" % str(v["list"]["rows"][0]))
	_check(v["laps"]["label"] == "CLASSEMENT" and v["laps"]["value"] == "1er" and v["laps"]["extra"] == "sur 3",
		"victoire : classement figé au lieu de « encore en course » (%s)" % str(v["laps"]))
	var fin_rows: Array = v["list"]["rows"]
	_check(v["list"]["title"] == "CLASSEMENT FINAL" and fin_rows.size() == 3 and fin_rows[2]["pos"] == "3." and fin_rows[2]["kind"] == "ok",
		"fin : classement final numéroté, éliminés compris (%s)" % str(v["list"]))
	var lost := win.duplicate(true)
	lost.merge({"ranking": ["b1", "b2", "me"], "eliminated": ["me", "b2"], "last": "b1"}, true)
	_check(m.view(_st(lost))["laps"]["value"] == "3e", "fin : 3e sur 3")
	# Moments communs (lot RT1) : bot éliminé, cycliste dernier, victoire, place, cycliste éliminé ; une fois chacun
	var ws = Model.new()
	var run := win.duplicate()
	run.merge({"finished": false, "eliminated": ["b2"], "ranking": ["me", "b1", "b2"], "alive": 2, "last": "b1"}, true)
	_check(ws.sounds(_st(run)) == [] and ws.moments(_st(run)).is_empty(), "épreuve en cours : sortis d'avant non annoncés")
	var run2 := run.duplicate()
	run2.merge({"eliminated": ["b2", "b3"], "ranking": ["me", "b1", "b3", "b2"]}, true)
	var mo: Array = ws.moments(_st(run2))
	_check(mo.size() == 1 and mo[0]["family"] == "bien" and mo[0]["title"] == "Marco est éliminé" and mo[0]["sub"] == "Plus que 2 en course"
		and mo[0]["sound"] == "jingle_elim", "bot éliminé : BIEN et jingle (%s)" % str(mo))
	var run3 := run2.duplicate()
	run3.merge({"last": "me", "to_elim_m": 240.0}, true)
	mo = ws.moments(_st(run3))
	_check(mo.size() == 1 and mo[0]["family"] == "attention" and mo[0]["sub"] == "Ligne d'élimination dans 240 m",
		"cycliste dernier : ATTENTION (%s)" % str(mo))
	_check(ws.moments(_st(run3)).is_empty(), "ATTENTION une seule fois")
	mo = ws.moments(_st(win))
	_check(mo.size() == 1 and mo[0]["family"] == "resultat" and mo[0]["tone"] == "win" and mo[0]["title"] == "VICTOIRE !"
		and mo[0]["done_k"] == "COURSE FINIE · 1er sur 3", "victoire : RÉSULTAT or (%s)" % str(mo))
	_check(ws.moments(_st(win)).is_empty(), "victoire : une seule fois")
	_check(ws.sounds(_st(win)) == ["track_crowd"] and ws.sounds(_st(win)) == [], "victoire : le public, une fois")
	var third := win.duplicate()
	third.merge({"ranking": ["b1", "b2", "me"]}, true)
	var fm: Dictionary = Model.new().finish_moment(third)
	_check(fm["title"] == "ARRIVÉE · 3e sur 3" and fm["tone"] == "place" and fm["done_k"] == "COURSE FINIE · 3e sur 3", "arrivée : place")
	var outs = Model.new()
	var me_out := run.duplicate()
	me_out.merge({"eliminated": ["b2", "me"], "ranking": ["b1", "me", "b2"]}, true)
	outs.moments(_st(run))
	mo = outs.moments(_st(me_out))
	_check(mo.size() == 1 and mo[0]["tone"] == "out" and mo[0]["title"] == "ÉLIMINÉ · 2e sur 3" and mo[0]["sound"] == "jingle_elim"
		and mo[0]["done_action"] == "Roule au calme : la course continue sans toi", "cycliste éliminé : RÉSULTAT rouge (%s)" % str(mo))
	var fin_out := me_out.duplicate()
	fin_out.merge({"finished": true}, true)
	_check(outs.moments(_st(fin_out)).is_empty() and outs.consigne(_st(me_out)).is_empty(),
		"cycliste éliminé : pas de second résultat à la fin, plus de consigne du mode")

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
	_check(m.consigne(_st(ma))["action"] == "Au repos en haut : redescends au passage de Bastien pour le relais",
		"américaine : au repos, consigne commune (%s)" % str(m.consigne(_st(ma))))
	ma["racers"]["home"] = "me"
	_check(m.consigne(_st(ma))["action"].begins_with("Sprint"), "américaine : en course, consigne du sprint")

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
	_check(v["banner"]["title"] == "Omnium · Élimination (3 / 4)" and m.consigne(_st(om))["action"].begins_with("Passe"), "omnium : sous-épreuve élimination (%s)" % v["banner"]["title"])

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

	_revue_e11()
	print("test_track_hud : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)


## Revue de code vague 3, lot EC4 : trame allégée (E11-01), omnium suivi sur plusieurs sous-épreuves (E11-02),
## peloton de plus de 8 coureurs (E11-05).
func _revue_e11() -> void:
	# E11-01 : un bot loin sans `name` une trame sur deux garde son nom
	var m = Model.new()
	var pts := _points()
	m.view({"session_state": "RUNNING", "bots": BOTS, "track": pts})
	var light := [{"id": "b1", "name": "Bastien"}, {"id": "b2"}, {"id": "b3"}]
	var v: Dictionary = m.view({"session_state": "RUNNING", "bots": light, "track": pts})
	var names: Array = []
	for r in v["list"]["rows"]:
		names.append(r["name"])
	_check(names == ["Bastien", "Toi", "Léa", "Marco"], "trame allégée : les noms restent (%s)" % str(names))
	_check(m.name_of("b2") == "Léa", "trame allégée : nom mémorisé gardé")
	var fresh = Model.new()
	fresh.view({"session_state": "RUNNING", "bots": [{"id": "b9"}], "track": pts})
	_check(fresh.name_of("b9") == "b9", "bot jamais nommé : identifiant en repli")

	# E11-02 : omnium, cycliste éliminé à la 3e épreuve, puis course aux points, puis fin
	var om = Model.new()
	var el := {"event": "omnium", "sub": "elimination", "sub_index": 3, "subs": 4, "neutral": false, "t_s": 900.0,
		"lap": 10, "laps": 24, "laps_to_go": 14, "bell": false, "ranking": ["b1", "b2", "me", "b3", "b4", "b5"],
		"points": [40, 36, 34, 30, 20, 10], "eliminated": ["b5"], "finished": false, "last": "me", "alive": 5}
	om.moments(_st(el))
	el.merge({"eliminated": ["b5", "me"], "last": "b4", "alive": 4}, true)
	var mo: Array = om.moments(_st(el))
	_check(mo.size() == 1 and mo[0]["family"] == "attention" and not mo[0].has("done_k"),
		"omnium : éliminé de l'épreuve, moment passager sans consigne de fin (%s)" % str(mo))
	_check(mo.size() == 1 and mo[0]["title"] == "Éliminé · 5e sur 6" and mo[0]["sub"] == "L'omnium continue à l'épreuve suivante",
		"omnium : place dans l'élimination, pas au général (%s)" % (str(mo[0]) if mo.size() > 0 else ""))
	var pr := {"event": "omnium", "sub": "points", "sub_index": 4, "subs": 4, "neutral": false, "t_s": 1300.0,
		"lap": 2, "laps": 20, "laps_to_go": 19, "bell": false, "ranking": ["b1", "me", "b2", "b3", "b4", "b5"],
		"points": [40, 38, 36, 30, 20, 10], "eliminated": [], "finished": false, "next_sprint_lap": 10}
	_check(om.moments(_st(pr)).is_empty() and not om.consigne(_st(pr)).is_empty(),
		"omnium : course aux points suivante avec sa consigne")
	pr.merge({"finished": true}, true)
	var fin: Array = om.moments(_st(pr))
	_check(fin.size() == 1 and fin[0]["family"] == "resultat" and fin[0]["title"] == "ARRIVÉE · 2e sur 6",
		"omnium : résultat final annoncé (%s)" % str(fin))
	var solo := {"event": "elimination", "t_s": 200.0, "lap": 6, "laps": 24, "laps_to_go": 18, "bell": false,
		"ranking": ["b1", "b2", "me"], "points": null, "eliminated": [], "finished": false, "last": "me", "alive": 3}
	var se = Model.new()
	se.moments(_st(solo))
	solo.merge({"eliminated": ["me"], "alive": 2}, true)
	var so: Array = se.moments(_st(solo))
	_check(so.size() == 1 and so[0]["family"] == "resultat" and str(so[0].get("done_k", "")).begins_with("COURSE FINIE POUR TOI"),
		"élimination seule : course finie pour toi, inchangé")

	# E11-05 : peloton de 12, cycliste 10e, dernier 12e : leurs lignes restent dans les 8
	var big_bots: Array = []
	var ranking: Array = []
	for i in range(1, 12):
		big_bots.append({"id": "b%d" % i, "name": "Nom%d" % i})
	for i in range(1, 10):
		ranking.append("b%d" % i)
	ranking += ["me", "b10", "b11"]
	var mass := {"event": "elimination", "t_s": 100.0, "lap": 3, "laps": 40, "laps_to_go": 37, "bell": false,
		"ranking": ranking, "points": null, "eliminated": [], "finished": false, "last": "b11", "alive": 12}
	var mb = Model.new()
	var rows: Array = mb.view({"session_state": "RUNNING", "bots": big_bots, "track": mass})["list"]["rows"]
	var kinds: Array = []
	for r in rows:
		kinds.append("%s:%s" % [r["pos"], r["kind"]])
	_check(rows.size() == Model.MAX_LINES and rows[rows.size() - 2]["pos"] == "10." and rows[rows.size() - 2]["kind"] == "me"
		and rows.back()["pos"] == "12." and rows.back()["kind"] == "danger", "12 coureurs : Toi et le dernier gardés (%s)" % str(kinds))
	_check(rows[0]["pos"] == "1." and rows[5]["pos"] == "6.", "12 coureurs : la tête ensuite, dans l'ordre")
	var board: String = mb.board_text({"session_state": "RUNNING", "bots": big_bots, "track": mass})
	_check(board.split("\n").size() <= Model.BOARD_LINES and board.contains("10. TOI") and board.contains("12. NOM11"),
		"tableau de la salle : Toi et le dernier y sont (%s)" % board.replace("\n", " | "))
	_check(Model.window_rows([1, 2], 0).is_empty(), "fenêtre de 0 ligne : vide")
