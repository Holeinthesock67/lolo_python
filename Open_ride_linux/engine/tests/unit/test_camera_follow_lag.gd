extends SceneTree

## Retard de la position affichée sur le core (camera_follow.gd, lot D4) quand une trame arrive juste avant
## chaque image : ~15 images/s en high, trames du core toutes les ~60 ms et parfois groupées (banc du
## Dernier survivant, 3 novembre : jusqu'à 4,2 m de retard, les bots, placés à leur s du core, semblaient
## traverser le cycliste). Le retard doit rester sous 0,5 m, sans recul ni saut de plus de 1 m par image.
## Lancement : godot --headless --path engine --script res://tests/unit/test_camera_follow_lag.gd

const CameraFollow := preload("res://scripts/camera_follow.gd")
const BotsViewModel := preload("res://scripts/bots_view_model.gd")

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
	_run()
	print("test_camera_follow_lag : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)


## Roule `seconds` à v m/s : trames du core toutes les `frame_ms` (groupées par `burst`), images toutes les
## `image_ms`, chaque trame reçue juste avant l'image qui suit ; renvoie {lag, back, jump} au pire.
func _ride(frame_ms: float, image_ms: float, burst: int, seconds: float, v: float) -> Dictionary:
	var f = CameraFollow.new()
	var t_core := 0.0          # s, horloge du core
	var pending: Array = []    # trames émises pas encore reçues
	var t_img := 0.0
	var shown := 0.0
	var worst := {"lag": 0.0, "back": 0.0, "jump": 0.0}
	f.push_frame(0, 0.0, v, true)
	var next_frame := frame_ms / 1000.0
	while t_img < seconds:
		t_img += image_ms / 1000.0
		while next_frame <= t_img:
			pending.append(next_frame)
			next_frame += frame_ms / 1000.0
		# Les trames arrivent par paquets de `burst` (ou toutes si l'image a pris du retard), à l'heure de l'image.
		if pending.size() >= burst:
			var now_us := int(t_img * 1e6) - 1000
			for t in pending:
				f.push_frame(now_us, v * t, v, true)
			pending.clear()
		var s: float = f.update(int(t_img * 1e6))
		if t_img > 2.0:   # régime établi
			worst["lag"] = maxf(worst["lag"], v * t_img - s)
			worst["back"] = maxf(worst["back"], shown - s)
			worst["jump"] = maxf(worst["jump"], s - shown)
		shown = s
	return worst


func _run() -> void:
	for case in [[60.0, 66.0, 1, "trame avant chaque image, 15 images/s"], [20.0, 66.0, 3, "trames groupées par 3, 15 images/s"],
			[50.0, 16.7, 1, "60 images/s"], [60.0, 100.0, 2, "10 images/s, trames par 2"]]:
		var w: Dictionary = _ride(case[0], case[1], case[2], 20.0, 5.5)
		_check(w["lag"] < 0.5, "%s : retard au plus %.2f m (< 0,5 m)" % [case[3], w["lag"]])
		_check(w["back"] <= 0.0001, "%s : jamais de recul" % case[3])
		_check(w["jump"] < 1.0, "%s : pas de saut (%.2f m par image au plus)" % [case[3], w["jump"]])
	# main.gd : bots placés avant le décor vivant, qui compte les contacts avec les places de cette image.
	var main_code := FileAccess.get_file_as_string("res://scripts/main.gd")
	var bots_at := main_code.find("_show_bots(s_route,")
	var living_at := main_code.find("_step_living(delta, s_route,")
	_check(bots_at > 0 and living_at > bots_at, "main.gd : bots placés avant le décor vivant dans la même image")
	# Banc course_bots du 6 novembre : un bot à 1,78 m derrière le cycliste dans le core s'affichait à moins de
	# 1,7 m (contacts « bot / cycliste à -2 m ») : il était extrapolé plus tard dans l'image que le cycliste.
	var same := _bot_gap(0.0)
	_check(absf(same["min"] + 1.78) < 0.01 and absf(same["max"] + 1.78) < 0.01,
		"bot à 1,78 m derrière, extrapolé au même instant que le cycliste : écart affiché %.3f à %.3f m" % [same["min"], same["max"]])
	var late := _bot_gap(20.0)
	_check(late["max"] > -1.7, "témoin : bot lu 20 ms plus tard dans l'image, écart affiché jusqu'à %.2f m (contact)" % late["max"])
	_check(main_code.contains("_show_bots(s_route, float(follow.last_frame[\"v\"]), now)"),
		"main.gd : bots de l'image extrapolés à l'instant `now` du cycliste")
	_check(main_code.contains("follow.push_frame(t_frame_us,") and main_code.contains("else null, t_frame_us)"),
		"main.gd : cycliste et bots d'une trame reçus à la même heure")


## Cycliste (camera_follow.gd) et bot (bots_view_model.gd) à 9,5 m/s, le bot 1,78 m derrière dans chaque trame
## du core (30 Hz, heures de réception qui varient de 0 à 25 ms), images toutes les 33 ms ; le bot est lu
## `late_ms` après le cycliste dans l'image. Renvoie l'écart affiché {min, max} (négatif : derrière).
func _bot_gap(late_ms: float) -> Dictionary:
	var f = CameraFollow.new()
	var bots = BotsViewModel.new()
	var v := 9.5
	var out := {"min": INF, "max": -INF}
	var t_core := 0.0
	var t_img := 0.0
	var k := 0
	while t_img < 10.0:
		t_img += 1.0 / 30.0
		while t_core <= t_img - 0.03:
			var t_us := int((t_core + 0.025 * float((k * 7) % 11) / 10.0) * 1e6)
			f.push_frame(t_us, v * t_core, v, true)
			bots.push([{"id": "b1", "s": v * t_core - 1.78, "v": v, "kind": "constant", "lane_m": 1.4}], t_us)
			t_core += 1.0 / 30.0
			k += 1
		var now := int(t_img * 1e6)
		var s: float = f.update(now)
		var view: Array = bots.view(s, v, now + int(late_ms * 1000.0))
		if t_img > 2.0:
			out["min"] = minf(out["min"], float(view[0]["gap_m"]))
			out["max"] = maxf(out["max"], float(view[0]["gap_m"]))
	return out
