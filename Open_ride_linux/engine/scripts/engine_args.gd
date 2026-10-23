extends RefCounted

## Arguments de l'engine, lus après `--` sur la ligne de commande (OS.get_cmdline_user_args()).
##
##   --ipc-state-port=5005    port d'écoute des trames du core
##   --ipc-cmd-port=5006      port du core vers lequel partent hello, heartbeat, cmd, bye
##   --routes-dir=CHEMIN      dossier des parcours (défaut : ~/.local/share/openride/routes)
##   --test-mode              journal « [test] clé=valeur » et messages de test (engine/tests/README.md)
## Pas de class_name : la scène est lancée sans passer par l'éditeur (charger par preload).

const DEFAULT_STATE_PORT := 5005
const DEFAULT_CMD_PORT := 5006


static func _home() -> String:
	return OS.get_environment("HOME")


static func default_routes_dir() -> String:
	return _home().path_join(".local/share/openride/routes")


## Renvoie {state_port, cmd_port, routes_dir, test_mode}, avec les valeurs par défaut pour ce qui manque.
static func parse(args: PackedStringArray) -> Dictionary:
	var out := {
		"state_port": DEFAULT_STATE_PORT,
		"cmd_port": DEFAULT_CMD_PORT,
		"routes_dir": default_routes_dir(),
		"test_mode": false,
	}
	for arg in args:
		if arg.begins_with("--ipc-state-port="):
			out["state_port"] = _port(arg, DEFAULT_STATE_PORT)
		elif arg.begins_with("--ipc-cmd-port="):
			out["cmd_port"] = _port(arg, DEFAULT_CMD_PORT)
		elif arg.begins_with("--routes-dir="):
			var path := arg.get_slice("=", 1)
			if path.begins_with("~"):
				path = _home() + path.substr(1)
			out["routes_dir"] = path
		elif arg == "--test-mode":
			out["test_mode"] = true
	return out


static func _port(arg: String, fallback: int) -> int:
	var text := arg.get_slice("=", 1)
	if not text.is_valid_int() or int(text) < 1 or int(text) > 65535:
		printerr("Argument ignoré (port invalide) : ", arg)
		return fallback
	return int(text)


static func current() -> Dictionary:
	return parse(OS.get_cmdline_user_args())
