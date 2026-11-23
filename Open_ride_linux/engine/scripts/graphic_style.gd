extends RefCounted

## Style graphique (lot CS1, réglage `render.style`, « Style graphique » de Réglages › Graphisme) : `realistic`
## (défaut, l'image du jeu telle quelle) ou `toon` (« dessin animé »). Le style est indépendant de la qualité
## (`render.quality` règle les distances et la densité, le style règle le look) et ne touche pas Cyber-Rogue,
## qui a sa scène et son environnement.
##
## Ce lot pose le réglage et son premier effet, les couleurs plus vives choisies par le propriétaire le
## 23 novembre (« vif », saturation 1,5 au lieu de RenderQuality.LOOK["saturation"]). L'ombrage à paliers, les
## contours et les aplats viennent aux lots CS2 à CS4 ; ils passeront par `variant()` : le même fichier de shader
## compilé une seconde fois derrière `#define STYLE_TOON`. En `realistic`, `variant()` rend le shader reçu, sans
## copie : le code compilé par défaut reste celui du fichier, au caractère près.
## Pas de class_name : charger par preload("res://scripts/graphic_style.gd").

const REALISTIC := "realistic"
const TOON := "toon"
const DEFAULT_STYLE := REALISTIC
const STYLES: Array[String] = [REALISTIC, TOON]
const SETTING_KEY := "render.style"
## Saturation de l'étalonnage en dessin animé (planches « Vif » du 23 novembre).
const TOON_SATURATION := 1.5
## Définition ajoutée devant le code d'un shader pour sa variante dessin animé.
const TOON_DEFINE := "STYLE_TOON"

static var _variants := {}


static func is_valid(style: String) -> bool:
	return style in STYLES


## Saturation de l'étalonnage : `base` (celle du préréglage, essais compris) en réaliste.
static func saturation(style: String, base: float) -> float:
	return TOON_SATURATION if style == TOON else base


## À appeler après chaque RenderQuality.apply_preset (qui repose la saturation commune) et à chaque changement
## du réglage : `base` est la saturation que le préréglage vient de poser.
static func apply(style: String, env: Environment, base: float) -> void:
	if env == null:
		return
	env.adjustment_saturation = saturation(style, base)


## Code d'un shader pour un style : inchangé en réaliste ; en dessin animé, précédé de `#define STYLE_TOON`
## (après la ligne `shader_type`, qui doit rester la première instruction).
static func variant_code(code: String, style: String) -> String:
	if style != TOON:
		return code
	var at := code.find("shader_type")
	var end := code.find(";", at) if at >= 0 else -1
	if end < 0:
		return code
	return code.substr(0, end + 1) + "\n#define " + TOON_DEFINE + "\n" + code.substr(end + 1)


## Shader à utiliser pour un style : le shader reçu en réaliste (même objet), une variante gardée en mémoire
## en dessin animé (une seule compilation par fichier).
static func variant(shader: Shader, style: String) -> Shader:
	if shader == null or style != TOON:
		return shader
	var key := shader.resource_path if shader.resource_path != "" else str(shader.get_instance_id())
	if not _variants.has(key):
		var out := Shader.new()
		out.code = variant_code(shader.code, TOON)
		_variants[key] = out
	return _variants[key]
