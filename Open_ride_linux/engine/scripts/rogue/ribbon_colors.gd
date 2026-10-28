extends RefCounted

## Couleur du ruban selon la pente (lot R10 §4.2), partie données. Les cinq couleurs sont les jetons
## `grade_*` de la charte (neon_palette.gd, lot R17) : < −3 % bleu, −3 à +1,5 % cyan, +1,5 à +4 % jaune,
## +4 à +6,5 % orange, ≥ +6,5 % magenta (mur). Pas de class_name :
## preload("res://scripts/rogue/ribbon_colors.gd").

const Palette := preload("res://scripts/rogue/neon_palette.gd")

## Distance devant le joueur où les couleurs sont franches (10 à 15 s d'avance) ; au-delà, elles s'atténuent.
const AHEAD_M := 200.0
## Part de l'éclat gardée au-delà de AHEAD_M.
const FAR_DIM := 0.35


static func token_for(grade_pct: float) -> String:
	return Palette.grade_token(grade_pct)


static func color_for(grade_pct: float, adapted: bool = false) -> Color:
	return Palette.color(token_for(grade_pct), adapted)


## Couleurs franches de chaque intervalle du profil [[s_m, pente %], ...].
static func segment_colors(profile: Array, adapted: bool = false) -> Array:
	var out: Array = []
	for p in profile:
		out.append(color_for(float(p[1]), adapted))
	return out


## Facteur d'éclat d'un point du ruban à `s_m` quand le joueur est à `player_s` : 1 jusqu'à AHEAD_M devant
## lui, puis FAR_DIM après un fondu de 40 m (même courbe que le shader du ruban).
static func brightness(s_m: float, player_s: float) -> float:
	var t := clampf((s_m - player_s - AHEAD_M) / 40.0, 0.0, 1.0)
	t = t * t * (3.0 - 2.0 * t)
	return lerpf(1.0, FAR_DIM, t)
