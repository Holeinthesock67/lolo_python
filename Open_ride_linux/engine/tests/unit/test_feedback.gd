extends SceneTree

## Tests sans écran des retours et consignes communs (lot RT1) : feedback_model.gd (familles de moments, bandeau,
## résultat, consigne de fin unique, départ, fin d'un entraînement) et feedback_view.gd (textes affichés).
## Lancement : godot --headless --path engine --script res://tests/unit/test_feedback.gd

const Model := preload("res://scripts/feedback_model.gd")
const View := preload("res://scripts/feedback_view.gd")
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


func _st(session := "RUNNING", extra := {}) -> Dictionary:
	var s := {"session_state": session, "s": 100.0}
	s.merge(extra, true)
	return s


func _run() -> void:
	var m = Model.new()
	# Hors séance : rien
	_check(not m.view(_st("IDLE"), 0.0)["visible"], "hors séance : rien")
	_check(m.view(_st(), 0.0)["consigne"].is_empty() and m.view(_st(), 0.0)["toast"].is_empty(), "séance libre sans consigne")

	# Chaque famille : mot de tête, couleur propre, son de la famille ou variante du mode
	var tags := {}
	var colors := {}
	for fam in ["depart", "bien", "attention", "refus"]:
		m.push(fam, "t", "s", 0.0)
		var t: Dictionary = m.view(_st(), 0.5)["toast"]
		tags[str(t["tag"])] = true
		colors[str(t["color"])] = true
	_check(tags.size() == 4 and tags.has("+ BIEN") and tags.has("! ATTENTION") and tags.has("× REFUSÉ") and tags.has("▶ DÉPART"),
		"un mot écrit par famille (%s)" % str(tags.keys()))
	_check(colors.size() == 4, "une couleur par famille")
	_check(m.push("bien", "Marco est éliminé", "", 10.0) == "fb_bien" and m.push("bien", "x", "", 10.0, "jingle_elim") == "jingle_elim",
		"son de la famille, ou variante du mode")
	_check(m.push("inconnue", "x", "", 10.0) == "" and m.push("resultat", "x", "", 10.0) == "", "famille inconnue ou résultat par push : rien")
	for j in ["fb_bien", "fb_attention", "fb_refus"]:
		_check(EventSounds.JINGLES.has(j), "%s déclaré" % j)

	# Bandeau : TOAST_S secondes
	var m2 = Model.new()
	m2.push("attention", "Tu es dernier en course", "Ligne dans 180 m", 100.0)
	_check(m2.view(_st(), 100.0 + Model.TOAST_S - 0.1)["toast"]["title"] == "Tu es dernier en course", "bandeau pendant TOAST_S")
	_check(m2.view(_st(), 100.0 + Model.TOAST_S + 0.1)["toast"].is_empty(), "bandeau effacé après TOAST_S")

	# Consigne du mode, puis résultat et consigne de fin unique (choix du 21/11 : on continue à rouler)
	var m3 = Model.new()
	var mode_c := {"k": "À FAIRE", "action": "Passe Marco avant la ligne", "detail": "Objectif : x", "chips": ["pédale"]}
	var v: Dictionary = m3.view(_st(), 0.0, mode_c)
	_check(v["consigne"]["action"] == "Passe Marco avant la ligne" and v["consigne"]["chips"] == ["pédale"], "consigne du mode")
	var snd: Array = m3.push_all([{"family": "bien", "title": "Hugo est éliminé", "sub": "", "sound": "jingle_elim"},
		{"family": "resultat", "tone": "win", "title": "VICTOIRE !", "sub": "1er sur 8", "done_k": "COURSE FINIE · 1er sur 8"}], 50.0)
	_check(snd == ["jingle_elim", "jingle_winner"], "sons dans l'ordre, une fois (%s)" % str(snd))
	v = m3.view(_st(), 51.0, mode_c)
	_check(v["result"]["title"] == "VICTOIRE !" and v["result"]["tag"] == "★ RÉSULTAT" and v["result"]["color"] == Model.GOLD_BG,
		"résultat au milieu, or pour la victoire")
	_check(v["toast"].is_empty(), "le résultat efface le bandeau en cours")
	_check(v["consigne"]["k"] == "COURSE FINIE · 1er sur 8" and v["consigne"]["action"] == "Roule au calme autant que tu veux"
		and v["consigne"]["chips"] == ["Y puis A maintenu = bilan"], "consigne de fin à la place de celle du mode (%s)" % str(v["consigne"]))
	v = m3.view(_st(), 50.0 + Model.RESULT_S + 30.0, mode_c)
	_check(v["result"].is_empty() and v["consigne"]["k"] == "COURSE FINIE · 1er sur 8", "après le résultat : la consigne de fin reste")
	_check(m3.is_done(), "issue connue")
	m3.on_state(_st("RUNNING"), 200.0)
	m3.on_state(_st("FINISHED"), 201.0)
	_check(not m3.is_done() and not m3.view(_st("FINISHED"), 202.0)["visible"], "séance finie : tout est oublié")
	var m4 = Model.new()
	m4.push_all([{"family": "resultat", "tone": "out", "title": "ÉLIMINÉ · 5e sur 8", "sub": "", "done_k": "COURSE FINIE POUR TOI",
		"done_action": "Roule au calme : la course continue sans toi"}], 0.0)
	v = m4.view(_st(), 1.0)
	_check(v["result"]["color"] == Model.OUT_BG and v["consigne"]["action"] == "Roule au calme : la course continue sans toi",
		"éliminé : rouge, la course continue sans lui")
	_check(Model.race_result(1, 8) == ["VICTOIRE !", "win"] and Model.race_result(3, 8) == ["ARRIVÉE · 3e sur 8", "place"], "titres de résultat")

	# Départ : bandeau ▶ DÉPART avec l'objectif du mode, sans son propre (pistolet ou jingle_start déjà là)
	var m5 = Model.new()
	m5.on_state(_st("READY"), 0.0, "être le dernier en course")
	_check(m5.on_state(_st("RUNNING"), 1.0, "être le dernier en course").is_empty(), "départ : pas de second son")
	var t5: Dictionary = m5.view(_st(), 1.5)["toast"]
	_check(t5["tag"] == "▶ DÉPART" and t5["sub"] == "être le dernier en course", "départ : objectif du mode")
	var m6 = Model.new()
	m6.on_state(_st("READY"), 0.0, "")
	m6.on_state(_st("RUNNING"), 1.0, "")
	_check(m6.view(_st(), 1.5)["toast"].is_empty(), "séance libre : pas de bandeau de départ")

	# Fin d'un entraînement ERG : RÉSULTAT et consigne de fin, une fois
	var m7 = Model.new()
	var done := _st("RUNNING", {"workout_done": {"workout_name": "Sweet spot"}})
	_check(m7.on_state(done, 10.0) == ["jingle_finish"] and m7.on_state(done, 11.0).is_empty(), "entraînement fini : un son, une fois")
	v = m7.view(done, 11.0)
	_check(v["result"]["title"] == "ENTRAÎNEMENT TERMINÉ" and v["result"]["sub"] == "« Sweet spot »"
		and v["consigne"]["k"] == "ENTRAÎNEMENT FINI" and v["consigne"]["chips"] == ["Y puis A maintenu = bilan"],
		"entraînement fini : résultat et consigne (%s)" % str(v))

	# Vue : textes affichés
	var view = View.new()
	get_root().add_child(view)
	var m9 = Model.new()
	m9.push_all([{"family": "resultat", "tone": "win", "title": "VICTOIRE !", "sub": "1er sur 8", "done_k": "COURSE FINIE · 1er sur 8"}], 50.0)
	view.update_view(m9.view(_st(), 51.0, mode_c))
	var info: Dictionary = view.test_info()
	_check(info["visible"] and info["result"] == "VICTOIRE !" and info["consigne_k"] == "COURSE FINIE · 1er sur 8"
		and info["chips"] == ["Y puis A maintenu = bilan"] and info["toast"] == "", "vue : résultat et consigne de fin (%s)" % str(info))
	var m8 = Model.new()
	m8.push("bien", "Hugo est éliminé", "Plus que 5 en course", 0.0)
	view.update_view(m8.view(_st(), 0.5, mode_c))
	info = view.test_info()
	_check(info["toast"] == "+ BIEN Hugo est éliminé" and info["consigne"] == "Passe Marco avant la ligne" and info["result"] == "",
		"vue : bandeau au-dessus de la consigne (%s)" % str(info))
	view.update_view({"visible": false})
	_check(not view.test_info()["visible"], "vue cachée hors séance")
	view.queue_free()

	print("test_feedback : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
