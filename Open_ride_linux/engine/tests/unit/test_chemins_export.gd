extends SceneTree

## Chemins compatibles avec l'export `.pck` (lot EX1, essai E2 du cadrage J9) : aucun
## `ProjectSettings.globalize_path` dans `scripts/` (un chemin `res://` n'a pas de fichier sur le disque une
## fois exporté), `Image.load_from_file` réservé aux textures du thème (dossier sans `.import`), images de la
## Collection et du globe en importeur `keep` (sinon l'export remplace le fichier d'origine par un `.ctex`),
## puis lecture réelle de ces images et du thème par défaut.
## Lancement : godot --headless --path engine --script res://tests/unit/test_chemins_export.gd

const CollectionView := preload("res://scripts/collection_view.gd")
const WorldMenuView := preload("res://scripts/world_menu_view.gd")
const ThemeLoader := preload("res://scripts/theme_loader.gd")

## Scripts qui ont le droit d'appeler Image.load_from_file : textures du thème et des biomes, rangées dans
## des dossiers sans `.import` (vérifié plus bas), donc lues telles quelles dans le projet comme dans le .pck.
const LOAD_FROM_FILE_OK := ["res://scripts/theme_loader.gd", "res://scripts/biome_textures.gd"]
## Dossiers d'images lues à l'exécution par FileAccess : chaque `.import` doit y garder le fichier d'origine.
const KEEP_DIRS := ["res://assets/collection/", "res://assets/globe/"]

var _failures := 0
var _checked := 0


func _init() -> void:
	_test_scripts()
	_test_imports()
	_test_themes_without_import()
	_test_loading()
	print("test_chemins_export : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


## Fichiers `ext` sous `dir`, récursivement.
func _files(dir: String, ext: String) -> PackedStringArray:
	var out := PackedStringArray()
	var d := DirAccess.open(dir)
	if d == null:
		return out
	for f in d.get_files():
		if f.ends_with(ext):
			out.append(dir.path_join(f))
	for sub in d.get_directories():
		out.append_array(_files(dir.path_join(sub), ext))
	return out


func _test_scripts() -> void:
	var scripts := _files("res://scripts", ".gd")
	_check(scripts.size() > 50, "%d scripts lus dans scripts/" % scripts.size())
	var globalize := PackedStringArray()
	var load_file := PackedStringArray()
	for path in scripts:
		var lines := FileAccess.get_file_as_string(path).split("\n")
		for i in lines.size():
			var code := lines[i].strip_edges()
			if code.begins_with("#"):
				continue
			if code.contains("globalize_path("):
				globalize.append("%s:%d" % [path, i + 1])
			if code.contains("Image.load_from_file(") and not path in LOAD_FROM_FILE_OK:
				load_file.append("%s:%d" % [path, i + 1])
	_check(globalize.is_empty(), "aucun globalize_path dans scripts/ (introuvable dans un .pck) : %s" % ", ".join(globalize))
	_check(load_file.is_empty(),
		"Image.load_from_file seulement pour les textures du thème (sinon FileAccess + load_*_from_buffer) : %s" % ", ".join(load_file))


func _test_imports() -> void:
	for dir in KEEP_DIRS:
		var imports := _files(dir, ".import")
		var bad := PackedStringArray()
		for path in imports:
			var cfg := ConfigFile.new()
			if cfg.load(path) != OK or str(cfg.get_value("remap", "importer", "")) != "keep":
				bad.append(path.get_file())
		_check(not imports.is_empty() and bad.is_empty(),
			"%s : %d .import en importeur keep (fichier d'origine gardé à l'export) %s" % [dir, imports.size(), ", ".join(bad)])


func _test_themes_without_import() -> void:
	var imports := _files("res://themes", ".import")
	_check(imports.is_empty(), "aucun .import sous themes/ (Image.load_from_file y reste silencieux) : %s" % ", ".join(imports))


func _test_loading() -> void:
	var visuals := PackedStringArray()
	for path in _files("res://assets/collection", ".png"):
		visuals.append(path.get_file().get_basename())
	var missing := PackedStringArray()
	for v in visuals:
		var tex := CollectionView.texture(v)
		if tex == null or tex.get_width() <= 0:
			missing.append(v)
	_check(not visuals.is_empty() and missing.is_empty(),
		"%d images de la Collection lues par FileAccess %s" % [visuals.size(), ", ".join(missing)])
	_check(CollectionView.texture("visuel_qui_n_existe_pas") == null, "visuel absent : pas de texture, sans erreur")
	var globe := WorldMenuView._load_texture(WorldMenuView.GLOBE_DIR + "globe.jpg")
	_check(globe != null and globe.get_width() > 0, "globe du monde ouvert lu par FileAccess")
	var res: Dictionary = ThemeLoader.load_theme(ThemeLoader.DEFAULT_THEME_DIR)
	_check((res.get("errors", []) as Array).is_empty() and (res.get("warnings", []) as Array).is_empty(),
		"thème par défaut chargé depuis res:// sans erreur ni avertissement : %s" % str(res.get("errors", [])))
