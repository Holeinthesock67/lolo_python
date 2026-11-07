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
const BAND_H_M := 1.6             # bandeau sombre du bas du mur, au-dessus du promenoir
const ROOF_RISE_M := 13.0         # flèche de la coupole
const ROOF_RINGS := 12
const RIB_EVERY := 8              # un arc sombre tous les 8 pas du contour (16 m)
const RAMPS := [0.28, 0.52, 0.74] # rampes d'éclairage, en fraction du rayon du toit depuis le mur
const RAMP_HALF := 0.012
const RAMP_DROP_M := 0.6
const SEAT_PITCH_M := 0.55        # écart entre deux places d'un gradin
const SCOREBOARD_DROP_M := 5.0

const FLOOR_COLOR := Color(0.30, 0.52, 0.38)       # pelouse centrale (sol sportif vert)
const TREAD_COLOR := Color(0.58, 0.58, 0.60)       # béton des gradins
const RISER_COLOR := Color(0.16, 0.30, 0.62)       # sièges bleus vus de face
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
var _crowd: MultiMeshInstance3D = null
var _seats_cache: Array = []
var _saved := {}              # ambiance d'avant la salle (restore)


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
	for c in get_children():
		remove_child(c)
		c.queue_free()
	_crowd = null
	crowd_count = 0
	built = false
	_seats_cache = []


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
		top = maxf(top, float(pr[pr.size() - 1][1]))
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
		lbl.text = "VÉLODROME\n250 m"
		lbl.font_size = 96
		lbl.pixel_size = 0.012
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


## Public : un sous-ensemble stable des places, couleurs de maillot et de peau tirées de l'indice.
func _place_crowd() -> void:
	if _crowd != null:
		remove_child(_crowd)
		_crowd.queue_free()
		_crowd = null
	var keep := occupied(_seats_cache.size(), QualityPresets.velodrome_crowd(quality))
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.use_custom_data = true
	mm.mesh = person_mesh()
	mm.instance_count = keep.size()
	for j in range(keep.size()):
		var i := keep[j]
		var t: Transform3D = _seats_cache[i]
		t.basis = t.basis.rotated(Vector3.UP, (hash01(i + 7) - 0.5) * 0.5)
		mm.set_instance_transform(j, t)
		mm.set_instance_custom_data(j, Color.from_hsv(hash01(i + 11), 0.15 + 0.45 * hash01(i + 13),
			0.25 + 0.6 * hash01(i + 17), hash01(i + 19)))
	var mat := ShaderMaterial.new()
	mat.shader = CrowdShader
	_crowd = MultiMeshInstance3D.new()
	_crowd.name = "Crowd"
	_crowd.multimesh = mm
	_crowd.material_override = mat
	_crowd.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(_crowd)
	crowd_count = keep.size()


## Personne assise vue de loin (5 pavés), regard vers −Z : couleur de sommet r = maillot, g = peau, b = pantalon.
static func person_mesh() -> ArrayMesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	_box(st, Vector3(0.0, 0.15, -0.18), Vector3(0.40, 0.16, 0.44), Color(0, 0, 1))   # cuisses
	_box(st, Vector3(0.0, 0.58, 0.02), Vector3(0.44, 0.58, 0.26), Color(1, 0, 0))    # buste
	_box(st, Vector3(0.0, 0.98, 0.0), Vector3(0.20, 0.22, 0.22), Color(0, 1, 0))     # tête
	_box(st, Vector3(-0.26, 0.55, -0.06), Vector3(0.09, 0.46, 0.12), Color(1, 0, 0)) # bras
	_box(st, Vector3(0.26, 0.55, -0.06), Vector3(0.09, 0.46, 0.12), Color(1, 0, 0))
	return st.commit()


static func _box(st: SurfaceTool, c: Vector3, size: Vector3, color: Color) -> void:
	var h := size * 0.5
	for axis in range(3):
		for sgn in [-1.0, 1.0]:
			var nn := Vector3.ZERO
			nn[axis] = sgn
			var u := Vector3.ZERO
			u[(axis + 1) % 3] = 1.0
			var w := Vector3.ZERO
			w[(axis + 2) % 3] = 1.0
			var o := c + nn * h
			var du := u * h
			var dw := w * h
			var q := [o - du - dw, o + du - dw, o + du + dw, o - du + dw]
			var order := [0, 1, 2, 0, 2, 3] if sgn < 0.0 else [0, 2, 1, 0, 3, 2]
			for idx in order:
				st.set_color(color)
				st.set_normal(nn)
				st.add_vertex(q[idx])


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
