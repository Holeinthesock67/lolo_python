extends SceneTree

## Tests sans écran du magasin de salles du Cyber-Rogue (lot R10) : messages en plusieurs parties, salle
## inconnue, demande de resynchronisation au plus une fois par seconde, nombre de salles gardées.
## Lancement : godot --headless --path engine --script res://tests/unit/test_room_store.gd

const RoomStore := preload("res://scripts/rogue/room_store.gd")

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


func _msg(rid: int, part: int = 1, parts: int = 1, n: int = 3) -> Dictionary:
	var prof: Array = []
	for i in n:
		prof.append([(part - 1) * 100.0 + i * 10.0, 2.0])
	return {"type": "room", "v": 1, "room_id": rid, "part": part, "parts": parts, "archetype": "diesel",
		"variant": "", "length_m": 300.0, "nominal_s": 60.0, "profile": prof,
		"markers": [{"kind": "arch", "s_m": 50.0 * part, "len_m": 10.0, "param": null}], "next": null}


func _run() -> void:
	var st = RoomStore.new()
	_check(st.add_part(_msg(1)) and st.has_room(1), "salle en une partie : complète")
	_check(st.room(1)["profile"].size() == 3 and st.room(1)["archetype"] == "diesel", "contenu de la salle")
	_check(not st.add_part(_msg(2, 2, 3)), "partie 2 sur 3 seule : incomplète")
	_check(not st.has_room(2), "salle incomplète inconnue")
	_check(not st.add_part(_msg(2, 1, 3)), "parties 1 et 2 sur 3 : incomplète")
	_check(st.add_part(_msg(2, 3, 3)), "les trois parties (dans le désordre) : complète")
	_check(st.room(2)["profile"].size() == 9 and st.room(2)["markers"].size() == 3, "profil et marqueurs réunis (%d points)" % st.room(2)["profile"].size())
	_check(not st.add_part({"room_id": -1}), "room_id invalide refusé")
	_check(not st.add_part(_msg(5, 4, 3)), "numéro de partie hors bornes refusé")
	# resynchronisation
	_check(not st.should_resync(1, 10.0), "salle connue : pas de demande")
	_check(st.should_resync(99, 10.0), "salle inconnue : demande")
	_check(not st.should_resync(99, 10.5), "0,5 s plus tard : pas de seconde demande")
	_check(st.should_resync(99, 11.1), "1,1 s plus tard : nouvelle demande")
	_check(st.resync_count == 2, "deux demandes comptées")
	_check(not st.should_resync(-1, 50.0), "room_id négatif : jamais de demande")
	# plafond de salles gardées
	for rid in range(100, 100 + RoomStore.MAX_ROOMS + 3):
		st.add_part(_msg(rid))
	_check(st.rooms.size() == RoomStore.MAX_ROOMS, "au plus %d salles gardées (%d)" % [RoomStore.MAX_ROOMS, st.rooms.size()])
	_check(st.has_room(100 + RoomStore.MAX_ROOMS + 2) and not st.has_room(100), "les plus anciennes sont oubliées")
	st.clear()
	_check(st.rooms.is_empty() and st.should_resync(7, 0.0), "clear : tout oublié, demande possible aussitôt")
	await process_frame
	print("test_room_store : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
