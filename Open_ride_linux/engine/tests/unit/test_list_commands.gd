extends SceneTree

## Tests unitaires sans écran des listes relancées par le client IPC (lot NT2, `ipc_client.gd`) :
## main.gd tait le bandeau « sans réponse du core » pour ces listes seulement ; l'import de fichiers
## (list_imports) est retiré en révision 1.15 et ne doit plus y figurer.
## Lancement : godot --headless --path engine --script res://tests/unit/test_list_commands.gd

const IpcClientScript := preload("res://scripts/ipc_client.gd")

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _run() -> void:
	var names: Array[String] = IpcClientScript.LIST_COMMANDS
	_check(names == ["list_routes", "list_workouts", "list_route_imports"], "listes relancées : %s" % [names])
	_check(not names.has("list_imports"), "list_imports retirée (révision 1.15)")
	var c = IpcClientScript.new()   # sans _ready : aucun port ouvert
	for n in names:
		_check(c.has_method(n), "méthode %s() du client pour chaque liste" % n)
	c.free()
	var main_src := FileAccess.get_file_as_string("res://scripts/main.gd")
	_check(not main_src.contains("\"list_imports\""), "main.gd ne cite plus list_imports")
	_check(main_src.contains("cmd_name in IpcClientScript.LIST_COMMANDS"), "_on_command_failed lit la liste du client")


func _initialize() -> void:
	_run()
	print("test_list_commands : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
