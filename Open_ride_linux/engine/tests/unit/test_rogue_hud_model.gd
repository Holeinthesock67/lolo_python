extends SceneTree

## Tests sans écran du modèle du HUD diégétique du Cyber-Rogue (lot R11) : vitesse « 01 » à « 12 », watts en
## % de FTP, arcs, W'bal, ennemi, Firewall, couloir, piratage, lissage sur 0,3 s et événements rendus une fois.
## Lancement : godot --headless --path engine --script res://tests/unit/test_rogue_hud_model.gd

const HudView := preload("res://scripts/rogue/rogue_hud_view.gd")
const HudModel := preload("res://scripts/rogue/rogue_hud_model.gd")

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


func _state(seq: int, rogue_over: Dictionary = {}, over: Dictionary = {}) -> Dictionary:
	var rogue := {"phase": "ROOM", "room_id": 7, "room_index": 3, "rooms_total": 9, "archetype": "puncheur",
		"boss_phase": null, "s_room": 812.5, "enemy_hp": 640.0, "enemy_hp_max": 1000.0, "shield": 40.0,
		"shield_max": 100.0, "adrenaline": 65.0, "w_bal_j": 15000.0, "w_prime_j": 20000.0, "posture": "FLUIDE",
		"firewall_gap_m": 120.5, "gold": 85, "windows": [], "hack": null, "overheat": false,
		"loot_focus": null, "events": []}
	rogue.merge(rogue_over, true)
	var st := {"type": "state", "seq": seq, "power_3s": 250.0, "cadence": 88.0, "gear": 5, "rogue": rogue}
	st.merge(over, true)
	return st


func _run() -> void:
	var m = HudModel.new()
	m.set_ftp(250.0)
	m.update({"type": "state", "seq": 1, "power_3s": 200.0}, 0.0)
	_check(not m.is_active() and m.values().is_empty(), "trame sans rogue : modèle vide")
	m.update(_state(2), 1.0)
	var v: Dictionary = m.values()
	_check(m.is_active() and v["gear_text"] == "05", "vitesse engagée « 05 »")
	_check(v["power_pct_text"] == "100 %", "watts en % de FTP")
	_check(v["cadence_text"] == "88" and v["posture"] == "FLUIDE" and v["posture_token"] == "neutral", "cadence et posture")
	_check(is_equal_approx(v["shield_frac"], 0.4) and is_equal_approx(v["adrenaline_frac"], 0.65), "arcs bouclier et adrénaline")
	_check(is_equal_approx(v["adrenaline_z_mark"], 0.5) and v["z_ready"], "seuil de l'attaque Z")
	_check(is_equal_approx(v["wbal_pct"], 75.0) and not v["wbal_low"], "W'bal 75 %")
	_check(is_equal_approx(v["enemy_pct"], 64.0) and v["has_enemy"], "PV de l'ennemi 64 %")
	_check(not v["firewall_danger"] and v["room_text"] == "3/9" and v["gold"] == 85, "Firewall loin, salle et or")
	_check(v["corridor"].is_empty() and v["hack"].is_empty(), "hors couloir et sans piratage")

	m.update(_state(3, {"w_bal_j": 4000.0, "firewall_gap_m": 12.0, "adrenaline": 30.0}, {"gear": 12}), 1.0)
	v = m.values()
	_check(v["gear_text"] == "12", "vitesse immédiate « 12 »")
	_check(is_equal_approx(v["wbal_pct"], 75.0) and is_equal_approx(v["firewall_gap_m"], 120.5), "dt = 0 : valeurs lissées inchangées")
	m.update(_state(4, {"w_bal_j": 4000.0, "firewall_gap_m": 12.0, "adrenaline": 30.0}), 1.15)
	v = m.values()
	_check(v["wbal_pct"] < 75.0 and v["wbal_pct"] > 20.0, "lissage à mi-chemin après 0,15 s")
	m.update(_state(5, {"w_bal_j": 4000.0, "firewall_gap_m": 12.0, "adrenaline": 30.0}), 1.5)
	v = m.values()
	_check(is_equal_approx(v["wbal_pct"], 20.0) and v["wbal_low"], "W'bal 20 % atteint en 0,3 s, rouge")
	_check(v["firewall_danger"] and not v["z_ready"], "Firewall à 12 m rouge, adrénaline sous Z")

	# Événements : une seule fois, même si la trame (même seq) est renvoyée.
	m.take_events()
	var ev := _state(6, {"events": ["perfect_shift", "hit"]})
	m.update(ev, 2.0)
	m.update(ev, 2.03)
	m.update(ev, 2.06)
	var got: Array = m.take_events()
	_check(got == ["perfect_shift", "hit"], "événements rendus une fois pour trois trames identiques")
	_check(m.take_events().is_empty(), "file vidée après lecture")
	m.update(_state(7, {"events": ["crit"]}), 2.1)
	_check(m.take_events() == ["crit"], "nouvelle trame, nouvel événement")

	# Couloir et piratage.
	m.set_loot({"cards": [{"id": "a"}, {"id": "b"}, {"id": "c"}], "doors": [{"side": "left"}, {"side": "right"}],
		"reroll_cost": 100, "gold": 85})
	m.update(_state(8, {"phase": "CORRIDOR", "loot_focus": 1, "hack": {"locked": true, "forced_gear": 3, "until_s": 4.5}}), 2.2)
	v = m.values()
	_check(v["corridor"]["cards"].size() == 3 and v["corridor"]["doors"].size() == 2 and v["corridor"]["focus"] == 1, "couloir : 3 cartes, 2 portes, sélection")
	_check(v["corridor"]["reroll_cost"] == 100 and not v["corridor"]["can_reroll"], "relance trop chère pour 85 d'or")
	_check(v["hack"]["locked"] and v["hack"]["forced_gear"] == 3 and is_equal_approx(v["hack"]["until_s"], 4.5), "piratage : pignon imposé et durée")

	# Cas limites : FTP inconnue, bouclier nul, ennemi absent.
	var m2 = HudModel.new()
	m2.update(_state(1, {"shield_max": 0.0, "enemy_hp_max": 0.0, "w_prime_j": 0.0}), 0.0)
	v = m2.values()
	_check(v["power_pct_text"] == "0 %" and v["shield_frac"] == 0.0 and not v["has_enemy"] and v["wbal_pct"] == 0.0, "FTP inconnue, divisions par zéro évitées")

	# Arcs au sol : vide à 0, demi-cercle à 1, côté gauche en x négatif, côté droit en x positif.
	_check(HudView.arc_mesh(0.0, -1).get_surface_count() == 0, "arc vide à 0 %")
	var left: ArrayMesh = HudView.arc_mesh(1.0, -1)
	var right: ArrayMesh = HudView.arc_mesh(1.0, 1)
	var lv: PackedVector3Array = left.surface_get_arrays(0)[Mesh.ARRAY_VERTEX]
	var rv: PackedVector3Array = right.surface_get_arrays(0)[Mesh.ARRAY_VERTEX]
	_check(lv[lv.size() - 1].x < -1.0 and rv[rv.size() - 1].x > 1.0, "arc gauche à gauche, arc droit à droite")
	_check(absf(lv[0].length() - 1.56) < 0.01, "rayon de l'arc : 1,5 m")

	print("test_rogue_hud_model : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
