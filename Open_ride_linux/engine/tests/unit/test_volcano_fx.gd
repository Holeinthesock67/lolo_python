extends SceneTree

## Tests sans écran de volcano_fx.gd (démo « Volcan en flammes », 13 novembre) : feu seulement dans les tuiles d'un
## paysage qui a une section `fire` dans le thème, lave jamais à moins de ROAD_CLEAR_M de l'axe de la route sur tout
## le parcours (épingle : la portion d'en face compte), placement déterministe, budgets par qualité, lueur.
## Lancement : godot --headless --path engine --script res://tests/unit/test_volcano_fx.gd

const VolcanoFx := preload("res://scripts/volcano_fx.gd")
const BiomeLayer := preload("res://scripts/biome_layer.gd")
const BiomeModel := preload("res://scripts/biome_model.gd")
const ThemeLoader := preload("res://scripts/theme_loader.gd")
const QualityPresets := preload("res://scripts/quality_presets.gd")
const RoadClearance := preload("res://scripts/road_clearance.gd")
const RouteDataScript := preload("res://scripts/route_data.gd")
const GrassTufts := preload("res://scripts/grass_tufts.gd")
const AtmosphereView := preload("res://scripts/atmosphere_view.gd")
const SeasonModel := preload("res://scripts/season_model.gd")

var _failures := 0
var _checked := 0


func _init() -> void:
	var loaded: Dictionary = ThemeLoader.load_theme(ThemeLoader.DEFAULT_THEME_DIR)
	var theme: Dictionary = loaded["theme"]
	_check(typeof(theme.get("landscapes", {}).get("volcan_actif", {}).get("fire", null)) == TYPE_DICTIONARY,
		"thème par défaut : landscapes.volcan_actif.fire")
	_test_theme_validation(theme)
	_test_placement(theme)
	_test_no_fire(theme)
	_test_budgets(theme)
	_test_grass_and_sky(theme)
	_test_no_snow(theme)
	print("test_volcano_fx : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _tile(landscape: Variant) -> Dictionary:
	var g := []
	for i in range(289):
		g.append(255)
	var variant = null if landscape == null else {"ground": "basalte", "roofs": null, "landscape": landscape}
	return {"version": "1.0", "biomes": ["volcanic"], "grid": 17, "weights": [g], "variant": variant}


func _model(theme: Dictionary, landscape: Variant) -> Object:
	var layer = BiomeLayer.new()
	for ix in range(-2, 2):
		for iz in range(-2, 2):
			var errors := PackedStringArray()
			layer.put_tile("near", ix, iz, BiomeLayer.parse_tile(_tile(landscape), errors))
	return BiomeModel.new(theme, layer)


## Épingle : montée vers le nord en x = 0 sur 600 m, demi-tour de rayon 8 m, retour vers le sud en x = 16.
static func _hairpin_point(s: float) -> Vector2:
	var arc := PI * 8.0
	if s <= 600.0:
		return Vector2(0.0, -s)
	if s <= 600.0 + arc:
		var a := PI * (1.0 - (s - 600.0) / arc)
		return Vector2(8.0 + 8.0 * cos(a), -600.0 - 8.0 * sin(a))
	return Vector2(16.0, -600.0 + (s - 600.0 - arc))


func _hairpin() -> Variant:
	var ds := 5.0
	var n := int(floor((1200.0 + PI * 8.0) / ds)) + 1
	var data := {"version": "1.0", "type": "open", "ds_m": ds, "n": n, "length_m": ds * (n - 1),
		"lat": [], "lon": [], "alt_m": [], "x": [], "z": [], "grade_pct": [], "heading_deg": []}
	for i in range(n):
		var p := _hairpin_point(i * ds)
		var nxt := _hairpin_point(i * ds + 0.5) - _hairpin_point(maxf(i * ds - 0.5, 0.0))
		data["lat"].append(45.0)
		data["lon"].append(6.0)
		data["alt_m"].append(500.0)
		data["x"].append(p.x)
		data["z"].append(p.y)
		data["grade_pct"].append(0.0)
		data["heading_deg"].append(fposmod(rad_to_deg(atan2(nxt.x, -nxt.y)), 360.0))
	var route = RouteDataScript.new()
	route.load_route_dict(data)
	return route


func _all_features(fx) -> Array:
	var out := []
	for k in range(0, int(ceil(fx.route.length_m / VolcanoFx.CHUNK_M))):
		out.append_array(fx.features_of_chunk(k))
	return out


func _test_theme_validation(theme: Dictionary) -> void:
	var ok := PackedStringArray()
	ThemeLoader._validate_v2(theme, ok)
	_check(ok.is_empty(), "thème par défaut valide : " + " ".join(ok).left(200))
	var errors := PackedStringArray()
	var bad := theme.duplicate(true)
	bad["landscapes"]["volcan_actif"]["fire"] = {"density": 5.0, "lava": "orange", "flames": true}
	ThemeLoader._validate_v2(bad, errors)
	var text := " ".join(errors)
	_check(text.contains("fire.density") and text.contains("fire.lava") and text.contains("flames"),
		"section fire invalide refusée : " + text.left(200))


func _test_placement(theme: Dictionary) -> void:
	var route = _hairpin()
	var fx = VolcanoFx.new()
	root.add_child(fx)
	fx.configure({"embers": 300, "plumes": 3, "fountains": 1, "lights": 2}, route, _model(theme, "volcan_actif"))
	_check(fx.active(), "paysage volcan_actif : effets actifs")
	var feats := _all_features(fx)
	var kinds := {}
	for f in feats:
		kinds[f["kind"]] = int(kinds.get(f["kind"], 0)) + 1
	_check(kinds.get("flow", 0) > 5 and kinds.get("pool", 0) > 0 and kinds.get("vent", 0) > 0,
		"coulées, lacs et évents posés : %s" % str(kinds))
	# Garde-fou : distance à TOUTE la route (les deux portions de l'épingle)
	var rc := RoadClearance.new(route)
	var worst := INF
	for f in feats:
		match str(f["kind"]):
			"flow":
				for p in f["points"]:
					worst = minf(worst, rc.distance(p.x, p.y) - float(f["width"]) * 0.5)
			"pool":
				worst = minf(worst, rc.distance(f["center"].x, f["center"].y) - float(f["radius"]) * 1.15)
			"vent":
				worst = minf(worst, rc.distance(f["center"].x, f["center"].y))
	_check(worst >= VolcanoFx.ROAD_CLEAR_M - 0.01, "lave à %.1f m au moins de l'axe de la route (≥ %.0f)" % [worst, VolcanoFx.ROAD_CLEAR_M])
	# Déterministe
	_check(str(fx.features_of_chunk(3)) == str(fx.features_of_chunk(3)), "même tronçon, mêmes éléments")
	var mesh: ArrayMesh = fx.build_mesh(feats, 500.0)
	_check(mesh != null and mesh.get_surface_count() == 1 and mesh.surface_get_array_len(0) > 100,
		"maillage de lave construit")
	# Fenêtre de tronçons et lueur
	for i in range(40):
		fx.update(Vector3(0.0, 501.0, -200.0), 200.0, 1.0 / 30.0)
	_check(fx.is_settled() and fx.chunk_count() > 0, "tronçons dessinés : %d" % fx.chunk_count())
	_check(fx.fire_level > 0.5 and fx.fire_level <= 1.0, "lueur qui monte en roulant : %.2f" % fx.fire_level)
	fx.fire_level = 0.0
	fx.update(Vector3(0.0, 501.0, -200.0), 200.0, 0.0)
	_check(fx.fire_level == 1.0, "scène figée (pas nul) : lueur tout de suite")
	fx.queue_free()


func _test_no_fire(theme: Dictionary) -> void:
	var route = _hairpin()
	for landscape in [null, "ile_volcanique"]:
		var fx = VolcanoFx.new()
		root.add_child(fx)
		fx.configure({"embers": 300, "plumes": 3, "fountains": 1, "lights": 2}, route, _model(theme, landscape))
		_check(_all_features(fx).is_empty(), "paysage %s : aucune lave" % str(landscape))
		for i in range(20):
			fx.update(Vector3(0.0, 501.0, -200.0), 200.0, 1.0 / 30.0)
		_check(fx.chunk_count() == 0 and fx.fire_level == 0.0, "paysage %s : rien dessiné, pas de lueur" % str(landscape))
		fx.queue_free()
	var none = VolcanoFx.new()
	root.add_child(none)
	none.configure({"embers": 300}, route, null)
	_check(not none.active(), "sans modèle de biome : inactif")
	none.queue_free()


func _test_budgets(theme: Dictionary) -> void:
	var low := VolcanoFx.budgets_of(QualityPresets.living("low"))
	var medium := VolcanoFx.budgets_of(QualityPresets.living("medium"))
	var high := VolcanoFx.budgets_of(QualityPresets.living("high"))
	_check(low["lights"] == 0 and low["fountains"] == 0 and low["embers"] <= 100, "low : ni lumière ni gerbe, peu de braises")
	_check(medium["embers"] < high["embers"] and medium["lights"] < high["lights"], "medium sous high")
	var off := VolcanoFx.budgets_of(QualityPresets.living("high", false))
	_check(off["embers"] == 0 and off["plumes"] == 0, "décor vivant coupé : aucune particule")
	var fx = VolcanoFx.new()
	root.add_child(fx)
	fx.configure(high, _hairpin(), _model(theme, "volcan_actif"))
	var counts: Dictionary = fx.node_counts()
	_check(counts["lights"] == high["lights"] and counts["fountains"] == high["fountains"] and counts["plumes"] == high["plumes"],
		"réserves de nœuds selon le budget : %s" % str(counts))
	fx.queue_free()



## Une seule règle (biome_model.gd `fire_at`) : pas d'herbe dans un paysage en feu ; ciel rougi par la lueur.
func _test_grass_and_sky(theme: Dictionary) -> void:
	var fire_model = _model(theme, "volcan_actif")
	_check(str(fire_model.fire_at(0.0, -100.0).get("glow", "")) != "" and float(fire_model.fire_at(0.0, -100.0)["density"]) == 1.5,
		"biome_model.fire_at : feu du thème complété")
	_check(_model(theme, "ile_volcanique").fire_at(0.0, -100.0).is_empty(), "île volcanique : pas de feu")
	var g = GrassTufts.new()
	g.biome_model = fire_model
	var empty := true
	for slot in range(20):
		empty = empty and g.dry_draw(1, slot, Vector3(30.0, 500.0, -100.0)) == -1
	_check(empty, "paysage en feu : aucune touffe d'herbe")
	g.biome_model = _model(theme, null)
	_check(g.dry_draw(1, 0, Vector3(30.0, 500.0, -100.0)) == 0, "volcanique sans feu : herbe d'avant")
	g.free()
	var av = AtmosphereView.new()
	av.set_fire(1.0, Color("#ff6a20"))
	var p := {"horizon_color": Color(0.7, 0.75, 0.8), "light_tint": Color.WHITE}
	av._with_fire(p)
	var m: Array = av._sky_mults(p)
	_check((p["horizon_color"] as Color).r > (p["horizon_color"] as Color).b and (m[1] as Color).r > (m[1] as Color).b
		and (m[0] as Color).get_luminance() < 1.0, "lueur : brume et horizon rougis, haut du ciel assombri")
	av.free()


## Pas de neige dans un paysage en feu (user, 14 novembre) : ni chute de neige ni limite abaissée l'hiver, même
## par temps de neige ; lueur posée dès la première image (pas de neige au départ) ; hors feu, rien ne change.
func _test_no_snow(theme: Dictionary) -> void:
	var route = _hairpin()
	var fx = VolcanoFx.new()
	root.add_child(fx)
	fx.configure({"embers": 300, "plumes": 3, "fountains": 1, "lights": 2}, route, _model(theme, "volcan_actif"))
	var snowing := {"rain": 0.0, "snow": 0.8, "fog_boost": 0.1}
	_check(fx.melt_snow(snowing)["snow"] == 0.8, "avant de rouler : neige inchangée")
	fx.update(Vector3(0.0, 501.0, -200.0), 200.0, 1.0 / 30.0)
	_check(fx.fire_level == 1.0, "première image dans le feu : lueur tout de suite (%.2f)" % fx.fire_level)
	_check(float(fx.melt_snow(snowing)["snow"]) == 0.0 and snowing["snow"] == 0.8,
		"météo de neige dans le feu : plus de neige qui tombe (copie)")
	var winter := SeasonModel.params("winter", 0.5, true)
	_check(float(winter["snow_drop_m"]) > 0.0 and float(fx.melt_snow(winter)["snow_drop_m"]) == 0.0,
		"hiver enneigé dans le feu : limite de neige non abaissée")
	fx.queue_free()
	var plain = VolcanoFx.new()
	root.add_child(plain)
	plain.configure({"embers": 300}, route, _model(theme, null))
	plain.update(Vector3(0.0, 501.0, -200.0), 200.0, 1.0 / 30.0)
	_check(plain.melt_snow(snowing)["snow"] == 0.8, "hors feu : la neige tombe comme avant")
	plain.queue_free()
	var fire_model = _model(theme, "volcan_actif")
	fire_model.set_season_date(1, 15, 45.0, true)
	var v := {"ground": "basalte", "roofs": null, "landscape": "volcan_actif"}
	_check(float(fire_model.params("volcanic", "", 0.0, v)["season_params"]["snow_drop_m"]) == 0.0,
		"biome_model : tuile en feu, janvier enneigé, pas de neige")
	var cold_model = _model(theme, null)
	cold_model.set_season_date(1, 15, 45.0, true)
	_check(float(cold_model.params("volcanic", "", 0.0, null)["season_params"]["snow_drop_m"]) > 0.0,
		"biome_model : volcanique sans feu, janvier enneigé, neige d'avant")
