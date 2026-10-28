extends SceneTree

## Tests sans écran de l'hôte de la scène du Cyber-Rogue (lot R10) : la scène apparaît quand `mode` vaut
## « ROGUE » et masque le monde classique ; une salle inconnue demande une resynchronisation (une fois par
## seconde) ; la salle reçue construit le ruban, les repères et le Firewall ; la sortie rend le monde
## classique intact (visibilité, environnement, caméra).
## Lancement : godot --headless --path engine --script res://tests/unit/test_rogue_host.gd

const Host := preload("res://scripts/rogue/rogue_host.gd")

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


func _rogue(phase: String, room_id: int, s: float, gap: float = 100.0, windows: Array = []) -> Dictionary:
	return {"phase": phase, "room_id": room_id, "room_index": 1, "rooms_total": 4, "archetype": "diesel",
		"boss_phase": null, "s_room": s, "enemy_hp": 100.0, "enemy_hp_max": 100.0, "shield": 50.0, "shield_max": 50.0,
		"adrenaline": 0.0, "w_bal_j": 0.0, "w_prime_j": 20000.0, "posture": "FLUIDE", "firewall_gap_m": gap,
		"gold": 0, "windows": windows, "hack": null, "overheat": false, "loot_focus": null, "events": []}


func _room_msg(rid: int) -> Dictionary:
	var prof: Array = []
	for i in 30:
		prof.append([i * 10.0, 3.0 if i < 15 else 7.0])
	return {"type": "room", "v": 1, "room_id": rid, "part": 1, "parts": 1, "archetype": "diesel", "variant": "",
		"length_m": 300.0, "nominal_s": 60.0, "profile": prof,
		"markers": [{"kind": "arch", "s_m": 100.0, "len_m": 10.0, "param": null},
			{"kind": "tunnel", "s_m": 150.0, "len_m": 50.0, "param": null}], "next": null}


func _run() -> void:
	var main := Node3D.new()
	root.add_child(main)
	var terrain := Node3D.new()
	var sun := DirectionalLight3D.new()
	var cam := Camera3D.new()
	var we := WorldEnvironment.new()
	var classic_env := Environment.new()
	we.environment = classic_env
	for n in [terrain, sun, cam, we]:
		main.add_child(n)
	cam.make_current()
	var host = Host.new()
	var classic := [terrain, sun, null]
	var sim := {"mode": "SIM", "rogue": null}
	_check(not host.update(sim, main, classic, we, cam, "low", 0.0) and not host.is_active(), "mode SIM : pas de scène du Cyber-Rogue")
	_check(terrain.visible and sun.visible and cam.current, "monde classique visible")
	# entrée en mode ROGUE sans salle connue
	var st := {"mode": "ROGUE", "rogue": _rogue("ROOM", 5, 20.0)}
	var wanted: bool = host.update(st, main, classic, we, cam, "low", 100.0)
	_check(host.is_active() and wanted, "mode ROGUE : scène créée et salle inconnue demandée")
	_check(not terrain.visible and not sun.visible, "monde classique masqué")
	_check(we.environment != classic_env and we.environment.glow_enabled, "environnement néon en place")
	_check(not cam.current and host.scene.camera.current, "la caméra de la scène est la caméra courante")
	_check(not host.scene.ribbon.visible, "pas de ruban tant que la salle est inconnue")
	_check(not host.update(st, main, classic, we, cam, "low", 100.4), "0,4 s plus tard : pas de seconde demande")
	_check(host.update(st, main, classic, we, cam, "low", 101.2), "1,2 s plus tard : nouvelle demande")
	_check(host.resync_requests == 2, "deux demandes comptées")
	# la salle arrive
	host.on_room(_room_msg(5))
	var windows := [{"kind": "arch", "s_start": 95.0, "s_end": 115.0}]
	host.update({"mode": "ROGUE", "rogue": _rogue("ROOM", 5, 120.0, 80.0, windows)}, main, classic, we, cam, "low", 102.0)
	var sc = host.scene
	_check(sc.ribbon.visible and sc.ribbon.mesh != null, "ruban construit depuis la salle")
	_check(sc.markers.size() == 2, "deux repères posés")
	_check(sc.markers[0]["node"].scale.x > 1.0 and is_equal_approx(sc.markers[1]["node"].scale.x, 1.0),
		"seule l'arche a sa fenêtre active")
	_check(is_equal_approx(sc.markers[0]["node"].position.z, -105.0), "arche à 105 m (z = −105)")
	_check(sc.firewall.visible and is_equal_approx(sc.firewall.position.z, -(sc._s_disp - 80.0)), "Firewall à 80 m derrière le joueur")
	_check(sc.ribbon_y(150.0) > sc.ribbon_y(50.0), "le ruban monte")
	# échauffement : pas de ruban
	host.update({"mode": "ROGUE", "rogue": _rogue("WARMUP", 0, 0.0)}, main, classic, we, cam, "low", 103.0)
	_check(not sc.ribbon.visible and not sc.firewall.visible, "échauffement : ni ruban ni Firewall")
	# sortie
	host.update({"mode": "SIM", "rogue": null}, main, classic, we, cam, "low", 104.0)
	await process_frame
	_check(not host.is_active(), "retour au mode SIM : scène libérée")
	_check(terrain.visible and sun.visible, "monde classique de nouveau visible")
	_check(we.environment == classic_env, "environnement classique rendu")
	_check(cam.current, "caméra classique de nouveau courante")
	_check(host.store.rooms.is_empty(), "salles oubliées à la sortie")
	main.queue_free()
	await process_frame
	print("test_rogue_host : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
