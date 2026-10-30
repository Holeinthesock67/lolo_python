extends RefCounted

## Garde-fou de charge (lot Y6, étape 2), sans nœud. Quand la carte graphique sature plusieurs secondes
## (village, pluie, foule), coupe un à un les effets les plus chers du préréglage, puis les rend quand la
## charge redescend. La résolution ne change jamais (consigne du propriétaire du 27 octobre), et aucun
## réglage qui recompile un shader en séance (qualité des ombres) n'est touché.
##
## Entrée : le temps GPU de la vue à chaque image (RenderingServer.viewport_get_measured_render_time_gpu).
## Moyenne glissante sur WINDOW_S ; au-dessus de GPU_HIGH_MS sur une fenêtre pleine, l'effet suivant de
## SHED_ORDER est coupé. La première fenêtre pleine après une coupe mesure ce qu'elle a fait gagner (coût de
## l'effet) ; le dernier effet coupé revient quand la moyenne plus son coût reste sous RESTORE_MS pendant
## LOW_HOLD_S (il ne refera pas dépasser GPU_HIGH_MS), ou, si la scène s'est allégée depuis, sous GPU_LOW_MS
## pendant LOW_HOLD_S. Jamais deux changements à moins de MIN_GAP_S ; la fenêtre repart de zéro après chaque
## changement, pour mesurer le nouvel état. Coupé dans config.toml par `[render] load_guard = false` (mesures des préréglages).
## Pas de class_name : charger par preload("res://scripts/load_guard.gd").

const RenderQuality := preload("res://scripts/render_quality.gd")

const GPU_HIGH_MS := 13.0   # 80 % d'une image à 60 Hz
const GPU_LOW_MS := 9.0
## Retour d'un effet : moyenne + coût mesuré de l'effet sous ce seuil (marge de 0,5 ms sous la coupe).
const RESTORE_MS := 12.5
const WINDOW_S := 3.0
const LOW_HOLD_S := 10.0
const MIN_GAP_S := 3.0
## Ordre de coupe, du plus cher au moins visible ; « msaa » passe de 4× (ou 8×) à 2×.
const SHED_ORDER := ["ssil", "ssao", "glow", "msaa"]
const LABELS := {"ssil": "SSIL", "ssao": "SSAO", "glow": "glow", "msaa": "MSAA 2×"}
const MSAA_SHED := 2

var enabled := true
## Effets coupés, dans l'ordre de coupe (le dernier revient le premier).
var shed: Array[String] = []
var _available: Array[String] = []
var _samples: Array = []   # [durée (s), temps GPU (ms)] de la fenêtre glissante
var _window_s := 0.0
var _low_s := 0.0
var _since_change_s := INF
## Gain mesuré à cette image (journal) : {"action": "gain", "effect", "gpu_ms", "gain_ms"} ou {}.
var gain_measured := {}
var _cost_ms := {}          # effet -> gain mesuré après sa coupe (ms)
var _pending := ""          # effet coupé dont le gain n'est pas encore mesuré
var _before_ms := 0.0       # moyenne qui a déclenché la coupe de `_pending`


## `img` : QualityPresets.image du préréglage ; seuls ses effets allumés peuvent être coupés.
func _init(img: Dictionary = {}, on := true, forward_plus := true) -> void:
	enabled = on
	reset(img, forward_plus)


## Nouveau préréglage : rien de coupé, fenêtre vide.
func reset(img: Dictionary, forward_plus := true) -> void:
	shed.clear()
	_available.clear()
	_cost_ms.clear()
	_pending = ""
	for e in SHED_ORDER:
		if is_available(e, img, forward_plus):
			_available.append(e)
	_restart_window()
	_since_change_s = INF


## Vrai si l'effet `e` est allumé par le préréglage `img` (SSAO et SSIL n'existent qu'en Forward+).
static func is_available(e: String, img: Dictionary, forward_plus: bool) -> bool:
	match e:
		"ssil", "ssao":
			return forward_plus and str(img.get(e, "off")) != "off"
		"glow":
			return bool(img.get("glow", false))
		"msaa":
			return int(img.get("msaa", 0)) > MSAA_SHED
	return false


## Une image de `delta_s` secondes rendue en `gpu_ms` ; renvoie {} ou le changement à appliquer :
## {"action": "cut" ou "restore", "effect": "ssil"…, "gpu_ms": moyenne de la fenêtre}. Le gain d'une coupe,
## mesuré sur la fenêtre qui la suit, est posé dans `gain_measured` pour le journal.
func step(gpu_ms: float, delta_s: float) -> Dictionary:
	gain_measured = {}
	if not enabled or delta_s <= 0.0:
		return {}
	_since_change_s += delta_s
	if gpu_ms <= 0.0:   # mesure pas encore prête (premières images, vue cachée)
		return {}
	_samples.append([delta_s, gpu_ms])
	_window_s += delta_s
	while _samples.size() > 1 and _window_s - float(_samples[0][0]) >= WINDOW_S - 1e-6:
		_window_s -= float(_samples.pop_front()[0])
	var avg := average_ms()
	var full := _window_s >= WINDOW_S - 1e-6
	if full and _pending != "":
		_cost_ms[_pending] = maxf(_before_ms - avg, 0.0)
		gain_measured = {"action": "gain", "effect": _pending, "gpu_ms": avg, "gain_ms": _cost_ms[_pending]}
		_pending = ""
	# Le calme se compte dès la première image (le critère du gain, une fois ce gain mesuré) ; la saturation
	# attend une fenêtre pleine.
	if not shed.is_empty() and (avg < GPU_LOW_MS
			or _pending == "" and avg + float(_cost_ms.get(shed.back(), 0.0)) < RESTORE_MS):
		_low_s += delta_s
	else:
		_low_s = 0.0
	if _since_change_s < MIN_GAP_S - 1e-6:
		return {}
	if full and avg > GPU_HIGH_MS and shed.size() < _available.size():
		var e := _available[shed.size()]
		shed.append(e)
		_pending = e
		_before_ms = avg
		return _changed("cut", e, avg)
	if _low_s >= LOW_HOLD_S - 1e-6:
		return _changed("restore", shed.pop_back(), avg)
	return {}


## Temps GPU moyen (ms) de la fenêtre, pondéré par la durée des images.
func average_ms() -> float:
	if _window_s <= 0.0:
		return 0.0
	var s := 0.0
	for sample in _samples:
		s += float(sample[0]) * float(sample[1])
	return s / _window_s


## Texte des effets coupés, pour le compteur d'images/s (« SSIL, SSAO ») ; vide si rien n'est coupé.
func shed_text() -> String:
	var names: Array[String] = []
	for e in shed:
		names.append(str(LABELS[e]))
	return ", ".join(names)


## Applique l'état du garde-fou par-dessus le préréglage `img` déjà posé par RenderQuality.apply_image :
## les effets coupés éteints, les autres comme le préréglage les veut.
func apply(img: Dictionary, env: Environment, viewport: Viewport, forward_plus: bool) -> void:
	env.ssil_enabled = is_available("ssil", img, forward_plus) and not shed.has("ssil")
	env.ssao_enabled = is_available("ssao", img, forward_plus) and not shed.has("ssao")
	env.glow_enabled = is_available("glow", img, forward_plus) and not shed.has("glow")
	viewport.msaa_3d = RenderQuality.MSAA[MSAA_SHED if shed.has("msaa") else int(img["msaa"])]


## Ligne du journal de l'engine pour un changement renvoyé par `step`, à `t_s` secondes du lancement.
static func log_line(change: Dictionary, t_s: float) -> String:
	if change["action"] == "gain":
		return "[charge] t=%.1f s gain de %s : %.1f ms (GPU %.1f ms en moyenne sur %d s)" % [t_s,
			LABELS[change["effect"]], float(change["gain_ms"]), float(change["gpu_ms"]), int(WINDOW_S)]
	var verb := "coupé" if change["action"] == "cut" else "rendu"
	return "[charge] t=%.1f s %s : %s (GPU %.1f ms en moyenne sur %d s)" % [t_s, verb, LABELS[change["effect"]],
		float(change["gpu_ms"]), int(WINDOW_S)]


func _changed(action: String, e: String, avg: float) -> Dictionary:
	_since_change_s = 0.0
	_restart_window()
	return {"action": action, "effect": e, "gpu_ms": avg}


func _restart_window() -> void:
	_samples.clear()
	_window_s = 0.0
	_low_s = 0.0
