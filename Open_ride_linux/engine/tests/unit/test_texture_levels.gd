extends SceneTree

## Niveau des textures du décor (lot P20, `texture_levels.gd`) : côté par préréglage, budget de mémoire vidéo,
## niveau imposé, niveaux d'un pack (`texture_levels`), repli sur le niveau inférieur puis la racine, textures
## 1.x du thème réduites au niveau, thème sans `texture_levels` inchangé.
## Lancement : godot --headless --path engine --script res://tests/unit/test_texture_levels.gd

const TextureLevels := preload("res://scripts/texture_levels.gd")
const QualityPresets := preload("res://scripts/quality_presets.gd")
const ThemeLoader := preload("res://scripts/theme_loader.gd")
const EngineArgs := preload("res://scripts/engine_args.gd")

const PACK_LEVELS := [
	{"name": "bas", "max_px": 512, "dir": "levels/512"},
	{"name": "moyen", "max_px": 1024, "dir": "levels/1024"},
	{"name": "haut", "max_px": 2048, "dir": "levels/2048"},
]

var _failures := 0
var _checked := 0


func _init() -> void:
	_test_presets()
	_test_without_levels()
	_test_pack_levels()
	_test_resolve_and_load()
	_test_validation()
	print("test_texture_levels : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _test_presets() -> void:
	_check(QualityPresets.texture_px("low") == 1024 and QualityPresets.texture_px("medium") == 1024
		and QualityPresets.texture_px("high") == 2048, "côtés : 1 024 en low et medium, 2 048 en high")
	_check(QualityPresets.texture_budget_bytes("low") == 512 << 20 and QualityPresets.texture_budget_bytes("medium") == 1 << 30
		and QualityPresets.texture_budget_bytes("high") == 1 << 30, "budgets : 512 Mo en low, 1 Go en medium et high (U-Q4)")
	_check(TextureLevels.estimate_bytes(1, 1024) == int(1024 * 1024 * 4 * 4.0 / 3.0), "estimation : 1 carte de 1 024 px = 5,3 Mo")
	var args := EngineArgs.parse(PackedStringArray(["--texture-level=high"]))
	_check(args["texture_level"] == "high", "--texture-level=high lu")
	_check(EngineArgs.parse(PackedStringArray(["--texture-level=ultra"]))["texture_level"] == "auto"
		and EngineArgs.last_error != "", "--texture-level inconnu : auto, avec un message")
	_check(EngineArgs.parse(PackedStringArray([]))["texture_level"] == "auto", "sans argument : auto")


func _test_without_levels() -> void:
	var six := 6 * 3 * 2
	var c6 := TextureLevels.choose({}, "high", "auto", six)
	_check(c6["px"] == 2048 and c6["dir"] == "" and c6["reason"] == "préréglage high",
		"6 biomes texturés (36 cartes) en high : 2 048 px, %.0f Mo (%s)" % [c6["bytes"] / 1048576.0, c6["reason"]])
	var c9 := TextureLevels.choose({}, "high", "auto", 54)
	_check(c9["px"] == 1024 and c9["reason"] == "budget de 1024 Mo",
		"54 cartes en high : %.0f Mo à 2 048 px, niveau 1 024 retenu (%s)" % [TextureLevels.estimate_bytes(54, 2048) / 1048576.0, c9["reason"]])
	_check(TextureLevels.choose({}, "low", "auto", six)["px"] == 1024, "low : 1 024 px")
	var c_low := TextureLevels.choose({}, "low", "auto", 100)
	_check(c_low["px"] == 512, "100 cartes en low : %.0f Mo à 1 024 px > 512 Mo, niveau 512 retenu" % (TextureLevels.estimate_bytes(100, 1024) / 1048576.0))
	var c_huge := TextureLevels.choose({}, "high", "auto", 2000)
	_check(c_huge["px"] == 0, "au-delà du budget même à 512 px : couleurs unies (%s)" % c_huge["reason"])
	_check(TextureLevels.choose({}, "high", "auto", 0)["px"] == 0, "aucune texture : couleurs unies")
	var none_line := TextureLevels.log_line("décor", TextureLevels.choose({}, "medium", "auto", 0), 0)
	_check(none_line.begins_with("[textures] décor : 0 cartes") and none_line.ends_with("préréglage medium"),
		"aucune texture : la ligne de journal dit quand même le préréglage (%s)" % none_line)
	var forced := TextureLevels.choose({}, "low", "high", 4)
	_check(forced["px"] == 2048 and forced["reason"] == "imposé (high)", "texture_level = high en low : 2 048 px (%s)" % forced["reason"])
	_check(TextureLevels.choose({}, "high", "low", 4)["px"] == 1024, "texture_level = low en high : 1 024 px")
	var line := TextureLevels.log_line("décor", forced, 4)
	_check(line.begins_with("[textures] décor : 4 cartes, niveau 2048 px (2048 px)") and line.contains("imposé"), "journal : « %s »" % line)


func _test_pack_levels() -> void:
	var theme := {"texture_levels": PACK_LEVELS.duplicate(true)}
	var levels := TextureLevels.levels_of(theme)
	_check(levels.size() == 3 and levels[0]["max_px"] == 2048 and levels[2]["max_px"] == 512, "niveaux du pack, du plus grand au plus petit")
	var low := TextureLevels.choose(theme, "low", "auto", 8)
	_check(low["name"] == "moyen" and low["dir"] == "levels/1024", "low : niveau « moyen » (1 024 px)")
	var low_big := TextureLevels.choose(theme, "low", "auto", 100)
	_check(low_big["name"] == "bas" and low_big["reason"] == "budget de 512 Mo", "pack dont le niveau 1 024 dépasse le budget low : niveau « bas » (512 px)")
	_check(TextureLevels.choose(theme, "low", "high", 8)["name"] == "haut", "texture_level = high : niveau « haut » (2 048 px) quel que soit le préréglage")
	_check(TextureLevels.choose(theme, "high", "auto", 8)["name"] == "haut", "high : niveau « haut »")
	var only_big := {"texture_levels": [{"name": "4k", "max_px": 4096, "dir": "levels/4096"}]}
	var c := TextureLevels.choose(only_big, "low", "auto", 1)
	_check(c["px"] == 4096, "pack d'un seul niveau plus grand que le préréglage : ce niveau (%d px)" % c["px"])


## Petit PNG de `px` × `px` au chemin `path` (dossiers créés).
func _png(path: String, px: int, color: Color) -> void:
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	var img := Image.create(px, px, false, Image.FORMAT_RGBA8)
	img.fill(color)
	img.save_png(path)


func _test_resolve_and_load() -> void:
	var dir := ProjectSettings.globalize_path("user://test_texture_levels")
	if DirAccess.dir_exists_absolute(dir):
		OS.move_to_trash(dir)
	_png(dir.path_join("levels/512/textures/herbe.png"), 64, Color.GREEN)
	_png(dir.path_join("levels/1024/textures/herbe.png"), 128, Color.GREEN)
	_png(dir.path_join("levels/512/textures/roche.png"), 64, Color.GRAY)
	_png(dir.path_join("textures/neige.png"), 256, Color.WHITE)
	var theme := {"texture_levels": PACK_LEVELS.duplicate(true), "terrain": {"grass": {"texture": "textures/herbe.png"},
		"rock": {"texture": "textures/roche.png"}, "snow": {"texture": "textures/neige.png"}}, "road": {"texture": "textures/absente.png"}}
	var high := TextureLevels.choose(theme, "high", "auto", 4)
	_check(TextureLevels.resolve(dir, "textures/herbe.png", high).ends_with("levels/1024/textures/herbe.png"),
		"herbe absente du niveau 2 048 : celle du niveau 1 024")
	_check(TextureLevels.resolve(dir, "textures/roche.png", high).ends_with("levels/512/textures/roche.png"),
		"roche seulement au niveau 512 : repli sur ce niveau")
	_check(TextureLevels.resolve(dir, "textures/neige.png", high) == dir.path_join("textures/neige.png"),
		"neige hors des niveaux : racine du thème")
	_check(TextureLevels.resolve(dir, "textures/absente.png", high) == "", "texture absente partout : chemin vide")
	_check(TextureLevels.resolve(dir, "../hors.png", high) == "", "chemin hors du thème refusé")
	var low := TextureLevels.choose(theme, "low", "auto", 4)
	_check(TextureLevels.resolve(dir, "textures/herbe.png", low).ends_with("levels/1024/textures/herbe.png"), "low : herbe du niveau 1 024")
	_check(ThemeLoader.decor_texture_count(theme) == 4, "4 textures 1.x comptées pour le budget")
	var tex := ThemeLoader.texture_for(theme, dir, "terrain.grass", high)
	_check(tex != null and tex.get_width() == 128, "texture_for : herbe du niveau 1 024 chargée (%d px)" % (tex.get_width() if tex != null else -1))
	_check(ThemeLoader.texture_for(theme, dir, "road.texture", high) == null, "route absente : couleur unie, sans erreur")
	var small := {"name": "64 px", "px": 64, "dir": "", "levels": []}
	var snow := ThemeLoader.texture_for(theme, dir, "terrain.snow", small)
	_check(snow != null and snow.get_width() == 64, "sans niveaux : neige de 256 px réduite au côté retenu (64 px)")
	_check(ThemeLoader.texture_for(theme, dir, "terrain.snow", {"px": 0, "levels": []}) == null, "budget dépassé (px = 0) : couleur unie")
	var plain := ThemeLoader.texture_for(theme, dir, "terrain.snow")
	_check(plain != null and plain.get_width() == 256, "sans niveau retenu : comportement d'avant P20 (taille du fichier)")
	OS.move_to_trash(dir)


func _test_validation() -> void:
	var dir := ProjectSettings.globalize_path("user://test_texture_levels_theme")
	DirAccess.make_dir_recursive_absolute(dir)
	var base := {"version": "1.2", "name": "Niveaux"}
	var cases := [
		[PACK_LEVELS, true, "trois niveaux valides"],
		[[{"name": "a", "max_px": 1000, "dir": "x"}], false, "côté qui n'est pas une puissance de 2"],
		[[{"name": "a", "max_px": 512, "dir": "../x"}], false, "dossier hors du thème"],
		[[{"name": "a", "max_px": 512, "dir": "x"}, {"name": "a", "max_px": 1024, "dir": "y"}], false, "noms en double"],
		["512", false, "pas un tableau"],
	]
	for c in cases:
		var data: Dictionary = base.duplicate(true)
		data["texture_levels"] = c[0]
		var f := FileAccess.open(dir.path_join("theme.json"), FileAccess.WRITE)
		f.store_string(JSON.stringify(data))
		f.close()
		var res := ThemeLoader.load_theme(dir)
		var ok: bool = (res["errors"] as PackedStringArray).is_empty()
		_check(ok == c[1], "validation : %s -> %s" % [c[2], "accepté" if ok else "refusé (%s)" % res["errors"][0]])
	var data: Dictionary = base.duplicate(true)
	var f := FileAccess.open(dir.path_join("theme.json"), FileAccess.WRITE)
	f.store_string(JSON.stringify(data))
	f.close()
	var res := ThemeLoader.load_theme(dir)
	_check(res["errors"].is_empty() and (res["theme"]["texture_levels"] as Array).is_empty()
		and not ",".join(res["warnings"]).contains("texture_levels"), "thème sans texture_levels : liste vide, aucun avertissement")
	OS.move_to_trash(dir)
