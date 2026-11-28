extends SceneTree

## Tests sans écran du paysage `ville_neon` (lot NV1) : section `neon` du thème par défaut, validation de la section
## (couleur invalide, densité hors de 0 à 2, clé inconnue), règle unique de biome_model.gd (`neon_of`, `neon_at`) :
## une tuile dont le paysage a une section `neon` est en ville néon, les autres non ; le feu et le néon ne se mêlent pas.
## Lancement : godot --headless --path engine --script res://tests/unit/test_neon_landscape.gd

const BiomeIds := preload("res://scripts/biome_ids.gd")
const BiomeLayer := preload("res://scripts/biome_layer.gd")
const BiomeModel := preload("res://scripts/biome_model.gd")
const ThemeLoader := preload("res://scripts/theme_loader.gd")

var _failures := 0
var _checked := 0


func _init() -> void:
	var theme: Dictionary = ThemeLoader.load_theme(ThemeLoader.DEFAULT_THEME_DIR)["theme"]
	_check(BiomeIds.LANDSCAPES.has("ville_neon"), "ville_neon dans BiomeIds.LANDSCAPES")
	var entry = theme.get("landscapes", {}).get("ville_neon", {})
	_check(typeof(entry.get("neon", null)) == TYPE_DICTIONARY, "thème par défaut : landscapes.ville_neon.neon")
	_check(typeof(entry.get("biomes", {}).get("coast", null)) == TYPE_DICTIONARY, "thème par défaut : ville_neon posée sur coast")
	_test_validation(theme)
	_test_model(theme)
	print("test_neon_landscape : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _model(theme: Dictionary, landscape: Variant) -> Object:
	var g := []
	for i in range(289):
		g.append(255)
	var variant = null if landscape == null else {"ground": null, "roofs": "toit_plat_blanc", "landscape": landscape}
	var tile := {"version": "1.0", "biomes": ["coast"], "grid": 17, "weights": [g], "variant": variant}
	var layer = BiomeLayer.new()
	for ix in range(-2, 2):
		for iz in range(-2, 2):
			var errors := PackedStringArray()
			layer.put_tile("near", ix, iz, BiomeLayer.parse_tile(tile, errors))
	return BiomeModel.new(theme, layer)


func _test_validation(theme: Dictionary) -> void:
	var ok := PackedStringArray()
	ThemeLoader._validate_v2(theme, ok)
	_check(ok.is_empty(), "thème par défaut valide : " + " ".join(ok).left(200))
	var errors := PackedStringArray()
	var bad := theme.duplicate(true)
	bad["landscapes"]["ville_neon"]["neon"] = {"density": 5.0, "pink": "rose", "lasers": true}
	ThemeLoader._validate_v2(bad, errors)
	var text := " ".join(errors)
	_check(text.contains("neon.density") and text.contains("neon.pink") and text.contains("lasers"),
		"section neon invalide refusée : " + text.left(200))
	errors = PackedStringArray()
	bad = theme.duplicate(true)
	bad["landscapes"]["ville_neon"]["neon"] = "rose"
	ThemeLoader._validate_v2(bad, errors)
	_check(" ".join(errors).contains("ville_neon.neon : doit être un objet"), "section neon qui n'est pas un objet refusée")


func _test_model(theme: Dictionary) -> void:
	var city = _model(theme, "ville_neon")
	var n: Dictionary = city.neon_at(0.0, -100.0)
	_check(str(n.get("pink", "")) == "#ff2a9e" and float(n.get("density", 0.0)) == 1.0, "neon_at : néon du thème")
	_check(city.fire_at(0.0, -100.0).is_empty(), "ville néon : pas de feu")
	_check(_model(theme, null).neon_at(0.0, -100.0).is_empty(), "sans paysage : pas de néon")
	_check(_model(theme, "volcan_actif").neon_at(0.0, -100.0).is_empty(), "volcan actif : pas de néon")
	_check(_model(theme, "fjord").neon_at(0.0, -100.0).is_empty(), "fjord : pas de néon")
	# Section partielle : complétée par NEON_DEFAULTS
	var partial := theme.duplicate(true)
	partial["landscapes"]["ville_neon"]["neon"] = {"density": 0.5}
	var p: Dictionary = _model(partial, "ville_neon").neon_of("ville_neon")
	_check(float(p["density"]) == 0.5 and str(p["cyan"]) == str(BiomeModel.NEON_DEFAULTS["cyan"]), "section partielle complétée")
	# Sol et végétation du paysage fusionnés sur le biome coast
	var params: Dictionary = city.params("coast", "", 0.0, {"landscape": "ville_neon"})
	var base: Dictionary = city.params("coast", "", 0.0, null)
	_check(str(params) != str(base), "paysage ville_neon : paramètres du biome coast modifiés")
