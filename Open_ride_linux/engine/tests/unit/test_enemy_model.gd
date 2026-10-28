extends SceneTree

## Tests sans écran du modèle de pose des ennemis du Cyber-Rogue (lot R12) : distance selon les PV, fuite en
## fin de salle perdue, phase du boss, drapeaux par archétype, impacts rendus une fois.
## Lancement : godot --headless --path engine --script res://tests/unit/test_enemy_model.gd

const EnemyModel := preload("res://scripts/rogue/enemy_model.gd")

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
	var r := {"phase": "ROOM", "room_id": 7, "archetype": "puncheur", "boss_phase": null, "enemy_hp": 1000.0,
		"enemy_hp_max": 1000.0, "firewall_gap_m": 120.0, "windows": [], "hack": null, "events": []}
	r.merge(over, true)
	return r


func _run() -> void:
	var m = EnemyModel.new()
	m.update(null, 1, 0.0, 0.1)
	_check(not m.pose()["visible"], "sans objet rogue : ennemi caché")
	m.update(_rogue({"archetype": null, "phase": "WARMUP"}), 2, 0.0, 0.1)
	_check(not m.pose()["visible"], "échauffement : pas d'ennemi")

	m.update(_rogue(), 3, 0.0, 0.1)
	var p: Dictionary = m.pose()
	_check(p["visible"] and p["archetype"] == "puncheur" and is_equal_approx(p["distance_m"], 30.0), "arrivée à 30 m (pleins PV)")
	for i in 20:
		m.update(_rogue(), 4 + i, 0.0, 0.1)
	_check(is_equal_approx(m.pose()["distance_m"], 30.0), "pleins PV : 30 m devant le joueur")
	for i in 20:
		m.update(_rogue({"enemy_hp": 250.0}), 30 + i, 0.0, 0.1)
	_check(is_equal_approx(m.pose()["distance_m"], 52.5), "25 % de PV : recule à 52,5 m")
	m.update(_rogue({"enemy_hp": 250.0}), 80, 0.0, 0.1)
	_check(is_equal_approx(m.pose()["distance_m"], 52.5) and is_equal_approx(m.pose()["hp_frac"], 0.25), "distance stable à PV constants")

	# Fuite : salle perdue
	m.update(_rogue({"events": ["room_fled"]}), 90, 0.0, 0.5)
	p = m.pose()
	_check(p["state"] == "fleeing" and p["distance_m"] > 70.0 and p["alpha"] < 1.0, "salle perdue : l'ennemi s'éloigne et s'éteint")
	for i in 5:
		m.update(_rogue({"phase": "RECOVERY"}), 91 + i, 0.0, 0.5)
	p = m.pose()
	_check(is_equal_approx(p["alpha"], 0.0) and not p["visible"] or p["alpha"] == 0.0, "éteint après 2 s")
	m.update(_rogue({"room_id": 8, "phase": "ROOM"}), 100, 0.0, 0.1)
	_check(m.pose()["state"] == "hold" and is_equal_approx(m.pose()["alpha"], 1.0), "salle suivante : ennemi neuf")

	# Victoire : extinction sur place en 0,5 s
	var w = EnemyModel.new()
	w.update(_rogue({"events": ["room_won"], "enemy_hp": 0.0}), 1, 0.0, 0.3)
	_check(w.pose()["state"] == "dead" and w.pose()["alpha"] > 0.0, "victoire : s'éteint")
	w.update(_rogue({"phase": "CORRIDOR", "enemy_hp": 0.0}), 2, 0.0, 0.3)
	_check(is_equal_approx(w.pose()["alpha"], 0.0), "éteint en 0,5 s")

	# Boss
	var b = EnemyModel.new()
	b.update(_rogue({"archetype": "boss", "phase": "BOSS", "boss_phase": 1}), 1, 0.0, 0.1)
	_check(b.pose()["boss_effect"] == "locks", "boss phase 1 : verrous")
	b.update(_rogue({"archetype": "boss", "phase": "BOSS", "boss_phase": 2}), 2, 0.0, 0.1)
	_check(b.pose()["boss_effect"] == "shockwaves", "boss phase 2 : ondes de choc")
	b.update(_rogue({"archetype": "boss", "phase": "BOSS", "boss_phase": 3}), 3, 0.0, 0.1)
	_check(b.pose()["boss_effect"] == "scarlet" and b.pose()["boss_phase"] == 3, "boss phase 3 : rouge écarlate")

	# Drapeaux par archétype
	var f = EnemyModel.new()
	f.update(_rogue({"windows": [{"kind": "tunnel", "s_start": 0, "s_end": 1}, {"kind": "parry_zone", "s_start": 0, "s_end": 1}]}), 1, 0.0, 0.1)
	_check(f.pose()["charge"] and f.pose()["prelight"] and not f.pose()["scatter"], "fenêtres : charge et zone allumée")
	f.update(_rogue({"firewall_gap_m": 12.0, "hack": {"locked": true, "forced_gear": null, "until_s": 3.0},
		"windows": [{"kind": "purge", "s_start": 0, "s_end": 1}]}), 2, 0.0, 0.1)
	_check(f.pose()["cloaked"] and f.pose()["glitch"] and f.pose()["scatter"], "Firewall proche, piratage, purge")
	_check(f.pose()["swarm"] == 24, "essaim de 24 cubes")
	for i in 100:
		f.update(_rogue(), 10 + i, 12.0, 0.1)
	_check(is_equal_approx(f.pose()["lift_m"], 6.0), "pente de 12 % : la route est soulevée de 6 m")

	# Impacts
	var q = EnemyModel.new()
	q.update(_rogue({"events": ["hit", "crit"]}), 1, 0.0, 0.1)
	q.update(_rogue({"events": ["hit", "crit"]}), 1, 0.0, 0.1)
	var imp: Array = q.take_impacts()
	_check(imp.size() == 2 and imp[0]["crit"] == false and imp[1]["crit"] == true and is_equal_approx(imp[0]["flash_s"], 0.1), "deux impacts, le critique plus gros, une seule fois")
	_check(q.take_impacts().is_empty(), "file vidée")
	q.update(_rogue({"events": ["hit"]}), 2, 0.0, 0.1, false)
	_check(q.take_impacts().is_empty() and not q.pose()["effects"], "budget d'images non tenu : plus d'impacts")

	print("test_enemy_model : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
