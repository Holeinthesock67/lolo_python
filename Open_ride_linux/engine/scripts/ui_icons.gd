extends RefCounted

## Pictogrammes des menus tracés par le code (lot « présentation des menus », étape 1) : traits sur une
## grille de 32 × 32 mise à l'échelle du rectangle demandé, aucune image. `ITEM_ICONS` donne le
## pictogramme d'une entrée par son identifiant (mêmes identifiants que menu_model.gd et menu_flow.gd) ;
## une entrée absente de la table n'a pas de pictogramme, sa place reste vide pour l'alignement.
## Pas de class_name : charger par preload("res://scripts/ui_icons.gd").

const ITEM_ICONS := {
	"world": "route", "change_route": "route", "ride": "bike", "erg": "bars", "workout": "bars",
	"open_world": "globe", "plan": "calendar", "ftp": "bolt", "sim": "chip", "settings": "gear",
	"devices": "list", "pairing": "list", "quit": "power", "start": "play", "resume": "play",
	"continue": "play", "records": "trophy", "end_save": "flag", "abandon": "cross", "no": "cross",
	"yes": "check", "difficulty": "slope",
}
## Formes connues de draw() ; un nom inconnu ne dessine rien.
const SHAPES := ["route", "bike", "bars", "globe", "calendar", "bolt", "chip", "gear", "list", "power",
	"play", "trophy", "flag", "cross", "check", "slope", "hold"]


## Pictogramme de l'entrée `item_id`, "" sans pictogramme.
static func for_item(item_id: String) -> String:
	return str(ITEM_ICONS.get(item_id, ""))


## Dessine `shape` dans `rect` sur `ci` (appelé depuis un _draw()), trait de `width` en unités de la grille.
static func draw(ci: CanvasItem, shape: String, rect: Rect2, color: Color, width := 2.2) -> void:
	var k := minf(rect.size.x, rect.size.y) / 32.0
	var o := rect.position + (rect.size - Vector2(32, 32) * k) / 2.0
	var w := width * k
	var p := func(x, y) -> Vector2: return o + Vector2(x, y) * k
	var line := func(pts: Array) -> void:
		var arr := PackedVector2Array()
		for q in pts:
			arr.append(p.call(q[0], q[1]))
		ci.draw_polyline(arr, color, w, true)
	var ring := func(x, y, r, from, to) -> void:
		ci.draw_arc(p.call(x, y), r * k, from, to, 32, color, w, true)
	match shape:
		"route":
			line.call([[6, 26], [10, 25], [12, 21], [16, 18], [20, 15], [21, 10], [26, 8]])
			ring.call(6, 26, 2.5, 0.0, TAU)
			ring.call(26, 8, 2.5, 0.0, TAU)
		"bike":
			ring.call(8, 21, 5.5, 0.0, TAU)
			ring.call(24, 21, 5.5, 0.0, TAU)
			line.call([[8, 21], [14, 11], [21, 11], [24, 21]])
			line.call([[14, 11], [18, 21]])
			line.call([[12, 8], [17, 8]])
		"bars":
			line.call([[5, 26], [5, 18], [10, 18], [10, 26]])
			line.call([[13, 26], [13, 10], [18, 10], [18, 26]])
			line.call([[21, 26], [21, 14], [26, 14], [26, 26]])
		"globe":
			ring.call(16, 16, 11, 0.0, TAU)
			line.call([[5, 16], [27, 16]])
			var meridian: Array = []
			for i in range(17):
				var a := PI * i / 16.0 - PI / 2
				meridian.append([16 + 5.0 * cos(a), 16 + 11.0 * sin(a)])
			line.call(meridian)
			line.call([[16, 5], [16, 27]])
		"calendar":
			line.call([[5, 10], [5, 27], [27, 27], [27, 10], [5, 10]])
			line.call([[5, 14], [27, 14]])
			line.call([[11, 5], [11, 10]])
			line.call([[21, 5], [21, 10]])
			line.call([[10, 20], [14, 20]])
		"bolt":
			line.call([[18, 4], [8, 18], [16, 18], [14, 28], [24, 14], [16, 14], [18, 4]])
		"chip":
			line.call([[8, 8], [24, 8], [24, 24], [8, 24], [8, 8]])
			for c in [12, 20]:
				line.call([[c, 4], [c, 8]])
				line.call([[c, 24], [c, 28]])
				line.call([[4, c], [8, c]])
				line.call([[24, c], [28, c]])
		"gear":
			ring.call(16, 16, 4.5, 0.0, TAU)
			for i in range(8):
				var a := TAU * i / 8.0
				var d := Vector2(cos(a), sin(a))
				ci.draw_line(p.call(16 + d.x * 8, 16 + d.y * 8), p.call(16 + d.x * 12, 16 + d.y * 12), color, w, true)
		"list":
			for y in [9, 16, 23]:
				line.call([[11, y], [26, y]])
				ci.draw_circle(p.call(6, y), 1.6 * k, color)
		"power":
			line.call([[16, 5], [16, 15]])
			ring.call(16, 17, 9, -PI / 2 + 0.75, 3 * PI / 2 - 0.75)
		"play":
			line.call([[10, 6], [26, 16], [10, 26], [10, 6]])
		"trophy":
			line.call([[10, 5], [22, 5], [22, 11], [20, 15], [16, 17], [12, 15], [10, 11], [10, 5]])
			line.call([[10, 8], [5, 8], [6, 12], [10, 14]])
			line.call([[22, 8], [27, 8], [26, 12], [22, 14]])
			line.call([[16, 17], [16, 22]])
			line.call([[11, 27], [21, 27]])
			line.call([[13, 22], [19, 22], [19, 27]])
		"flag":
			line.call([[8, 28], [8, 5]])
			line.call([[8, 6], [24, 6], [20, 11], [24, 16], [8, 16]])
		"cross":
			line.call([[8, 8], [24, 24]])
			line.call([[24, 8], [8, 24]])
		"check":
			line.call([[6, 17], [13, 24], [26, 9]])
		"slope":
			line.call([[4, 24], [13, 10], [18, 18], [21, 14], [28, 24], [4, 24]])
		"hold":
			# Appui long : anneau aux trois quarts rempli.
			ci.draw_arc(p.call(16, 16), 11 * k, 0.0, TAU, 32, Color(color, 0.25), w, true)
			ci.draw_arc(p.call(16, 16), 11 * k, -PI / 2, PI, 32, color, w, true)
