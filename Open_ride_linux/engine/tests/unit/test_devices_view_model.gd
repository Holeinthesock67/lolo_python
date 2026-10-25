extends SceneTree

## Tests unitaires sans écran du modèle d'état des appareils (Lot N5).
## Lancement : godot --headless --path engine --script res://tests/unit/test_devices_view_model.gd

const DevicesViewModel := preload("res://scripts/devices_view_model.gd")

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
	var nodes_before := Performance.get_monitor(Performance.OBJECT_NODE_COUNT)
	var vm = DevicesViewModel.new()

	# 1. Trame v1.1 du scénario demo (trainer, deux boîtiers à 80 %, ceinture) : 4 lignes ok
	var state_demo := {
		"devices": {
			"trainer": {"name": "HomeTrainer", "status": "CONNECTED", "address": "AA:BB:CC:DD:EE:FF"},
			"click": [
				{"side": "plus", "status": "CONNECTED", "battery_pct": 80},
				{"side": "minus", "status": "CONNECTED", "battery_pct": 80}
			],
			"hr": {"status": "CONNECTED", "source": "strap", "battery_pct": 90}
		}
	}
	var rows_demo: Array = vm.rows(state_demo)
	_check(rows_demo.size() == 4, "scénario demo v1.1 : exactement 4 lignes")
	var all_ok := true
	for r in rows_demo:
		if r["level"] != "ok":
			all_ok = false
	_check(all_ok, "scénario demo v1.1 : les 4 lignes ont le niveau 'ok'")
	_check(rows_demo[0]["label"] == "Trainer HomeTrainer" and rows_demo[0]["status_text"] == "connecté", "trainer libellé et statut corrects")
	_check(rows_demo[1]["label"] == "Click +" and rows_demo[1]["status_text"] == "connecté, batterie 80 %", "click + libellé et statut corrects")
	_check(rows_demo[2]["label"] == "Click −" and rows_demo[2]["status_text"] == "connecté, batterie 80 %", "click − libellé et statut corrects")
	_check(rows_demo[3]["label"] == "Cardio" and rows_demo[3]["status_text"] == "ceinture", "cardio libellé et statut corrects")

	# 2. Trame v1 sans devices : 2 lignes, niveaux tirés de trainer_status et input_status
	var state_v1 := {
		"trainer_status": "CONNECTED",
		"input_status": "KEYBOARD"
	}
	var rows_v1: Array = vm.rows(state_v1)
	_check(rows_v1.size() == 2, "trame v1 sans devices : exactement 2 lignes")
	_check(rows_v1[0]["id"] == "trainer" and rows_v1[0]["level"] == "ok", "v1 : trainer level ok")
	_check(rows_v1[1]["id"] == "input" and rows_v1[1]["status_text"] == "clavier seul", "v1 : commandes clavier seul")

	var state_v1_lost := {
		"trainer_status": "LOST",
		"input_status": "LOST"
	}
	var rows_v1_lost: Array = vm.rows(state_v1_lost)
	_check(rows_v1_lost[0]["level"] == "error" and rows_v1_lost[1]["level"] == "error", "v1 perdu : niveaux error")

	# 3. Suite de trames : batterie 25, 19, 18, 9 % : exactement deux alertes (sous 20 %, sous 10 %)
	func_test_battery_alerts(vm)

	# 4. Boîtier « − » LOST puis CONNECTED : une alerte de perte, une de retour, rien entre les deux
	func_test_lost_reconnected_alerts(vm)

	# 5. ready_to_ride : trainer LOST refusé avec une raison ; Click absent accepté avec la raison « clavier seul »
	var st_ready := vm.ready_to_ride(state_demo)
	_check(st_ready["ok"] == true, "ready_to_ride : demo complet prêt")

	var st_trainer_lost := vm.ready_to_ride({
		"devices": {
			"trainer": {"name": "HomeTrainer", "status": "LOST"},
			"click": [{"side": "plus", "status": "CONNECTED", "battery_pct": 80}]
		}
	})
	_check(st_trainer_lost["ok"] == false, "ready_to_ride : trainer LOST refusé")
	_check(st_trainer_lost["reason"] != "", "ready_to_ride : raison fournie pour trainer LOST")

	var st_no_click := vm.ready_to_ride({
		"devices": {
			"trainer": {"name": "HomeTrainer", "status": "CONNECTED"},
			"click": []
		}
	})
	_check(st_no_click["ok"] == true, "ready_to_ride : Click absent accepté")
	_check("clavier seul" in st_no_click["reason"], "ready_to_ride : raison mentionne 'clavier seul'")

	# 6. Performance : aucun nœud créé
	var nodes_after := Performance.get_monitor(Performance.OBJECT_NODE_COUNT)
	_check(nodes_after == nodes_before, "aucun nœud créé (Performance.OBJECT_NODE_COUNT constant)")

	print("test_devices_view_model : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)


func func_test_battery_alerts(vm: RefCounted) -> void:
	var make_frame = func(bat: int) -> Dictionary:
		return {
			"devices": {
				"trainer": {"status": "CONNECTED"},
				"click": [{"side": "plus", "status": "CONNECTED", "battery_pct": bat}],
				"hr": {"status": "CONNECTED", "source": "strap"}
			}
		}

	var f25 = make_frame.call(25)
	var f19 = make_frame.call(19)
	var f18 = make_frame.call(18)
	var f9 = make_frame.call(9)

	var all_battery_alerts := []

	# 25 -> 19
	var a1 = vm.alerts(f25, f19)
	for a in a1:
		all_battery_alerts.append(a)

	# 19 -> 18
	var a2 = vm.alerts(f19, f18)
	for a in a2:
		all_battery_alerts.append(a)

	# 18 -> 9
	var a3 = vm.alerts(f18, f9)
	for a in a3:
		all_battery_alerts.append(a)

	_check(all_battery_alerts.size() == 2, "suite 25 -> 19 -> 18 -> 9 %% : exactement deux alertes")
	_check("< 20 %" in all_battery_alerts[0]["text"], "première alerte batterie sous 20 %")
	_check("< 10 %" in all_battery_alerts[1]["text"], "deuxième alerte batterie sous 10 %")


func func_test_lost_reconnected_alerts(vm: RefCounted) -> void:
	var make_click_minus = func(status: String) -> Dictionary:
		return {
			"devices": {
				"trainer": {"status": "CONNECTED"},
				"click": [{"side": "minus", "status": status, "battery_pct": 50}],
				"hr": {"status": "CONNECTED", "source": "strap"}
			}
		}

	var f_ok = make_click_minus.call("CONNECTED")
	var f_lost1 = make_click_minus.call("LOST")
	var f_lost2 = make_click_minus.call("LOST")
	var f_reconn = make_click_minus.call("CONNECTED")

	var al_lost1: Array = vm.alerts(f_ok, f_lost1)
	var al_lost2: Array = vm.alerts(f_lost1, f_lost2)
	var al_reconn: Array = vm.alerts(f_lost2, f_reconn)

	_check(al_lost1.size() == 1 and "perdu" in al_lost1[0]["text"], "boîtier − LOST : 1 alerte de perte")
	_check(al_lost2.is_empty(), "boîtier − toujours LOST : aucune alerte répétée")
	_check(al_reconn.size() == 1 and "reconnecté" in al_reconn[0]["text"], "boîtier − CONNECTED : 1 alerte de retour")
