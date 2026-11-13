extends RefCounted

## Objets du Grand Prix côté engine (série GP, lot GP8) : noms, familles et pastilles des maquettes GP6
## validées le 7 novembre 2026 (charte cartoon CT9, aucun nouveau jeton de couleur) :
##
## | Famille | Jeton | Forme | Objets |
## | Pour soi | spark | rond | gel, gel_x3, star, team_car, stealth |
## | Attaque | hot | triangle | musette, musette_x3, homing |
## | Piège derrière soi | warm | carré | bottle, bottle_x3 |
## | Contre la tête | sling | losange | storm, headwind |
## | Défense | fresh | écu | bell |
##
## Noms et familles repris du core (`core/src/openride_core/grandprix/items.py` LABELS et FAMILIES ; test
## test_gp_hud.gd). La couleur n'est jamais seule : chaque famille a sa forme (règle 4 de CT9), et chaque
## objet son dessin à l'encre dans la pastille (sachet de gel, bidon, musette en toile, nuage, étoile,
## sonnette, manche à air, voiture d'équipe, silhouette en pointillés).
## Fonctions statiques seulement : draw_badge() dessine sur n'importe quel CanvasItem (HUD, bande de course).
## Pas de class_name : preload("res://scripts/grandprix/gp_items.gd").

# Jetons de la charte CT9 (ct9_lib.js des maquettes)
const INK := Color(0.082, 0.071, 0.110)        # #15121C
const PAPER := Color(1.0, 0.965, 0.878)        # #FFF6E0
const FRESH := Color(0.180, 0.545, 1.0)        # #2E8BFF
const WARM := Color(1.0, 0.549, 0.102)         # #FF8C1A
const HOT := Color(1.0, 0.180, 0.243)          # #FF2E3E
const DRAFT := Color(0.133, 0.878, 0.816)      # #22E0D0
const SLING := Color(0.651, 0.302, 1.0)        # #A64DFF
const SPARK := Color(1.0, 0.914, 0.239)        # #FFE93D

const IDS := ["gel", "gel_x3", "bottle", "bottle_x3", "musette", "musette_x3", "homing", "storm", "star", "bell",
	"headwind", "team_car", "stealth"]
const LABELS := {
	"gel": "Coup de fouet", "gel_x3": "Trois coups de fouet", "bottle": "Bidon glissant",
	"bottle_x3": "Trois bidons", "musette": "Musette lancée", "musette_x3": "Trois musettes",
	"homing": "Musette guidée", "storm": "Nuage d'orage", "star": "Super-forme", "bell": "Sonnette",
	"headwind": "Vent contraire", "team_car": "Voiture d'équipe", "stealth": "Furtif",
}
const FAMILIES := {
	"gel": "self", "gel_x3": "self", "star": "self", "team_car": "self", "stealth": "self",
	"musette": "attack", "musette_x3": "attack", "homing": "attack",
	"bottle": "trap", "bottle_x3": "trap",
	"storm": "leader", "headwind": "leader",
	"bell": "guard",
}
const CHARGES := {"gel_x3": 3, "bottle_x3": 3, "musette_x3": 3}
const FAMILY_COLOR := {"self": SPARK, "attack": HOT, "trap": WARM, "leader": SLING, "guard": FRESH}
const FAMILY_SHAPE := {"self": "circle", "attack": "triangle", "trap": "square", "leader": "diamond", "guard": "shield"}
## Familles dont un effet en cours sur un coureur veut dire qu'il a été touché (pastille `warm` à croix, §5.1).
const HIT_FAMILIES := ["attack", "trap", "leader"]


static func label(kind: String) -> String:
	return str(LABELS.get(kind, kind))


static func family(kind: String) -> String:
	return str(FAMILIES.get(kind, ""))


static func color(kind: String) -> Color:
	return FAMILY_COLOR.get(family(kind), PAPER)


static func shape(kind: String) -> String:
	return str(FAMILY_SHAPE.get(family(kind), "circle"))


static func charges(kind: String) -> int:
	return int(CHARGES.get(kind, 1))


static func known(kind: String) -> bool:
	return LABELS.has(kind)


## Objets qui portent la marque `breakaway` de l'Échappée (TT4) : le Furtif (lot GP4, items.py `self_fx`).
const UNSEEN := ["stealth"]


## Vrai quand un coureur est sous le Furtif (lot GP4) : `fx` du cycliste (`gp.fx`, [[objet, reste], ...]) ou d'un
## bot (`bots[].fx`, [objet, ...]). Son avatar est alors translucide, comme pendant l'Échappée (lot TT6).
static func unseen(fx) -> bool:
	if not (fx is Array):
		return false
	for e in fx:
		var kind = e[0] if e is Array and not e.is_empty() else e
		if kind is String and UNSEEN.has(kind):
			return true
	return false


## Contour de la pastille d'une forme, centrée sur `c`, de rayon `r`.
static func shape_points(form: String, c: Vector2, r: float) -> PackedVector2Array:
	match form:
		"triangle":
			return PackedVector2Array([c + Vector2(0, -r), c + Vector2(r * 0.95, r * 0.78), c + Vector2(-r * 0.95, r * 0.78)])
		"square":
			var h := r * 0.82
			return PackedVector2Array([c + Vector2(-h, -h), c + Vector2(h, -h), c + Vector2(h, h), c + Vector2(-h, h)])
		"diamond":
			return PackedVector2Array([c + Vector2(0, -r), c + Vector2(r, 0), c + Vector2(0, r), c + Vector2(-r, 0)])
		"shield":
			return PackedVector2Array([c + Vector2(-r * 0.8, -r * 0.85), c + Vector2(0, -r), c + Vector2(r * 0.8, -r * 0.85),
				c + Vector2(r * 0.8, -r * 0.05), c + Vector2(r * 0.45, r * 0.6), c + Vector2(0, r),
				c + Vector2(-r * 0.45, r * 0.6), c + Vector2(-r * 0.8, -r * 0.05)])
	var p := PackedVector2Array()
	for i in range(24):
		var a := TAU * i / 24.0
		p.append(c + Vector2(cos(a), sin(a)) * r)
	return p


## Pastille complète d'un objet : forme de la famille en aplat, bord à l'encre, dessin de l'objet.
## Objet inconnu : pastille papier sans dessin.
static func draw_badge(ci: CanvasItem, c: Vector2, r: float, kind: String) -> void:
	var pts := shape_points(shape(kind), c, r)
	ci.draw_colored_polygon(pts, color(kind))
	var closed := pts.duplicate()
	closed.append(pts[0])
	ci.draw_polyline(closed, INK, maxf(r * 0.11, 1.5), true)
	draw_glyph(ci, c + Vector2(0, r * 0.08 if shape(kind) == "triangle" else 0.0), r * 0.5, kind)


## Pastille « touché » de la bande de course : rond `warm` barré d'une croix (§5.1, choix 6).
static func draw_hit(ci: CanvasItem, c: Vector2, r: float) -> void:
	ci.draw_circle(c, r, WARM)
	ci.draw_arc(c, r, 0.0, TAU, 24, INK, maxf(r * 0.12, 1.5), true)
	var k := r * 0.45
	ci.draw_line(c + Vector2(-k, -k), c + Vector2(k, k), INK, maxf(r * 0.16, 1.5), true)
	ci.draw_line(c + Vector2(k, -k), c + Vector2(-k, k), INK, maxf(r * 0.16, 1.5), true)


## Dessin de l'objet à l'encre, dans un carré de demi-côté `s` autour de `c`.
static func draw_glyph(ci: CanvasItem, c: Vector2, s: float, kind: String) -> void:
	var w := maxf(s * 0.14, 1.2)
	match kind:
		"gel", "gel_x3":   # sachet de gel et son éclair
			_rect(ci, c, Vector2(s * 0.55, s * 0.8), PAPER, w)
			_poly(ci, [c + Vector2(s * 0.1, -s * 0.55), c + Vector2(-s * 0.25, s * 0.08), c + Vector2(0, s * 0.08),
				c + Vector2(-s * 0.1, s * 0.55), c + Vector2(s * 0.25, -s * 0.08), c + Vector2(0, -s * 0.08)], INK, 0.0)
		"bottle", "bottle_x3":   # bidon : corps, bouchon, bec
			_rect(ci, c + Vector2(0, s * 0.15), Vector2(s * 0.42, s * 0.7), PAPER, w)
			_rect(ci, c + Vector2(0, -s * 0.62), Vector2(s * 0.25, s * 0.14), INK, 0.0)
			ci.draw_line(c + Vector2(-s * 0.42, s * 0.05), c + Vector2(s * 0.42, s * 0.05), INK, w, true)
		"musette", "musette_x3", "homing":   # musette en toile et sa bandoulière
			ci.draw_arc(c + Vector2(0, -s * 0.2), s * 0.45, PI, TAU, 12, INK, w, true)
			_rect(ci, c + Vector2(0, s * 0.25), Vector2(s * 0.7, s * 0.45), PAPER, w)
			ci.draw_line(c + Vector2(-s * 0.7, s * 0.1), c + Vector2(s * 0.7, s * 0.1), INK, w, true)
			if kind == "homing":   # cible du verrouillage
				ci.draw_circle(c + Vector2(s * 0.62, -s * 0.62), s * 0.3, PAPER)
				ci.draw_arc(c + Vector2(s * 0.62, -s * 0.62), s * 0.3, 0.0, TAU, 16, HOT, w, true)
				ci.draw_circle(c + Vector2(s * 0.62, -s * 0.62), s * 0.1, HOT)
		"storm":   # nuage et éclair
			for k in [[Vector2(-0.4, 0.0), 0.38], [Vector2(0.05, -0.2), 0.48], [Vector2(0.45, 0.05), 0.35]]:
				ci.draw_circle(c + k[0] * s, s * k[1], PAPER)
				ci.draw_arc(c + k[0] * s, s * k[1], 0.0, TAU, 16, INK, w, true)
			_poly(ci, [c + Vector2(0, s * 0.2), c + Vector2(-s * 0.2, s * 0.65), c + Vector2(0, s * 0.6),
				c + Vector2(-s * 0.1, s * 0.95), c + Vector2(s * 0.2, s * 0.45), c + Vector2(0, s * 0.5)], INK, 0.0)
		"star":   # étoile à cinq branches
			var pts: Array = []
			for i in range(10):
				var a := -PI / 2.0 + PI * i / 5.0
				pts.append(c + Vector2(cos(a), sin(a)) * (s * (0.85 if i % 2 == 0 else 0.38)))
			_poly(ci, pts, PAPER, w)
		"bell":   # sonnette : dôme, base, levier
			ci.draw_circle(c + Vector2(0, s * 0.1), s * 0.55, PAPER)
			ci.draw_arc(c + Vector2(0, s * 0.1), s * 0.55, PI, TAU, 14, INK, w, true)
			_rect(ci, c + Vector2(0, s * 0.42), Vector2(s * 0.7, s * 0.14), INK, 0.0)
			ci.draw_line(c + Vector2(s * 0.3, -s * 0.4), c + Vector2(s * 0.7, -s * 0.7), INK, w, true)
		"headwind":   # manche à air : mât et trois rafales
			ci.draw_line(c + Vector2(-s * 0.7, -s * 0.7), c + Vector2(-s * 0.7, s * 0.8), INK, w, true)
			_poly(ci, [c + Vector2(-s * 0.7, -s * 0.65), c + Vector2(s * 0.6, -s * 0.45), c + Vector2(s * 0.6, -s * 0.15),
				c + Vector2(-s * 0.7, s * 0.05)], PAPER, w)
			for y in [0.35, 0.65]:
				ci.draw_line(c + Vector2(-s * 0.35, s * y), c + Vector2(s * 0.75, s * y), INK, w, true)
		"team_car":   # voiture d'équipe vue de côté, vélo sur le toit
			_rect(ci, c + Vector2(0, s * 0.15), Vector2(s * 0.85, s * 0.3), PAPER, w)
			_poly(ci, [c + Vector2(-s * 0.45, -s * 0.15), c + Vector2(-s * 0.25, -s * 0.45), c + Vector2(s * 0.3, -s * 0.45),
				c + Vector2(s * 0.5, -s * 0.15)], PAPER, w)
			for x in [-0.5, 0.5]:
				ci.draw_circle(c + Vector2(s * x, s * 0.5), s * 0.2, INK)
			ci.draw_arc(c + Vector2(-s * 0.2, -s * 0.72), s * 0.16, 0.0, TAU, 10, INK, w * 0.8, true)
			ci.draw_arc(c + Vector2(s * 0.25, -s * 0.72), s * 0.16, 0.0, TAU, 10, INK, w * 0.8, true)
		"stealth":   # silhouette en pointillés
			for i in range(8):
				var a0 := TAU * i / 8.0
				ci.draw_arc(c + Vector2(0, -s * 0.35), s * 0.3, a0, a0 + TAU / 16.0, 3, INK, w, true)
			for i in range(6):
				var b0 := PI + PI * i / 6.0
				ci.draw_arc(c + Vector2(0, s * 0.75), s * 0.65, b0, b0 + PI / 12.0, 3, INK, w, true)


static func _rect(ci: CanvasItem, c: Vector2, half: Vector2, fill: Color, w: float) -> void:
	var r := Rect2(c - half, half * 2.0)
	ci.draw_rect(r, fill, true)
	if w > 0.0:
		ci.draw_rect(r, INK, false, w)


static func _poly(ci: CanvasItem, pts: Array, fill: Color, w: float) -> void:
	var p := PackedVector2Array(pts)
	ci.draw_colored_polygon(p, fill)
	if w > 0.0:
		var closed := p.duplicate()
		closed.append(p[0])
		ci.draw_polyline(closed, INK, w, true)
