extends SceneTree

## Tests unitaires sans écran du garde-fou de charge (`load_guard.gd`, lot Y6 étape 2), sur des temps GPU
## simulés à 60 images/s. Vérifie les critères du cahier : 3 s à 15 ms coupent le SSIL, 3 s de plus coupent
## le SSAO, 10 s à 8 ms rendent le SSAO ; jamais deux changements à moins de 3 s ; rien entre les deux seuils ;
## seuls les effets allumés du préréglage sont coupés ; coupé, il ne fait rien ; état appliqué à
## l'Environment et au viewport sans toucher à la résolution.
## Lancement : godot --headless --path engine --script res://tests/unit/test_load_guard.gd

const LoadGuard := preload("res://scripts/load_guard.gd")
const QualityPresets := preload("res://scripts/quality_presets.gd")
const RenderQuality := preload("res://scripts/render_quality.gd")

const DT := 1.0 / 60.0

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


var gains: Array = []   # gains mesurés après les coupes (`gain_measured`, journal seulement)


## `seconds` secondes à `gpu_ms` ; renvoie les changements avec l'instant (s, depuis `t0`) où ils tombent.
func _feed(g, gpu_ms: float, seconds: float, t0 := 0.0) -> Array:
	var out := []
	var n := int(round(seconds / DT))
	for i in n:
		var c: Dictionary = g.step(gpu_ms, DT)
		if not g.gain_measured.is_empty():
			gains.append(g.gain_measured)
		if not c.is_empty():
			c["t"] = t0 + (i + 1) * DT
			out.append(c)
	return out


func _run() -> void:
	var high: Dictionary = QualityPresets.image("high")
	var g = LoadGuard.new(high)

	# Saturation : SSIL coupé à 3 s, SSAO 3 s plus tard.
	var c := _feed(g, 15.0, 3.0)
	_check(c.size() == 1 and c[0]["action"] == "cut" and c[0]["effect"] == "ssil" and absf(c[0]["t"] - 3.0) < 0.05,
		"3 s à 15 ms : SSIL coupé à 3 s (%s)" % str(c))
	c = _feed(g, 15.0, 3.0, 3.0)
	_check(c.size() == 1 and c[0]["effect"] == "ssao" and absf(c[0]["t"] - 6.0) < 0.05,
		"3 s de plus : SSAO coupé à 6 s (%s)" % str(c))
	_check(g.shed_text() == "SSIL, SSAO", "texte des effets coupés : « %s »" % g.shed_text())

	# Retour au calme : SSAO rendu après 10 s, puis SSIL 10 s plus tard.
	c = _feed(g, 8.0, 10.0)
	_check(c.size() == 1 and c[0]["action"] == "restore" and c[0]["effect"] == "ssao" and absf(c[0]["t"] - 10.0) < 0.05,
		"10 s à 8 ms : SSAO rendu (%s)" % str(c))
	c = _feed(g, 8.0, 10.0)
	_check(c.size() == 1 and c[0]["effect"] == "ssil" and g.shed.is_empty(), "10 s de plus : SSIL rendu, plus rien de coupé")

	# Pic passé, scène encore chargée (essai 7bc du 30 octobre, village en medium) : le SSAO, qui a fait gagner
	# 1,5 ms, revient puisque 10,7 + 1,5 reste sous 12,5 ms ; le SSIL (0,5 ms) ne revient pas tant que
	# 12,2 + 0,5 dépasse 12,5 ms.
	g = LoadGuard.new(high)
	_feed(g, 14.0, 3.0)
	_feed(g, 13.5, 3.0)
	_check(g.shed == ["ssil", "ssao"], "pic : SSIL puis SSAO coupés")
	c = _feed(g, 12.0, 3.0)
	c += _feed(g, 10.7, 15.0, 3.0)
	_check(not gains.is_empty() and gains.back()["effect"] == "ssao" and absf(gains.back()["gain_ms"] - 1.5) < 1e-3,
		"gain du SSAO mesuré sur la fenêtre suivant sa coupe : %s" % str(gains.back() if not gains.is_empty() else {}))
	_check(LoadGuard.log_line(gains.back(), 9.0).begins_with("[charge] t=9.0 s gain de SSAO : 1.5 ms"),
		"gain écrit au journal : « %s »" % LoadGuard.log_line(gains.back(), 9.0))
	_check(c.size() == 1 and c[0]["action"] == "restore" and c[0]["effect"] == "ssao" and c[0]["t"] >= 13.0 and c[0]["t"] <= 16.1,
		"10,7 ms après le pic : SSAO (gain 1,5 ms) rendu 10 à 13 s plus tard (%s)" % str(c))
	c = _feed(g, 12.2, 30.0)
	_check(c.is_empty() and g.shed == ["ssil"], "12,2 ms ensuite : SSIL (gain 0,5 ms) reste coupé, rien n'oscille")

	# Entre les deux seuils, avec un gain qui ferait repasser au-dessus : rien ne bouge.
	g = LoadGuard.new(high)
	_feed(g, 15.0, 3.0)
	c = _feed(g, 11.0, 30.0)
	_check(c.is_empty() and g.shed == ["ssil"], "30 s à 11 ms après un gain de 4 ms : rien ne change (coupés : %s)" % str(g.shed))

	# Jamais deux changements à moins de 3 s, même avec une charge énorme ; tout coupé au plus une fois.
	g = LoadGuard.new(high)
	c = _feed(g, 40.0, 30.0)
	var gaps_ok := true
	for i in range(1, c.size()):
		gaps_ok = gaps_ok and c[i]["t"] - c[i - 1]["t"] >= LoadGuard.MIN_GAP_S - 0.05
	_check(gaps_ok and c.size() == 4, "40 ms pendant 30 s : 4 coupes espacées d'au moins 3 s (%d)" % c.size())
	_check(g.shed == ["ssil", "ssao", "glow", "msaa"], "ordre de coupe SSIL, SSAO, glow, MSAA (%s)" % str(g.shed))

	# Un pic court ne coupe rien : la moyenne sur 3 s reste sous le seuil.
	g = LoadGuard.new(high)
	_feed(g, 8.0, 5.0)
	c = _feed(g, 30.0, 0.5)
	c += _feed(g, 8.0, 5.0)
	_check(c.is_empty(), "pic de 0,5 s à 30 ms : rien coupé")

	# Mesure pas encore prête (0 ms) : ignorée.
	g = LoadGuard.new(high)
	c = _feed(g, 0.0, 20.0)
	_check(c.is_empty(), "temps GPU nul (mesure absente) : rien ne change")

	# Préréglage low : ni SSAO, ni SSIL, ni MSAA ; seul le glow peut être coupé s'il est allumé.
	var low: Dictionary = QualityPresets.image("low")
	g = LoadGuard.new(low)
	c = _feed(g, 20.0, 30.0)
	var expected := ["glow"] if bool(low["glow"]) else []
	_check(g.shed == expected, "low : seuls ses effets allumés sont coupés (%s)" % str(g.shed))
	# Compatibility : pas de SSAO ni de SSIL à couper.
	g = LoadGuard.new(high, true, false)
	_feed(g, 20.0, 30.0)
	_check(not g.shed.has("ssil") and not g.shed.has("ssao"), "Compatibility : SSAO et SSIL jamais coupés")

	# Coupé (config.toml `[render] load_guard = false`) : rien.
	g = LoadGuard.new(high, false)
	c = _feed(g, 40.0, 30.0)
	_check(c.is_empty() and g.shed.is_empty(), "garde-fou coupé : aucun changement")

	# Application : effets coupés éteints, résolution intacte, MSAA 4× → 2×.
	var env := Environment.new()
	var vp := SubViewport.new()
	root.add_child(vp)
	g = LoadGuard.new(high)
	_feed(g, 40.0, 12.0)
	g.apply(high, env, vp, true)
	_check(not env.ssil_enabled and not env.ssao_enabled and not env.glow_enabled
		and vp.msaa_3d == RenderQuality.MSAA[2] and vp.scaling_3d_scale == 1.0,
		"tout coupé : SSIL, SSAO, glow éteints, MSAA 2×, résolution native")
	g.reset(high)
	g.apply(high, env, vp, true)
	_check(env.ssil_enabled and env.ssao_enabled and env.glow_enabled == bool(high["glow"])
		and vp.msaa_3d == RenderQuality.MSAA[int(high["msaa"])], "remis à zéro : effets du préréglage rendus")
	_check(LoadGuard.log_line({"action": "cut", "effect": "ssil", "gpu_ms": 15.04}, 40.25)
		== "[charge] t=40.2 s coupé : SSIL (GPU 15.0 ms en moyenne sur 3 s)", "ligne du journal horodatée")
	vp.queue_free()

	print("test_load_guard : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)


func _init() -> void:
	call_deferred("_run")
