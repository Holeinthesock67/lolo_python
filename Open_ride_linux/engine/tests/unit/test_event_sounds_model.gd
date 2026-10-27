extends SceneTree

## Tests sans écran des jingles d'événements (lot T17) : modèle event_sounds_model.gd (sommet, sprint et
## variantes record, arches comme `ArchSchedule.crossed` du core, sauts ignorés, sans bonus ni hors
## séance, fin de séance en SIM et en ERG) et synthèse de sound_player.gd (un flux par jingle, non
## bouclé, durée, niveau sans écrêtage, lecteur sur le bus « Events »).
## Lancement : godot --headless --path engine --script res://tests/unit/test_event_sounds_model.gd

const Model := preload("res://scripts/event_sounds_model.gd")
const SoundPlayer := preload("res://scripts/sound_player.gd")

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


func _st(s: float, session: String = "RUNNING", bonus: bool = true) -> Dictionary:
	var st := {"session_state": session, "s": s}
	if bonus:
		st["powerup"] = {"held": null, "active": null, "remaining_s": null}
	return st


func _ride(m, from_s: float, to_s: float, step_m: float, bonus: bool = true) -> Array:
	var out := []
	var s := from_s
	while s <= to_s + 1e-9:
		out.append_array(m.on_state(_st(s, "RUNNING", bonus)))
		s += step_m
	return out


func _run() -> void:
	var m = Model.new()
	# Segments
	_check(m.on_segment_result({"kind": "climb", "pr": false}) == "jingle_summit", "fin de montée : sommet")
	_check(m.on_segment_result({"kind": "climb", "pr": true}) == "jingle_summit_pr", "sommet avec record")
	_check(m.on_segment_result({"kind": "sprint", "pr": false}) == "jingle_sprint", "fin de sprint")
	_check(m.on_segment_result({"kind": "sprint", "pr": true}) == "jingle_sprint_pr", "sprint avec record")
	_check(m.on_segment_result({"kind": "autre"}) == "", "type inconnu : rien")

	# Arches sur un parcours ouvert de 12 km tous les 5 km : 5 000 et 10 000 m.
	m.set_route(5000.0, 12000.0, false)
	var got := _ride(m, 0.0, 12000.0, 10.0)
	_check(got == ["jingle_arch", "jingle_arch"], "parcours ouvert : deux arches (%s)" % str(got))
	m.set_route(5000.0, 12000.0, false)
	got = _ride(m, 4990.0, 5010.0, 10.0, false)
	_check(got.is_empty(), "sans champ powerup (ERG, bonus coupés) : aucune arche")
	m.set_route(0.0, 12000.0, false)
	_check(_ride(m, 0.0, 12000.0, 10.0).is_empty(), "arch_every_m = 0 : aucune arche")
	# Boucle de 10 km tous les 2,5 km : arches à 2 500, 5 000, 7 500 m de chaque tour.
	m.set_route(2500.0, 10000.0, true)
	got = _ride(m, 0.0, 20000.0, 20.0)
	_check(got.size() == 6, "boucle, deux tours : 6 arches (%d)" % got.size())
	_check(m.crossed(7400.0, 12600.0) == 2 and m.crossed(9990.0, 10010.0) == 0, "franchissements cumulés comme le core")
	# Vecteurs partagés avec le core : mêmes positions que segment_markers_model.arch_positions.
	var vec: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://tests/data/arch_schedule_vectors.json"))
	for v in vec["positions"]:
		m.set_route(float(v["every_m"]), float(v["length_m"]), false)
		_check(m.crossed(0.0, float(v["length_m"])) == (v["positions"] as Array).size(),
			"vecteur every %s / longueur %s" % [v["every_m"], v["length_m"]])
	# Saut (reprise après coupure) : pas de jingle ; pause puis reprise : franchissement compté.
	m.set_route(5000.0, 12000.0, false)
	m.on_state(_st(100.0))
	_check(m.on_state(_st(6000.0)).is_empty(), "saut de 5,9 km : ignoré")
	m.on_state(_st(4990.0))
	m.on_state(_st(4995.0, "PAUSED"))
	_check(m.on_state(_st(5003.0)) == ["jingle_arch"], "arche juste après une pause")
	m.on_state(_st(9995.0, "READY"))
	_check(m.on_state(_st(10005.0)).is_empty(), "hors séance avant la trame : pas de franchissement")

	# Fin de séance
	m.on_state(_st(11000.0))
	_check(m.on_state(_st(11000.0, "FINISHED")) == ["jingle_finish"], "RUNNING → FINISHED : fin de séance")
	_check(m.on_state(_st(11000.0, "FINISHED")).is_empty(), "FINISHED répété : une seule fois")
	m.on_state(_st(0.0, "PAUSED", false))
	_check(m.on_state(_st(0.0, "FINISHED", false)) == ["jingle_finish"], "ERG en pause → FINISHED : fin de séance")
	m.on_state(_st(0.0, "READY", false))
	_check(m.on_state(_st(0.0, "FINISHED", false)).is_empty(), "READY → FINISHED : rien")

	# Synthèse (bus « Events » créé ici comme le fera le volume réglable : sans lui, Godot rend « Master »)
	if AudioServer.get_bus_index("Events") < 0:
		AudioServer.add_bus()
		AudioServer.set_bus_name(AudioServer.bus_count - 1, "Events")
	var sp = SoundPlayer.new()
	for jingle in Model.JINGLES:
		var wav: AudioStreamWAV = sp.stream(jingle)
		_check(wav != null and wav.loop_mode == AudioStreamWAV.LOOP_DISABLED, "%s : flux non bouclé" % jingle)
		var dur := wav.data.size() / 2.0 / wav.mix_rate
		_check(absf(dur - Model.duration_s(jingle)) < 0.01 and dur < 2.5, "%s : %.2f s" % [jingle, dur])
		var peak := 0
		for i in range(0, wav.data.size(), 2):
			peak = maxi(peak, absi(wav.data.decode_s16(i)))
		_check(peak > 20000 and peak < 32767, "%s : pic %d sans écrêtage" % [jingle, peak])
	var ep: AudioStreamPlayer = sp.get_node("EventPlayer")
	_check(ep.bus == &"Events" and ep.max_polyphony == 3, "lecteur des jingles sur le bus Events, 3 voix")
	sp.play_event("jingle_arch")
	sp.play_event("inconnu")
	_check(sp.events_played == ["jingle_arch"], "play_event : nom inconnu ignoré")
	sp.free()

	print("%d vérifications, %d échec(s)" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
