extends RefCounted

## Salles reçues du core (lot R10) : réassemble les messages `room` en plusieurs parties (contrat 1.4), garde
## les salles par `room_id` et limite les demandes `rogue_resync` à une par seconde. Sans nœud. Pas de
## class_name : preload("res://scripts/rogue/room_store.gd").

const RESYNC_MIN_INTERVAL_S := 1.0
const MAX_ROOMS := 8        # une salle courante, la suivante et ses deux portes, plus quelques anciennes

var rooms: Dictionary = {}                 # room_id -> {archetype, variant, length_m, nominal_s, profile, markers, next}
var _parts: Dictionary = {}                # room_id -> {parts, got, profile, markers, head}
var _order: Array = []
var _last_resync_s := -INF
var resync_count := 0


## Ajoute une partie ; renvoie true quand la salle est complète (ou déjà connue).
func add_part(msg: Dictionary) -> bool:
	var rid := int(msg.get("room_id", -1))
	if rid < 0:
		return false
	var parts := maxi(int(msg.get("parts", 1)), 1)
	var part := int(msg.get("part", 1))
	if part < 1 or part > parts:
		return false
	var acc: Dictionary = _parts.get(rid, {"parts": parts, "got": {}, "head": msg})
	if int(acc["parts"]) != parts:
		acc = {"parts": parts, "got": {}, "head": msg}
	acc["got"][part] = {"profile": msg.get("profile", []), "markers": msg.get("markers", [])}
	if part == 1:
		acc["head"] = msg
	_parts[rid] = acc
	if acc["got"].size() < parts:
		return false
	var profile: Array = []
	var markers: Array = []
	for p in range(1, parts + 1):
		profile.append_array(acc["got"][p]["profile"])
		markers.append_array(acc["got"][p]["markers"])
	var head: Dictionary = acc["head"]
	rooms[rid] = {"archetype": str(head.get("archetype", "")), "variant": str(head.get("variant", "")),
		"length_m": float(head.get("length_m", 0.0)), "nominal_s": float(head.get("nominal_s", 0.0)),
		"profile": profile, "markers": markers, "next": head.get("next", null)}
	_parts.erase(rid)
	_order.erase(rid)
	_order.append(rid)
	while _order.size() > MAX_ROOMS:
		rooms.erase(_order.pop_front())
	return true


func has_room(room_id: int) -> bool:
	return rooms.has(room_id)


func room(room_id: int) -> Dictionary:
	return rooms.get(room_id, {})


## Vrai au plus une fois par seconde quand la salle `room_id` est inconnue : le temps `now_s` est celui de l'appelant.
func should_resync(room_id: int, now_s: float) -> bool:
	if room_id < 0 or rooms.has(room_id):
		return false
	if now_s - _last_resync_s < RESYNC_MIN_INTERVAL_S:
		return false
	_last_resync_s = now_s
	resync_count += 1
	return true


func clear() -> void:
	rooms.clear()
	_parts.clear()
	_order.clear()
	_last_resync_s = -INF
