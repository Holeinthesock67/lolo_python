extends RefCounted

## Arguments de l'engine, lus après `--` sur la ligne de commande (OS.get_cmdline_user_args()).
##
##   --ipc-state-port=5005    port d'écoute des trames du core
##   --ipc-cmd-port=5006      port du core vers lequel partent hello, heartbeat, cmd, bye
##   --routes-dir=CHEMIN      dossier des parcours (défaut : ~/.local/share/openride/routes)
##   --quality=low|medium|high préréglage de qualité graphique (défaut : low, lot L4)
##   --theme=NOM              thème visuel actif (défaut : default, lot L4)
##   --workouts-dir=CHEMIN    dossier des entraînements (défaut : ~/OpenRide/Workouts, lot N16)
##   --sim-session            session simulée (lanceur, code 65) : l'accueil propose de revenir au matériel
##   --test-mode              journal « [test] clé=valeur » et messages de test (engine/tests/README.md)
## Pas de class_name : la scène est lancée sans passer par l'éditeur (charger par preload).

const DEFAULT_STATE_PORT := 5005
const DEFAULT_CMD_PORT := 5006
const DEFAULT_QUALITY := "low"
const DEFAULT_THEME := "default"
const VALID_QUALITIES := ["low", "medium", "high"]

static var last_error := ""


static func _home() -> String:
	return OS.get_environment("HOME")


static func default_workouts_dir() -> String:
	return _home().path_join("OpenRide/Workouts")


static func default_routes_dir() -> String:
	return _home().path_join(".local/share/openride/routes")


## Renvoie {state_port, cmd_port, routes_dir, workouts_dir, quality, theme, test_mode, sim_session}, avec les valeurs par défaut pour ce qui manque.
static func parse(args: PackedStringArray) -> Dictionary:
	last_error = ""
	var out := {
		"state_port": DEFAULT_STATE_PORT,
		"cmd_port": DEFAULT_CMD_PORT,
		"routes_dir": default_routes_dir(),
		"workouts_dir": default_workouts_dir(),
		"quality": DEFAULT_QUALITY,
		"theme": DEFAULT_THEME,
		"test_mode": false,
		"sim_session": false,
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
		elif arg.begins_with("--workouts-dir="):
			var wpath := arg.get_slice("=", 1)
			if wpath.begins_with("~"):
				wpath = _home() + wpath.substr(1)
			out["workouts_dir"] = wpath
		elif arg.begins_with("--quality="):
			out["quality"] = _quality(arg, DEFAULT_QUALITY)
		elif arg.begins_with("--theme="):
			out["theme"] = _theme(arg, DEFAULT_THEME)
		elif arg == "--test-mode":
			out["test_mode"] = true
		elif arg == "--sim-session":
			out["sim_session"] = true
	return out


static func _port(arg: String, fallback: int) -> int:
	var text := arg.get_slice("=", 1)
	if not text.is_valid_int() or int(text) < 1 or int(text) > 65535:
		last_error = "Argument ignoré (port invalide) : " + arg
		printerr("Argument ignoré (port invalide) : ", arg)
		return fallback
	return int(text)


static func _quality(arg: String, fallback: String) -> String:
	var val := arg.get_slice("=", 1).strip_edges()
	if not (val in VALID_QUALITIES):
		last_error = "Argument ignoré (qualité invalide) : " + arg
		printerr("Argument ignoré (qualité invalide) : ", arg)
		return fallback
	return val


static func _theme(arg: String, fallback: String) -> String:
	var val := arg.get_slice("=", 1).strip_edges()
	if val.is_empty():
		last_error = "Argument ignoré (thème vide) : " + arg
		printerr("Argument ignoré (thème vide) : ", arg)
		return fallback
	return val


static func current() -> Dictionary:
	return parse(OS.get_cmdline_user_args())
