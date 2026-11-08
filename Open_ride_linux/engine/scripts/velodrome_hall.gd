extends Node3D

## Salle couverte du vélodrome (série VD, lot VD5, plan §7.2) : décor unique, intérieur, construit à partir de la
## piste (route + couche venue) au chargement, sans terrain, végétation, biome, ciel ni météo.
## - Pelouse centrale (sol de l'intérieur de l'anneau), bancs et home trainers d'échauffement le long de la droite
##   d'arrivée.
## - Tribunes en gradins derrière la balustrade, sur tout le tour ; promenoir ; mur de la salle avec un bandeau
##   sombre ; toit à arcs (coupole sur l'ovale du mur, arcs plus sombres) ; rampes d'éclairage émissives
##   (pas une lumière par projecteur) ; tableau d'affichage suspendu au centre.
## - Public : un MultiMesh (1 000, 3 000 ou 6 000 personnes selon le préréglage, QualityPresets.velodrome_crowd),
##   posé une fois, aucune création pendant l'épreuve.
## - Ambiance : fond uni, lumière ambiante de la salle, « soleil » devenu lumière zénithale, sans brouillard ;
##   état d'avant gardé et rendu en quittant la piste (apply_indoor / restore).
## Ombres : seuls les coureurs en portent (salle, public et toit sans ombre, plan §7.2).
## Constructeurs statiques sans nœud (build_arrays, seats, occupied) : testés sans écran
## (tests/unit/test_velodrome_hall.gd).

const RoadBuilder := preload("res://scripts/road_builder.gd")
const QualityPresets := preload("res://scripts/quality_presets.gd")
const CrowdShader := preload("res://shaders/velodrome_crowd.gdshader")

const OUTLINE_STEP_M := 2.0       # pas du contour de la salle le long de la piste
const WALKWAY_M := 2.5            # passage entre la balustrade et le premier gradin (vue de côté dégagée)
const ROWS := 14                  # gradins
const TREAD_M := 0.85             # profondeur d'un gradin
const RISER_M := 0.42             # hauteur d'un gradin
const CONCOURSE_M := 3.0          # promenoir derrière le dernier gradin
const FLOOR_BELOW_M := 2.0        # pied du mur sous la piste
const WALL_ABOVE_M := 5.0         # mur au-dessus du dernier gradin le plus haut
const SCOREBOARD_IDLE := "VÉLODROME\n250 m"   # texte hors épreuve (track_hud_model.gd board_text)
const SCOREBOARD_FONT_MAX := 96
const SCOREBOARD_PIXEL_M := 0.012
const SCOREBOARD_FACE_W_M := 5.6   # face de 6 m, marge comprise
const SCOREBOARD_FACE_H_M := 3.0   # face de 3,2 m
const SCOREBOARD_LINE_FACTOR := 1.2   # hauteur d'une ligne / taille de police
const SCOREBOARD_CHAR_FACTOR := 0.6   # largeur moyenne d'une capitale / taille de police
const BAND_H_M := 1.6             # bandeau sombre du bas du mur, au-dessus du promenoir
const ROOF_RISE_M := 13.0         # flèche de la coupole
const ROOF_RINGS := 12
const RIB_EVERY := 8              # un arc sombre tous les 8 pas du contour (16 m)
const RAMPS := [0.28, 0.52, 0.74] # rampes d'éclairage, en fraction du rayon du toit depuis le mur
const RAMP_HALF := 0.012
const RAMP_DROP_M := 0.6
const SEAT_PITCH_M := 0.55        # écart entre deux places d'un gradin
const SCOREBOARD_DROP_M := 5.0
const STANDING_SHARE := 0.08     # spectateurs debout

const FLOOR_COLOR := Color(0.30, 0.52, 0.38)       # pelouse centrale (sol sportif vert)
const TREAD_COLOR := Color(0.58, 0.58, 0.60)       # béton des gradins
const RISER_COLOR := Color(0.48, 0.48, 0.50)       # contremarche en béton
const SEAT_COLOR := Color(0.16, 0.30, 0.62)        # banquettes bleues
const SEAT_H_M := 0.42                             # hauteur de l'assise sur le gradin
const SEAT_FRONT_M := 0.10                         # assise de 0,1 m devant à 0,3 m derrière la place
const SEAT_BACK_M := 0.30
const CONCOURSE_COLOR := Color(0.42, 0.42, 0.45)
const WALL_COLOR := Color(0.80, 0.81, 0.84)
const BAND_COLOR := Color(0.10, 0.16, 0.32)
const ROOF_COLOR := Color(0.86, 0.83, 0.76)        # sous-face en bois clair
const RIB_COLOR := Color(0.45, 0.40, 0.34)
const LIGHT_COLOR := Color(1.0, 0.97, 0.90)
const LIGHT_ENERGY := 6.0
const BACKGROUND := Color(0.05, 0.05, 0.06)
const AMBIENT := Color(0.72, 0.73, 0.76)
const AMBIENT_ENERGY := 0.38
const TOP_LIGHT_DIR := Vector3(0.25, -1.0, 0.35)   # lumière zénithale des rampes
const TOP_LIGHT_COLOR := Color(1.0, 0.97, 0.92)
const TOP_LIGHT_ENERGY := 0.7

var quality := "low"
var crowd_count := 0          # personnes posées (tests et journal)
var built := false
var _crowd: MultiMeshInstance3D = null            # assis
var _crowd_standing: MultiMeshInstance3D = null   # debout
var _seats_cache: Array = []
var _saved := {}              # ambiance d'avant la salle (restore)
var _scoreboard_text := ""     # dernier texte posé (set_scoreboard)


# --- construction -----------------------------------------------------------------------------------------

## Pose la salle de la piste `route` (vide la précédente). Rien sur une route.
func build(route, preset_name: String) -> void:
	clear()
	if not RoadBuilder.is_track(route):
		return
	quality = preset_name
	var arrays := build_arrays(route)
	_add_mesh("Floor", arrays["floor"], _material(false))
	_add_mesh("Stands", arrays["stands"], _material(false))
	_add_mesh("Walls", arrays["walls"], _material(false))
	_add_mesh("Roof", arrays["roof"], _material(false))
	_add_mesh("Lights", arrays["lights"], _material(true))
	_add_infield(route, arrays["info"])
	_add_scoreboard(arrays["info"])
	_seats_cache = seats(route)
	_place_crowd()
	built = true


## Préréglage changé : nombre de spectateurs du nouveau préréglage (mêmes places, sous-ensemble stable).
func set_quality(preset_name: String) -> void:
	quality = preset_name
	if built:
		_place_crowd()


func clear() -> void:
	_scoreboard_text = ""
	for c in get_children():
		remove_child(c)
		c.queue_free()
	_crowd = null
	_crowd_standing = null
	crowd_count = 0
	built = false
	_seats_cache = []


## Texte du tableau d'affichage (lot VD9, track_hud_model.gd board_text) sur ses quatre faces ; la taille des
## lettres suit le nombre de lignes et la plus longue, pour tenir sur la face (6 m × 3,2 m).
func set_scoreboard(text: String) -> void:
	if text == _scoreboard_text:
		return
	_scoreboard_text = text
	var size := scoreboard_font_size(text)
	for k in range(4):
		var lbl := get_node_or_null("ScoreboardText%d" % k) as Label3D
		if lbl != null:
			lbl.text = text
			lbl.font_size = size


func scoreboard_text() -> String:
	var lbl := get_node_or_null("ScoreboardText0") as Label3D
	return lbl.text if lbl != null else ""


static func scoreboard_font_size(text: String) -> int:
	var lines := text.split("\n")
	var longest := 1
	for l in lines:
		longest = maxi(longest, l.length())
	var by_h := SCOREBOARD_FACE_H_M / (lines.size() * SCOREBOARD_LINE_FACTOR * SCOREBOARD_PIXEL_M)
	var by_w := SCOREBOARD_FACE_W_M / (longest * SCOREBOARD_CHAR_FACTOR * SCOREBOARD_PIXEL_M)
	return clampi(int(minf(by_h, by_w)), 16, SCOREBOARD_FONT_MAX)


## Contour de la salle : un point tous les OUTLINE_STEP_M le long de la piste, avec la direction vers
## l'extérieur (horizontale), la distance horizontale et la hauteur du haut de la balustrade et du bord de
## la zone de sécurité, comme road_builder.gd les dessine.
static func outline(route) -> Array:
	var prof := RoadBuilder.track_profile(route)
	var n := maxi(8, int(round(route.length_m / OUTLINE_STEP_M)))
	var out: Array = []
	for i in range(n):
		var s: float = route.length_m * i / n
		var p: Vector3 = route.sample_point(s)
		var h := deg_to_rad(route.sample_heading_deg(s))
		var r := Vector3(cos(h), 0.0, sin(h))
		var b := deg_to_rad(route.bank_at(s))
		out.append({"s": s, "p": p, "out": r,
			"barrier_d": float(prof["outer"]) * cos(b),
			"barrier_y": p.y + float(prof["outer"]) * sin(b) + RoadBuilder.TRACK_BARRIER_H,
			"inner_d": -float(prof["inner"]) * cos(b) - float(prof["flat"]),
			"inner_y": p.y - float(prof["inner"]) * sin(b)})
	return out


## Profil en travers des tribunes au point `o` du contour : [distance horizontale, hauteur, couleur] du
## haut de la balustrade au pied du mur.
static func stand_profile(o: Dictionary) -> Array:
	var d: float = o["barrier_d"]
	var y: float = o["barrier_y"]
	var prof: Array = [[d, y, TREAD_COLOR], [d + WALKWAY_M, y, TREAD_COLOR]]
	d += WALKWAY_M
	for i in range(ROWS):
		y += RISER_M
		prof.append([d, y, RISER_COLOR])
		d += TREAD_M
		prof.append([d, y, TREAD_COLOR])
	d += CONCOURSE_M
	prof.append([d, y, CONCOURSE_COLOR])
	return prof


## Tableaux de maillage (Mesh.ARRAY_MAX, triangles sans index) de la salle, et repères `info`
## {center, floor_y, wall_top, roof_top, wall_ring, outline}.
static func build_arrays(route) -> Dictionary:
	var ol := outline(route)
	var n := ol.size()
	var center := Vector3.ZERO
	var floor_y := INF
	var top := -INF
	var profiles: Array = []
	for o in ol:
		center += o["p"]
		floor_y = minf(floor_y, float(o["inner_y"]))
		var pr := stand_profile(o)
		profiles.append(pr)
		top = maxf(top, float(pr[pr.size() - 1][1]) + SEAT_H_M)   # dessus de la dernière banquette
	center /= float(n)
	var wall_top := top + WALL_ABOVE_M
	var wall_bottom := floor_y - FLOOR_BELOW_M
	var floor_tris := Tris.new()
	var stands := Tris.new()
	var walls := Tris.new()
	var roof := Tris.new()
	var lights := Tris.new()
	var wall_ring: Array = []
	for i in range(n):
		var pr: Array = profiles[i]
		wall_ring.append(_at(ol[i], float(pr[pr.size() - 1][0]), wall_top))
	var c_floor := Vector3(center.x, floor_y - 0.02, center.z)
	var c_roof := Vector3(center.x, wall_top + ROOF_RISE_M, center.z)
	for i in range(n):
		var j := (i + 1) % n
		var a: Dictionary = ol[i]
		var b: Dictionary = ol[j]
		# Pelouse centrale : éventail du centre au bord de la zone de sécurité (prolongé de 0,3 m dessous).
		floor_tris.tri(c_floor, _at(a, float(a["inner_d"]) + 0.3, float(a["inner_y"]) - 0.02),
			_at(b, float(b["inner_d"]) + 0.3, float(b["inner_y"]) - 0.02), FLOOR_COLOR, Vector3.UP)
		# Tribunes : bandes entre deux points du contour, une par segment du profil.
		var pa: Array = profiles[i]
		var pb: Array = profiles[j]
		for k in range(pa.size() - 1):
			stands.quad(_at(a, pa[k][0], pa[k][1]), _at(b, pb[k][0], pb[k][1]), _at(b, pb[k + 1][0], pb[k + 1][1]),
				_at(a, pa[k + 1][0], pa[k + 1][1]), pa[k + 1][2], Vector3.UP - (a["out"] as Vector3))
		# Banquettes : une par gradin, sous les places (seats), dessus et face avant.
		for row in range(ROWS):
			var k := 3 + 2 * row
			var ya_s: float = float(pa[k][1])
			var yb_s: float = float(pb[k][1])
			var fa: float = float(pa[k][0]) - 0.5 * TREAD_M - SEAT_FRONT_M
			var fb: float = float(pb[k][0]) - 0.5 * TREAD_M - SEAT_FRONT_M
			var w := SEAT_FRONT_M + SEAT_BACK_M
			var up_in := Vector3.UP - (a["out"] as Vector3)
			stands.quad(_at(a, fa, ya_s), _at(b, fb, yb_s), _at(b, fb, yb_s + SEAT_H_M), _at(a, fa, ya_s + SEAT_H_M),
				SEAT_COLOR, -(a["out"] as Vector3))
			stands.quad(_at(a, fa, ya_s + SEAT_H_M), _at(b, fb, yb_s + SEAT_H_M), _at(b, fb + w, yb_s + SEAT_H_M),
				_at(a, fa + w, ya_s + SEAT_H_M), SEAT_COLOR, up_in)
		# Mur : pied sous la piste et bandeau sombre au-dessus du promenoir, panneaux clairs au-dessus.
		var da: float = pa[pa.size() - 1][0]
		var db: float = pb[pb.size() - 1][0]
		var ya: float = pa[pa.size() - 1][1]
		var yb: float = pb[pb.size() - 1][1]
		var inward := -(a["out"] as Vector3)
		walls.quad(_at(a, da, wall_bottom), _at(b, db, wall_bottom), _at(b, db, yb + BAND_H_M), _at(a, da, ya + BAND_H_M),
			BAND_COLOR, inward)
		walls.quad(_at(a, da, ya + BAND_H_M), _at(b, db, yb + BAND_H_M), _at(b, db, wall_top), _at(a, da, wall_top),
			WALL_COLOR, inward)
		# Toit : coupole du mur au centre ; arcs sombres réguliers.
		var col := RIB_COLOR if i % RIB_EVERY == 0 else ROOF_COLOR
		for k in range(ROOF_RINGS):
			var t0 := float(k) / ROOF_RINGS
			var t1 := float(k + 1) / ROOF_RINGS
			roof.quad(_roof_pt(wall_ring[i], c_roof, t0), _roof_pt(wall_ring[j], c_roof, t0),
				_roof_pt(wall_ring[j], c_roof, t1), _roof_pt(wall_ring[i], c_roof, t1), col, Vector3.DOWN)
		# Rampes d'éclairage : anneaux émissifs sous le toit.
		var down := Vector3.DOWN * RAMP_DROP_M
		for t in RAMPS:
			lights.quad(_roof_pt(wall_ring[i], c_roof, t - RAMP_HALF) + down, _roof_pt(wall_ring[j], c_roof, t - RAMP_HALF) + down,
				_roof_pt(wall_ring[j], c_roof, t + RAMP_HALF) + down, _roof_pt(wall_ring[i], c_roof, t + RAMP_HALF) + down,
				LIGHT_COLOR, Vector3.DOWN)
	return {"floor": floor_tris.arrays(), "stands": stands.arrays(), "walls": walls.arrays(), "roof": roof.arrays(),
		"lights": lights.arrays(),
		"info": {"center": center, "floor_y": floor_y, "wall_top": wall_top, "roof_top": c_roof.y, "wall_ring": wall_ring,
			"outline": ol}}


## Places des tribunes : Transform3D d'une personne assise (regard −Z vers la piste), sur chaque gradin.
static func seats(route) -> Array:
	var ol := outline(route)
	var n := ol.size()
	var profiles: Array = []
	for o in ol:
		profiles.append(stand_profile(o))
	var out: Array = []
	for row in range(ROWS):
		var k := 3 + 2 * row   # point du profil au fond du gradin `row` (marche d'avant + giron)
		for i in range(n):
			var a: Dictionary = ol[i]
			var b: Dictionary = ol[(i + 1) % n]
			var pa: Array = profiles[i][k]
			var pb: Array = profiles[(i + 1) % n][k]
			var qa := _at(a, float(pa[0]) - 0.5 * TREAD_M, float(pa[1]))
			var qb := _at(b, float(pb[0]) - 0.5 * TREAD_M, float(pb[1]))
			var count := maxi(1, int(qa.distance_to(qb) / SEAT_PITCH_M))
			for m in range(count):
				var u := (m + 0.5) / count
				var facing: Vector3 = -((a["out"] as Vector3).lerp(b["out"], u)).normalized()
				out.append(Transform3D(Basis.looking_at(facing, Vector3.UP), qa.lerp(qb, u)))
	return out


## Places occupées pour `count` spectateurs parmi `total` : sous-ensemble stable (une place prise en `low`
## l'est aussi en `medium` et `high`), réparti sur tout le tour.
static func occupied(total: int, count: int) -> PackedInt32Array:
	var keep := PackedInt32Array()
	if total <= 0 or count <= 0:
		return keep
	var ratio := minf(1.0, float(count) / total)
	for i in range(total):
		if hash01(i) < ratio:
			keep.append(i)
	return keep


static func hash01(i: int) -> float:
	var h := (i * 2654435761) & 0xffffffff
	h = ((h ^ (h >> 15)) * 2246822519) & 0xffffffff
	h = h ^ (h >> 13)
	return float(h & 0xffffff) / float(0x1000000)


static func _at(o: Dictionary, d: float, y: float) -> Vector3:
	var p: Vector3 = o["p"] + (o["out"] as Vector3) * d
	return Vector3(p.x, y, p.z)


static func _roof_pt(w: Vector3, c: Vector3, t: float) -> Vector3:
	var hp := Vector3(w.x, 0.0, w.z).lerp(Vector3(c.x, 0.0, c.z), t)
	return Vector3(hp.x, w.y + (c.y - w.y) * sin(t * PI * 0.5), hp.z)


## Triangles sans index, normale de face orientée vers `hint`.
class Tris:
	var v := PackedVector3Array()
	var nrm := PackedVector3Array()
	var col := PackedColorArray()

	func tri(a: Vector3, b: Vector3, c: Vector3, color: Color, hint: Vector3) -> void:
		var nn := (b - a).cross(c - a)
		if nn.length_squared() < 1e-12:
			return
		nn = nn.normalized()
		if nn.dot(hint) < 0.0:
			nn = -nn
			var t := b
			b = c
			c = t
		v.append_array([a, b, c])
		nrm.append_array([nn, nn, nn])
		col.append_array([color, color, color])

	func quad(a: Vector3, b: Vector3, c: Vector3, d: Vector3, color: Color, hint: Vector3) -> void:
		tri(a, b, c, color, hint)
		tri(a, c, d, color, hint)

	func arrays() -> Array:
		var arr := []
		arr.resize(Mesh.ARRAY_MAX)
		arr[Mesh.ARRAY_VERTEX] = v
		arr[Mesh.ARRAY_NORMAL] = nrm
		arr[Mesh.ARRAY_COLOR] = col
		return arr


# --- nœuds -------------------------------------------------------------------------------------------------

func _material(emissive: bool) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.vertex_color_use_as_albedo = true
	m.vertex_color_is_srgb = true
	m.cull_mode = BaseMaterial3D.CULL_DISABLED
	m.roughness = 0.85
	if emissive:
		m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		m.emission_enabled = true
		m.emission = LIGHT_COLOR
		m.emission_energy_multiplier = LIGHT_ENERGY
	return m


func _add_mesh(node_name: String, arrays: Array, mat: Material) -> MeshInstance3D:
	var mesh := ArrayMesh.new()
	if (arrays[Mesh.ARRAY_VERTEX] as PackedVector3Array).size() > 0:
		mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
		mesh.surface_set_material(0, mat)
	var mi := MeshInstance3D.new()
	mi.name = node_name
	mi.mesh = mesh
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(mi)
	return mi


## Bancs et home trainers d'échauffement sur la pelouse, le long de la droite d'arrivée (côté intérieur).
func _add_infield(route, info: Dictionary) -> void:
	var prof := RoadBuilder.track_profile(route)
	var inner := -float(prof["inner"]) - float(prof["flat"])
	var floor_y: float = info["floor_y"]
	var t_list: Array = []
	var b_list: Array = []
	var s := -15.0
	while s <= 15.0:
		var ss: float = route.wrap_s(s)
		var p: Vector3 = route.sample_point(ss)
		var h := deg_to_rad(route.sample_heading_deg(ss))
		var r := Vector3(cos(h), 0.0, sin(h))
		var basis := Basis(r, Vector3.UP, r.cross(Vector3.UP))
		t_list.append(Transform3D(basis, Vector3(p.x, floor_y + 0.5, p.z) + r * (inner - 3.0)))
		if int(round(s / 2.5)) % 2 == 0:
			b_list.append(Transform3D(basis, Vector3(p.x, floor_y + 0.22, p.z) + r * (inner - 6.0)))
		s += 2.5
	_add_boxes("Trainers", Vector3(0.5, 1.0, 1.6), Color(0.12, 0.12, 0.14), t_list)
	_add_boxes("Benches", Vector3(0.45, 0.45, 2.4), Color(0.55, 0.38, 0.22), b_list)


func _add_boxes(node_name: String, size: Vector3, color: Color, transforms: Array) -> void:
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	var bm := BoxMesh.new()
	bm.size = size
	bm.material = _flat_material(color)
	mm.mesh = bm
	mm.instance_count = transforms.size()
	for i in range(transforms.size()):
		mm.set_instance_transform(i, transforms[i])
	var mmi := MultiMeshInstance3D.new()
	mmi.name = node_name
	mmi.multimesh = mm
	mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(mmi)


## Tableau d'affichage à quatre faces suspendu au-dessus du centre de la pelouse.
func _add_scoreboard(info: Dictionary) -> void:
	var c: Vector3 = info["center"]
	var y: float = float(info["roof_top"]) - SCOREBOARD_DROP_M
	var box := MeshInstance3D.new()
	box.name = "Scoreboard"
	var bm := BoxMesh.new()
	bm.size = Vector3(6.0, 3.2, 6.0)
	var mat := _flat_material(Color(0.06, 0.07, 0.10))
	mat.emission_enabled = true
	mat.emission = Color(0.10, 0.18, 0.40)
	mat.emission_energy_multiplier = 0.6
	bm.material = mat
	box.mesh = bm
	box.position = Vector3(c.x, y, c.z)
	box.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(box)
	for k in range(4):
		var lbl := Label3D.new()
		lbl.name = "ScoreboardText%d" % k
		lbl.text = SCOREBOARD_IDLE
		lbl.font_size = SCOREBOARD_FONT_MAX
		lbl.pixel_size = SCOREBOARD_PIXEL_M
		lbl.modulate = Color(1.0, 0.72, 0.18)
		lbl.shaded = false
		var ang := k * PI * 0.5
		lbl.transform = Transform3D(Basis(Vector3.UP, ang), Vector3(c.x, y, c.z) + Vector3(sin(ang), 0.0, cos(ang)) * 3.02)
		add_child(lbl)


func _flat_material(color: Color) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = color
	m.roughness = 0.8
	return m


## Public : un sous-ensemble stable des places ; une personne sur STANDING_SHARE debout (bras levés pour la
## moitié d'entre elles), les autres assises ; tenue, peau et cheveux tirés de l'indice de la place.
func _place_crowd() -> void:
	for c in [_crowd, _crowd_standing]:
		if c != null:
			remove_child(c)
			c.queue_free()
	_crowd = null
	_crowd_standing = null
	var keep := occupied(_seats_cache.size(), QualityPresets.velodrome_crowd(quality))
	var seated: Array = []
	var standing: Array = []
	for i in keep:
		(standing if hash01(i + 23) < STANDING_SHARE else seated).append(i)
	_crowd = _crowd_node("Crowd", person_mesh(false), seated)
	_crowd_standing = _crowd_node("CrowdStanding", person_mesh(true), standing)
	crowd_count = keep.size()


func _crowd_node(node_name: String, mesh: Mesh, places: Array) -> MultiMeshInstance3D:
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.use_custom_data = true
	mm.mesh = mesh
	mm.instance_count = places.size()
	for j in range(places.size()):
		var i: int = places[j]
		var t: Transform3D = _seats_cache[i]
		var s := 0.92 + 0.16 * hash01(i + 29)   # tailles variées
		t.basis = t.basis.rotated(Vector3.UP, (hash01(i + 7) - 0.5) * 0.6).scaled(Vector3(s, s, s))
		mm.set_instance_transform(j, t)
		# rgb : maillot (teintes franches ou sombres) ; a : peau et cheveux (shader).
		var sat := 0.25 + 0.6 * hash01(i + 13)
		var val := 0.25 + 0.65 * hash01(i + 17)
		mm.set_instance_custom_data(j, Color.from_hsv(hash01(i + 11), sat, val, hash01(i + 19)))
	var mat := ShaderMaterial.new()
	mat.shader = CrowdShader
	var mmi := MultiMeshInstance3D.new()
	mmi.name = node_name
	mmi.multimesh = mm
	mmi.material_override = mat
	mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(mmi)
	return mmi


## Personne vue des tribunes (environ 150 triangles), regard vers −Z, pieds sur le gradin : assise (cuisses
## en avant, mains sur les genoux) ou debout (`standing`, bras levés). Couleur de sommet : r = maillot,
## g = peau, b = pantalon, a = cheveux (velodrome_crowd.gdshader).
static func person_mesh(standing: bool) -> ArrayMesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var shirt := Color(1, 0, 0, 0)
	var skin := Color(0, 1, 0, 0)
	var trousers := Color(0, 0, 1, 0)
	var hair := Color(0, 0, 0, 1)
	var hip := 0.88 if standing else 0.42
	for side in [-1.0, 1.0]:
		var x: float = 0.1 * side
		if standing:
			_tube(st, Vector3(x, hip, 0.0), Vector3(x, 0.45, -0.02), 0.075, 0.06, 5, trousers)
			_tube(st, Vector3(x, 0.45, -0.02), Vector3(x, 0.02, 0.0), 0.06, 0.05, 5, trousers)
		else:
			_tube(st, Vector3(x, hip, 0.04), Vector3(x * 1.2, 0.46, -0.40), 0.08, 0.065, 5, trousers)   # cuisse
			_tube(st, Vector3(x * 1.2, 0.46, -0.40), Vector3(x * 1.2, 0.02, -0.44), 0.06, 0.05, 5, trousers)   # jambe
	var shoulder := hip + 0.52
	_tube(st, Vector3(0.0, hip - 0.02, 0.02), Vector3(0.0, shoulder, 0.05), 0.15, 0.19, 6, shirt)   # buste
	_tube(st, Vector3(0.0, shoulder, 0.05), Vector3(0.0, shoulder + 0.07, 0.05), 0.12, 0.05, 6, shirt)   # épaules
	var head := Vector3(0.0, shoulder + 0.19, 0.04)
	_ellipsoid(st, head, Vector3(0.095, 0.115, 0.105), 6, 4, skin, -1.0)
	_ellipsoid(st, head + Vector3(0.0, 0.015, 0.012), Vector3(0.105, 0.12, 0.112), 6, 2, hair, 0.05)   # calotte
	for side in [-1.0, 1.0]:
		var sh: Vector3 = Vector3(0.2 * side, shoulder - 0.03, 0.05)
		if standing and side > 0.0:
			_tube(st, sh, Vector3(0.26 * side, shoulder + 0.5, 0.0), 0.05, 0.04, 4, shirt)   # bras levé
		elif standing:
			_tube(st, sh, Vector3(0.24 * side, hip - 0.05, 0.02), 0.05, 0.04, 4, shirt)
		else:
			_tube(st, sh, Vector3(0.17 * side, hip + 0.1, -0.30), 0.05, 0.04, 4, shirt)   # mains sur les genoux
	st.generate_normals()
	return st.commit()


## Tube tronconique de `a` (rayon ra) à `b` (rayon rb), `sides` faces, bouts ouverts (cachés dans le corps).
static func _tube(st: SurfaceTool, a: Vector3, b: Vector3, ra: float, rb: float, sides: int, color: Color) -> void:
	var axis := (b - a).normalized()
	var u := axis.cross(Vector3.FORWARD if absf(axis.y) > 0.9 else Vector3.UP).normalized()
	var w := axis.cross(u).normalized()
	for k in range(sides):
		var a0 := TAU * k / sides
		var a1 := TAU * (k + 1) / sides
		var d0 := u * cos(a0) + w * sin(a0)
		var d1 := u * cos(a1) + w * sin(a1)
		_tri(st, a + d0 * ra, b + d0 * rb, b + d1 * rb, color)
		_tri(st, a + d0 * ra, b + d1 * rb, a + d1 * ra, color)


## Ellipsoïde (ou sa partie au-dessus de y_frac du rayon vertical : calotte des cheveux).
static func _ellipsoid(st: SurfaceTool, c: Vector3, r: Vector3, seg: int, rings: int, color: Color, y_frac: float) -> void:
	var lat0 := asin(clampf(y_frac, -1.0, 1.0))
	for i in range(rings):
		var t0 := lerpf(lat0, PI * 0.5, float(i) / rings)
		var t1 := lerpf(lat0, PI * 0.5, float(i + 1) / rings)
		for k in range(seg):
			var p0 := TAU * k / seg
			var p1 := TAU * (k + 1) / seg
			var q := [_sph(c, r, t0, p0), _sph(c, r, t0, p1), _sph(c, r, t1, p1), _sph(c, r, t1, p0)]
			_tri(st, q[0], q[2], q[1], color)
			_tri(st, q[0], q[3], q[2], color)


static func _sph(c: Vector3, r: Vector3, lat: float, lon: float) -> Vector3:
	return c + Vector3(r.x * cos(lat) * cos(lon), r.y * sin(lat), r.z * cos(lat) * sin(lon))


static func _tri(st: SurfaceTool, a: Vector3, b: Vector3, c: Vector3, color: Color) -> void:
	for p in [a, b, c]:
		st.set_color(color)
		st.add_vertex(p)


# --- ambiance ----------------------------------------------------------------------------------------------

## Ambiance de salle : fond uni, lumière ambiante, lumière zénithale, sans brouillard ni brume. L'état d'avant
## est gardé une fois (restore) ; à rappeler après tout changement de préréglage ou de thème qui le réécrit.
func apply_indoor(env: Environment, sun: DirectionalLight3D) -> void:
	if env != null:
		if not _saved.has("env"):
			_saved["env"] = {"background_mode": env.background_mode, "background_color": env.background_color,
				"ambient_light_source": env.ambient_light_source, "ambient_light_color": env.ambient_light_color,
				"ambient_light_energy": env.ambient_light_energy, "reflected_light_source": env.reflected_light_source,
				"fog_enabled": env.fog_enabled, "volumetric_fog_enabled": env.volumetric_fog_enabled}
		env.background_mode = Environment.BG_COLOR
		env.background_color = BACKGROUND
		env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
		env.ambient_light_color = AMBIENT
		env.ambient_light_energy = AMBIENT_ENERGY
		env.reflected_light_source = Environment.REFLECTION_SOURCE_BG
		env.fog_enabled = false
		env.volumetric_fog_enabled = false
	if sun != null:
		if not _saved.has("sun"):
			_saved["sun"] = {"basis": sun.basis, "light_color": sun.light_color, "light_energy": sun.light_energy}
		sun.basis = Basis.looking_at(TOP_LIGHT_DIR.normalized(), Vector3.FORWARD)
		sun.light_color = TOP_LIGHT_COLOR
		sun.light_energy = TOP_LIGHT_ENERGY


## Retour à l'ambiance d'avant la salle (parcours suivant sur route) ; le brouillard est reposé par
## l'atmosphère du parcours (atmosphere_view.set_world) juste après.
func restore(env: Environment, sun: DirectionalLight3D) -> void:
	if env != null and _saved.has("env"):
		for k in _saved["env"]:
			env.set(k, _saved["env"][k])
	if sun != null and _saved.has("sun"):
		for k in _saved["sun"]:
			sun.set(k, _saved["sun"][k])
	_saved = {}


func is_indoor() -> bool:
	return not _saved.is_empty()
