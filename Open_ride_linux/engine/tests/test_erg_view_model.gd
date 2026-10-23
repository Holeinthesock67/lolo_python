extends SceneTree

## Tests sans écran du modèle de vue ERG `erg_view_model.gd` (Lot I6).
##
## - Cas unitaires : toutes les règles du §4.1 (visible, title, target_text, biais, roue libre,
##   next_text, dernier bloc, remaining_text interpolé et figé en pause, progress, beep unique
##   à 30 Hz et 144 Hz, bloc < 4 s, saut de bloc, paused_text, profile_bars).
## - Scénario face au faux core (`fake_core.py --erg-workout`) : reçoit les trames UDP `state`
##   pour les 10 blocs de référence du lot F et vérifie les 10 bips à 3,0 s ± 0,1 s (et l'absence
##   de bip lorsqu'un bloc est en pause pendant ses 3 dernières secondes).

const ErgViewModel := preload("res://scripts/erg_view_model.gd")

var _checked := 0
var _failures := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if not cond:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _make_erg(overrides: Dictionary = {}) -> Dictionary:
	var base := {
		"workout_name": "Référence lot F",
		"block_index": 2,
		"block_count": 10,
		"block_type": "steady",
		"block_remaining_s": 42.0,
		"block_total_s": 1200.0,
		"target_w": 238,
		"next_target_w": 300,
		"bias_pct": 100,
		"paused": false,
	}
	for k in overrides.keys():
		base[k] = overrides[k]
	return base


func _run_unit_tests() -> void:
	var vm = ErgViewModel.new()

	# 1. visible : faux si erg est null
	var d_null: Dictionary = vm.update(null, 0.0)
	_check(d_null["visible"] == false, "erg null -> visible == false")

	# 2. title, target_text (biais 100 %), next_text, remaining_text, progress, paused_text
	var d_std: Dictionary = vm.update(_make_erg(), 10.0)
	_check(d_std["visible"] == true, "erg présent -> visible == true")
	_check(str(d_std["title"]).contains("Référence lot F") and str(d_std["title"]).contains("Bloc 2 / 10"), "title: nom et Bloc 2 / 10")
	_check(d_std["target_text"] == "238 W", "target_text: 238 W")
	_check(d_std["next_text"] == "Ensuite : 300 W dans 0:42", "next_text: Ensuite : 300 W dans 0:42")
	_check(d_std["remaining_text"] == "0:42", "remaining_text: 0:42")
	_check(absf(float(d_std["progress"]) - (1200.0 - 42.0) / 1200.0) < 1e-5, "progress cohérent")
	_check(d_std["paused_text"] == "", "paused_text vide hors pause")
	_check(d_std["beep"] == false, "pas de bip à 42 s")

	# 3. Biais != 100 % et roue libre
	var d_bias: Dictionary = vm.update(_make_erg({"bias_pct": 110}), 11.0)
	_check(d_bias["target_text"] == "238 W (110 %)", "target_text avec biais 110 %")

	var d_free: Dictionary = vm.update(_make_erg({"block_type": "freeride", "target_w": 0}), 12.0)
	_check(d_free["target_text"] == "Roue libre", "target_text en freeride")

	var d_free_bias: Dictionary = vm.update(_make_erg({"block_type": "freeride", "target_w": 0, "bias_pct": 96}), 13.0)
	_check(d_free_bias["target_text"] == "Roue libre (96 %)", "target_text en freeride avec biais")

	# 4. Dernier bloc -> next_text vide
	var d_last: Dictionary = vm.update(_make_erg({"block_index": 10, "block_count": 10, "next_target_w": null}), 14.0)
	_check(d_last["next_text"] == "", "dernier bloc -> next_text vide")

	# 5. Interpolation du temps restant entre deux trames (et figé en pause)
	vm.on_state(_make_erg({"block_remaining_s": 10.0, "paused": false}), 100.0)
	var d_interp1: Dictionary = vm.evaluate(100.25)
	_check(absf(float(d_interp1["remaining_s"]) - 9.75) < 1e-4, "remaining_s interpolé à +0,25 s")
	_check(d_interp1["remaining_text"] == "0:09", "remaining_text passe à 0:09")

	vm.on_state(_make_erg({"block_remaining_s": 10.0, "paused": true}), 200.0)
	var d_paused: Dictionary = vm.evaluate(205.0)
	_check(absf(float(d_paused["remaining_s"]) - 10.0) < 1e-6, "remaining_s figé en pause")
	_check(d_paused["paused_text"] == "ERG en pause", "paused_text en pause")

	# 6. Unicité du bip à 30 Hz et à 144 Hz de rendu
	for render_hz in [30.0, 144.0]:
		var vm_hz = ErgViewModel.new()
		var beeps := 0
		var beep_rem := -1.0
		var state_dt := 1.0 / 30.0
		var render_dt := 1.0 / float(render_hz)
		var t_cur := 0.0
		var last_state_t := -1.0
		while t_cur <= 5.0:
			if last_state_t < 0.0 or (t_cur - last_state_t) >= state_dt - 1e-6:
				last_state_t = t_cur
				var rem_frame := maxf(0.0, round((5.0 - t_cur) * 100.0) / 100.0)
				vm_hz.on_state(_make_erg({"block_index": 1, "block_remaining_s": rem_frame, "block_total_s": 60.0}), t_cur)
			var out: Dictionary = vm_hz.evaluate(t_cur)
			if bool(out["beep"]):
				beeps += 1
				beep_rem = float(out["remaining_s"])
			t_cur += render_dt
		_check(beeps == 1, "unicité du bip à %.0f Hz (reçu %d)" % [render_hz, beeps])
		_check(beep_rem >= 2.9 and beep_rem <= 3.1, "bip entre 2,9 et 3,1 s à %.0f Hz (%.3f s)" % [render_hz, beep_rem])

	# 7. Bloc court (< 4 s) -> jamais de bip
	var vm_short = ErgViewModel.new()
	var short_beeps := 0
	for k in range(100):
		var t_s := k * 0.03
		var rem_s := maxf(0.0, 3.5 - t_s)
		var res_s: Dictionary = vm_short.update(
			_make_erg({"block_index": 1, "block_total_s": 3.5, "block_remaining_s": rem_s}),
			t_s
		)
		if bool(res_s["beep"]):
			short_beeps += 1
	_check(short_beeps == 0, "bloc de 3,5 s (< 4 s) -> 0 bip")

	# 8. Saut de bloc -> bip de nouveau possible sur le nouveau bloc
	var vm_skip = ErgViewModel.new()
	var b1: Dictionary = vm_skip.update(_make_erg({"block_index": 1, "block_remaining_s": 2.95, "block_total_s": 60.0}), 1.0)
	var b1_again: Dictionary = vm_skip.update(_make_erg({"block_index": 1, "block_remaining_s": 2.80, "block_total_s": 60.0}), 1.15)
	# Saut direct du bloc 1 au bloc 3
	var b3_early: Dictionary = vm_skip.update(_make_erg({"block_index": 3, "block_remaining_s": 15.0, "block_total_s": 60.0}), 2.0)
	var b3_beep: Dictionary = vm_skip.update(_make_erg({"block_index": 3, "block_remaining_s": 2.98, "block_total_s": 60.0}), 14.02)
	_check(bool(b1["beep"]) == true and bool(b1_again["beep"]) == false, "bip unique sur bloc 1")
	_check(bool(b3_early["beep"]) == false and bool(b3_beep["beep"]) == true, "bip réarmé après saut au bloc 3")

	# 9. Histogramme profile_bars
	var ref_blocks := [
		{"type": "warmup", "duration_s": 600.0, "start_frac": 0.5, "end_frac": 0.75},
		{"type": "steady", "duration_s": 1200.0, "start_frac": 0.95, "end_frac": 0.95},
		{"type": "freeride", "duration_s": 120.0, "start_frac": null, "end_frac": null},
		{"type": "cooldown", "duration_s": 300.0, "start_frac": 0.7, "end_frac": 0.4},
	]
	var bars: Array = ErgViewModel.profile_bars(ref_blocks, 250.0, 400.0, 100.0)
	_check(bars.size() == 4, "profile_bars: 4 barres")
	_check(absf(float(bars[0]["x0"]) - 0.0) < 1e-5 and absf(float(bars[3]["x1"]) - 400.0) < 1e-4, "profile_bars: couvre [0, width]")
	_check(float(bars[0]["h0"]) < float(bars[0]["h1"]), "profile_bars: warmup monte (trapèze)")
	_check(absf(float(bars[1]["h0"]) - float(bars[1]["h1"])) < 1e-5, "profile_bars: steady plat (rectangle)")
	_check(float(bars[2]["h0"]) == 0.0 and float(bars[2]["h1"]) == 0.0, "profile_bars: freeride hauteur 0")


func _get_arg_int(prefix: String, default_val: int) -> int:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with(prefix):
			return int(arg.substr(prefix.length()))
	return default_val


func _run_udp_scenario(state_port: int, cmd_port: int) -> void:
	var udp := PacketPeerUDP.new()
	var err := udp.bind(state_port, "127.0.0.1")
	_check(err == OK, "UDP bind sur le port %d" % state_port)
	if err != OK:
		return

	var tx := PacketPeerUDP.new()
	tx.set_dest_address("127.0.0.1", cmd_port)
	tx.put_packet('{"type":"hello","v":1}'.to_utf8_buffer())

	var vm_pass1 = ErgViewModel.new()
	var vm_pass2 = ErgViewModel.new()
	var pass1_beeps: Array = []
	var pass2_beeps_by_block: Dictionary = {}

	var deadline_ms := Time.get_ticks_msec() + 10000
	var done := false
	while Time.get_ticks_msec() < deadline_ms and not done:
		while udp.get_available_packet_count() > 0:
			var raw := udp.get_packet().get_string_from_utf8()
			var msg = JSON.parse_string(raw)
			if typeof(msg) != TYPE_DICTIONARY:
				continue
			var d: Dictionary = msg
			if d.get("type") == "shutdown":
				done = true
				break
			if d.get("type") != "state" or not d.has("erg"):
				continue
			var erg: Dictionary = d["erg"]
			var t_frame := float(d.get("ts_ms", 0)) / 1000.0
			var w_name := str(erg.get("workout_name", ""))
			var is_pass2 := w_name.contains("(pause)")
			var vm = vm_pass2 if is_pass2 else vm_pass1

			vm.on_state(erg, t_frame)
			# Simule 4 sous-pas de rendu (~120 Hz) entre deux trames à 30 Hz
			for sub in range(4):
				var t_render := t_frame + sub * (1.0 / 120.0)
				var out: Dictionary = vm.evaluate(t_render)
				if bool(out["beep"]):
					var b_idx := int(erg.get("block_index", 0))
					var rem_at_beep := float(out["remaining_s"])
					if is_pass2:
						pass2_beeps_by_block[b_idx] = pass2_beeps_by_block.get(b_idx, 0) + 1
					else:
						pass1_beeps.append({"block": b_idx, "rem_s": rem_at_beep})
		if not done:
			OS.delay_msec(2)

	udp.close()
	tx.close()

	_check(done, "scénario UDP ERG terminé par shutdown")
	_check(pass1_beeps.size() == 10, "passe 1 (10 blocs sans pause) : exactement 10 bips (reçu %d)" % pass1_beeps.size())
	for i in range(pass1_beeps.size()):
		var item: Dictionary = pass1_beeps[i]
		_check(int(item["block"]) == i + 1, "bip %d sur le bloc %d" % [i + 1, i + 1])
		var r := float(item["rem_s"])
		_check(r >= 2.9 and r <= 3.1, "bloc %d : bip entre 2,9 et 3,1 s avant la fin (%.3f s)" % [i + 1, r])

	_check(not pass2_beeps_by_block.has(4), "passe 2 (pause pendant les 3 dernières s du bloc 4) : 0 bip sur le bloc 4")
	_check(pass2_beeps_by_block.size() == 9, "passe 2 : 9 bips sur les 9 autres blocs (reçu %d)" % pass2_beeps_by_block.size())


func _init() -> void:
	_run_unit_tests()

	var state_port := _get_arg_int("--ipc-state-port=", 0)
	var cmd_port := _get_arg_int("--ipc-cmd-port=", 0)
	if state_port > 0 and cmd_port > 0:
		_run_udp_scenario(state_port, cmd_port)

	print("Tests ERG vérifiés : %d, échecs : %d" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
