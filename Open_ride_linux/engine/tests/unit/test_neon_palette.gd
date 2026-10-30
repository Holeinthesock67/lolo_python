extends SceneTree

## Tests sans écran de la charte du Cyber-Rogue (lot R17) : jetons, variante « couleurs adaptées »,
## contraste des chiffres du HUD, couleurs de pente, catalogue des objets et des effets, réglages de
## l'environnement par préréglage, aucune texture ni modèle dans le dépôt.
## Lancement : godot --headless --path engine --script res://tests/unit/test_neon_palette.gd

const Palette := preload("res://scripts/rogue/neon_palette.gd")
const Catalog := preload("res://scripts/rogue/neon_catalog.gd")
const RogueEnvironment := preload("res://scripts/rogue/rogue_environment.gd")

const CHARTE := ["void", "night", "grid", "player", "energy", "parry", "gold", "danger", "glitch", "neutral"]

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


func _test_tokens() -> void:
	for t in CHARTE:
		_check(Palette.COLORS.has(t), "jeton de la charte : %s" % t)
	_check(Palette.color("player").is_equal_approx(Color("18F0FF")), "le joueur est cyan #18F0FF")
	_check(Palette.color("danger").is_equal_approx(Color("FF2E4C")), "le danger est rouge #FF2E4C")
	for t in Palette.tokens():
		var c: Color = Palette.color(t)
		_check(c.a == 1.0, "couleur opaque : %s" % t)
	var others := 0
	for t in Palette.tokens():
		var c: Color = Palette.color(t)
		if t != "player" and c.g > 0.85 and c.b > 0.85 and c.r < 0.3:
			others += 1
	_check(others == 0, "le joueur est la seule source cyan vive (%d autres)" % others)


static func _dist(a: Color, b: Color) -> float:
	return Vector3(a.r - b.r, a.g - b.g, a.b - b.b).length()


func _test_adapted() -> void:
	_check(not Palette.color("danger", true).is_equal_approx(Palette.color("danger", false)), "variante adaptée : le danger change")
	_check(not Palette.color("energy", true).is_equal_approx(Palette.color("energy", false)), "variante adaptée : l'énergie change")
	_check(Palette.color("player", true).is_equal_approx(Palette.color("player", false)), "variante adaptée : le joueur ne change pas")
	var gap_plain := _dist(Palette.color("danger"), Palette.color("energy"))
	var gap_adapted := _dist(Palette.color("danger", true), Palette.color("energy", true))
	_check(gap_adapted > gap_plain, "danger et énergie plus écartés (%.2f > %.2f)" % [gap_adapted, gap_plain])
	_check(Palette.pattern("danger", true) != Palette.pattern("energy", true), "danger et énergie ont aussi des motifs différents")
	_check(Palette.pattern("danger", false) == "plain", "sans la variante, pas de motif")


func _test_contrast() -> void:
	for t in ["neutral", "gold", "player"]:
		var c := Palette.contrast(Palette.color(t), Palette.color("void"))
		_check(c >= 7.0, "chiffres du HUD %s sur le fond : contraste %.1f ≥ 7" % [t, c])
	var glow_floor := Palette.color("void").lerp(Palette.color("night"), 0.5)
	_check(Palette.contrast(Palette.color("neutral"), glow_floor) >= 7.0, "texte neutre sur le fond avec glow : ≥ 7")


func _test_intensity_and_grade() -> void:
	_check(Palette.INTENSITY["low"] < Palette.INTENSITY["medium"] and Palette.INTENSITY["medium"] < Palette.INTENSITY["high"],
		"intensité émissive croissante avec la qualité")
	_check(Palette.glow_color("player", "high").r >= Palette.color("player").r, "le glow éclaircit la couleur")
	_check(Palette.body_color().is_equal_approx(Palette.color("void").lerp(Color.WHITE, 0.1)), "volume sombre = void éclairci de 10 %")
	for pair in [[-5.0, "grade_down"], [0.0, "grade_flat"], [2.0, "grade_up"], [5.0, "grade_hard"], [8.0, "grade_wall"]]:
		_check(Palette.grade_token(pair[0]) == pair[1], "pente %.0f %% : %s" % [pair[0], pair[1]])
	_check(Palette.grade_token(-3.0) == "grade_flat" and Palette.grade_token(1.5) == "grade_up" and Palette.grade_token(6.5) == "grade_wall",
		"seuils de R10 : −3 / 1,5 / 6,5")


func _test_catalog() -> void:
	for id in Catalog.object_ids():
		var spec: Dictionary = Catalog.OBJECTS[id]
		_check(Palette.COLORS.has(spec["token"]), "objet %s : jeton %s connu" % [id, spec["token"]])
		_check(Catalog.SHAPES.has(spec["shape"]), "objet %s : forme %s connue" % [id, spec["shape"]])
	_check(Catalog.object_ids().size() >= 20, "catalogue des objets complet (%d)" % Catalog.object_ids().size())
	for id in ["player_bike", "firewall", "perfect_shift_arch", "corridor_door", "boss_chimera", "end_chest"]:
		_check(Catalog.OBJECTS.has(id), "objet du catalogue : %s" % id)
	for id in Catalog.effect_ids():
		var e: Dictionary = Catalog.EFFECTS[id]
		_check(Palette.COLORS.has(e["token"]), "effet %s : jeton %s connu" % [id, e["token"]])
		_check(e["flashes_per_s"] <= Catalog.MAX_FLASHES_PER_S, "effet %s : %.1f éclairs/s ≤ 3" % [id, e["flashes_per_s"]])
		_check(e["fullscreen_flash"] == false, "effet %s : pas de grand flash plein écran" % id)
		# Une courte durée avec des éclairs rapides ne doit pas dépasser 3 éclairs dans la seconde.
		if e["duration_s"] > 0.0 and e["flashes_per_s"] > 0.0:
			_check(e["flashes_per_s"] * minf(e["duration_s"], 1.0) <= 3.0, "effet %s : au plus 3 éclairs sur sa durée" % id)
	for ev in ["perfect_shift", "hit", "crit", "parry", "parry_miss", "firewall_contact", "room_won", "room_fled",
			"room_skipped", "defeat", "boss_phase"]:
		_check(Catalog.EFFECTS.has(ev), "effet du catalogue : %s" % ev)


func _test_environment() -> void:
	var low: Dictionary = RogueEnvironment.settings("low")
	var high: Dictionary = RogueEnvironment.settings("high")
	_check(low["glow_levels"] == 3 and high["glow_levels"] == 7, "glow : 3 niveaux en low, 7 en high")
	_check(RogueEnvironment.settings("medium")["glow_levels"] == 5, "glow : 5 niveaux en medium")
	_check(absf(low["glow_bloom"] - 0.05) < 0.001 and absf(high["glow_bloom"] - 0.15) < 0.001, "bloom 0,05 / 0,15")
	_check(low["fog_end_m"] == 400.0 and high["fog_end_m"] == 900.0, "brume 400 m / 900 m")
	_check(high["chromatic"] and not low["chromatic"], "aberration chromatique seulement en high")
	_check(low["particles_share"] < RogueEnvironment.settings("medium")["particles_share"], "particules 25 % < 60 %")
	var env := Environment.new()
	for p in ["low", "medium", "high"]:
		RogueEnvironment.apply(env, p)
		_check(env.background_color.is_equal_approx(Palette.color("void")), "%s : fond void" % p)
		_check(env.glow_enabled and env.fog_enabled, "%s : glow et brume allumés" % p)
		var lit := 0
		for i in RogueEnvironment.GLOW_LEVEL_COUNT:
			if env.get_glow_level(i) > 0.0:
				lit += 1
		_check(lit == RogueEnvironment.settings(p)["glow_levels"], "%s : %d niveaux de glow allumés" % [p, lit])
		# La densité doit survivre au changement de mode (Godot la remet à 1,0 : brume opaque en high)
		var st: Dictionary = RogueEnvironment.settings(p)
		var dens := RogueEnvironment.exponential_density(st["fog_end_m"]) if st["fog_exponential"] else 1.0
		_check(is_equal_approx(env.fog_density, dens), "%s : densité de brume %.4f (lue %.4f)" % [p, dens, env.fog_density])
		_check(env.fog_mode == (Environment.FOG_MODE_EXPONENTIAL if st["fog_exponential"] else Environment.FOG_MODE_DEPTH),
				"%s : mode de brume" % p)


func _test_no_imported_assets() -> void:
	var found: Array = []
	_scan("res://", found)
	_check(found.is_empty(), "aucune texture ni modèle importé dans les ressources du mode (%s)" % str(found))


func _scan(dir_path: String, found: Array) -> void:
	var dir := DirAccess.open(dir_path)
	if dir == null:
		return
	for sub in dir.get_directories():
		if sub.begins_with(".") or sub in ["assets", "tests", "themes", "demo"]:
			continue
		_scan(dir_path.path_join(sub), found)
	for f in dir.get_files():
		if dir_path.contains("/rogue") and f.get_extension().to_lower() in ["png", "jpg", "jpeg", "glb", "gltf", "obj", "webp"]:
			found.append(dir_path.path_join(f))


func _run() -> void:
	_test_tokens()
	_test_adapted()
	_test_contrast()
	_test_intensity_and_grade()
	_test_catalog()
	_test_environment()
	_test_no_imported_assets()
	await process_frame
	print("test_neon_palette : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
