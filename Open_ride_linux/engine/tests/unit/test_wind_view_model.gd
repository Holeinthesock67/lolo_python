extends SceneTree

## Tests unitaires sans écran de l'indicateur du vent et de l'abri `wind_view_model.gd` (Lot P4).
## Lancement : godot --headless --path engine --script res://tests/unit/test_wind_view_model.gd

const WindViewModel := preload("res://scripts/wind_view_model.gd")

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


static func _state(speed_kmh: float, from_deg: float, head_mps := 0.0) -> Dictionary:
	return {"wind": {"speed_mps": speed_kmh / 3.6, "from_deg": from_deg, "head_mps": head_mps, "gust": 0.0}}


## Envoie le même vent 2 fois par seconde pendant `seconds` (trames sans `wind` entre deux) ; dernière vue.
static func _ride(vm, state: Dictionary, heading: float, t0: float, seconds: float) -> Dictionary:
	var out: Dictionary = {}
	var t := t0
	var next_wire := t0
	while t <= t0 + seconds + 1e-6:
		var frame: Dictionary = state if t >= next_wire - 1e-6 else {}
		if t >= next_wire - 1e-6:
			next_wire += 0.5
		out = vm.view(frame, heading, t)
		t += 1.0 / 30.0
	return out


# Critère 2 : secteurs, flèche et vitesse
func _test_sectors() -> void:
	var north := _state(20.0, 0.0)
	var vm = WindViewModel.new()
	var v: Dictionary = _ride(vm, north, 0.0, 0.0, 1.0)
	_check(v["label"] == "face" and is_equal_approx(v["arrow_deg"], 0.0) and v["speed_text"] == "20 km/h",
		"route plein nord, vent du nord 20 km/h : face, 0°, 20 km/h (%s, %.0f°, %s)" % [v["label"], v["arrow_deg"], v["speed_text"]])
	vm = WindViewModel.new()
	v = _ride(vm, north, 180.0, 0.0, 1.0)
	_check(v["label"] == "dos" and is_equal_approx(v["arrow_deg"], 180.0), "route plein sud : dos, 180° (%s, %.0f°)" % [v["label"], v["arrow_deg"]])
	vm = WindViewModel.new()
	v = _ride(vm, north, 90.0, 0.0, 1.0)
	_check(v["label"] == "travers gauche", "route plein est : travers gauche (%s)" % v["label"])
	vm = WindViewModel.new()
	v = _ride(vm, north, 270.0, 0.0, 1.0)
	_check(v["label"] == "travers droit", "route plein ouest : travers droit (%s)" % v["label"])
	_check(v["visible"], "avec vent : indicateur visible")


# Critère 3 : ± 3° autour d'une limite de secteur ne change pas le label
func _test_label_hysteresis() -> void:
	var vm = WindViewModel.new()
	var v: Dictionary = vm.view(_state(20.0, 40.0), 0.0, 0.0)   # face, près de la limite de 45°
	var stable: bool = v["label"] == "face"
	for i in range(40):
		var dir: float = 45.0 + (3.0 if i % 2 == 0 else -3.0)
		v = vm.view(_state(20.0, dir), 0.0, 0.05 * (i + 1))
		stable = stable and v["label"] == "face"
	_check(stable, "direction 45 ± 3° : label « face » inchangé")
	v = vm.view(_state(20.0, 60.0), 0.0, 3.0)
	_check(v["label"] == "travers droit", "direction 60° : bascule en travers droit (%s)" % v["label"])


# Critère 5 : sans vent, indicateur caché ; le vent expire 2 s après la dernière trame
func _test_hidden_without_wind() -> void:
	var vm = WindViewModel.new()
	var v: Dictionary = vm.view({"session_state": "RUNNING"}, 0.0, 0.0)
	_check(not v["visible"] and v["speed_text"] == "" and v["draft_text"] == "",
		"sans wind ni draft : indicateur caché")
	vm.view(_state(20.0, 0.0), 0.0, 1.0)
	_check(vm.view({}, 0.0, 2.9)["visible"], "vent gardé 1,9 s après la dernière trame")
	_check(not vm.view({}, 0.0, 3.1)["visible"], "vent expiré 2,1 s après la dernière trame")


# Critère 6 : abri
func _test_draft() -> void:
	var vm = WindViewModel.new()
	var v: Dictionary = vm.view({"draft": 0.135}, 0.0, 0.0)
	_check(v["draft_text"] == "Abri 30 %" and v["visible"], "draft 0,135 : « Abri 30 %% » (%s)" % v["draft_text"])
	_check(vm.view({"draft": 0.01}, 0.0, 0.1)["draft_text"] == "", "draft 0,01 : rien sous 5 %")
	_check(vm.view({"draft": 0.45}, 0.0, 0.2)["draft_text"] == "Abri 100 %", "draft 0,45 : « Abri 100 % »")


# Critère 7 : verdict favorable ou non
func _test_verdict() -> void:
	var vm = WindViewModel.new()
	var v: Dictionary = _ride(vm, _state(15.0, 0.0, 3.0), 0.0, 0.0, 3.0)
	_check(v["verdict_text"] == "Vent défavorable" and v["tone"] == "bad", "head_mps 3 : défavorable, bad (%s)" % v["verdict_text"])
	vm = WindViewModel.new()
	v = _ride(vm, _state(15.0, 180.0, -3.0), 0.0, 0.0, 3.0)
	_check(v["verdict_text"] == "Vent favorable" and v["tone"] == "good", "head_mps −3 : favorable, good (%s)" % v["verdict_text"])
	vm = WindViewModel.new()
	v = _ride(vm, _state(20.0, 90.0, 0.0), 0.0, 0.0, 3.0)
	_check(v["verdict"] == "neutre" and v["tone"] == "neutral", "20 km/h plein travers : neutre (%s)" % v["verdict"])
	# head_mps oscillant entre 0,9 et 1,1 : verdict inchangé, depuis neutre comme depuis défavorable
	for start_head in [0.0, 3.0]:
		vm = WindViewModel.new()
		v = _ride(vm, _state(10.0, 0.0, start_head), 0.0, 0.0, 5.0)
		var before: String = v["verdict"]
		var same := true
		for i in range(60):
			v = _ride(vm, _state(10.0, 0.0, 0.9 if i % 2 == 0 else 1.1), 0.0, 5.0 + i * 0.5, 0.4)
			same = same and v["verdict"] == before
		_check(same, "head_mps 0,9 ↔ 1,1 depuis %s : verdict inchangé" % before)


# Critère 8 : niveaux d'intensité et rafale isolée
func _test_levels() -> void:
	var expected := {3.0: 0, 10.0: 1, 20.0: 2, 30.0: 3, 45.0: 4}
	for kmh in expected:
		var vm = WindViewModel.new()
		var v: Dictionary = _ride(vm, _state(kmh, 90.0), 0.0, 0.0, 3.0)
		_check(v["level"] == expected[kmh] and v["level_text"] == WindViewModel.LEVEL_TEXTS[expected[kmh]],
			"%.0f km/h : niveau %d (%s), reçu %d" % [kmh, expected[kmh], WindViewModel.LEVEL_TEXTS[expected[kmh]], v["level"]])
	var vm2 = WindViewModel.new()
	_ride(vm2, _state(20.0, 90.0), 0.0, 0.0, 3.0)
	# Rafale isolée de 0,8 s à 45 km/h (deux trames), puis retour à 20 km/h
	var v2: Dictionary = vm2.view(_state(45.0, 90.0), 0.0, 3.2)
	v2 = vm2.view(_state(45.0, 90.0), 0.0, 3.7)
	v2 = vm2.view(_state(20.0, 90.0), 0.0, 4.0)
	v2 = _ride(vm2, _state(20.0, 90.0), 0.0, 4.5, 2.0)
	_check(v2["level"] == 2, "rafale isolée de 0,8 s : niveau inchangé (%d)" % v2["level"])
	v2 = _ride(vm2, _state(30.0, 90.0), 0.0, 7.0, 2.0)
	_check(v2["level"] == 3, "vent soutenu à 30 km/h : niveau 3 après 1 s (%d)" % v2["level"])
	# Hystérésis de 2 km/h autour de 15 km/h
	var vm3 = WindViewModel.new()
	_ride(vm3, _state(16.5, 90.0), 0.0, 0.0, 3.0)
	var v3: Dictionary = _ride(vm3, _state(14.5, 90.0), 0.0, 3.0, 3.0)
	_check(v3["level"] == 2, "16,5 puis 14,5 km/h : reste modéré (hystérésis) (%d)" % v3["level"])
	v3 = _ride(vm3, _state(13.5, 90.0), 0.0, 6.0, 3.0)
	_check(v3["level"] == 1, "13,5 km/h : redescend à faible (%d)" % v3["level"])


func _init() -> void:
	_test_sectors()
	_test_label_hysteresis()
	_test_hidden_without_wind()
	_test_draft()
	_test_verdict()
	_test_levels()
	print("test_wind_view_model : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
