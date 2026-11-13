extends SceneTree

## Tests sans écran de l'affichage du « Grand Prix des objets » (série GP, lot GP8) : objet `gp` de la trame
## `state` (contrat 1.7) traduit en case d'objet, place, bande de course, voies et avertissements ; lignes
## du bilan (`summary.gp`) ; pastilles des treize objets ; vue construite et remplie sans plantage.
## Cas du cahier GP8 : valeurs absentes, 12 coureurs. Lot GP4 : Furtif lu dans `fx` (avatar translucide).
## Lancement : godot --headless --path engine --script res://tests/unit/test_gp_hud.gd

const Model := preload("res://scripts/grandprix/gp_hud_model.gd")
const View := preload("res://scripts/grandprix/gp_view.gd")
const Items := preload("res://scripts/grandprix/gp_items.gd")
const SummaryViewModel := preload("res://scripts/summary_view_model.gd")
const BotsModel := preload("res://scripts/bots_view_model.gd")

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


# Scène 6 des maquettes : 3e sur 5, tour 2 / 3, trois musettes en réserve
const BOTS := [{"id": "bot1", "name": "Grimpeur", "s": 1540.0, "v": 10.0, "kind": "constant", "gap_s": 6.4, "item": "bell", "fx": []},
	{"id": "bot2", "name": "Rouleur", "s": 1520.0, "v": 10.0, "kind": "constant", "gap_s": 4.3, "item": null, "fx": []},
	{"id": "bot3", "name": "Sprinteur", "s": 1494.0, "v": 10.0, "kind": "constant", "gap_s": -0.6, "item": "bottle", "fx": []},
	{"id": "bot4", "name": "Diesel", "s": 1436.0, "v": 10.0, "kind": "constant", "gap_s": -6.4, "item": null, "fx": ["musette"]}]
const GP := {"place": 3, "of": 5, "gap_s": 2.1, "held": "musette_x3", "n": 3, "roll_s": 0.0, "lane": 1, "auto": false,
	"fx": [], "warn": null, "obj": [[17, "bottle", 1560.0, 1]], "boxes": [1950], "pick": true, "lap": [2, 3]}


func _state(gp: Dictionary, bots: Array = BOTS, s := 1500.0) -> Dictionary:
	return {"session_state": "RUNNING", "s": s, "v": 10.0, "bots": bots, "gp": gp}


func _run() -> void:
	var m = Model.new()
	_check(not m.view({"session_state": "RUNNING"}, 0.0)["visible"], "hors du mode : rien")
	_check(not m.view(null, 0.0)["visible"], "sans trame : rien")

	var v: Dictionary = m.view(_state(GP), 10.0)
	var it: Dictionary = v["item"]
	_check(v["visible"] and it["kind"] == "musette_x3" and it["n"] == 3 and it["key"] == "Z : Trois musettes",
		"case d'objet : trois musettes, badge ×3, invite Z")
	var pl: Dictionary = v["place"]
	_check(pl["place"] == "3e" and pl["of"] == "/ 5" and pl["lap"] == "tour 2 / 3", "place et tours")
	_check(pl["gap"] == "à 2,1 s de Rouleur", "écart avec le coureur de devant, nommé (%s)" % pl["gap"])
	var rows: Array = v["strip"]
	var names: Array = []
	for r in rows:
		names.append(r["name"])
	_check(names == ["Grimpeur", "Rouleur", "Toi", "Sprinteur", "Diesel"], "bande : ordre de la course (%s)" % str(names))
	_check(rows[0]["gap"] == "—" and rows[1]["gap"] == "+2,1 s" and rows[2]["gap"] == "+6,4 s" and rows[4]["gap"] == "+12,8 s",
		"bande : retard sur le premier (%s, %s, %s)" % [rows[1]["gap"], rows[2]["gap"], rows[4]["gap"]])
	_check(rows[2]["me"] and rows[2]["item"] == "musette_x3", "bande : Toi avec son objet")
	_check(rows[0]["item"] == "bell" and rows[3]["item"] == "bottle" and rows[1]["item"] == "", "bande : objet tenu par chaque bot")
	_check(rows[4]["hit"] and not rows[3]["hit"], "bande : Diesel touché par une musette")
	var ln: Dictionary = v["lanes"]
	_check(ln["lane"] == 1 and not ln["auto"] and ln["hint"] == "Bidon glissant en vue : A ou ← →", "voies : objet en vue (%s)" % ln["hint"])
	_check(v["warn"].is_empty(), "pas de menace : pas d'avertissement")

	# Roulette pendant le tirage : l'objet tourne, pas d'invite Z, rien dans la bande pour Toi
	var roll := GP.duplicate()
	roll["roll_s"] = 1.4
	var a: Dictionary = m.item_view(roll, 0.05)
	var b: Dictionary = m.item_view(roll, 0.05 + Model.ROLL_STEP_S)
	_check(a["rolling"] and a["kind"] != b["kind"] and a["key"] == "Tirage…" and a["n"] == 0, "roulette : un objet après l'autre")
	_check(m.view(_state(roll), 0.0)["strip"][2]["item"] == "", "roulette : objet de Toi pas encore connu")
	_check(m.item_view(roll, -3.0)["kind"] != "", "roulette : horloge négative sans plantage")

	# Case vide, charges d'un objet simple
	var empty := GP.duplicate()
	empty["held"] = null
	_check(m.item_view(empty, 0.0)["empty"], "sans objet : case vide")
	var single := GP.duplicate()
	single["held"] = "homing"
	single["n"] = 1
	_check(m.item_view(single, 0.0)["n"] == 0 and m.item_view(single, 0.0)["key"] == "Z : Musette guidée", "objet simple : pas de badge")
	var two := GP.duplicate()
	two["n"] = 2
	_check(m.item_view(two, 0.0)["n"] == 2, "trois musettes, une lancée : ×2")

	# Avertissements
	var warn := GP.duplicate()
	warn["warn"] = ["homing", 42.0]
	var w: Dictionary = m.view(_state(warn), 0.0)["warn"]
	_check(w["text"] == "Musette guidée derrière !" and w["arrow"] == "down" and w["outline"] and w["chevrons"] and w["color"] == Items.HOT,
		"musette guidée derrière : flèche vers le bas, contour et chevrons")
	warn["warn"] = ["storm", 0.0]
	w = m.view(_state(warn), 0.0)["warn"]
	_check(w["text"] == "Nuage d'orage sur toi !" and w["arrow"] == "" and not w["chevrons"] and w["color"] == Items.SLING,
		"orage sur le cycliste : contour violet, sans flèche")
	var storm := GP.duplicate()
	storm["obj"] = [[18, "storm", 1700.0, -1]]
	w = m.view(_state(storm), 0.0)["warn"]
	_check(w["text"] == "Orage vers le premier" and not w["outline"] and w["arrow"] == "up", "orage vers un autre : sans contour")

	# Voies : placement automatique, A garde la vue (pick faux)
	var auto := GP.duplicate()
	auto["auto"] = true
	auto["pick"] = false
	auto["lane"] = 2
	ln = m.view(_state(auto), 0.0)["lanes"]
	_check(ln["auto"] and ln["lane"] == 2 and ln["hint"] == "← → : voie", "voies : automatique, flèches seulement")
	var near := GP.duplicate()
	near["obj"] = []
	_check(m.view(_state(near), 0.0)["lanes"]["hint"] == "A : voie suivante · ← → : voie", "voies : A change de voie, rien en vue")

	# En tête et deuxième
	var lead := GP.duplicate()
	lead["place"] = 1
	_check(m.place_view(lead, [])["gap"] == "2,1 s d'avance", "en tête : avance sur le deuxième")
	lead["place"] = 2
	_check(m.place_view(lead, [])["gap"] == "à 2,1 s du premier", "deuxième : écart au premier")

	# Valeurs absentes : rien ne plante, rien d'inventé
	var bare = Model.new()
	var vb: Dictionary = bare.view({"s": 100.0, "gp": {}}, 0.0)
	_check(vb["visible"] and vb["item"]["empty"] and vb["place"].is_empty() and vb["warn"].is_empty() and vb["fx"].is_empty(),
		"trame gp vide : case vide, pas de place ni d'avertissement")
	_check(vb["strip"].size() == 1 and vb["strip"][0]["name"] == "Toi" and vb["lanes"]["lane"] == 1, "trame gp vide : Toi seul, voie du centre")
	var odd := {"place": "x", "warn": [], "obj": [[1], "bad"], "fx": [["inconnu", 3.0], "bad"], "lap": [], "held": "boomerang"}
	var vo: Dictionary = bare.view({"gp": odd, "bots": "bad"}, 0.0)
	_check(vo["visible"] and vo["item"]["empty"] and vo["fx"].is_empty() and vo["warn"].is_empty(), "valeurs mal formées : ignorées")

	# Bots loin (peloton) : nom, objet et effets gardés quand ils ne sont pas dans la trame ; écart estimé
	var far = Model.new()
	far.view(_state(GP), 0.0)
	var light := [{"id": "bot1", "s": 1540.0, "v": 10.0, "kind": "constant"}]
	var rl: Array = far.view(_state(GP, light), 0.0)["strip"]
	_check(rl[0]["name"] == "Grimpeur" and rl[0]["item"] == "bell", "bot loin : nom et objet gardés")
	_check(rl[1]["me"] and rl[1]["gap"] == "+4,0 s", "bot loin sans gap_s : écart estimé par la distance (%s)" % rl[1]["gap"])

	# 12 coureurs : 11 bots et le cycliste, 12 lignes au plus
	var many: Array = []
	for i in range(11):
		many.append({"id": "b%d" % i, "name": "Bot %d" % i, "s": 2000.0 - i * 40.0, "v": 10.0, "kind": "constant",
			"gap_s": (2000.0 - i * 40.0 - 1700.0) / 10.0, "item": Items.IDS[i], "fx": []})
	var g12 := GP.duplicate()
	g12["place"] = 9
	g12["of"] = 12
	var r12: Array = Model.new().view(_state(g12, many, 1700.0), 0.0)["strip"]
	_check(r12.size() == 12 and r12[8]["me"] and r12[11]["name"] == "Bot 10", "12 coureurs : Toi 9e, douze lignes")
	_check(r12[11]["gap"] == "+40,0 s", "12 coureurs : retard du dernier (%s)" % r12[11]["gap"])

	# Bilan (maquette 7)
	var sm := {"place": 2, "of": 5, "launched": {"gel": 2, "musette_x3": 1, "bottle": 1}, "received": {"homing": 1, "bottle": 1},
		"dodged": 4, "gained_s": {"gel": 7.6, "musette_x3": 5.2, "bottle": 2.1}, "lost_s": {"homing": 3.9, "bottle": 3.7},
		"distance_km": 15.2}
	var lines: Array = Model.summary_lines(sm)
	_check(lines[0]["value"] == "2e sur 5" and lines[1]["value"] == "4 lancés · 2 reçus · 4 esquivés", "bilan : place et objets")
	_check(lines[2]["label"] == "Coup de fouet" and lines[2]["value"] == "+7,6 s · lancé ×2", "bilan : objet le plus fort en tête")
	var found_loss := false
	var total := ""
	for l in lines:
		found_loss = found_loss or (l["label"] == "Musette guidée" and l["value"] == "−3,9 s · reçu ×1")
		if l["label"] == "Bilan des objets":
			total = l["value"]
	_check(found_loss, "bilan : temps perdu par objet reçu")
	_check(total == "+7,3 s", "bilan : bilan des objets (%s)" % total)
	_check(Model.summary_lines({})[0]["value"] == "course non finie" and Model.summary_lines({})[1]["value"] == "0 lancés · 0 reçus · 0 esquivés",
		"bilan : valeurs absentes")
	var many_items := {"place": 1, "of": 12, "launched": {}, "received": {}, "dodged": 0, "gained_s": {}, "lost_s": {}}
	for k in Items.IDS:
		many_items["launched"][k] = 1
		many_items["gained_s"][k] = 1.0
	_check(Model.summary_lines(many_items).size() == 2 + Model.MAX_ITEM_LINES + 3, "bilan : %d lignes d'objets au plus" % Model.MAX_ITEM_LINES)
	var svm = SummaryViewModel.new()
	var has_gp := false
	for l in svm.lines({"duration_s": 900.0, "distance_m": 15200.0, "gp": sm}):
		has_gp = has_gp or str(l.get("label", "")) == "Grand Prix des objets"
	_check(has_gp, "bilan de séance : lignes du Grand Prix")

	# Pastilles : treize objets, une famille et une forme chacun
	var shapes := {}
	for k in Items.IDS:
		shapes[Items.shape(k)] = true
		_check(Items.family(k) != "" and Items.label(k) != k, "objet %s : famille et nom" % k)
	_check(shapes.size() == 5, "cinq formes de pastille")
	_check(Items.shape_points("shield", Vector2.ZERO, 10.0).size() == 8 and Items.shape_points("circle", Vector2.ZERO, 10.0).size() == 24,
		"contours des pastilles")

	# Furtif (lot GP4) : avatar translucide, cycliste (`gp.fx`, [[objet, reste]]) ou bot (`bots[].fx`, [objet])
	_check(Items.unseen([["stealth", 9.5]]) and Items.unseen(["gel", "stealth"]), "Furtif : vu dans les deux formes de fx")
	_check(not Items.unseen([["team_car", 5.0]]) and not Items.unseen([]) and not Items.unseen(null), "Furtif : absent")
	var bvm = BotsModel.new()
	bvm.push([{"id": "bot1", "kind": "profile", "s": 10.0, "fx": ["stealth"]},
		{"id": "bot2", "kind": "profile", "s": 5.0, "fx": []}], 0)
	var unseen := {}
	for bv in bvm.view(0.0, 0.0, 0):
		unseen[bv["id"]] = bv.get("unseen", false)
	_check(unseen.get("bot1", false) and not unseen.get("bot2", true), "Furtif : bot translucide seulement sous l'objet")

	# Vue : construite, remplie et dessinée sans erreur
	var view = View.new()
	get_root().add_child(view)
	var vm = Model.new()
	view.update_view(vm.view(_state(warn), 0.0))
	await process_frame
	var info: Dictionary = view.test_info()
	_check(info["visible"] and info["item"] == "musette_x3" and info["key"] == "Z : Trois musettes", "vue : case d'objet")
	_check(info["place"] == "3e / 5" and info["strip"].size() == 5 and info["strip"][2] == "Toi", "vue : place et bande")
	_check(info["warn"] == "Nuage d'orage sur toi !" and info["outline"], "vue : avertissement et contour")
	view.update_view(vm.view(_state(g12, many, 1700.0), 0.0))
	await process_frame
	_check(view.test_info()["strip"].size() == 12, "vue : 12 lignes")
	_check(view.test_info()["strip_bottom"] < 720.0, "vue : la bande tient dans l'écran de base (%.0f)" % view.test_info()["strip_bottom"])
	view.update_view({"visible": false})
	_check(not view.test_info()["visible"], "vue cachée hors du mode")
	view.queue_free()

	print("test_gp_hud : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
