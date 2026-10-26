extends SceneTree

## Tests sans écran du sous-menu ERG (Lot N16) : création d'intervalles `workout_builder.gd` et
## fichiers `workout_files.gd` (enregistrement, fichiers proposés à l'import, copie sans écraser).
## Lancement : godot --headless --path engine --script res://tests/unit/test_workout_builder.gd

const WorkoutBuilder := preload("res://scripts/workout_builder.gd")
const WorkoutFiles := preload("res://scripts/workout_files.gd")

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _write(path: String, text: String) -> void:
	var f := FileAccess.open(path, FileAccess.WRITE)
	f.store_string(text)
	f.close()


func _init() -> void:
	_test_builder()
	_test_files()
	print("test_workout_builder : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)


func _test_builder() -> void:
	var b = WorkoutBuilder.new()
	_check(b.duration_s() == 10 * 60 + 5 * (240 + 180) + 10 * 60, "durée par défaut : 10 + 5 × 7 + 10 min")
	_check(b.workout_name() == "Intervalles 5 × 4 min à 105 %", "nom : " + b.workout_name())
	_check(b.workout_id() == "intervalles_5x240s_105", "identifiant : " + b.workout_id())
	var items: Array = b.menu_items()
	_check(items.size() == 8 and items[-1]["id"] == "save", "sept paramètres puis « Enregistrer et choisir »")
	_check(items[0]["label"] == "Échauffement : 10 min", "libellé : " + items[0]["label"])
	_check(items[3]["label"] == "Puissance de l'effort : 105 % de la FTP", "libellé : " + items[3]["label"])
	_check(str(items[-1]["detail"]).ends_with("55 min"), "détail : " + str(items[-1]["detail"]))
	_check(WorkoutBuilder.format_duration(270) == "4 min 30 s" and WorkoutBuilder.format_duration(45) == "45 s",
		"durées lisibles")
	# Bornes.
	_check(b.set_value("reps", 99) and b.values["reps"] == 20, "répétitions bornées à 20")
	_check(b.set_value("on_pct", 10) and b.values["on_pct"] == 50, "puissance bornée à 50 %")
	_check(not b.set_value("inconnu", 3), "clé inconnue refusée")
	b.reset()
	# Paramètre pour l'écran de modification (clé préfixée, format gardé).
	var e: Dictionary = b.edit_item("on_s")
	_check(e["key"] == "workout.on_s" and e["step"] == 15 and e["format"] == "s", "paramètre à modifier : workout.on_s")
	# Fichier .zwo.
	var zwo: String = b.to_zwo()
	_check(zwo.contains("<name>Intervalles 5 × 4 min à 105 %</name>"), "zwo : nom")
	_check(zwo.contains("<Warmup Duration=\"600\""), "zwo : échauffement de 600 s")
	_check(zwo.contains("<IntervalsT Repeat=\"5\" OnDuration=\"240\" OffDuration=\"180\" OnPower=\"1.05\" OffPower=\"0.55\"/>"),
		"zwo : intervalles")
	_check(zwo.contains("<Cooldown Duration=\"600\""), "zwo : retour au calme")
	b.set_value("warmup_min", 0)
	b.set_value("cooldown_min", 0)
	_check(not b.to_zwo().contains("Warmup") and not b.to_zwo().contains("Cooldown"), "sans échauffement ni retour au calme")
	var xml := XMLParser.new()
	_check(xml.open_buffer(b.to_zwo().to_utf8_buffer()) == OK, "zwo lisible en XML")


func _test_files() -> void:
	var base := OS.get_cache_dir().path_join("openride_test_workouts_%d" % Time.get_ticks_usec())
	var home := base.path_join("home")
	var wdir := home.path_join("OpenRide/Workouts")
	DirAccess.make_dir_recursive_absolute(home.path_join("Téléchargements"))
	DirAccess.make_dir_recursive_absolute(home.path_join("OpenRide/Import"))
	# Enregistrement (dossier créé au besoin).
	var b = WorkoutBuilder.new()
	_check(WorkoutFiles.save(wdir, b.workout_id(), b.to_zwo()) == "", "entraînement créé enregistré")
	_check(FileAccess.file_exists(wdir.path_join("intervalles_5x240s_105.zwo")), "fichier intervalles_5x240s_105.zwo")
	# Fichiers proposés : extensions reconnues seulement, dossier source indiqué.
	_write(home.path_join("Téléchargements/seuil.zwo"), "<workout_file/>")
	_write(home.path_join("Téléchargements/notes.txt"), "rien")
	_write(home.path_join("OpenRide/Import/sortie.erg"), "[COURSE HEADER]")
	_write(home.path_join("plan.MRC"), "[COURSE HEADER]")
	var found: Array = WorkoutFiles.candidates(home, wdir)
	var names := []
	for c in found:
		names.append(c["file"])
	names.sort()
	_check(names == ["plan.MRC", "seuil.zwo", "sortie.erg"], "fichiers proposés : %s" % str(names))
	var seuil: Dictionary = {}
	for c in found:
		if c["file"] == "seuil.zwo":
			seuil = c
	_check(seuil.get("source", "") == "Téléchargements" and not seuil.get("imported", true), "seuil.zwo : Téléchargements, pas importé")
	# Import, puis même fichier : pas de doublon ; fichier différent du même nom : suffixe _2.
	var src := home.path_join("Téléchargements/seuil.zwo")
	_check(WorkoutFiles.import_file(src, wdir) == {"id": "seuil"}, "import : id seuil")
	_check(WorkoutFiles.import_file(src, wdir) == {"id": "seuil"}, "même fichier réimporté : pas de copie")
	_check(WorkoutFiles.candidates(home, wdir).filter(func(c): return c["file"] == "seuil.zwo")[0]["imported"],
		"seuil.zwo marqué déjà importé")
	_write(src, "<workout_file><name>autre</name></workout_file>")
	_check(WorkoutFiles.import_file(src, wdir) == {"id": "seuil_2"}, "fichier différent du même nom : seuil_2")
	_write(home.path_join("Téléchargements/seuil.erg"), "[COURSE HEADER]")
	_check(WorkoutFiles.import_file(home.path_join("Téléchargements/seuil.erg"), wdir) == {"id": "seuil_3"},
		"seuil.erg : id libre seuil_3 (le .zwo l'emporterait sur seuil)")
	_check(WorkoutFiles.import_file(home.path_join("absent.zwo"), wdir).has("error"), "fichier absent : erreur")
	_rm(base)


func _rm(path: String) -> void:
	var d := DirAccess.open(path)
	if d == null:
		return
	for f in d.get_files():
		d.remove(f)
	for sub in d.get_directories():
		_rm(path.path_join(sub))
	DirAccess.remove_absolute(path)
