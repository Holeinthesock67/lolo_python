extends SceneTree

## Tests sans écran du paysage `ville_neon` (lot NV1) : section `neon` du thème par défaut, validation de la section
## (couleur invalide, densité hors de 0 à 2, clé inconnue), règle unique de biome_model.gd (`neon_of`, `neon_at`) :
## une tuile dont le paysage a une section `neon` est en ville néon, les autres non ; le feu et le néon ne se mêlent pas.
## Lancement : godot --headless --path engine --script res://tests/unit/test_neon_landscape.gd

const BiomeIds := preload("res://scripts/biome_ids.gd")
const BiomeLayer := preload("res://scripts/biome_layer.gd")
const BiomeModel := preload("res://scripts/biome_model.gd")
const ThemeLoader := preload("res://scripts/theme_loader.gd")
const NeonFx := preload("res://scripts/neon_fx.gd")
const AtmosphereView := preload("res://scripts/atmosphere_view.gd")

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
	_test_fx(theme)
	_test_atmosphere(theme)
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


## neon_fx.gd (lot NV2) : actif seulement si le thème du parcours a un paysage néon ; ambiance posée dès la
## première image dans une tuile en ville néon, nulle ailleurs ; coucher du soleil tenu, puis la nuit tombe ;
## la pause (pas nul) n'avance pas la nuit.
func _test_fx(theme: Dictionary) -> void:
	var fx = NeonFx.new()
	fx.configure(null)
	_check(not fx.active(), "sans modèle de biome : inactif")
	fx.configure(_model(theme, "ville_neon"))
	_check(fx.active() and fx.neon_level == 0.0, "thème avec ville néon : actif, ambiance nulle avant la première image")
	fx.update(Vector3(0.0, 0.0, -100.0), 0.016)
	_check(fx.neon_level == 1.0 and fx.night == 0.0, "première image en ville néon : ambiance entière, coucher du soleil")
	for i in range(60):
		fx.update(Vector3(0.0, 0.0, -100.0), 1.0)
	_check(fx.night == 0.0, "coucher du soleil tenu pendant %d s" % int(NeonFx.DUSK_HOLD_S))
	for i in range(300):
		fx.update(Vector3(0.0, 0.0, -100.0), 1.0)
	var mid: float = fx.night
	_check(mid > 0.1 and mid < 0.9, "la nuit tombe : %.2f à 6 min" % mid)
	fx.update(Vector3(0.0, 0.0, -100.0), 0.0)
	_check(fx.night == mid, "pause : la nuit n'avance pas")
	for i in range(300):
		fx.update(Vector3(0.0, 0.0, -100.0), 1.0)
	_check(fx.night == 1.0, "nuit complète à %d s" % int(NeonFx.NIGHT_AT_S))
	# La nuit tombe par paliers : le ciel et la lumière ne sont pas reposés à chaque image (banc PC du 27 novembre)
	var stepped = NeonFx.new()
	stepped.configure(_model(theme, "ville_neon"))
	var changes := 0
	var last := -1.0
	var biggest := 0.0
	for i in range(int(NeonFx.NIGHT_AT_S + 10.0) * 20):
		stepped.update(Vector3(0.0, 0.0, -100.0), 0.05)
		if stepped.night != last:
			changes += 1
			biggest = maxf(biggest, stepped.night - maxf(last, 0.0))
			last = stepped.night
	_check(changes == NeonFx.NIGHT_STEPS + 1 and stepped.night == 1.0 and biggest < 0.011,
		"nuit par paliers : %d changements en 10 min à 20 images/s (un palier d'au plus 1,1 %%)" % changes)
	fx.night_override = 0.25
	fx.update(Vector3(0.0, 0.0, -100.0), 1.0)
	_check(fx.night == 0.25, "nuit imposée pour les captures")
	var out = NeonFx.new()
	out.configure(_model(theme, "fjord"))
	out.update(Vector3(0.0, 0.0, -100.0), 0.016)
	_check(out.neon_level == 0.0, "tuile sans néon : ambiance nulle")
	fx.free()
	out.free()


## atmosphere_view.gd `set_neon` : sans ambiance, les paramètres ne changent pas ; avec, brume rose, lumière
## rasante rosée, ciel du thème ; la nuit, lumière faible venue d'en haut, étoiles, ciel assombri.
func _test_atmosphere(theme: Dictionary) -> void:
	var palette: Dictionary = _model(theme, "ville_neon").neon_of("ville_neon")
	var av = AtmosphereView.new()
	var base := {"horizon_color": Color(0.7, 0.75, 0.8), "light_tint": Color.WHITE, "light_energy_factor": 1.0,
		"sun_direction": Vector3(0.3, 0.8, 0.5).normalized()}
	var p := base.duplicate()
	av.set_neon(0.0, 0.0, palette)
	av._with_neon(p)
	_check(str(p) == str(base), "ambiance nulle : paramètres inchangés")
	av.set_neon(1.0, 0.0, {})
	av._with_neon(p)
	_check(str(p) == str(base), "sans section neon : paramètres inchangés")
	av.set_neon(1.0, 0.0, palette)
	av._with_neon(p)
	var hz: Color = p["horizon_color"]
	_check(hz.r > hz.g and float(p["neon"]) == 1.0 and (p["sun_direction"] as Vector3).y < 0.2
		and float(p["light_energy_factor"]) > 1.0 and p.has("ambient_energy") and p.has("sky_top"),
		"coucher du soleil : brume rose, soleil bas, lumière ambiante posée")
	var dusk: Array = av.neon_sky()
	var n := base.duplicate()
	av.set_neon(1.0, 1.0, palette)
	av._with_neon(n)
	var night: Array = av.neon_sky()
	_check(float(n["light_energy_factor"]) < 0.3 and (n["sun_direction"] as Vector3).y > 0.5 and float(n["stars"]) == 1.0
		and (night[0] as Color).get_luminance() < (dusk[0] as Color).get_luminance()
		and (night[2] as Color).get_luminance() < (dusk[2] as Color).get_luminance(),
		"nuit : lumière faible d'en haut, étoiles, ciel assombri")
	# Nuit par paliers : l'atmosphère n'est reposée qu'à chaque palier, pas tous les quarts de seconde
	var counts := {}
	for stepped: bool in [true, false]:
		var prev := {}
		var applied := 0
		var t := 0.0
		while t <= NeonFx.NIGHT_AT_S + 10.0:
			var q := base.duplicate()
			q["fog_end_factor"] = 1.0
			q["heat_haze"] = 0.0
			av.set_neon(1.0, NeonFx.night_step_at(t) if stepped else NeonFx.night_at(t), palette)
			av._with_neon(q)
			if AtmosphereView._differs(q, prev):
				applied += 1
				prev = q
			t += AtmosphereView.PERIOD_S
		counts[stepped] = applied
	_check(int(counts[true]) == NeonFx.NIGHT_STEPS + 1 and int(counts[false]) > 10 * int(counts[true]),
		"atmosphère reposée %d fois par paliers (%d fois en continu)" % [int(counts[true]), int(counts[false])])
	var half := base.duplicate()
	av.set_neon(0.5, 0.0, palette)
	av._with_neon(half)
	_check(float(half["light_energy_factor"]) > 1.0 and float(half["light_energy_factor"]) < float(p["light_energy_factor"]),
		"entrée dans le paysage : fondu")
	av.free()
