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
	var v: Dictionary = vm.view({"draft": 0.165}, 0.0, 0.0)
	_check(v["draft_text"] == "Abri 30 %" and v["visible"], "draft 0,165 : « Abri 30 %% » (%s)" % v["draft_text"])
	_check(vm.view({"draft": 0.01}, 0.0, 0.1)["draft_text"] == "", "draft 0,01 : rien sous 5 %")
	_check(vm.view({"draft": 0.45}, 0.0, 0.2)["draft_text"] == "Abri 80 %", "draft 0,45 : « Abri 80 % » (lot AS4)")
	_check(vm.view({"draft": 0.55}, 0.0, 0.3)["draft_text"] == "Abri 100 %", "draft 0,55, cœur d'un groupe : « Abri 100 % »")
	# Lot AS5 : watts économisés sous la pastille, seulement avec elle
	var w: Dictionary = vm.view({"draft": 0.135, "draft_w": 48}, 0.0, 0.3)
	_check(w["draft_w_text"] == "−48 W", "draft_w 48 : « −48 W » (%s)" % w["draft_w_text"])
	_check(vm.view({"draft": 0.135}, 0.0, 0.4)["draft_w_text"] == "", "sans draft_w : pas de watts (HUD inchangé)")
	_check(vm.view({"draft": 0.01, "draft_w": 3}, 0.0, 0.5)["draft_w_text"] == "", "sans pastille (abri < 5 %) : pas de watts")
	_check(vm.view({"draft": 0.135, "draft_w": 0}, 0.0, 0.6)["draft_w_text"] == "", "0 W économisé : rien")


# Critère 7 : verdict favorable ou non
func _test_verdict() -> void:
	var vm = WindViewModel.new()
	var v: Dictionary = _ride(vm, _state(15.0, 0.0, 3.0), 0.0, 0.0, 3.0)
	_check(v["verdict"] == "defavorable" and v["tone"] == "bad", "head_mps 3 : défavorable, bad (%s)" % v["verdict"])
	vm = WindViewModel.new()
	v = _ride(vm, _state(15.0, 180.0, -3.0), 0.0, 0.0, 3.0)
	_check(v["verdict"] == "favorable" and v["tone"] == "good", "head_mps −3 : favorable, good (%s)" % v["verdict"])
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


# Critère 8 (lot NI1) : sens écrit en mots pour le HUD, une seule info avec la vitesse (plus de niveau d'intensité)
func _test_direction_text() -> void:
	var cases := {0.0: "de face", 180.0: "de dos", 90.0: "de droite", 270.0: "de gauche"}
	for from_deg in cases:
		var vm = WindViewModel.new()
		var v: Dictionary = _ride(vm, _state(20.0, from_deg), 0.0, 0.0, 3.0)
		_check(v["direction_text"] == cases[from_deg] and not v.has("level") and not v.has("level_text")
			and not v.has("verdict_text"), "vent venant de %.0f° : « %s » (%s), sans niveau ni pastille" % [from_deg,
			cases[from_deg], v["direction_text"]])
	var none: Dictionary = WindViewModel.new().view({}, 0.0, 0.0)
	_check(none["direction_text"] == "", "sans vent : pas de sens écrit")


func _init() -> void:
	_test_sectors()
	_test_label_hysteresis()
	_test_hidden_without_wind()
	_test_draft()
	_test_verdict()
	_test_direction_text()
	print("test_wind_view_model : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
