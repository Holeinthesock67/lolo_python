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
	"yes": "check", "difficulty": "slope", "ride_mode": "bars", "target_w": "bolt", "cadence_rpm": "bike", "bot1": "rider", "bot2": "rider", "bot3": "rider", "bot4": "rider", "ghost": "ghost", "peloton": "rider",
	"rogue": "rider", "rogue_change": "gear", "objective": "flag", "duration": "calendar", "wprime": "bolt",
	"chassis": "bike", "launch": "play", "history": "list",
	"garage": "bike", "bike": "bike", "outfit": "rider", "avatar": "rider", "save": "check", "cancel": "cross",
}
## Bonus du HUD (lot TT6, maquettes validées le 8 novembre) : forme de chaque valeur de `powerup.held` et
## `powerup.active` (contrat 1.13) ; la Puissance reprend l'éclair, une valeur inconnue l'icône neutre.
const POWERUP_SHAPES := {"feather": "pu_feather", "light": "pu_feather", "anvil": "pu_anvil",
	"draft_plus": "pu_draft_plus", "aero": "pu_aero", "power": "bolt", "breakaway": "pu_breakaway",
	"roller": "pu_roller"}
const POWERUP_UNKNOWN := "pu_unknown"
## Formes connues de draw() ; un nom inconnu ne dessine rien. `strike` : trait du refus, posé sur une icône.
const SHAPES := ["route", "bike", "bars", "globe", "calendar", "bolt", "chip", "gear", "list", "power",
	"play", "trophy", "flag", "cross", "check", "slope", "hold", "rider", "ghost", "pu_feather", "pu_anvil",
	"pu_draft_plus", "pu_aero", "pu_breakaway", "pu_roller", "pu_unknown", "strike"]


## Pictogramme de l'entrée `item_id`, "" sans pictogramme.
static func for_item(item_id: String) -> String:
	return str(ITEM_ICONS.get(item_id, ""))


## Pictogramme du bonus `kind` (valeur du contrat) ; l'icône neutre pour une valeur inconnue.
static func powerup_shape(kind: String) -> String:
	return str(POWERUP_SHAPES.get(kind, POWERUP_UNKNOWN))


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
	# Trait en tirets (Échappée, sol du Rouleau) : `on` tracé, `off` vide, en unités de la grille.
	var dashed := func(pts: Array, on: float, off: float) -> void:
		for i in range(pts.size() - 1):
			var a := Vector2(pts[i][0], pts[i][1])
			var b := Vector2(pts[i + 1][0], pts[i + 1][1])
			var d := a.distance_to(b)
			var t := 0.0
			while t < d:
				ci.draw_line(p.call(a.lerp(b, t / d).x, a.lerp(b, t / d).y),
					p.call(a.lerp(b, minf(t + on, d) / d).x, a.lerp(b, minf(t + on, d) / d).y), color, w, true)
				t += on + off
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
		"rider":
			# Bot (lot O7) : coureur, tête et buste penché sur le guidon.
			ring.call(21, 7, 3, 0.0, TAU)
			line.call([[19, 11], [10, 16], [12, 26]])
			line.call([[19, 11], [24, 18]])
			line.call([[10, 16], [18, 20], [20, 27]])
		"ghost":
			# Fantôme de la dernière séance (lot O7) : dôme et bas ondulé.
			line.call([[7, 27], [7, 14]])
			ring.call(16, 14, 9, PI, TAU)
			line.call([[25, 14], [25, 27], [22, 24], [19, 27], [16, 24], [13, 27], [10, 24], [7, 27]])
		"pu_feather":
			# Plume : tige courbe, contour de la barbe et deux barbules.
			line.call([[26, 5], [19, 7], [13, 12], [10, 19], [7, 27]])
			line.call([[26, 5], [25, 12], [20, 17], [11, 20]])
			line.call([[12, 16], [19, 14]])
			line.call([[15, 12], [21, 11]])
		"pu_anvil":
			line.call([[4, 11], [21, 11], [22, 14], [25, 15.5], [28, 16], [28, 17.5], [20, 17.5], [19, 21], [23, 21],
				[23, 25], [9, 25], [9, 21], [13, 21], [12, 17.5], [7, 16], [4.5, 13.5], [4, 11]])
		"pu_draft_plus":
			# Aspiration + : coureur, lignes d'air devant lui, signe plus.
			ring.call(22.5, 9.5, 2.7, 0.0, TAU)
			line.call([[20, 13], [17, 19], [22, 19], [23.5, 25]])
			for y in [12, 17, 22]:
				line.call([[3, y], [11, y]])
			line.call([[26, 1.5], [26, 6.5]])
			line.call([[23.5, 4], [28.5, 4]])
		"pu_aero":
			# Casque aéro : profil allongé et une fente.
			line.call([[4, 21.3], [4, 17], [6, 12.5], [10, 9.5], [17, 8], [23, 9], [27, 11.5], [29, 14.5], [21, 16],
				[19, 18.5], [17, 20.5], [13, 21.3], [4, 21.3]])
			line.call([[12, 14.7], [20, 14.7]])
		"pu_breakaway":
			# Échappée : coureur en tirets (on ne le voit plus), traits de vitesse derrière.
			for i in range(12):
				var a0 := TAU * i / 12.0
				if i % 2 == 0:
					ci.draw_arc(p.call(20, 6.7), 2.7 * k, a0, a0 + TAU / 12.0, 4, color, w, true)
			dashed.call([[17.3, 10.7], [13.3, 17.3], [20, 17.3], [21.3, 25.3]], 3.3, 2.7)
			line.call([[3, 16], [8, 16]])
			line.call([[4, 21.3], [8, 21.3]])
		"pu_roller":
			# Rouleau compresseur : cylindre, timon, sol en pointillés.
			ring.call(9.3, 17.3, 5.3, PI / 2, 3 * PI / 2)
			ring.call(14.7, 17.3, 5.3, -PI / 2, PI / 2)
			line.call([[9.3, 12], [14.7, 12]])
			line.call([[9.3, 22.6], [14.7, 22.6]])
			line.call([[20, 17.3], [24, 17.3], [28, 8]])
			dashed.call([[1.3, 26.7], [30.7, 26.7]], 2.0, 3.3)
		"pu_unknown":
			line.call([[9, 5.3], [23, 5.3], [26.7, 9], [26.7, 23], [23, 26.7], [9, 26.7], [5.3, 23], [5.3, 9], [9, 5.3]])
			ring.call(16, 13.3, 2.7, PI, TAU + PI / 2)
			line.call([[16, 16], [16, 18.7]])
			ci.draw_circle(p.call(16, 22.7), 1.3 * k, color)
		"strike":
			line.call([[4, 28], [28, 4]])
