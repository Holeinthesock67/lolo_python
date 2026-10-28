extends RefCounted

## Charte graphique du mode Cyber-Rogue (lot R17), partie données : jetons de couleur, intensités par
## préréglage de qualité et variante « couleurs adaptées ». Aucune couleur n'est écrite en dur ailleurs
## dans le mode : on prend le jeton de son rôle ici. Pas de class_name : charger par
## preload("res://scripts/rogue/neon_palette.gd").
##
## Charte (docs/lots/LOT_R17_direction_artistique.md §4.1) :
## - Formes : lignes et arêtes lumineuses sur volumes presque noirs (`void` éclairci de 10 %), pas de
##   dégradé photo, pas de texture (invariant A9).
## - Lisibilité : une couleur = un rôle ; le joueur est la seule source cyan, le danger est toujours rouge.
## - Mouvement : décor lent (0,5 à 1 Hz), événements de jeu jamais plus de 3 clignotements par seconde.
## Les cinq couleurs de pente de R10 sont aussi des jetons (`grade_*`) ; la pente « plat » est un cyan
## plus sombre et plus vert que `player`, pour que le joueur reste la seule source cyan vive.

const VOID := "void"
const NIGHT := "night"
const GRID := "grid"
const PLAYER := "player"
const ENERGY := "energy"
const PARRY := "parry"
const GOLD := "gold"
const DANGER := "danger"
const GLITCH := "glitch"
const NEUTRAL := "neutral"
const GRADE_DOWN := "grade_down"
const GRADE_FLAT := "grade_flat"
const GRADE_UP := "grade_up"
const GRADE_HARD := "grade_hard"
const GRADE_WALL := "grade_wall"

## Valeurs de départ (charte §4.1).
const COLORS := {
	"void": Color("05060F"),
	"night": Color("0B1030"),
	"grid": Color("1E6BFF"),
	"player": Color("18F0FF"),
	"energy": Color("FF8A1E"),
	"parry": Color("2E7BFF"),
	"gold": Color("FFD23C"),
	"danger": Color("FF2E4C"),
	"glitch": Color("C23CFF"),
	"neutral": Color("E8F0FF"),
	"grade_down": Color("2A5CFF"),
	"grade_flat": Color("1FB8A8"),
	"grade_up": Color("F0E03C"),
	"grade_hard": Color("FF7A1E"),
	"grade_wall": Color("E01EC8"),
}

## Variante « couleurs adaptées » (daltonisme) : danger et énergie, confondables, s'écartent en clarté
## et en teinte ; la forme les distingue aussi (motifs de `ADAPTED_PATTERNS`).
const ADAPTED_COLORS := {
	"danger": Color("FF3DA0"),
	"energy": Color("FFB000"),
}

## Motif qui double la couleur quand la variante adaptée est active.
const ADAPTED_PATTERNS := {
	"danger": "hatch",      # hachures
	"energy": "dots",       # pointillés
	"parry": "chevron",
	"gold": "plain",
}

## Intensité émissive des lignes (multiplicateur de la couleur) selon le préréglage de qualité.
const INTENSITY := {
	"low": 1.6,
	"medium": 2.0,
	"high": 2.4,
}
const GRID_INTENSITY := 0.35
const ADAPTED_SETTING := "rogue_adapted_colors"

## Un volume sombre : `void` éclairci de 10 %.
const BODY_LIGHTEN := 0.10


static func tokens() -> Array:
	return COLORS.keys()


static func color(token: String, adapted: bool = false) -> Color:
	if adapted and ADAPTED_COLORS.has(token):
		return ADAPTED_COLORS[token]
	assert(COLORS.has(token), "jeton inconnu : %s" % token)
	return COLORS[token]


## Couleur d'un volume sombre de la charte.
static func body_color() -> Color:
	return COLORS["void"].lerp(Color.WHITE, BODY_LIGHTEN)


## Couleur émissive d'une ligne : le jeton multiplié par l'intensité du préréglage.
static func glow_color(token: String, preset: String = "low", adapted: bool = false) -> Color:
	var k: float = INTENSITY.get(preset, INTENSITY["low"])
	var c := color(token, adapted)
	return Color(c.r * k, c.g * k, c.b * k, 1.0)


static func pattern(token: String, adapted: bool) -> String:
	return ADAPTED_PATTERNS.get(token, "plain") if adapted else "plain"


## Couleur de la pente affichée sur le ruban (pourcentage), seuils de R10.
static func grade_token(grade_pct: float) -> String:
	if grade_pct < -3.0:
		return GRADE_DOWN
	if grade_pct < 1.5:
		return GRADE_FLAT
	if grade_pct < 4.0:
		return GRADE_UP
	if grade_pct < 6.5:
		return GRADE_HARD
	return GRADE_WALL


## Luminance relative WCAG d'une couleur opaque.
static func luminance(c: Color) -> float:
	var ch := func(v: float) -> float: return v / 12.92 if v <= 0.03928 else pow((v + 0.055) / 1.055, 2.4)
	return 0.2126 * ch.call(c.r) + 0.7152 * ch.call(c.g) + 0.0722 * ch.call(c.b)


## Rapport de contraste WCAG de deux couleurs opaques.
static func contrast(a: Color, b: Color) -> float:
	var la := luminance(a)
	var lb := luminance(b)
	return (maxf(la, lb) + 0.05) / (minf(la, lb) + 0.05)
