extends SceneTree

## Lot P32 : véhicules, cyclistes du décor et un bot ensemble sur 30 km, graines 1 à 8 ; les graines
## 9 à 16 sont dans test_traffic_mixed_b.gd. Sorti de test_traffic_model.gd le 27 novembre (95 s sur 120 s de
## délai en CI, dont 80 % pour cette séance) ; mêmes contrôles, sur chaque moitié.
## Lancement : godot --headless --path engine --script res://tests/unit/test_traffic_mixed_a.gd

const Ride := preload("res://tests/traffic_test_ride.gd")

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


func _run() -> void:
	var route = Ride.route()
	var mixed := {"hits": 0, "hit_vehicles": 0, "hit_cyclists": 0, "close_pass": 0, "met": 0, "waited": 0, "spawned": 0, "groups": 0}
	for sd in range(1, 9):
		var rm: Dictionary = Ride.ride_mixed(route, sd)
		for key in mixed:
			mixed[key] = int(mixed[key]) + int(rm[key])
	print("véhicules et cyclistes ensemble, graines %s : %s" % [str(range(1, 9)), str(mixed)])
	_check(mixed["met"] > 0 and mixed["hits"] == 0, "jamais un véhicule sur un cycliste du décor ou le bot (%d croisements)" % mixed["met"])
	_check(mixed["hit_vehicles"] == 0, "jamais deux véhicules l'un sur l'autre, cyclistes du décor présents")
	_check(mixed["hit_cyclists"] == 0, "jamais deux cyclistes l'un sur l'autre (décor, cycliste, bot) (%d)" % mixed["hit_cyclists"])
	_check(mixed["close_pass"] == 0, "cyclistes du décor et bot doublés à 1,5 m au moins (%d écarts)" % mixed["close_pass"])
	print("test_traffic_mixed_a : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
