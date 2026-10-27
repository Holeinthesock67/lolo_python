extends RefCounted

## Avatar du cycliste sans affichage (lot V6, contrat IPC 1.4 §5) : réglages lus dans
## `hello_ack.config.progression.avatar` avec leurs défauts et leurs bornes, angle du pédalier intégré
## depuis la cadence, position assis ou en danseuse avec hystérésis.
##
## - Réglages : taille (`height`), silhouette (`build`), peau, cheveux, couleur des cheveux, deux couleurs
##   de tenue (indices de palettes fixes) et numéro. Une valeur absente ou hors liste reprend son défaut :
##   l'avatar s'affiche toujours (core sans `progression` : avatar par défaut).
## - Pédalier : l'angle avance de cadence × temps écoulé entre deux appels (la cadence de la dernière trame
##   sert d'extrapolation) ; il reste figé à 0 tr/min, sans cadence et en pause. Un écart de temps long
##   (onglet gelé, retour du core) est borné par MAX_STEP_S.
## - Danseuse : au-dessus de `standing_grade_pct` (pente) ou de `standing_power_pct` (% de la FTP) ;
##   retour assis quand la pente est repassée 1 point sous son seuil et la puissance 10 points de FTP sous
##   le sien, au moins MIN_STANDING_S après le passage debout.
## Pas de class_name : charger par preload("res://scripts/avatar_model.gd").

const HEIGHTS := ["S", "M", "L", "XL"]
const BUILDS := ["slim", "medium", "strong"]
const SKIN_MAX := 7
const HAIR_MAX := 5
const HAIR_COLOR_MAX := 7
const KIT_MAX := 15
const NUMBER_MAX := 999
const GRADE_BOUNDS := [3.0, 15.0]     # `[avatar] standing_grade_pct`, comme le core
const POWER_BOUNDS := [100.0, 300.0]  # `[avatar] standing_power_pct`

const DEFAULTS := {
	"height": "M", "build": "medium", "skin": 3, "hair": 2, "hair_color": 1,
	"kit_primary": 4, "kit_secondary": 11, "number": 0,
	"standing_grade_pct": 8.0, "standing_power_pct": 150.0,
}

const GRADE_EXIT_MARGIN_PCT := 1.0
const POWER_EXIT_MARGIN_PCT := 10.0
const MIN_STANDING_S := 2.0
const MAX_STEP_S := 0.25

## Palettes fixes (le Garage et V7 les reprennent) : on choisit un indice, jamais une couleur libre.
const SKIN_COLORS := [
	Color("f6d9c3"), Color("efc4a2"), Color("e0a97f"), Color("c98b5e"),
	Color("a96a42"), Color("8a4f2d"), Color("6a3a20"), Color("4a2812")]
const HAIR_COLORS := [
	Color("1b1410"), Color("3b2a1e"), Color("6b4428"), Color("a8763a"),
	Color("d9b66a"), Color("a63a22"), Color("8c8c90"), Color("e8e4dc")]
const KIT_COLORS := [
	Color("d62839"), Color("f26b21"), Color("f2c230"), Color("9bc53d"),
	Color("2a9d5c"), Color("1fa3a3"), Color("2b7bd6"), Color("1d3f8f"),
	Color("6a3fb5"), Color("c13c9e"), Color("f2f2f2"), Color("b8bcc4"),
	Color("6b7079"), Color("2a2d33"), Color("7a4a2a"), Color("e8d9b0")]
## Échelle par taille et par silhouette (hauteur du corps, épaisseur du tronc et des membres).
const HEIGHT_SCALE := {"S": 0.92, "M": 1.0, "L": 1.07, "XL": 1.14}
const BUILD_SCALE := {"slim": 0.88, "medium": 1.0, "strong": 1.14}

var settings: Dictionary = DEFAULTS.duplicate()
var ftp_w := 0.0
var crank_angle := 0.0          # radians, pédale droite ; la gauche est décalée de π
var standing := false
var cadence_rpm := 0.0
var _last_t := -1.0
var _stand_since := -1000.0


## Réglages complets et bornés à partir d'un dictionnaire du contrat (ou de n'importe quoi).
static func parse_settings(raw) -> Dictionary:
	var out: Dictionary = DEFAULTS.duplicate()
	if not (raw is Dictionary):
		return out
	if str(raw.get("height", "")) in HEIGHTS:
		out["height"] = str(raw["height"])
	if str(raw.get("build", "")) in BUILDS:
		out["build"] = str(raw["build"])
	for key in ["skin", "hair", "hair_color", "kit_primary", "kit_secondary", "number"]:
		var hi := {"skin": SKIN_MAX, "hair": HAIR_MAX, "hair_color": HAIR_COLOR_MAX,
			"kit_primary": KIT_MAX, "kit_secondary": KIT_MAX, "number": NUMBER_MAX}[key] as int
		var v = raw.get(key)
		if (v is int or (v is float and v == floorf(v))) and int(v) >= 0 and int(v) <= hi:
			out[key] = int(v)
	for key in ["standing_grade_pct", "standing_power_pct"]:
		var b: Array = GRADE_BOUNDS if key == "standing_grade_pct" else POWER_BOUNDS
		var v = raw.get(key)
		if (v is int or v is float) and float(v) >= b[0] and float(v) <= b[1]:
			out[key] = float(v)
	return out


static func height_scale(height: String) -> float:
	return float(HEIGHT_SCALE.get(height, 1.0))


static func build_scale(build: String) -> float:
	return float(BUILD_SCALE.get(build, 1.0))


func configure(raw_settings, ftp: float) -> void:
	settings = parse_settings(raw_settings)
	ftp_w = maxf(ftp, 0.0)


## Avance d'une image. `cadence`, `power` et `grade` viennent de la dernière trame `state` (ou null).
## Renvoie vrai quand la position change (assis ↔ danseuse).
func update(now_s: float, cadence, power, grade, paused: bool) -> bool:
	var dt := 0.0 if _last_t < 0.0 else clampf(now_s - _last_t, 0.0, MAX_STEP_S)
	_last_t = now_s
	cadence_rpm = float(cadence) if (cadence is float or cadence is int) and float(cadence) > 0.0 else 0.0
	if not paused and cadence_rpm > 0.0:
		crank_angle = fposmod(crank_angle + cadence_rpm / 60.0 * TAU * dt, TAU)
	var was := standing
	var g := float(grade) if (grade is float or grade is int) else 0.0
	var p := float(power) if (power is float or power is int) else 0.0
	var pct := p / ftp_w * 100.0 if ftp_w > 0.0 else 0.0
	var grade_on := float(settings["standing_grade_pct"])
	var power_on := float(settings["standing_power_pct"])
	if not standing:
		if g >= grade_on or pct >= power_on:
			standing = true
			_stand_since = now_s
	elif now_s - _stand_since >= MIN_STANDING_S \
			and g < grade_on - GRADE_EXIT_MARGIN_PCT and pct < power_on - POWER_EXIT_MARGIN_PCT:
		standing = false
	return standing != was


func reset() -> void:
	crank_angle = 0.0
	standing = false
	cadence_rpm = 0.0
	_last_t = -1.0
	_stand_since = -1000.0


## Vue demandée → avatar visible ? Caché en vue subjective (la caméra est dans la tête), visible ailleurs.
static func visible_in_view(view: String) -> bool:
	return view != "subjective"
