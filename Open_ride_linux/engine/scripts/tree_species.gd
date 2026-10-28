extends RefCounted

## Espèces d'arbres et de plantes construites par code, sans fichier externe (lot U7, série U).
## Une fonction par espèce de `vegetation.species` (thème 2.0, Format .world v1 §9) ; chaque espèce a
## un modèle proche (LOD 0, moins de 300 triangles) et un modèle lointain en panneaux croisés (LOD 1,
## 4 triangles), aux dimensions réelles en mètres, le pied à y = 0. La teinte de chaque arbre
## (couleur d'instance) et sa taille (0,7 à 1,3) sont tirées par tree_renderer.gd.
## `GENERIC` (255) désigne l'arbre d'avant la série U (tree_renderer.build_lod0_mesh), gardé tel quel
## pour les parcours sans biome.
## Pas de class_name : charger par preload("res://scripts/tree_species.gd").

const BiomeIds := preload("res://scripts/biome_ids.gd")

const GENERIC := 255
const SIDES := 6

## Hauteur nominale (m) et feuillage caduc (saisons de P18 et U13) de chaque espèce.
const INFO := {
	"oak": {"height": 14.0, "deciduous": true},
	"beech": {"height": 17.0, "deciduous": true},
	"spruce": {"height": 20.0, "deciduous": false},
	"pine": {"height": 16.0, "deciduous": false},
	"birch": {"height": 12.0, "deciduous": true},
	"larch": {"height": 17.0, "deciduous": true},
	"olive": {"height": 6.0, "deciduous": false},
	"holm_oak": {"height": 9.0, "deciduous": false},
	"cypress": {"height": 14.0, "deciduous": false},
	"stone_pine": {"height": 13.0, "deciduous": false},
	"palm": {"height": 12.0, "deciduous": false},
	"acacia": {"height": 8.0, "deciduous": false},
	"baobab": {"height": 14.0, "deciduous": false},
	"cactus": {"height": 4.5, "deciduous": false},
	"tree_fern": {"height": 6.0, "deciduous": false},
	"reed": {"height": 2.2, "deciduous": false},
	"dwarf_shrub": {"height": 0.8, "deciduous": false},
	"vine_row": {"height": 1.6, "deciduous": true},
}

## Matière de chaque face, portée par l'alpha de la couleur du sommet (code / 16) et dessinée par
## tree_sway.gdshader (lot Y8 étape 2) ; alpha 1 : couleur unie.
const MAT_BARK := 1          # écorce crevassée
const MAT_BARK_SMOOTH := 2   # écorce lisse
const MAT_BARK_BIRCH := 3
const MAT_BARK_PLATES := 4   # écorce en plaques des pins
const MAT_PALM_TRUNK := 5
const MAT_CACTUS := 6
const MAT_STEM := 7          # ceps, tiges
const MAT_LEAVES := 8
const MAT_NEEDLES := 9
const MAT_FRONDS := 10

const BARK := Color(0.33, 0.24, 0.16, MAT_BARK / 16.0)
const BARK_GREY := Color(0.45, 0.43, 0.40, MAT_BARK / 16.0)
const BARK_SMOOTH := Color(0.47, 0.45, 0.42, MAT_BARK_SMOOTH / 16.0)
const BARK_WHITE := Color(0.86, 0.85, 0.80, MAT_BARK_BIRCH / 16.0)
const BARK_RED := Color(0.48, 0.30, 0.20, MAT_BARK_PLATES / 16.0)
const PALM_TRUNK := Color(0.45, 0.40, 0.33, MAT_PALM_TRUNK / 16.0)


## Couleur `rgb` avec la matière `code` dans l'alpha.
static func mat(rgb: Color, code: int) -> Color:
	return Color(rgb.r, rgb.g, rgb.b, code / 16.0)


## Couleur assombrie de `f`, matière gardée.
static func shade(col: Color, f: float) -> Color:
	return Color(col.r * f, col.g * f, col.b * f, col.a)


static func index_of(kind: String) -> int:
	var i := BiomeIds.SPECIES.find(kind)
	return i if i >= 0 else GENERIC


static func kind_of(index: int) -> String:
	return BiomeIds.SPECIES[index] if index >= 0 and index < BiomeIds.SPECIES.size() else "generic"


static func height_m(kind: String) -> float:
	return float(INFO.get(kind, {"height": 5.4})["height"])


static func is_deciduous(kind: String) -> bool:
	return bool(INFO.get(kind, {"deciduous": true})["deciduous"])


# --- Primitives -------------------------------------------------------------------------------

static func _tri(st: SurfaceTool, a: Vector3, b: Vector3, c: Vector3, col: Color, n: Vector3 = Vector3.ZERO) -> void:
	var nn := n if n != Vector3.ZERO else (b - a).cross(c - a).normalized()
	for p in [a, b, c]:
		st.set_color(col)
		st.set_normal(nn)
		st.add_vertex(p)


## Tronc ou branche : faces latérales d'un tronc de cône incliné de `base` à `top`.
static func _limb(st: SurfaceTool, base: Vector3, top: Vector3, r0: float, r1: float, col: Color, sides: int = SIDES) -> void:
	var axis := (top - base).normalized()
	var side := axis.cross(Vector3.FORWARD if absf(axis.z) < 0.9 else Vector3.RIGHT).normalized()
	var other := axis.cross(side).normalized()
	for i in range(sides):
		var a0 := TAU * i / sides
		var a1 := TAU * (i + 1) / sides
		var d0 := side * cos(a0) + other * sin(a0)
		var d1 := side * cos(a1) + other * sin(a1)
		var n := ((d0 + d1) * 0.5).normalized()
		_tri(st, base + d0 * r0, base + d1 * r0, top + d0 * r1, col, -n)
		_tri(st, base + d1 * r0, top + d1 * r1, top + d0 * r1, col, -n)


## Cône de feuillage (faces latérales et dessous).
static func _cone(st: SurfaceTool, y0: float, y1: float, r: float, col: Color, center: Vector3 = Vector3.ZERO) -> void:
	var tip := center + Vector3(0, y1, 0)
	for i in range(SIDES):
		var a0 := TAU * i / SIDES
		var a1 := TAU * (i + 1) / SIDES
		var p0 := center + Vector3(cos(a0) * r, y0, sin(a0) * r)
		var p1 := center + Vector3(cos(a1) * r, y0, sin(a1) * r)
		_tri(st, p1, p0, tip, col)
		_tri(st, center + Vector3(0, y0, 0), p0, p1, shade(col, 0.8), Vector3.DOWN)


## Houppier en ellipsoïde à facettes (6 méridiens, `rings` parallèles) : 12 × (rings − 1) triangles.
static func _blob(st: SurfaceTool, c: Vector3, radii: Vector3, col: Color, rings: int = 4) -> void:
	var pts := []
	for r in range(rings + 1):
		var phi := PI * r / rings
		var row := []
		for i in range(SIDES):
			var th := TAU * i / SIDES + (0.5 if r % 2 == 1 else 0.0)
			row.append(c + Vector3(sin(phi) * cos(th) * radii.x, cos(phi) * radii.y, sin(phi) * sin(th) * radii.z))
		pts.append(row)
	for r in range(rings):
		for i in range(SIDES):
			var a: Vector3 = pts[r][i]
			var b: Vector3 = pts[r][(i + 1) % SIDES]
			var d: Vector3 = pts[r + 1][i]
			var e: Vector3 = pts[r + 1][(i + 1) % SIDES]
			var tone := shade(col, 1.0 - 0.18 * float(r) / rings)
			if r > 0:
				_tri(st, a, d, b, tone, ((a + b + d) / 3.0 - c).normalized())
			if r < rings - 1:
				_tri(st, b, d, e, tone, ((b + d + e) / 3.0 - c).normalized())


## Palme ou fronde : bande en deux segments qui retombe, vue des deux côtés (8 triangles).
static func _frond(st: SurfaceTool, base: Vector3, angle: float, length: float, rise: float, droop: float,
		width: float, col: Color) -> void:
	var dir := Vector3(cos(angle), 0, sin(angle))
	var lat := Vector3(-dir.z, 0, dir.x) * width * 0.5
	var mid := base + dir * length * 0.5 + Vector3(0, rise, 0)
	var tip := base + dir * length + Vector3(0, rise - droop, 0)
	var quads := [[base, mid, lat], [mid, tip, lat * 0.35]]
	for q in quads:
		var p0: Vector3 = q[0]
		var p1: Vector3 = q[1]
		var w: Vector3 = q[2]
		_tri(st, p0 - w, p1 - w, p1 + w, col, Vector3.UP)
		_tri(st, p0 - w, p1 + w, p0 + w, col, Vector3.UP)
		# Dessous éclairé comme le dessus (normale vers le haut) : une palme vue d'en bas reste verte.
		_tri(st, p1 + w, p1 - w, p0 - w, shade(col, 0.85), Vector3.UP)
		_tri(st, p0 + w, p1 + w, p0 - w, shade(col, 0.85), Vector3.UP)


## Panneaux croisés du LOD 1 à la silhouette de l'espèce : houppier en cône (`cone`, du pied de la
## couronne `cy` à la cime) ou en octogone (`round`, centre `cy`, demi-hauteur `ry`) sur un tronc de largeur
## `trunk_w` ; `box` : rectangle plein (plantes basses, cactus). 4 à 28 triangles.
static func _profile(crown: Dictionary, height: float) -> ArrayMesh:
	var shape := str(crown.get("shape", "box"))
	if shape == "box":
		return _cross(float(crown["w"]), height, crown["col"])
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var w := float(crown["w"]) * 0.5
	var cy := float(crown["cy"])
	var ry := float(crown["ry"])
	var tw := float(crown["trunk_w"]) * 0.5
	var col: Color = crown["col"]
	for axis in [Vector3.RIGHT, Vector3.BACK]:
		var n: Vector3 = Vector3.UP.cross(axis)
		var top_trunk := cy if shape == "cone" else cy - ry * 0.6
		_tri(st, -axis * tw, axis * tw, axis * tw + Vector3(0, top_trunk, 0), BARK, n)
		_tri(st, -axis * tw, axis * tw + Vector3(0, top_trunk, 0), -axis * tw + Vector3(0, top_trunk, 0), BARK, n)
		if shape == "cone":
			_tri(st, -axis * w + Vector3(0, cy, 0), axis * w + Vector3(0, cy, 0), Vector3(0, height, 0), col, n)
		else:
			var c := Vector3(0, cy, 0)
			for i in range(8):
				var a0 := TAU * i / 8.0
				var a1 := TAU * (i + 1) / 8.0
				_tri(st, c, c + axis * cos(a0) * w + Vector3(0, sin(a0) * ry, 0), c + axis * cos(a1) * w + Vector3(0, sin(a1) * ry, 0), col, n)
	return st.commit()


## Panneaux croisés du LOD 1 : couronne colorée sur la hauteur du modèle.
static func _cross(width: float, height: float, col: Color) -> ArrayMesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var w := width * 0.5
	for axis in [Vector3.RIGHT, Vector3.BACK]:
		var n: Vector3 = Vector3.UP.cross(axis)
		var a: Vector3 = -axis * w
		var b: Vector3 = axis * w
		_tri(st, a, b, b + Vector3(0, height, 0), col, n)
		_tri(st, a, b + Vector3(0, height, 0), a + Vector3(0, height, 0), col, n)
	return st.commit()


# --- Espèces ----------------------------------------------------------------------------------

## Renvoie {"lod0": ArrayMesh, "lod1": ArrayMesh, "height": float, "deciduous": bool}.
static func build(kind: String) -> Dictionary:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var crown := {"w": 4.0, "col": Color(0.2, 0.4, 0.18)}
	match kind:
		"oak":
			_limb(st, Vector3.ZERO, Vector3(0, 5.5, 0), 0.45, 0.32, BARK)
			_limb(st, Vector3(0, 4.5, 0), Vector3(1.8, 7.5, 0.4), 0.22, 0.12, BARK, 4)
			_blob(st, Vector3(0, 9.0, 0), Vector3(4.8, 4.2, 4.6), mat(Color(0.22, 0.38, 0.14), MAT_LEAVES))
			_blob(st, Vector3(2.2, 8.0, 1.2), Vector3(2.8, 2.6, 2.6), mat(Color(0.25, 0.42, 0.16), MAT_LEAVES))
			crown = {"w": 9.0, "col": mat(Color(0.22, 0.38, 0.14), MAT_LEAVES), "shape": "round", "cy": 8.8, "ry": 4.4, "trunk_w": 0.6}
		"beech":
			_limb(st, Vector3.ZERO, Vector3(0, 8.0, 0), 0.35, 0.25, BARK_SMOOTH)
			_blob(st, Vector3(0, 11.5, 0), Vector3(3.8, 5.5, 3.8), mat(Color(0.26, 0.46, 0.18), MAT_LEAVES), 5)
			crown = {"w": 7.5, "col": mat(Color(0.26, 0.46, 0.18), MAT_LEAVES), "shape": "round", "cy": 11.5, "ry": 5.5, "trunk_w": 0.5}
		"spruce":
			_limb(st, Vector3.ZERO, Vector3(0, 3.0, 0), 0.35, 0.28, BARK)
			_cone(st, 2.0, 9.0, 3.4, mat(Color(0.10, 0.25, 0.13), MAT_NEEDLES))
			_cone(st, 6.5, 14.0, 2.6, mat(Color(0.11, 0.27, 0.14), MAT_NEEDLES))
			_cone(st, 11.0, 20.0, 1.7, mat(Color(0.12, 0.29, 0.15), MAT_NEEDLES))
			crown = {"w": 6.0, "col": mat(Color(0.11, 0.27, 0.14), MAT_NEEDLES), "shape": "cone", "cy": 2.0, "ry": 0.0, "trunk_w": 0.5}
		"pine":
			_limb(st, Vector3.ZERO, Vector3(0, 10.0, 0), 0.32, 0.22, BARK_RED)
			_cone(st, 8.0, 13.5, 3.0, mat(Color(0.16, 0.30, 0.14), MAT_NEEDLES))
			_cone(st, 11.5, 16.0, 2.0, mat(Color(0.17, 0.32, 0.15), MAT_NEEDLES))
			crown = {"w": 5.5, "col": mat(Color(0.16, 0.30, 0.14), MAT_NEEDLES), "shape": "cone", "cy": 8.0, "ry": 0.0, "trunk_w": 0.45}
		"birch":
			_limb(st, Vector3.ZERO, Vector3(0.2, 7.0, 0), 0.18, 0.12, BARK_WHITE)
			_blob(st, Vector3(0.2, 8.6, 0), Vector3(2.2, 3.8, 2.2), mat(Color(0.42, 0.58, 0.24), MAT_LEAVES))
			crown = {"w": 4.2, "col": mat(Color(0.42, 0.58, 0.24), MAT_LEAVES), "shape": "round", "cy": 8.6, "ry": 3.8, "trunk_w": 0.3}
		"larch":
			_limb(st, Vector3.ZERO, Vector3(0, 4.0, 0), 0.3, 0.24, BARK_RED)
			_cone(st, 3.0, 11.0, 3.0, mat(Color(0.36, 0.52, 0.22), MAT_NEEDLES))
			_cone(st, 8.0, 17.0, 2.0, mat(Color(0.38, 0.55, 0.24), MAT_NEEDLES))
			crown = {"w": 5.5, "col": mat(Color(0.37, 0.53, 0.23), MAT_NEEDLES), "shape": "cone", "cy": 3.0, "ry": 0.0, "trunk_w": 0.45}
		"olive":
			_limb(st, Vector3.ZERO, Vector3(0.4, 1.8, 0.2), 0.32, 0.26, BARK_GREY)
			_limb(st, Vector3(0.4, 1.6, 0.2), Vector3(-0.8, 3.0, 0.3), 0.18, 0.12, BARK_GREY, 4)
			_blob(st, Vector3(0.1, 3.9, 0.1), Vector3(2.8, 1.9, 2.6), mat(Color(0.45, 0.52, 0.36), MAT_LEAVES))
			crown = {"w": 5.2, "col": mat(Color(0.45, 0.52, 0.36), MAT_LEAVES), "shape": "round", "cy": 3.9, "ry": 1.9, "trunk_w": 0.5}
		"holm_oak":
			_limb(st, Vector3.ZERO, Vector3(0, 3.0, 0), 0.3, 0.22, BARK_GREY)
			_blob(st, Vector3(0, 5.6, 0), Vector3(3.4, 3.2, 3.3), mat(Color(0.17, 0.29, 0.14), MAT_LEAVES))
			crown = {"w": 6.4, "col": mat(Color(0.17, 0.29, 0.14), MAT_LEAVES), "shape": "round", "cy": 5.6, "ry": 3.2, "trunk_w": 0.45}
		"cypress":
			_limb(st, Vector3.ZERO, Vector3(0, 1.0, 0), 0.25, 0.22, BARK)
			_blob(st, Vector3(0, 7.2, 0), Vector3(1.2, 6.8, 1.2), mat(Color(0.12, 0.24, 0.12), MAT_NEEDLES), 6)
			crown = {"w": 2.4, "col": mat(Color(0.12, 0.24, 0.12), MAT_NEEDLES), "shape": "round", "cy": 7.2, "ry": 6.8, "trunk_w": 0.4}
		"stone_pine":
			_limb(st, Vector3.ZERO, Vector3(0.3, 9.5, 0), 0.32, 0.22, BARK_RED)
			_limb(st, Vector3(0.3, 8.5, 0), Vector3(2.5, 10.8, 0.6), 0.16, 0.1, BARK_RED, 4)
			_blob(st, Vector3(0.6, 11.4, 0.2), Vector3(5.2, 1.6, 5.0), mat(Color(0.18, 0.33, 0.15), MAT_NEEDLES))
			crown = {"w": 10.0, "col": mat(Color(0.18, 0.33, 0.15), MAT_NEEDLES), "shape": "round", "cy": 11.4, "ry": 1.6, "trunk_w": 0.45}
		"palm":
			_limb(st, Vector3.ZERO, Vector3(0.6, 6.0, 0), 0.26, 0.2, PALM_TRUNK)
			_limb(st, Vector3(0.6, 6.0, 0), Vector3(0.9, 11.0, 0), 0.2, 0.17, PALM_TRUNK)
			for i in range(8):
				_frond(st, Vector3(0.9, 11.0, 0), TAU * i / 8.0 + 0.3, 4.2, 0.6, 2.2, 1.5, mat(Color(0.22, 0.42, 0.16), MAT_FRONDS))
			crown = {"w": 7.0, "col": mat(Color(0.22, 0.42, 0.16), MAT_FRONDS), "shape": "round", "cy": 10.6, "ry": 1.8, "trunk_w": 0.4}
		"acacia":
			_limb(st, Vector3.ZERO, Vector3(0.3, 4.0, 0), 0.22, 0.16, BARK)
			_limb(st, Vector3(0.3, 3.6, 0), Vector3(2.4, 6.0, 0.5), 0.12, 0.08, BARK, 4)
			_limb(st, Vector3(0.3, 3.6, 0), Vector3(-1.8, 6.1, -0.8), 0.12, 0.08, BARK, 4)
			_blob(st, Vector3(0.3, 6.8, 0), Vector3(5.0, 1.0, 4.6), mat(Color(0.33, 0.42, 0.18), MAT_LEAVES))
			crown = {"w": 10.0, "col": mat(Color(0.33, 0.42, 0.18), MAT_LEAVES), "shape": "round", "cy": 6.8, "ry": 1.0, "trunk_w": 0.35}
		"baobab":
			_limb(st, Vector3.ZERO, Vector3(0, 9.0, 0), 2.2, 1.4, mat(Color(0.55, 0.45, 0.38), MAT_BARK_SMOOTH), 8)
			for i in range(5):
				var a := TAU * i / 5.0
				_limb(st, Vector3(0, 8.6, 0), Vector3(cos(a) * 3.2, 12.0, sin(a) * 3.2), 0.4, 0.15, mat(Color(0.55, 0.45, 0.38), MAT_BARK_SMOOTH), 4)
			_blob(st, Vector3(0, 12.6, 0), Vector3(4.0, 1.2, 4.0), mat(Color(0.30, 0.42, 0.18), MAT_LEAVES))
			crown = {"w": 8.0, "col": mat(Color(0.42, 0.40, 0.30), MAT_LEAVES), "shape": "round", "cy": 12.4, "ry": 1.6, "trunk_w": 3.6}
		"cactus":
			var green := mat(Color(0.28, 0.42, 0.22), MAT_CACTUS)
			_limb(st, Vector3.ZERO, Vector3(0, 4.5, 0), 0.32, 0.28, green, 8)
			_limb(st, Vector3(0, 1.6, 0), Vector3(0.9, 1.9, 0), 0.2, 0.2, green, 6)
			_limb(st, Vector3(0.9, 1.9, 0), Vector3(0.9, 3.4, 0), 0.2, 0.18, green, 6)
			_limb(st, Vector3(0, 2.2, 0), Vector3(-0.8, 2.4, 0.2), 0.18, 0.18, green, 6)
			_limb(st, Vector3(-0.8, 2.4, 0.2), Vector3(-0.8, 3.6, 0.2), 0.18, 0.16, green, 6)
			crown = {"w": 2.2, "col": green, "shape": "box", "cy": 0.0, "ry": 0.0, "trunk_w": 0.0}
		"tree_fern":
			_limb(st, Vector3.ZERO, Vector3(0.2, 4.6, 0), 0.22, 0.18, mat(Color(0.25, 0.18, 0.12), MAT_BARK))
			for i in range(9):
				_frond(st, Vector3(0.2, 4.6, 0), TAU * i / 9.0, 2.8, 0.7, 1.2, 1.3, mat(Color(0.20, 0.45, 0.16), MAT_FRONDS))
			crown = {"w": 5.0, "col": mat(Color(0.20, 0.45, 0.16), MAT_FRONDS), "shape": "round", "cy": 4.8, "ry": 1.2, "trunk_w": 0.35}
		"reed":
			for i in range(7):
				var a := TAU * i / 7.0
				var r := 0.25 + 0.15 * (i % 3)
				var base := Vector3(cos(a) * r, 0, sin(a) * r)
				var top := base * 1.6 + Vector3(0, 1.8 + 0.2 * (i % 2), 0)
				_limb(st, base, top, 0.03, 0.02, mat(Color(0.52, 0.56, 0.30), MAT_STEM), 3)
				_limb(st, top, top + Vector3(0, 0.35, 0), 0.06, 0.02, mat(Color(0.40, 0.30, 0.20), MAT_STEM), 3)
			crown = {"w": 1.4, "col": mat(Color(0.52, 0.56, 0.30), MAT_LEAVES), "shape": "box", "cy": 0.0, "ry": 0.0, "trunk_w": 0.0}
		"dwarf_shrub":
			_blob(st, Vector3(0, 0.4, 0), Vector3(0.8, 0.45, 0.7), mat(Color(0.35, 0.36, 0.20), MAT_LEAVES), 3)
			_blob(st, Vector3(0.6, 0.3, 0.4), Vector3(0.5, 0.32, 0.5), mat(Color(0.40, 0.34, 0.22), MAT_LEAVES), 3)
			crown = {"w": 1.8, "col": mat(Color(0.37, 0.35, 0.21), MAT_LEAVES), "shape": "box", "cy": 0.0, "ry": 0.0, "trunk_w": 0.0}
		"vine_row":
			# Rang de 6 m : piquets et ceps sous une haie de feuillage basse, orienté selon x.
			for i in range(4):
				var x := -3.0 + 2.0 * i
				_limb(st, Vector3(x, 0, 0), Vector3(x, 1.4, 0), 0.04, 0.04, mat(Color(0.40, 0.33, 0.24), MAT_STEM), 4)
			for i in range(3):
				_blob(st, Vector3(-2.0 + 2.0 * i, 1.05, 0), Vector3(1.15, 0.45, 0.4), mat(Color(0.28, 0.44, 0.16), MAT_LEAVES), 3)
			crown = {"w": 6.0, "col": mat(Color(0.28, 0.44, 0.16), MAT_LEAVES), "shape": "box", "cy": 0.0, "ry": 0.0, "trunk_w": 0.0}
		_:
			return {}
	var mesh := st.commit()
	var h := height_m(kind)
	return {"lod0": mesh, "lod1": _profile(crown, h), "height": h,
		"deciduous": is_deciduous(kind)}


## Triangles d'un maillage (contrôle du budget de 300 triangles en LOD 0).
static func triangle_count(mesh: ArrayMesh) -> int:
	var n := 0
	for s in range(mesh.get_surface_count()):
		n += (mesh.surface_get_arrays(s)[Mesh.ARRAY_VERTEX] as PackedVector3Array).size() / 3
	return n
