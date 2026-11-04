extends SceneTree

## Tests sans écran de l'affichage du mode « Dernier survivant » (série DS, lots DS5 et DS6) : objet `survivor`
## de la trame `state` et messages `elimination` (contrat 1.5) traduits en bloc, liste des coureurs, bandeaux,
## jingles, portiques d'élimination et lignes du bilan ; bots éliminés qui se rangent ; vue sans plantage.
## Cas du cahier DS6 : joueur dernier, joueur éliminé, vainqueur, 11 adversaires.
## Lancement : godot --headless --path engine --script res://tests/unit/test_survivor_hud.gd

const Model := preload("res://scripts/survivor/survivor_hud_model.gd")
const View := preload("res://scripts/survivor/survivor_view.gd")
const SummaryViewModel := preload("res://scripts/summary_view_model.gd")
const BotsViewModel := preload("res://scripts/bots_view_model.gd")
const EventSounds := preload("res://scripts/event_sounds_model.gd")

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


const BOTS := [{"id": "bot1", "name": "Grimpeur", "s": 5400.0, "v": 10.0, "kind": "constant", "gap_s": 6.0},
	{"id": "bot2", "name": "Sprinteur", "s": 5370.0, "v": 10.0, "kind": "constant", "gap_s": 2.3},
	{"id": "bot3", "name": "Rouleur", "s": 5360.0, "v": 10.0, "kind": "constant", "gap_s": 1.2},
	{"id": "bot4", "name": "Diesel", "s": 5100.0, "v": 4.0, "kind": "constant", "gap_s": -25.0, "out": 1}]


func _state(sv: Dictionary, s := 5350.0, bots: Array = BOTS) -> Dictionary:
	return {"session_state": "RUNNING", "s": s, "bots": bots, "survivor": sv}


func _run() -> void:
	var m = Model.new()
	_check(not m.view({"session_state": "RUNNING"}, 0.0)["visible"], "hors du mode : rien")
	_check(not m.view(null, 0.0)["visible"], "sans trame : rien")

	# Joueur dernier à l'approche de l'arche 2 (maquette « Dernier »)
	var sv := {"arch": 2, "arches": 4, "d_m": 650.0, "alive": ["bot1", "bot2", "bot3", "me"], "last": "me",
		"gap_last_s": 1.2, "out": [["bot4", 1]], "me_out": null, "winner": null}
	var v: Dictionary = m.view(_state(sv), 10.0)
	var b: Dictionary = v["block"]
	_check(v["visible"] and b["arch"] == "Arche 2 / 4" and b["dist"] == "dans 650 m", "bloc : arche et distance")
	_check(b["rank"] == "4e sur 4 en course", "bloc : rang parmi les coureurs en course")
	_check(b["danger"] and b["danger_text"] == "DERNIER" and b["last"] == "Rouleur à 1,2 s",
		"joueur dernier : cadre rouge, « DERNIER » et écart avec celui qui le précède")
	var rows: Array = v["list"]
	_check(rows.size() == 5 and rows[3]["name"] == "Toi" and rows[3]["me"] and rows[3]["detail"] == "dernier",
		"liste : Toi dernier")
	_check(rows[0]["detail"] == "+6,0 s" and not rows[0]["last"], "liste : écart au cycliste en secondes")
	_check(rows[4]["name"] == "Diesel" and rows[4]["out"] and rows[4]["detail"] == "arche 1", "liste : éliminé barré avec son arche")
	sv["d_m"] = 320.0
	b = m.view(_state(sv, 5680.0), 11.0)["block"]
	_check(absf(float(b["bar"]) - (1.0 - 320.0 / 650.0)) < 0.01, "barre d'approche depuis le début de l'arche")
	_check(is_equal_approx(m.arch_s(2), 6000.0), "position de l'arche sur la route : s + d_m")
	var draw: Array = m.arches_to_draw(_state(sv, 5680.0))
	_check(draw.size() == 1 and draw[0]["arch"] == 2 and str(draw[0]["lines"][0]) == "Élimination"
		and str(draw[0]["lines"][1]).begins_with("Arche 2 sur 4"), "portique : la prochaine arche seulement au début")

	# Joueur 2e, pas dernier
	var sv2 := sv.duplicate(true)
	sv2["alive"] = ["bot1", "me", "bot2", "bot3"]
	sv2["last"] = "bot3"
	sv2["gap_last_s"] = 2.4
	b = m.view(_state(sv2, 5680.0), 12.0)["block"]
	_check(not b["danger"] and b["danger_text"] == "" and b["last"] == "Dernier : Rouleur à 2,4 s" and b["rank"] == "2e sur 4 en course",
		"joueur 2e : écart avec le dernier")
	var rows2: Array = m.view(_state(sv2, 5680.0), 12.0)["list"]
	_check(rows2[3]["last"] and rows2[3]["name"] == "Rouleur", "dernier marqué")

	# Élimination d'un bot : bandeau du bas 3 s, doublons ignorés, jingle
	var msg := {"type": "elimination", "v": 1, "arch": 2, "rider": "bot2", "name": "Sprinteur", "place": 4, "gap_s": 0.6, "alive": 3}
	_check(m.on_elimination(msg, 20.0) == ["jingle_elim"], "élimination : jingle")
	_check(m.on_elimination(msg, 21.0).is_empty() and m.on_elimination(msg, 22.0).is_empty(), "doublons (3 envois) ignorés")
	var sv3 := sv2.duplicate(true)
	sv3["arch"] = 3
	sv3["alive"] = ["bot1", "me", "bot3"]
	sv3["out"] = [["bot4", 1], ["bot2", 2]]
	sv3["d_m"] = 1990.0
	v = m.view(_state(sv3, 6010.0), 21.0)
	_check(v["bottom"].get("title", "") == "Éliminé : Sprinteur" and v["bottom"]["sub"] == "arche 2 · à 0,6 s", "bandeau du bas")
	_check(m.view(_state(sv3, 6010.0), 23.5)["bottom"].is_empty(), "bandeau du bas effacé après 3 s")
	var rows3: Array = v["list"]
	_check(rows3[3]["name"] == "Sprinteur" and rows3[4]["name"] == "Diesel", "éliminés du plus récent au plus ancien")
	draw = m.arches_to_draw(_state(sv3, 6010.0))
	_check(draw.size() == 2 and draw[0]["arch"] == 2 and draw[1]["arch"] == 3, "arche passée et prochaine : deux au plus")

	# Joueur éliminé (maquette « Éliminé · 3e sur 5 »)
	var me_msg := {"type": "elimination", "v": 1, "arch": 3, "rider": "me", "name": "", "place": 3, "gap_s": 1.9, "alive": 2}
	_check(m.on_elimination(me_msg, 30.0) == ["jingle_elim"], "joueur éliminé : jingle")
	var sv4 := {"arch": 4, "arches": 4, "d_m": null, "alive": ["bot1", "bot3"], "last": "bot3", "gap_last_s": null,
		"out": [["bot4", 1], ["bot2", 2]], "me_out": 3, "winner": null}
	v = m.view(_state(sv4, 7000.0), 31.0)
	_check(v["block"].is_empty(), "joueur éliminé : plus de bloc")
	_check(v["center"].get("title", "") == "ÉLIMINÉ · 3e sur 5" and str(v["center"]["sub"]).begins_with("Tu continues à rouler"),
		"bandeau rouge du milieu (continuer à rouler)")
	_check(v["list"][2]["name"] == "Toi" and v["list"][2]["out"] and v["list"][2]["detail"] == "arche 3", "Toi barré dans la liste")
	var m_end = Model.new()
	m_end.after_out = "end"
	m_end.view(_state(sv4.merged({"me_out": null, "alive": ["bot1", "bot3", "me"]}, true), 7000.0), 0.0)
	m_end.on_elimination(me_msg, 1.0)
	_check(m_end.view(_state(sv4, 7000.0), 2.0)["center"]["sub"] == "Bilan de la course", "réglage « terminer la séance »")

	# Vainqueur (maquette « Dernier survivant ! »)
	var w = Model.new()
	w.view(_state({"arch": 4, "arches": 4, "d_m": 50.0, "alive": ["me", "bot1"], "last": "bot1", "gap_last_s": 2.2,
		"out": [["bot4", 1], ["bot2", 2], ["bot3", 3]], "me_out": null, "winner": null}, 7950.0), 0.0)
	var jingles: Array = w.on_elimination({"type": "elimination", "v": 1, "arch": 4, "rider": "bot1", "name": "Grimpeur",
		"place": 2, "gap_s": 2.2, "alive": 1}, 1.0)
	_check(jingles == ["jingle_elim", "jingle_winner"], "victoire : jingles d'élimination et de victoire")
	v = w.view(_state({"arch": 4, "arches": 4, "d_m": null, "alive": ["me"], "last": "me", "gap_last_s": null,
		"out": [["bot4", 1], ["bot2", 2], ["bot3", 3], ["bot1", 4]], "me_out": null, "winner": "me"}, 8010.0), 2.0)
	_check(v["center"].get("title", "") == "DERNIER SURVIVANT !" and v["center"]["sub"] == "1er sur 5 · Grimpeur éliminé à 2,2 s",
		"bandeau vert du vainqueur")
	_check(v["list"][0]["name"] == "Toi" and v["list"][0]["detail"] == "vainqueur" and not v["list"][0]["last"], "Toi vainqueur")
	_check(v["bottom"].is_empty() and v["block"].is_empty(), "pas de bandeau du bas ni de bloc après la victoire")

	# 11 adversaires (peloton DS8) : 12 lignes au plus
	var many := Model.new()
	var alive: Array = ["me"]
	var bots: Array = []
	for i in range(11):
		alive.append("bot%d" % (i + 1))
		bots.append({"id": "bot%d" % (i + 1), "name": "Bot %d" % (i + 1), "s": 100.0, "v": 10.0, "kind": "constant"})
	v = many.view(_state({"arch": 1, "arches": 11, "d_m": 2000.0, "alive": alive, "last": "bot11", "gap_last_s": 0.5,
		"out": [], "me_out": null, "winner": null}, 0.0, bots), 0.0)
	_check(v["list"].size() == 12 and v["block"]["rank"] == "1er sur 12 en course" and v["block"]["arch"] == "Arche 1 / 11",
		"11 adversaires : 12 lignes, rang sur 12")
	_check(v["block"]["dist"] == "dans 2,00 km", "distance au-delà d'un kilomètre")
	many.reset()
	_check(many.names.is_empty() and many.arches_to_draw(_state({"arch": 1, "arches": 11})).is_empty(), "reset : course suivante vierge")

	# Bilan
	var sum := {"place": 2, "of": 5, "arches": 4, "spacing_km": 2.0, "winner": "bot1", "winner_name": "Grimpeur",
		"eliminated": [[1, "bot4", "Diesel", 3.4], [2, "bot2", "Sprinteur", 0.6], [3, "bot3", "Rouleur", 1.9], [4, "me", "me", 2.2]]}
	var lines: Array = Model.summary_lines(sum)
	_check(lines[0] == {"label": "Dernier survivant", "value": "2e sur 5", "unit": ""}, "bilan : place")
	_check(lines[1]["label"] == "Vainqueur" and lines[1]["value"] == "Grimpeur", "bilan : vainqueur nommé")
	_check(lines[2]["label"] == "Arche 1 (2,0 km)" and lines[2]["value"] == "Diesel, à 3,4 s", "bilan : arche 1")
	_check(lines[5]["value"] == "Toi, à 2,2 s", "bilan : arche du joueur")
	_check(lines[-1]["label"] == "Records" and lines[-1]["value"] == "aucun dans ce mode", "bilan : pas de records")
	var all: Array = SummaryViewModel.new().lines({"duration_s": 1008.0, "distance_m": 8900.0, "survivor": sum})
	_check(all.any(func(l): return l["label"] == "Dernier survivant"), "bilan général : lignes du mode")
	var unfinished: Array = Model.summary_lines({"place": null, "of": 5, "arches": 4, "spacing_km": 2, "winner": null, "eliminated": []})
	_check(unfinished[0]["value"] == "course non finie" and unfinished.size() == 2, "séance arrêtée avant la fin")

	# Jingles synthétisés
	_check(EventSounds.JINGLES.has("jingle_elim") and EventSounds.JINGLES.has("jingle_winner"), "jingles déclarés")
	_check(str(EventSounds.JINGLES["jingle_elim"]) != str(EventSounds.JINGLES["jingle_finish"]), "élimination différente de l'arrivée")

	# Bot éliminé : glisse vers le bas-côté (lot DS5)
	var bm = BotsViewModel.new()
	bm.push([{"id": "bot2", "name": "Sprinteur", "s": 100.0, "v": 8.0, "kind": "constant", "lane_m": 1.2}], 0)
	var first: Array = bm.view(90.0, 8.0, 0)
	_check(is_equal_approx(float(first[0]["lateral"]), 1.2), "en course : place du core")
	bm.push([{"id": "bot2", "name": "Sprinteur", "s": 101.0, "v": 4.0, "kind": "constant", "lane_m": 1.9, "out": 2}], 250000)
	_check(is_equal_approx(float(bm.view(90.0, 8.0, 250000)[0]["lateral"]), 1.9), "éliminé avec lane_m : place du core (il glisse côté core)")
	bm.push([{"id": "bot2", "name": "Sprinteur", "s": 101.0, "v": 4.0, "kind": "constant", "out": 2}], 500000)
	var lat0 := 1.9
	var lat := lat0
	var kept_out := true
	for i in range(1, 6):
		var vv: Array = bm.view(90.0, 8.0, 500000 + i * 500000)
		lat = float(vv[0]["lateral"])
		kept_out = kept_out and vv[0]["out"] == 2
	_check(kept_out, "champ out gardé dans la vue")
	_check(lat > lat0 + 0.5 and lat <= BotsViewModel.OUT_LATERAL_M + 0.001, "éliminé sans lane_m : glisse vers le bas-côté (%.2f m)" % lat)
	for i in range(6, 30):
		lat = float(bm.view(90.0, 8.0, 500000 + i * 500000)[0]["lateral"])
	_check(is_equal_approx(lat, BotsViewModel.OUT_LATERAL_M), "puis reste sur le bas-côté")

	# Vue : construite et remplie sans erreur
	var view = View.new()
	get_root().add_child(view)
	var vm = Model.new()
	vm.view(_state(sv), 0.0)
	view.update_view(vm.view(_state(sv), 0.0))
	var info: Dictionary = view.test_info()
	_check(info["visible"] and info["block"] == "Arche 2 / 4" and info["danger"] == "DERNIER", "vue : bloc en danger")
	_check(info["list"].size() == 5 and str(info["list"][3]).contains("Toi"), "vue : liste des coureurs")
	vm.on_elimination(msg, 0.0)
	view.update_view(vm.view(_state(sv3), 0.5))
	_check(view.test_info()["bottom"] == "Éliminé : Sprinteur", "vue : bandeau du bas")
	view.update_view({"visible": false})
	_check(not view.test_info()["visible"], "vue cachée hors du mode")
	view.queue_free()

	# Coureur devant et puissance pour le rejoindre (essai du 4 novembre)
	var a = Model.new()
	a.remember_names([{"id": "bot1", "name": "Grimpeur"}])
	a.ftp_w = 250.0
	_check(a.ahead_lines({"id": "bot1", "gap_s": 4.24, "catch_w": 245}, 195.0) == ["Devant : Grimpeur à 4,2 s", "245 W (+50) pour le rejoindre"],
		"devant : écart et puissance (%s)" % str(a.ahead_lines({"id": "bot1", "gap_s": 4.24, "catch_w": 245}, 195.0)))
	_check(a.ahead_lines({"id": "bot1", "gap_s": 30.0, "catch_w": 420}, 195.0)[1] == "hors de portée", "au-delà de 1,5 × FTP : hors de portée")
	_check(a.ahead_lines({"id": "bot1", "gap_s": 2.0, "catch_w": null}, 195.0) == ["Devant : Grimpeur à 2,0 s", ""], "arche déjà passée par le bot : pas de puissance")
	_check(a.ahead_lines(null, 195.0) == ["", ""], "en tête : rien")

	print("test_survivor_hud : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
