extends RefCounted

## Fichiers d'entraînement du menu ERG (lot N16) : enregistrement d'un entraînement créé et import
## d'un fichier `.zwo`, `.erg` ou `.mrc` dans le dossier des entraînements (~/OpenRide/Workouts/,
## le même que celui du core ; option --workouts-dir de l'engine, engine_args.gd).
##
## Import au Click, sans boîte de dialogue : `candidates()` liste les fichiers d'entraînement des
## dossiers habituels (SOURCES, sans sous-dossiers), les plus récents d'abord. Le core relit le
## dossier à la demande `list_workouts` : un fichier invalide y apparaît avec son erreur.
## Pas de class_name : charger par preload("res://scripts/workout_files.gd").

const SUFFIXES := ["zwo", "erg", "mrc"]
## Dossiers fouillés pour l'import, relatifs au dossier personnel, avec le nom affiché.
const SOURCES := [
	["Téléchargements", "Téléchargements"], ["Downloads", "Téléchargements"], ["Bureau", "Bureau"],
	["Desktop", "Bureau"], ["OpenRide/Import", "OpenRide/Import"], ["", "Dossier personnel"]]
const MAX_CANDIDATES := 30


## Écrit `<dossier>/<id>.zwo` ; renvoie "" ou le message d'erreur.
static func save(directory: String, workout_id: String, content: String) -> String:
	var err := DirAccess.make_dir_recursive_absolute(directory)
	if err != OK:
		return "dossier %s impossible à créer (%s)" % [directory, error_string(err)]
	var f := FileAccess.open(directory.path_join(workout_id + ".zwo"), FileAccess.WRITE)
	if f == null:
		return "écriture impossible (%s)" % error_string(FileAccess.get_open_error())
	f.store_string(content)
	f.close()
	return ""


## Fichiers importables : [{path, file, source, imported}], les plus récents d'abord. `imported` : un
## fichier du même nom est déjà dans le dossier des entraînements.
static func candidates(home: String, workouts_dir: String) -> Array:
	var found: Array = []
	var seen := {}
	for src in SOURCES:
		var dir_path: String = home.path_join(src[0]) if src[0] != "" else home
		var d := DirAccess.open(dir_path)
		if d == null:
			continue
		for name in d.get_files():
			var path := dir_path.path_join(name)
			if not name.get_extension().to_lower() in SUFFIXES or seen.has(path):
				continue
			seen[path] = true
			found.append({"path": path, "file": name, "source": src[1],
				"imported": FileAccess.file_exists(workouts_dir.path_join(name)),
				"mtime": FileAccess.get_modified_time(path)})
	found.sort_custom(func(a, b): return a["mtime"] > b["mtime"] or (a["mtime"] == b["mtime"] and a["file"] < b["file"]))
	return found.slice(0, MAX_CANDIDATES)


## Identifiant déjà pris, quelle que soit l'extension (le core préfère .zwo, puis .erg, puis .mrc).
static func _id_taken(workouts_dir: String, workout_id: String) -> bool:
	for suffix in SUFFIXES:
		if FileAccess.file_exists(workouts_dir.path_join(workout_id + "." + suffix)):
			return true
	return false


## Copie un fichier dans le dossier des entraînements ; renvoie {id} ou {error}. Un entraînement différent
## du même nom (toute extension) n'est pas écrasé : la copie prend le suffixe « _2 », « _3 »…
static func import_file(path: String, workouts_dir: String) -> Dictionary:
	if not FileAccess.file_exists(path):
		return {"error": "fichier introuvable : " + path.get_file()}
	var err := DirAccess.make_dir_recursive_absolute(workouts_dir)
	if err != OK:
		return {"error": "dossier %s impossible à créer (%s)" % [workouts_dir, error_string(err)]}
	var stem := path.get_file().get_basename()
	var ext := path.get_extension().to_lower()
	var target_id := stem
	var n := 1
	while true:
		var target := workouts_dir.path_join(target_id + "." + ext)
		if FileAccess.file_exists(target) and FileAccess.get_md5(target) == FileAccess.get_md5(path):
			return {"id": target_id}   # déjà importé, identique
		if not _id_taken(workouts_dir, target_id):
			break
		n += 1
		target_id = "%s_%d" % [stem, n]
	err = DirAccess.copy_absolute(path, workouts_dir.path_join(target_id + "." + ext))
	if err != OK:
		return {"error": "copie impossible (%s)" % error_string(err)}
	return {"id": target_id}
