extends SceneTree

## Tests unitaires de l'option « gravel » dans l'engine (lot U22) : colonne `surface` de route_data.gd,
## surface effective (road_surface.gd), ruban de road_builder.gd, poussière (weather_particles.gd), crissement
## (sound_model.gd), argument `--gravel=` (engine_args.gd) ; réglage `gravel.mode` du menu (lot U16 :
## textes des choix et légende de la carte de détail, settings_view_model.gd).
##
## Critères du cahier (docs/lots/LOT_U22_gravel_rendu_engine.md §7) :
## - 2 : route sans colonne en `auto`, ou option coupée : tableaux du ruban identiques à ceux d'avant U22 ;
##   même route en `gravel` : ruban de gravier de bout en bout ;
## - 3 : portion `dirt` large de 3 m en moyenne à 0,2 m près, tronçons raccordés sans trou ni recouvrement ;
## - 5 : pluie active, aucune poussière.

const RoadBuilder := preload("res://scripts/road_builder.gd")
const RoadSurface := preload("res://scripts/road_surface.gd")
const RouteDataScript := preload("res://scripts/route_data.gd")
const WeatherParticles := preload("res://scripts/weather_particles.gd")
const WeatherModel := preload("res://scripts/weather_model.gd")
const SoundModel := preload("res://scripts/sound_model.gd")
const EngineArgs := preload("res://scripts/engine_args.gd")
const QualityPresets := preload("res://scripts/quality_presets.gd")
const SettingsViewModel := preload("res://scripts/settings_view_model.gd")

var _failures := 0
var _checked := 0


func _init() -> void:
	call_deferred("_run")


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


## Route droite vers le nord, un point tous les 10 m ; `surface` : colonne (vide : pas de colonne).
func _make_route(length_m: float, surface: Array = []):
	var d := {"version": "1.0", "ds_m": 10.0, "n": 0, "length_m": 0.0, "type": "open",
		"lat": [], "lon": [], "alt_m": [], "x": [], "z": [], "grade_pct": [], "heading_deg": []}
	var n := int(length_m / 10.0) + 1
	for k in range(n):
		d["lat"].append(45.0)
		d["lon"].append(6.0)
		d["alt_m"].append(500.0)
		d["x"].append(0.0)
		d["z"].append(-k * 10.0)
		d["grade_pct"].append(0.0)
		d["heading_deg"].append(0.0)
	d["n"] = n
	d["length_m"] = (n - 1) * 10.0
	if not surface.is_empty():
		d["surface"] = surface.slice(0, n) if surface.size() >= n else surface
	var route = RouteDataScript.new()
	_check(route.load_route_dict(d), "route de %d m chargée (%s)" % [int(length_m), route.load_error])
	return route


## Colonne : bitume jusqu'à `from_m`, `kind` ensuite.
func _column(length_m: float, from_m: float, kind: String) -> Array:
	var out := []
	for k in range(int(length_m / 10.0) + 1):
		out.append("paved" if k * 10.0 < from_m else kind)
	return out


func _same(a: Array, b: Array) -> bool:
	for i in [Mesh.ARRAY_VERTEX, Mesh.ARRAY_NORMAL, Mesh.ARRAY_TEX_UV, Mesh.ARRAY_INDEX, Mesh.ARRAY_COLOR, Mesh.ARRAY_TEX_UV2]:
		if a[i] != b[i]:
			return false
	return true


## Largeur de la chaussée à chaque coupe (sommets 2 et 3 de la coupe, route droite vers le nord : x).
func _widths(arrays: Array) -> PackedFloat64Array:
	var v: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
	var out := PackedFloat64Array()
	for c in range(v.size() / RoadBuilder.VERTS_PER_SECTION):
		out.append(v[c * RoadBuilder.VERTS_PER_SECTION + 3].x - v[c * RoadBuilder.VERTS_PER_SECTION + 2].x)
	return out


func _test_route_column() -> void:
	var r = _make_route(200.0, _column(200.0, 100.0, "gravel"))
	_check(r.surface_at(95.0) == "paved" and r.surface_at(100.0) == "gravel" and r.surface_at(200.0) == "gravel",
		"surface_at : la surface d'un point vaut jusqu'au point suivant")
	_check(_make_route(200.0).surface_at(50.0) == "paved", "route sans colonne : partout « paved »")


func _test_effective() -> void:
	_check(RoadSurface.effective("dirt", "off") == "paved", "off : bitume partout")
	_check(RoadSurface.effective("dirt", "auto") == "dirt" and RoadSurface.effective("paved", "auto") == "paved",
		"auto : colonne de la route")
	_check(RoadSurface.effective("paved", "gravel") == "gravel", "surface imposée sur la trace revêtue (U-Q8)")
	var s := RoadSurface.surfaces_of({"surfaces": {"dirt": {"color": "#806040", "width_m": 2.5}}})
	_check(is_equal_approx(s["dirt"]["width_m"], 2.5) and s["dirt"]["color"].is_equal_approx(Color.html("#806040"))
		and is_equal_approx(s["gravel"]["width_m"], 3.5) and is_equal_approx(s["compacted"]["width_m"], 4.0),
		"surfaces du thème, valeurs par défaut pour le reste")


# Critère 2
func _test_identical_when_off() -> void:
	var plain = _make_route(1500.0)
	var dirt = _make_route(1500.0, _column(1500.0, 0.0, "dirt"))
	var ok := true
	for k in range(RoadBuilder.chunk_count(plain)):
		var before := RoadBuilder.build_chunk_arrays(plain, k)
		ok = ok and _same(before, RoadBuilder.build_chunk_arrays(plain, k, RoadBuilder.ROAD_WIDTH_M, {"mode": "auto"}))
		ok = ok and _same(before, RoadBuilder.build_chunk_arrays(dirt, k, RoadBuilder.ROAD_WIDTH_M, {"mode": "off"}))
		ok = ok and before[Mesh.ARRAY_COLOR] == null
	_check(ok, "auto sans colonne et option coupée : ruban identique à celui d'avant U22")
	var forced := RoadBuilder.build_chunk_arrays(plain, 0, RoadBuilder.ROAD_WIDTH_M, {"mode": "gravel"})
	var cols: PackedColorArray = forced[Mesh.ARRAY_COLOR]
	var all_gravel := cols.size() > 0
	for c in cols:
		all_gravel = all_gravel and is_zero_approx(c.a)
	var w := _widths(forced)
	var mean := 0.0
	for x in w:
		mean += x
	mean /= w.size()
	_check(all_gravel and absf(mean - 3.5) < 0.2, "gravel imposé : gravier de bout en bout, %.2f m de large" % mean)


# Critère 3
func _test_dirt_width_and_joints() -> void:
	var r = _make_route(2400.0, _column(2400.0, 300.0, "dirt"))
	var g := {"mode": "auto", "surfaces": RoadSurface.surfaces_of({})}
	var widths := PackedFloat64Array()
	var joints_ok := true
	var prev_last := PackedVector3Array()
	for k in range(RoadBuilder.chunk_count(r)):
		var arr := RoadBuilder.build_chunk_arrays(r, k, RoadBuilder.ROAD_WIDTH_M, g)
		var v: PackedVector3Array = arr[Mesh.ARRAY_VERTEX]
		var first := v.slice(0, RoadBuilder.VERTS_PER_SECTION)
		if k > 0:
			for i in range(RoadBuilder.VERTS_PER_SECTION):
				joints_ok = joints_ok and first[i].is_equal_approx(prev_last[i])
		prev_last = v.slice(v.size() - RoadBuilder.VERTS_PER_SECTION)
		var s_values := RoadBuilder.section_s(r, k)
		var ws := _widths(arr)
		for j in range(ws.size()):
			if s_values[j] >= 310.0:
				widths.append(ws[j])
	var mean := 0.0
	var lo := INF
	var hi := -INF
	for x in widths:
		mean += x
		lo = minf(lo, x)
		hi = maxf(hi, x)
	mean /= widths.size()
	_check(absf(mean - 3.0) <= 0.2, "portion dirt : largeur moyenne %.3f m (3 m à 0,2 m près)" % mean)
	_check(hi - lo > 0.05 and hi - lo <= 4.0 * RoadSurface.EDGE_NOISE_M + 1e-6,
		"bords irréguliers : largeur de %.2f à %.2f m" % [lo, hi])
	_check(joints_ok, "tronçons raccordés : dernière coupe d'un tronçon = première du suivant")
	var a0 := RoadBuilder.build_chunk_arrays(r, 0, RoadBuilder.ROAD_WIDTH_M, g)
	var w0 := _widths(a0)
	var ss := RoadBuilder.section_s(r, 0)
	var at := func(s: float) -> float: return w0[ss.find(s)]
	_check(is_equal_approx(at.call(296.0), 6.0) and at.call(298.0) < 6.0 and at.call(302.0) < at.call(298.0) and at.call(304.0) < 3.3,
		"biseau de 5 m : 6 m à 296 m, %.2f m à 298 m, %.2f m à 302 m, %.2f m à 304 m" % [at.call(298.0), at.call(302.0), at.call(304.0)])
	var c: PackedColorArray = a0[Mesh.ARRAY_COLOR]
	var uv2: PackedVector2Array = a0[Mesh.ARRAY_TEX_UV2]
	var sec_400 := ss.find(400.0) * RoadBuilder.VERTS_PER_SECTION
	var sec_100 := ss.find(100.0) * RoadBuilder.VERTS_PER_SECTION
	_check(is_zero_approx(c[sec_400].a) and is_equal_approx(c[sec_100].a, 1.0)
		and c[sec_400].is_equal_approx(Color(RoadSurface.DEFAULT_COLOR["dirt"], 0.0))
		and absf(uv2[sec_400].x - 1.5) < 0.3 and is_equal_approx(uv2[sec_100].x, 3.0),
		"couleur de la surface (alpha = part de bitume) et demi-largeur dans UV2")
	# Coût : construction d'un tronçon avec gravel au plus 3 fois celle d'avant
	var t0 := Time.get_ticks_usec()
	for i in range(3):
		RoadBuilder.build_chunk_arrays(r, 1)
	var t_plain := Time.get_ticks_usec() - t0
	t0 = Time.get_ticks_usec()
	for i in range(3):
		RoadBuilder.build_chunk_arrays(r, 1, RoadBuilder.ROAD_WIDTH_M, g)
	var t_gravel := Time.get_ticks_usec() - t0
	_check(t_gravel <= 3 * t_plain + 30000, "coût : %.1f ms avec gravel, %.1f ms sans (3 tronçons)" % [t_gravel / 1000.0, t_plain / 1000.0])


func _eval(kind: String, intensity: float) -> Dictionary:
	var w := WeatherModel.from_theme({"weather": {"kind": kind, "intensity": intensity}})
	return WeatherModel.evaluate(w, 500.0, 500.0, {"dir": Vector3.ZERO, "strength": 0.0})


# Critère 5
func _test_dust() -> void:
	for preset in ["low", "medium", "high"]:
		var budget: int = QualityPresets.living(preset)["weather_particles"]
		var p = WeatherParticles.new()
		root.add_child(p)
		p.configure(budget)
		p.update(Vector3.ZERO, _eval("clear", 0.0))
		p.update_dust(Vector3.ZERO, Vector3(0, 0, 1), 8.0, "dirt")
		var dust: GPUParticles3D = p.get_emitter("dust")
		var dry_on := dust.emitting
		var total := dust.amount + p.get_emitter("rain").amount
		p.update(Vector3.ZERO, _eval("rain", 0.6))
		p.update_dust(Vector3.ZERO, Vector3(0, 0, 1), 8.0, "dirt")
		_check(dry_on and not dust.emitting and total <= budget,
			"%s : poussière par temps sec (%d grains), aucune sous la pluie, total %d ≤ %d" % [preset, dust.amount, total, budget])
		p.queue_free()
	_check(not WeatherParticles.dust_wanted("paved", 8.0, true) and not WeatherParticles.dust_wanted("compacted", 8.0, true)
		and not WeatherParticles.dust_wanted("dirt", 1.0, true) and WeatherParticles.dust_wanted("gravel", 5.0, true),
		"poussière seulement sur dirt et gravel, en roulant")


func _test_sound() -> void:
	var m = SoundModel.new()
	var state := {"speed_kmh": 30.0, "power_w": 200.0, "cadence": 85.0, "paused": false}
	m.on_state(state, Vector3.ZERO, 0.0)
	var paved: Dictionary = m.evaluate(0.0)["gravel"]
	m.set_surface("gravel")
	var gravel: Dictionary = m.evaluate(0.1)["gravel"]
	for i in range(80):   # 12 dB/s au plus : 8 s pour monter du silence
		m.on_state(state, Vector3.ZERO, 0.2 + i * 0.1)
		gravel = m.evaluate(0.2 + i * 0.1)["gravel"]
	var target := SoundModel._target_gravel_db("gravel", 30.0, false)
	_check(paved["volume_db"] <= SoundModel.SILENCE_DB and is_equal_approx(gravel["volume_db"], target),
		"crissement : silence sur le bitume, %.1f dB à 30 km/h sur le gravier" % gravel["volume_db"])
	_check(SoundModel._target_gravel_db("gravel", 35.0, false) > SoundModel._target_gravel_db("gravel", 15.0, false)
		and SoundModel._target_gravel_db("compacted", 30.0, false) < target
		and SoundModel._target_gravel_db("dirt", 30.0, true) <= SoundModel.SILENCE_DB,
		"volume selon la vitesse, plus bas sur compacted, silence en pause")


func _test_args() -> void:
	_check(EngineArgs.parse(PackedStringArray([]))["gravel"] == "off", "--gravel absent : off")
	_check(EngineArgs.parse(PackedStringArray(["--gravel=dirt"]))["gravel"] == "dirt", "--gravel=dirt lu")


func _test_menu_setting() -> void:
	var it := {"key": "gravel.mode", "label": "Gravel", "group": "ride", "type": "choice",
		"value": "off", "choices": RoadSurface.MODES.duplicate(), "applies": "next_session",
		"help": "Coupé : bitume partout. Chemins réels : seules les portions non revêtues du parcours."}
	var texts := []
	for m in RoadSurface.MODES:
		texts.append(SettingsViewModel.format_value(it, m))
	_check(texts == ["coupé", "chemins réels", "chemin compact", "gravier", "terre"], "choix du menu en français : %s" % [texts])
	var vm := SettingsViewModel.new()
	vm.on_settings({"items": [it]})
	_check(SettingsViewModel.group_of(it) == "ride", "rangé dans « Séance »")
	var lines: Array = vm.sheet("gravel.mode")["lines"]
	_check(lines.size() == 3 and str(lines[1]) == it["help"] and str(lines[2]) == "S'applique à la séance suivante",
		"carte de détail : choix, légende, séance suivante")
	vm.begin("gravel.mode")
	vm.step(+1)
	vm.step(+1)
	_check(str(vm.sheet("gravel.mode")["tiles"][0]["value"]) == "chemin compact", "en modification : la carte suit la valeur de la rangée")
	vm.cancel()
	_check(str(vm.sheet("gravel.mode")["tiles"][0]["value"]) == "coupé", "modification annulée : valeur enregistrée")
	it.erase("help")
	_check(vm.sheet("gravel.mode")["lines"].size() == 2, "sans légende : pas de ligne de plus")


func _run() -> void:
	_test_route_column()
	_test_effective()
	_test_identical_when_off()
	_test_dirt_width_and_joints()
	_test_dust()
	_test_sound()
	_test_args()
	_test_menu_setting()
	print("test_road_surface : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
