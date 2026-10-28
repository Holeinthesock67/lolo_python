extends SceneTree

## Tests sans écran du modèle sonore du Cyber-Rogue (lot R18) : un son par événement, plafond de 8 voix et
## priorités, 60 ms entre deux sons identiques, boucles lissées à 12 dB/s, couches de musique en fondu de 2 s,
## sons dérivés d'un changement d'état, et volumes des bus du mode.
## Lancement : godot --headless --path engine --script res://tests/unit/test_rogue_sound_model.gd

const SoundModel := preload("res://scripts/rogue/rogue_sound_model.gd")
const Synth := preload("res://scripts/rogue/rogue_sound_synth.gd")
const AudioMix := preload("res://scripts/audio_mix.gd")

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


func _rogue(over: Dictionary = {}) -> Dictionary:
	var r := {"phase": "ROOM", "archetype": "puncheur", "boss_phase": null, "shield": 100.0, "gold": 0,
		"firewall_gap_m": 120.0, "overheat": false, "hack": null, "events": []}
	r.merge(over, true)
	return r


func _run() -> void:
	# Un son par événement, sons rendus une fois par trame
	var m = SoundModel.new()
	m.update(_rogue(), 5, 1, 0.0)
	m.update(_rogue({"events": ["perfect_shift", "hit"]}), 5, 2, 1.0)
	_check(m.take_plays() == ["rogue_perfect_shift", "rogue_hit"], "perfect_shift et hit : deux sons")
	m.update(_rogue({"events": ["perfect_shift", "hit"]}), 5, 2, 1.01)
	_check(m.take_plays().is_empty(), "trame renvoyée : aucun son de plus")
	var all_events := {"crit": "rogue_crit", "parry": "rogue_parry", "parry_miss": "rogue_parry_miss", "room_won": "rogue_room_won",
		"room_fled": "rogue_room_fled", "room_skipped": "rogue_room_skipped", "defeat": "rogue_defeat", "card_taken": "rogue_card_pick"}
	var t := 10.0
	var seq := 10
	var ok := true
	for ev in all_events:
		var mm = SoundModel.new()
		mm.update(_rogue(), 5, 1, t)
		mm.update(_rogue({"events": [ev]}), 5, 2, t + 0.1)
		ok = ok and mm.take_plays() == [all_events[ev]]
	_check(ok, "chaque événement du core a son son")
	_check(Synth.SOUNDS.has("rogue_boss_won") and Synth.SOUNDS.has("rogue_chest"), "sons sans signal présents dans la table")

	# Sons dérivés
	var d = SoundModel.new()
	d.update(_rogue(), 5, 1, 0.0)
	d.update(_rogue({"shield": 80.0}), 6, 2, 1.0)
	_check(d.take_plays() == ["rogue_shift_tick", "rogue_shield_hit"], "changement de vitesse, bouclier touché")
	d.update(_rogue({"shield": 80.0, "hack": {"locked": true, "forced_gear": null, "until_s": 3.0}}), 6, 3, 2.0)
	_check(d.take_plays() == ["rogue_hack"], "début du piratage")
	d.update(_rogue({"shield": 80.0, "gold": 10}), 6, 4, 3.0)
	_check(d.take_plays() == ["rogue_gold"], "or gagné")
	d.update(_rogue({"archetype": "boss", "phase": "BOSS", "boss_phase": 1, "shield": 80.0, "gold": 10}), 6, 5, 4.0)
	d.update(_rogue({"archetype": "boss", "phase": "BOSS", "boss_phase": 2, "shield": 80.0, "gold": 10}), 6, 6, 5.0)
	_check(d.take_plays() == ["rogue_boss_phase"], "changement de phase du boss")
	d.update(_rogue({"archetype": "boss", "phase": "BOSS", "boss_phase": 3, "shield": 80.0, "gold": 10, "events": ["room_won"]}), 6, 7, 6.0)
	var plays: Array = d.take_plays()
	_check("rogue_boss_won" in plays and not "rogue_room_won" in plays, "boss battu : fanfare du boss à la place de la salle gagnée")
	d.update(_rogue({"phase": "CORRIDOR"}), 6, 8, 7.0)
	d.update(_rogue({"phase": "ROOM"}), 6, 9, 8.0)
	_check("rogue_door" in d.take_plays(), "couloir quitté : porte")
	d.update(_rogue({"phase": "RECOVERY"}), 6, 10, 9.0)
	d.take_plays()
	d.update(_rogue({"phase": "ROOM"}), 6, 11, 10.0)
	_check("rogue_recovery_end" in d.take_plays(), "fin de la récupération")
	d.update(_rogue({"phase": "RESULTS"}), 6, 12, 11.0, "victory")
	_check(d.take_plays() == ["rogue_result"], "bilan de victoire")
	var d2 = SoundModel.new()
	d2.update(_rogue({"phase": "COOLDOWN"}), 6, 1, 0.0)
	d2.update(_rogue({"phase": "RESULTS"}), 6, 2, 1.0, "defeat")
	_check(d2.take_plays() == ["rogue_result_lost"], "bilan de défaite")
	var l = SoundModel.new()
	l.on_loot({"corridor_id": 3, "cards": [{"id": "a"}, {"id": "b"}, {"id": "c"}]}, 0.0)
	l.update(_rogue({"phase": "CORRIDOR"}), 6, 1, 0.1)
	l.on_loot({"corridor_id": 3, "cards": [{"id": "d"}, {"id": "e"}, {"id": "c"}]}, 1.0)
	_check(l.take_plays() == ["rogue_reroll"], "relance : mêmes couloir, autres cartes")

	# Budget : 8 voix, priorités, 60 ms
	var b = SoundModel.new()
	b.update(_rogue(), 5, 1, 0.0)
	b.update(_rogue({"events": ["hit"]}), 5, 2, 1.000)
	b.update(_rogue({"events": ["hit"]}), 5, 3, 1.030)
	_check(b.take_plays() == ["rogue_hit"], "même son avant 60 ms : ignoré")
	b.update(_rogue({"events": ["hit"]}), 5, 4, 1.070)
	_check(b.take_plays() == ["rogue_hit"], "après 60 ms : rejoué")
	var s = SoundModel.new()
	s.update(_rogue(), 5, 1, 0.0)
	var low := ["rogue_gold", "rogue_card_pick", "rogue_reroll", "rogue_door", "rogue_hack", "rogue_purge", "rogue_chest", "rogue_boss_phase"]
	for i in 8:
		s._request(low[i], 2.0 + 0.001 * i)
	_check(s.voices(2.01) == 8, "huit voix en jeu")
	s._request("rogue_shield_hit", 2.02)
	_check(s.voices(2.02) == 8 and not "rogue_shield_hit" in s.take_plays(), "neuvième son peu prioritaire : refusé")
	s.take_plays()
	s._request("rogue_defeat", 2.03)
	_check(s.voices(2.03) == 8 and s.take_plays().back() == "rogue_defeat", "la défaite prend la place du son le moins prioritaire")
	_check(s.voices(10.0) == 0, "les voix se libèrent à la fin des sons")

	# Boucles lissées à 12 dB/s
	var o = SoundModel.new()
	o.update(_rogue(), 5, 1, 0.0)
	o.update(_rogue({"overheat": true}), 5, 2, 0.5)
	_check(is_equal_approx(float(o.loops()["overheat_db"]), -60.0 + 6.0), "surchauffe : +6 dB en 0,5 s")
	o.update(_rogue({"overheat": true}), 5, 3, 5.5)
	_check(is_equal_approx(float(o.loops()["overheat_db"]), -12.0), "surchauffe : plafond -12 dB")
	var h = SoundModel.new()
	h.update(_rogue({"firewall_gap_m": 100.0}), 5, 1, 0.0)
	_check(float(h.loops()["hum_db"]) <= -59.0, "Firewall loin : pas de ronflement")
	for i in 20:
		h.update(_rogue({"firewall_gap_m": 15.0}), 5, 2 + i, 0.5 + 0.5 * i)
	var mid_db: float = h.loops()["hum_db"]
	for i in 20:
		h.update(_rogue({"firewall_gap_m": 3.0}), 5, 30 + i, 11.0 + 0.5 * i)
	_check(float(h.loops()["hum_db"]) > mid_db and float(h.loops()["hum_db"]) <= -6.0, "le ronflement monte quand le mur approche")
	_check(h.loops()["beat"], "battement de l'alarme au contact")

	# Musique par phase, fondu de 2 s
	var mu = SoundModel.new()
	mu.update(_rogue({"phase": "WARMUP"}), 5, 1, 0.0)
	mu.update(_rogue({"phase": "WARMUP"}), 5, 2, 2.0)
	_check(is_equal_approx(float(mu.music()["bass"]), 1.0) and float(mu.music()["pulse"]) == 0.0, "échauffement : basse seule")
	mu.update(_rogue({"phase": "ROOM"}), 5, 3, 3.0)
	_check(is_equal_approx(float(mu.music()["pulse"]), 0.5), "salle : pulsation à moitié après 1 s")
	mu.update(_rogue({"phase": "ROOM"}), 5, 4, 5.0)
	_check(is_equal_approx(float(mu.music()["pulse"]), 1.0) and float(mu.music()["arp"]) == 0.0, "pulsation pleine, pas d'arpège")
	mu.update(_rogue({"phase": "BOSS"}), 5, 5, 7.0)
	_check(is_equal_approx(float(mu.music()["arp"]), 1.0), "boss : arpège")

	# Volumes des bus du mode
	AudioMix.ensure_buses()
	_check(AudioMix.volume_pct(AudioMix.ROGUE_SFX) == 70 and AudioMix.volume_pct(AudioMix.ROGUE_MUSIC) == 40, "bus du mode à 70 % et 40 % au départ")
	AudioMix.set_volume(AudioMix.ROGUE_SFX, 0)
	_check(AudioMix.volume_pct(AudioMix.ROGUE_SFX) == 0, "0 % coupe les bruitages")
	AudioMix.apply_settings([{"key": "audio.rogue_music_pct", "value": 50}])
	_check(AudioMix.volume_pct(AudioMix.ROGUE_MUSIC) == 50, "réglage audio.rogue_music_pct appliqué")
	AudioMix.apply_settings([{"key": "audio.master_pct", "value": 0}])
	_check(AudioMix.volume_pct(AudioMix.MASTER) == 0, "master_pct à 0 : muet total")
	AudioMix.set_volume(AudioMix.MASTER, 100)

	print("test_rogue_sound_model : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
