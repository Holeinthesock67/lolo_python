extends SceneTree

## Tests sans écran du Cyber-Rogue sur les trames que le vrai core envoie (revue de code vague 3, lot EC3) : les
## autres tests du mode fabriquaient des trames que le core n'envoie jamais (écart au Firewall de 120 m dans toutes
## les phases, `route_length_m` renseigné, `s_room` non nul en couloir, ennemi encore là dans la trame de fin de
## salle). Trames : `tests/data/rogue_trames_core.json`, écrites par `python -m openride_core.tools.rogue_trames`
## (vraie run du core, vérifiée par `core/tests/test_rogue_trames.py`).
## Constats couverts : E10-01 (offre redemandée), E10-02 (« N m restants »), E10-03 (son du bilan), E10-04 (son
## hors salle), E10-05 (couloir et récupération sans ruban ni Firewall), E10-06 (récupération sans contact),
## E10-07 (couloir caché en pause), E10-09 (fin de l'ennemi vue).
## Lancement : godot --headless --path engine --script res://tests/unit/test_rogue_trames_core.gd

const Host := preload("res://scripts/rogue/rogue_host.gd")
const HudModel := preload("res://scripts/rogue/rogue_hud_model.gd")
const GuideModel := preload("res://scripts/rogue/rogue_guide_model.gd")
const SoundModel := preload("res://scripts/rogue/rogue_sound_model.gd")
const EnemyModel := preload("res://scripts/rogue/enemy_model.gd")
const DATA := "res://tests/data/rogue_trames_core.json"

var _failures := 0
var _checked := 0
var _data: Dictionary = {}


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _init() -> void:
	call_deferred("_run")


## Trame `name` du fichier (copie : les modèles ne la modifient pas, mais un test peut la changer).
func _f(name: String) -> Dictionary:
	return (_data["frames"][name] as Dictionary).duplicate(true)


func _room_msg(rid: int) -> Dictionary:
	for m in _data["room"]:
		if int(m["room_id"]) == rid:
			return m
	return {}


func _run() -> void:
	var parsed = JSON.parse_string(FileAccess.get_file_as_string(DATA))
	_check(parsed is Dictionary and parsed.has("frames"), "trames réelles du core lues (%s)" % DATA)
	if not (parsed is Dictionary):
		quit(1)
		return
	_data = parsed
	_guide()
	_hud_recovery()
	_sound()
	_enemy()
	await _scene()
	print("test_rogue_trames_core : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)


## E10-02 : la longueur de la salle vient du message `room`, le core envoie `route_length_m` nul.
func _guide() -> void:
	var room := _f("room")
	_check(room["route_length_m"] == null, "vraie trame de salle : route_length_m nul")
	var g = GuideModel.new()
	var r: Dictionary = room["rogue"]
	var o: Dictionary = g.compute(room, r, 100.0, [])
	_check(o["title_right"] == "", "salle inconnue du guide : pas de distance inventée")
	var msg := _room_msg(int(r["room_id"]))
	g.set_room(int(r["room_id"]), msg["markers"], float(msg["length_m"]))
	o = g.compute(room, r, 100.0, [])
	var left := int(maxf(float(msg["length_m"]) - float(r["s_room"]), 0.0))
	_check(o["title_right"] == "%d m restants" % left, "« %d m restants » d'après la salle reçue (%s)" % [left, o["title_right"]])
	# Phase 3 du boss, 8 m avant la fin, boss encore debout : l'avertissement de fin s'affiche.
	var boss := _f("boss_end_prev")
	var br: Dictionary = boss["rogue"]
	var bmsg := _room_msg(int(br["room_id"]))
	g.set_room(int(br["room_id"]), bmsg["markers"], float(bmsg["length_m"]))
	var warn := GuideModel.room_end_text(boss, br, g.room_length(boss, br))
	_check(warn.begins_with("Fin du boss dans "), "fin du boss annoncée sur la vraie trame (%s)" % warn)
	o = g.compute(boss, br, 100.0, [])
	_check(o["title_right"].ends_with("m restants"), "boss : distance restante affichée")
	# Salle d'une autre trame que celle affichée : pas la longueur d'une autre salle.
	_check(g.room_length(room, r) == 0.0, "longueur gardée pour la seule salle affichée")


## E10-06 : récupération après un contact du Firewall, écart figé à 0 : ni contact, ni bords rouges.
func _hud_recovery() -> void:
	var m = HudModel.new()
	m.set_ftp(250.0)
	m.update(_f("room"), 1.0)
	# Trames de récupération posées dans la trame de séance d'une salle : numéros de trame à la suite.
	var rs := _f("recovery_start")
	rs["seq"] = int(rs["seq"]) + 1
	m.update(rs, 2.0)
	_check(bool(m.values()["hurt"]), "défaite : le bouclier tombe, un coup est signalé")
	var rc := _f("recovery")
	rc["seq"] = int(rc["seq"]) + 6
	m.update(rc, 3.0)
	var v: Dictionary = m.values()
	_check(not bool(v["hurt"]), "récupération : pas de bords rouges en continu")
	_check(not bool(v["has_firewall"]) and not bool(v["firewall_danger"]), "récupération : Firewall ni affiché ni en rouge")
	var fw: Dictionary = v["guide"]["fw"]
	_check(fw.get("text", "") != "TE TOUCHE !" and fw.get("title", "") == "Firewall arrêté" and fw.get("level", "") == "ok",
		"récupération : panneau « Firewall arrêté », pas « TE TOUCHE ! » (%s)" % str(fw))
	_check(not str(fw.get("sub", "")).contains("or perdu"), "récupération : pas d'« or perdu »")
	_check(v["guide"]["hint"].begins_with("Défaite : roule souple"), "récupération : la consigne du bas reste « roule souple »")
	# En vraie salle, un écart nul est bien un contact.
	var hot := _f("room")
	hot["rogue"]["firewall_gap_m"] = 0.0
	m.update(hot, 4.0)
	_check(bool(m.values()["hurt"]) and m.values()["guide"]["fw"]["text"] == "TE TOUCHE !", "salle au contact : toujours signalé")


func _replay_sound(names: Array, result_of: Callable = Callable()) -> Array:
	var s = SoundModel.new()
	var t := 0.0
	for i in names.size():
		var fr := _f(names[i])
		var res := ""
		if result_of.is_valid():
			res = result_of.call(fr)
		s.update(fr["rogue"], int(fr["gear"]), int(fr["seq"]), t, res)
		t += 1.0
	return [s, s.take_plays()]


func _sound() -> void:
	# E10-03 : le bilan n'est pas dans la trame RESULTS ; le son se décide sur la fin du boss vue.
	var scene_result := func(fr: Dictionary) -> String:      # ce que la scène passe : vide sans bilan
		var sm = fr.get("summary", null)
		return str(sm["rogue"].get("result", "")) if sm is Dictionary and sm.get("rogue", null) is Dictionary else ""
	var lost: Array = _replay_sound(["boss_end_prev", "boss_end", "cooldown", "results"], scene_result)
	_check(lost[1].has("rogue_result_lost") and not lost[1].has("rogue_result"), "run perdue : jingle de défaite (%s)" % str(lost[1]))
	var won: Array = _replay_sound(["victory_boss_end_prev", "victory_boss_end", "victory_results"], scene_result)
	_check(won[1].has("rogue_boss_won") and won[1].has("rogue_result") and not won[1].has("rogue_result_lost"),
		"run gagnée : boss battu puis jingle de victoire (%s)" % str(won[1]))
	# E10-04 : hors salle, l'écart nul du core ne fait ni ronflement ni alarme.
	for name in ["warmup", "corridor", "recovery", "cooldown"]:
		var s = SoundModel.new()
		var fr := _f(name)
		for i in 20:
			s.update(fr["rogue"], int(fr["gear"]), int(fr["seq"]) + i, i * 0.5)
		var loops: Dictionary = s.loops()
		_check(float(loops["hum_db"]) <= SoundModel.SILENCE_DB + 0.01 and not bool(loops["beat"]),
			"%s : Firewall muet (ronflement %.0f dB, alarme %s)" % [name, float(loops["hum_db"]), loops["beat"]])
	var hot := _f("room")
	hot["rogue"]["firewall_gap_m"] = 0.0
	var s2 = SoundModel.new()
	for i in 20:
		s2.update(hot["rogue"], int(hot["gear"]), int(hot["seq"]) + i, i * 0.5)
	_check(float(s2.loops()["hum_db"]) > SoundModel.HUM_MIN_DB and bool(s2.loops()["beat"]), "salle au contact : ronflement et alarme")


## E10-09 : la trame de fin de salle n'a plus d'ennemi ; l'extinction se joue avec le dernier archétype vu.
func _enemy() -> void:
	for pair in [["room_end_prev", "room_end", "dead"], ["boss_end_prev", "boss_end", "fleeing"]]:
		var e = EnemyModel.new()
		var a := _f(pair[0])
		var b := _f(pair[1])
		e.update(a["rogue"], int(a["seq"]), 0.0, 0.02)
		_check(bool(e.pose()["visible"]), "%s : ennemi affiché" % pair[0])
		var arch := str(e.pose()["archetype"])
		e.update(b["rogue"], int(b["seq"]), 0.0, 0.02)
		var p: Dictionary = e.pose()
		_check(bool(p["visible"]) and p["state"] == pair[2] and p["archetype"] == arch and not bool(p["cloaked"]),
			"%s : animation de fin « %s » visible, %s (%s)" % [pair[1], pair[2], arch, str(p)])
		for i in 150:
			e.update(b["rogue"], int(b["seq"]), 0.0, 0.02)
		_check(not bool(e.pose()["visible"]), "%s : ennemi éteint au bout de l'animation" % pair[1])


## E10-01, E10-05, E10-07 : scène réelle, trames du core.
func _scene() -> void:
	var main := Node3D.new()
	root.add_child(main)
	var host = Host.new()
	for m in _data["room"]:
		host.on_room(m)
	var t := 100.0
	var room := _f("room")
	host.update(room, main, [], null, null, "low", t)
	var sc = host.scene
	_check(sc.ribbon.visible and sc.firewall.visible, "salle : ruban et Firewall")
	for name in ["room_end", "corridor", "recovery_start", "recovery", "cooldown"]:
		t += 1.0
		var fr := _f(name)
		host.update(fr, main, [], null, null, "low", t)
		_check(not sc.ribbon.visible and not sc.firewall.visible, "%s : ni ruban ni Firewall sur le vélo" % name)
		_check(is_equal_approx(sc._s_target, float(fr["s"])), "%s : le vélo avance de la distance de la run (%.0f m)" % [name, float(fr["s"])])
	# E10-01 : couloir avec offre ouverte mais sans message `loot` (core relancé) : l'offre est redemandée.
	t += 2.0
	var corr := _f("room_end")
	_check(corr["rogue"]["loot_stage"] == "card", "trame d'entrée en couloir : offre de cartes ouverte")
	var before: int = host.resync_requests
	_check(host.update(corr, main, [], null, null, "low", t) and host.resync_requests == before + 1,
		"offre ouverte sans `loot` reçu : resynchronisation demandée")
	_check(not host.update(corr, main, [], null, null, "low", t + 0.3), "pas plus d'une demande par seconde")
	host.on_loot(_data["loot"])
	_check(not host.update(corr, main, [], null, null, "low", t + 2.0), "`loot` reçu : plus de demande")
	# E10-07 : en pause, l'écran des cartes se retire sous le menu de pause.
	sc._tick_hud(0.016)
	_check(sc.corridor_view.visible, "couloir : cartes et portes affichées")
	var paused := corr.duplicate(true)
	paused["session_state"] = "PAUSED"
	host.update(paused, main, [], null, null, "low", t + 2.1)
	sc._tick_hud(0.016)
	_check(not sc.corridor_view.visible and not sc.hud_view.visible, "pause en couloir : cartes, portes et HUD cachés")
	host.update(corr, main, [], null, null, "low", t + 2.2)
	sc._tick_hud(0.016)
	_check(sc.corridor_view.visible, "reprise : le couloir revient")
	main.queue_free()
	await process_frame
