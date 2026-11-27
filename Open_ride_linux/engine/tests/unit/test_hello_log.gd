extends SceneTree

## Journal du hello_ack (revue E1-07) : seules les clés sûres de la configuration sont écrites avec leur valeur ;
## le dernier départ du monde ouvert, la FTP, le profil et les dossiers ne sont nommés que par leur clé.
## Lancement : godot --headless --path engine --script res://tests/unit/test_hello_log.gd

const IpcClientScript := preload("res://scripts/ipc_client.gd")

var _failures := 0


func _init() -> void:
	call_deferred("_run")


func _check(cond: bool, msg: String) -> void:
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _run() -> void:
	var cfg := {
		"gears_total": 24, "theme": "default", "difficulty_pct": 50, "ftp_w": 250,
		"open_world_dir": "/home/fictif/OpenRide/Cache/monde",
		"profile": {"id": "principal", "name": "Cycliste fictif"},
		"last_choices": {"open_world": {"lat": 12.34567, "lon": 98.76543}},
	}
	var line: String = IpcClientScript.hello_config_log(cfg)
	_check(line.contains("\"gears_total\":24"), "nombre de braquets écrit : " + line)
	_check(not line.contains("12.34") and not line.contains("98.76"), "aucune position du dernier départ")
	_check(not line.contains("250"), "FTP non écrite")
	_check(not line.contains("fictif"), "ni nom du profil ni dossier personnel")
	_check(line.contains("autres clés : ftp_w, last_choices, open_world_dir, profile"), "autres clés nommées")
	var pub: Dictionary = IpcClientScript.hello_config_public(cfg)
	_check(pub.keys().size() == 3 and pub.has("theme"), "configuration publique du journal de test")
	_check(IpcClientScript.hello_config_log({}).ends_with("autres clés : aucune"), "configuration vide")
	quit(1 if _failures > 0 else 0)
