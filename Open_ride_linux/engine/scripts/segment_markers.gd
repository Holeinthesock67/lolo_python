extends Node3D

## Lignes, portiques, panneaux des segments et arches de bonus dans la scène (lot T8, série T), construits
## par code d'après segment_markers_model.gd. Pas de class_name : charger par
## preload("res://scripts/segment_markers.gd"). Créé par main.gd.
##
## - `set_route(route, arch_every_m, road_width_m, route_gates)` : marques du parcours (couche `segments` de
##   la route, départ et arrivée du parcours sauf monde ouvert, arches tous les `arch_every_m`).
## - `update(cam_s, arches_on)` une fois par image : ne garde en scène que les marques entre BEHIND_M
##   derrière et AHEAD_M devant la caméra (quelques nœuds, aucun quand rien n'est proche). `arches_on`
##   faux (ERG, option « Bonus » coupée, hors séance : la trame `state` n'a pas de champ `powerup`) :
##   aucune arche.
## Portique (29/10, une seule forme pour tous) : arche gonflable (tube à coins arrondis, maillage partagé
## refait seulement quand la largeur de route change) lestée de deux blocs, bandeau suspendu (titre en
## capitales, sous-titre plus petit), deux drapeaux-plumes de part et d'autre, ligne peinte au sol. Le style
## de la marque (`STYLES`) choisit les couleurs : sprint vert à bandes blanches, montée et sommet blancs à
## pois rouges (bandeau blanc au départ, rouge au sommet), départ du parcours bleu, arrivée du parcours en
## damier, arche de bonus violette et lumineuse. Toute arrivée (fin de sprint, sommet, arrivée, ligne
## d'une boucle) a une frise en damier sous le bandeau et une ligne en damier au sol ; tout départ, une
## ligne blanche. Bandeau imprimé des deux côtés (demi-tour, lot N17 : `back_lines`, le dos du départ d'un
## parcours en ligne annonce l'arrivée). Panneaux à gauche de la route, face au cycliste qui arrive (une seule
## face : rien ne se chronomètre à rebours). Aucune ombre portée.
## - Lot DS5 : `set_survivor_arches(arches)` pose les portiques d'élimination du Dernier survivant (style `elim` :
##   tube à bandes rouges et noires, bandeau rouge foncé « ÉLIMINATION », frise et ligne en damier), mis à jour
##   par `update` comme les autres marques ; un portique de segment confondu (moins de MERGE_M) n'est pas doublé.
## - `warm_up(camera)` après `set_route` (préchauffage, 02/11) : un exemplaire de chaque sorte de marque du
##   parcours, minuscule et collé devant la caméra pendant WARM_FRAMES images, pour que le premier dessin
##   (pipelines des matériaux, textures, glyphes des Label3D) se fasse au chargement et non en roulant
##   (banc 7bx : à-coups de ~130 ms au premier portique et à la première arrivée, 400 m avant eux).

const Model := preload("res://scripts/segment_markers_model.gd")

const ARCH_HEIGHT_M := 5.2           # axe du tube au sommet de l'arche
const ARCH_CORNER_M := 1.6
const TUBE_RADIUS_M := 0.42
const TUBE_SIDES := 12
const CORNER_STEPS := 8
const ARCH_OUT_M := 0.7              # axe des pieds à 0,7 m + rayon du tube du bord de la chaussée
const BALLAST := Vector3(1.1, 0.35, 1.1)
const BANNER_HEIGHT_M := 1.3
const BANNER_DEPTH_M := 0.08
const STRIP_HEIGHT_M := 0.22         # frise en damier des arrivées, sous le bandeau
const FLAG_POLE_M := 3.8
const FLAG_SIZE := Vector3(0.75, 2.6, 0.03)
const FLAG_OUT_M := 1.5              # drapeaux à 1,5 m à l'extérieur des pieds de l'arche
const LINE_DEPTH_M := 0.5
const FINISH_LINE_DEPTH_M := 1.0     # damier des arrivées, plus large pour se voir de loin
const LINE_LIFT_M := 0.03            # au-dessus de la chaussée, contre le scintillement
const PANEL_SIZE := Vector3(1.4, 0.8, 0.05)
const PANEL_HEIGHT_M := 1.9
const PANEL_OUT_M := 1.5
const LETTER_HEIGHT_M := 0.14
const COLORS := {
	"green": Color(0.08, 0.55, 0.22),
	"red": Color(0.78, 0.07, 0.07),
	"blue": Color(0.10, 0.28, 0.72),
	"dark": Color(0.10, 0.10, 0.12),
	"white": Color(0.96, 0.96, 0.94),
	"arch": Color(0.55, 0.20, 0.85),
	"post": Color(0.85, 0.85, 0.87),
	"ballast": Color(0.25, 0.25, 0.27),
	"panel": Color(0.96, 0.96, 0.94),
	"line": Color(0.97, 0.97, 0.97),
	"elim": Color(0.55, 0.05, 0.07),
}
## Style -> matériaux : tube de l'arche, fond du bandeau, encre du texte, tissu des drapeaux ; arrivée ou non.
const STYLES := {
	"sprint_start": {"tube": "tube_sprint", "banner": "green", "ink": "white", "flag": "green", "finish": false},
	"sprint_finish": {"tube": "tube_sprint", "banner": "green", "ink": "white", "flag": "green", "finish": true},
	"climb_start": {"tube": "tube_polka", "banner": "white", "ink": "red", "flag": "flag_polka", "finish": false},
	"summit": {"tube": "tube_polka", "banner": "red", "ink": "white", "flag": "flag_polka", "finish": true},
	"route_start": {"tube": "tube_route", "banner": "blue", "ink": "white", "flag": "blue", "finish": false},
	"route_finish": {"tube": "tube_checker", "banner": "dark", "ink": "white", "flag": "flag_checker", "finish": true},
	"route_line": {"tube": "tube_checker", "banner": "dark", "ink": "white", "flag": "flag_checker", "finish": true},
	"arch": {"tube": "arch", "banner": "arch", "ink": "white", "flag": "", "finish": false},
	"elim": {"tube": "tube_elim", "banner": "elim", "ink": "white", "flag": "", "finish": true},
}

var road_width_m := 6.0
var marks: Array = []
var _starts := PackedFloat64Array()
var _route = null
var _nodes: Dictionary = {}         # indice de la marque -> Node3D
var _box: ArrayMesh = null
var _tube: ArrayMesh = null
var _tube_width_m := -1.0
var _mats: Dictionary = {}
var _warm: Node3D = null            # exemplaires du préchauffage, retirés après WARM_FRAMES appels à update
var _warm_frames := 0
var _elim: Array = []               # portiques d'élimination du Dernier survivant : [{s (dans le tour), arch, lines}]
var _elim_nodes: Dictionary = {}    # arche -> Node3D

const WARM_FRAMES := 3
const WARM_SCALE := 0.0005          # un portique de 8 m tient dans 4 mm : rien de visible à l'écran
const WARM_DIST_M := 2.0


func _init() -> void:
	var b := BoxMesh.new()
	b.size = Vector3.ONE
	_box = ArrayMesh.new()
	_box.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, b.get_mesh_arrays())
	for key in COLORS:
		var m := StandardMaterial3D.new()
		m.albedo_color = COLORS[key]
		_mats[key] = m
	_mats["arch"].emission_enabled = true
	_mats["arch"].emission = COLORS["arch"]
	_mats["arch"].emission_energy_multiplier = 0.8
	# tube en mètres (u le long de l'arche, v autour) : motif répété tous les `tile` mètres
	_mats["tube_sprint"] = _textured(_band_image(COLORS["green"], COLORS["white"]), Vector3(1.0 / 2.4, 1.0, 1.0))
	_mats["tube_elim"] = _textured(_band_image(Color(0.80, 0.08, 0.08), COLORS["dark"]), Vector3(1.0 / 2.4, 1.0, 1.0))
	_mats["tube_route"] = _textured(_band_image(COLORS["blue"], COLORS["white"]), Vector3(1.0 / 2.4, 1.0, 1.0))
	_mats["tube_polka"] = _textured(_polka_image(), Vector3(1.0 / 1.3, 1.0 / 1.32, 1.0))
	_mats["tube_checker"] = _textured(_checker_image(4, 4), Vector3(1.0 / 1.32, 1.0 / 1.32, 1.0))
	_mats["flag_polka"] = _textured(_polka_image(), Vector3(4.5, 10.0, 1.0))      # face avant d'une boîte : 1/3 × 1/2 de la texture
	_mats["flag_checker"] = _textured(_checker_image(4, 4), Vector3(3.0, 7.0, 1.0))
	_mats["strip"] = _textured(_checker_image(8, 2), Vector3(4.0, 1.0, 1.0))
	_mats["finish_line"] = _textured(_checker_image(8, 4), Vector3(3.0, 2.0, 1.0))   # cases de 25 cm
	for key in _mats:
		(_mats[key] as StandardMaterial3D).roughness = 0.6   # toile enduite : léger reflet du ciel


static func _polka_image() -> Image:
	var img := Image.create(64, 64, false, Image.FORMAT_RGB8)
	img.fill(Color(0.97, 0.97, 0.97))
	var red := Color(0.80, 0.08, 0.08)
	for c in [Vector2(16, 16), Vector2(48, 48)]:
		for y in range(64):
			for x in range(64):
				if Vector2(x, y).distance_to(c) <= 8.0:
					img.set_pixel(x, y, red)
	return img


## Damier de `cols` × `rows` cases sur 64 × (64 × rows / cols) pixels.
static func _checker_image(cols: int, rows: int) -> Image:
	var cell := 64 / cols
	var img := Image.create(64, cell * rows, false, Image.FORMAT_RGB8)
	for y in range(cell * rows):
		for x in range(64):
			var dark := (x / cell + y / cell) % 2 == 0
			img.set_pixel(x, y, Color(0.08, 0.08, 0.08) if dark else Color(0.97, 0.97, 0.97))
	return img


## Bande claire d'un quart de motif sur fond `base` (u seul).
static func _band_image(base: Color, band: Color) -> Image:
	var img := Image.create(64, 4, false, Image.FORMAT_RGB8)
	for y in range(4):
		for x in range(64):
			img.set_pixel(x, y, band if x >= 40 and x < 56 else base)
	return img


func _textured(img: Image, uv_scale: Vector3) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	img.generate_mipmaps()
	m.albedo_texture = ImageTexture.create_from_image(img)
	# filtre linéaire anisotrope : damier et pois sans scintillement vus en rasant
	m.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
	m.uv1_scale = uv_scale
	return m


## Demi-largeur de l'arche, à l'axe des pieds.
func arch_half_m() -> float:
	return road_width_m * 0.5 + ARCH_OUT_M + TUBE_RADIUS_M


## Tube de l'arche (pieds verticaux, coins arrondis, traverse), UV en mètres ; partagé par tous les portiques.
static func tube_mesh(half_m: float) -> ArrayMesh:
	var path: Array = [Vector2(-half_m, 0.0)]
	var h := ARCH_HEIGHT_M
	var r := ARCH_CORNER_M
	for i in range(CORNER_STEPS + 1):
		var a := PI - PI * 0.5 * i / CORNER_STEPS
		path.append(Vector2(-half_m + r, h - r) + Vector2(cos(a), sin(a)) * r)
	for i in range(CORNER_STEPS + 1):
		var a := PI * 0.5 - PI * 0.5 * i / CORNER_STEPS
		path.append(Vector2(half_m - r, h - r) + Vector2(cos(a), sin(a)) * r)
	path.append(Vector2(half_m, 0.0))
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var u := 0.0
	var circ := TAU * TUBE_RADIUS_M
	for k in range(path.size()):
		if k > 0:
			u += (path[k] as Vector2).distance_to(path[k - 1])
		var t: Vector2 = ((path[mini(k + 1, path.size() - 1)] as Vector2) - (path[maxi(k - 1, 0)] as Vector2)).normalized()
		var n := Vector3(-t.y, t.x, 0.0)
		for j in range(TUBE_SIDES + 1):
			var a := TAU * j / TUBE_SIDES
			var dir := n * cos(a) + Vector3(0.0, 0.0, sin(a))
			st.set_normal(dir)
			st.set_uv(Vector2(u, circ * j / TUBE_SIDES))
			st.add_vertex(Vector3(path[k].x, path[k].y, 0.0) + dir * TUBE_RADIUS_M)
	var ring := TUBE_SIDES + 1
	for k in range(path.size() - 1):
		for j in range(TUBE_SIDES):
			var a := k * ring + j
			var b := a + ring
			for idx in [a, b, a + 1, a + 1, b, b + 1]:
				st.add_index(idx)
	st.generate_tangents()
	return st.commit()


func set_route(route, arch_every_m: float = Model.DEFAULT_ARCH_EVERY_M, p_road_width_m: float = 6.0,
		route_gates: bool = true) -> void:
	clear()
	_route = route
	road_width_m = p_road_width_m
	if not is_equal_approx(_tube_width_m, road_width_m):
		_tube = tube_mesh(arch_half_m())
		_tube_width_m = road_width_m
	marks = []
	if route != null:
		var segs = route.get("segments")
		if typeof(segs) != TYPE_ARRAY:
			segs = []
		marks = Model.items(route, segs, arch_every_m, route_gates)
	_starts = Model.starts(marks)


## Monde ouvert (lot W21) : route prolongée ou réécrite depuis `from_s`, ou segments trouvés en roulant.
## Les marques sont recalculées (portiques, panneaux, arches jusqu'au bout de la route connue) ; un nœud déjà
## en scène est gardé si sa marque n'a pas changé et qu'elle est avant `from_s` (route inchangée sous elle),
## pour ne pas faire clignoter un portique proche.
func refresh(route, arch_every_m: float, from_s: float = INF) -> void:
	_route = route
	var segs = route.get("segments") if route != null else []
	if typeof(segs) != TYPE_ARRAY:
		segs = []
	var fresh: Array = Model.items(route, segs, arch_every_m, false) if route != null else []
	var index := {}
	for i in range(fresh.size()):
		index[mark_key(fresh[i])] = i
	var kept := {}
	for i in _nodes.keys():
		var node: Node3D = _nodes[i]
		var key := mark_key(marks[i]) if i < marks.size() else ""
		if index.has(key) and float(marks[i]["s"]) < from_s:
			kept[index[key]] = node
		else:
			node.queue_free()
	_nodes = kept
	marks = fresh
	_starts = Model.starts(marks)


## Clé d'une marque (lot W21) : sorte, segment, position au décimètre et textes.
static func mark_key(m: Dictionary) -> String:
	return "%s|%s|%.1f|%s" % [m.get("kind", ""), m.get("segment_id", ""), float(m.get("s", 0.0)), str(m.get("lines", []))]


func clear() -> void:
	_drop_warm()
	_clear_elim()
	for i in _nodes:
		(_nodes[i] as Node3D).queue_free()
	_nodes.clear()


func update(cam_s: float, arches_on: bool) -> void:
	if _warm != null:
		_warm_frames -= 1
		if _warm_frames <= 0:
			_drop_warm()
	_update_elim(cam_s)
	if _route == null or marks.is_empty():
		return
	var want := {}
	for i in Model.window(_starts, cam_s, float(_route.length_m), _route.is_loop()):
		if marks[i]["kind"] == "arch" and not arches_on:
			continue
		if marks[i]["kind"] in ["start", "finish"] and _near_elim(float(marks[i]["s"])):
			continue   # fondu dans le portique d'élimination posé sur la même ligne
		want[i] = true
	for i in _nodes.keys():
		if not want.has(i):
			(_nodes[i] as Node3D).queue_free()
			_nodes.erase(i)
	for i in want:
		if not _nodes.has(i):
			var node := build_mark(marks[i])
			_place(node, marks[i])
			add_child(node)
			_nodes[i] = node


## Portiques d'élimination du Dernier survivant (lot DS5) : `arches` = [{s (cumulé), arch, lines}] de
## survivor_hud_model.arches_to_draw() (la prochaine arche et celle qu'on vient de passer) ; [] : aucun. Un
## portique de segment ou du parcours à moins de MERGE_M n'est pas doublé : le portique d'élimination le
## remplace et prend son titre en sous-titre (arche calée sur une ligne de sprint ou un sommet par le core).
func set_survivor_arches(arches: Array) -> void:
	var next: Array = []
	for a in arches:
		if not a is Dictionary:
			continue
		var s := float(a.get("s", 0.0))
		if _route != null:
			s = float(_route.wrap_s(s))
		var lines: Array = (a.get("lines", ["Élimination"]) as Array).duplicate()
		var merged := _merged_title(s)
		if merged != "" and lines.size() > 1:
			lines[1] = "%s · %s" % [lines[1], merged]
		next.append({"kind": "elim", "style": "elim", "s": s, "side": 0, "arch": int(a.get("arch", 0)), "lines": lines})
	_elim = next
	var keep := {}
	for e in _elim:
		keep[int(e["arch"])] = true
	for k in _elim_nodes.keys():
		if not keep.has(k):
			(_elim_nodes[k] as Node3D).queue_free()
			_elim_nodes.erase(k)


## Portiques d'élimination posés (tests).
func survivor_arches() -> Array:
	return _elim


func _clear_elim() -> void:
	for k in _elim_nodes:
		(_elim_nodes[k] as Node3D).queue_free()
	_elim_nodes.clear()
	_elim = []


func _ahead_of(s: float, cam_s: float) -> float:
	var d := s - cam_s
	if _route != null and _route.is_loop():
		var length := float(_route.length_m)
		d = fposmod(d + length / 2.0, length) - length / 2.0
	return d


func _near_elim(s: float) -> bool:
	for e in _elim:
		if absf(_ahead_of(s, float(e["s"]))) < Model.MERGE_M:
			return true
	return false


func _merged_title(s: float) -> String:
	for m in marks:
		if m["kind"] in ["start", "finish"] and absf(_ahead_of(float(m["s"]), s)) < Model.MERGE_M:
			return str((m["lines"] as Array)[0]) if not (m["lines"] as Array).is_empty() else ""
	return ""


func _update_elim(cam_s: float) -> void:
	if _route == null:
		return
	for e in _elim:
		var k := int(e["arch"])
		var d := _ahead_of(float(e["s"]), cam_s)
		var want := d >= -Model.BEHIND_M and d <= Model.AHEAD_M
		if want and not _elim_nodes.has(k):
			var node := build_mark(e)
			_place(node, e)
			add_child(node)
			_elim_nodes[k] = node
		elif not want and _elim_nodes.has(k):
			(_elim_nodes[k] as Node3D).queue_free()
			_elim_nodes.erase(k)


## Préchauffage : une marque de chaque sorte (panneau, ou portique d'un style donné) du parcours, construite
## comme en séance, sous `camera` à WARM_DIST_M devant elle et réduite à WARM_SCALE ; avec `survivor`, aussi un
## portique d'élimination (lot DS5). Sans caméra ou sans
## marque : rien. Retourne le nombre d'exemplaires.
func warm_up(camera: Node3D, survivor := false) -> int:
	_drop_warm()
	if camera == null or marks.is_empty():
		return 0
	var seen := {}
	_warm = Node3D.new()
	_warm.name = "SegmentMarkersWarm"
	_warm.position = Vector3(0.0, 0.0, -WARM_DIST_M)
	_warm.scale = Vector3.ONE * WARM_SCALE
	for m in marks:
		var key := "%s/%s" % [m["kind"], m.get("style", "")]
		if seen.has(key):
			continue
		seen[key] = true
		_warm.add_child(build_mark(m))
	if survivor:   # séance du Dernier survivant préparée : le portique d'élimination aussi (lot DS5)
		seen["elim/elim"] = true
		_warm.add_child(build_mark({"kind": "elim", "style": "elim", "s": 0.0, "side": 0,
			"lines": ["Élimination", "Arche 1 sur 4 · le dernier sort"]}))
	camera.add_child(_warm)
	_warm_frames = WARM_FRAMES
	return seen.size()


## Exemplaires du préchauffage encore en scène (tests).
func warm_count() -> int:
	return 0 if _warm == null else _warm.get_child_count()


func _drop_warm() -> void:
	if _warm != null:
		_warm.queue_free()
	_warm = null
	_warm_frames = 0


## Marques en scène (tests).
func shown() -> Array:
	var out: Array = []
	for i in _nodes:
		out.append(marks[i])
	for e in _elim:
		if _elim_nodes.has(int(e["arch"])):
			out.append(e)
	return out


## Nœuds actifs (budget du lot : moins de 50).
func active_node_count() -> int:
	var n := 0
	for i in _nodes:
		n += 1 + (_nodes[i] as Node3D).get_child_count()
	for k in _elim_nodes:
		n += 1 + (_elim_nodes[k] as Node3D).get_child_count()
	return n


func _mesh(parent: Node3D, mat_key: String, pos: Vector3, size: Vector3, mesh: Mesh = null) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	mi.mesh = _box if mesh == null else mesh
	mi.material_override = _mats[mat_key]
	mi.position = pos
	mi.scale = size
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	parent.add_child(mi)
	return mi


func _label(parent: Node3D, lines: Array, pos: Vector3, width_m: float, height_m: float, ink: Color,
		min_letter_m: float = LETTER_HEIGHT_M) -> Label3D:
	var label := Label3D.new()
	label.text = "\n".join(lines)
	label.modulate = ink
	label.outline_size = 6
	label.outline_modulate = Color(0, 0, 0, 0.8)
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	label.font_size = 48
	var longest := 1
	for l in lines:
		longest = maxi(longest, str(l).length())
	var by_width := width_m * 0.92 / (longest * 0.55 * label.font_size)
	var by_height := height_m * 0.85 / (lines.size() * 1.2 * label.font_size)
	label.pixel_size = maxf(min_letter_m / label.font_size, minf(by_width, by_height))
	label.position = pos
	parent.add_child(label)
	return label


## Nœud d'une marque `{kind, style, type, lines}` (repère local : x vers la droite, -z vers l'avant du parcours).
func build_mark(mark: Dictionary) -> Node3D:
	var root := Node3D.new()
	var kind: String = mark["kind"]
	root.name = "%s_%d" % [kind, int(mark["s"])]
	if kind == "panel":
		_mesh(root, "post", Vector3(0.0, PANEL_HEIGHT_M * 0.5, 0.0), Vector3(0.08, PANEL_HEIGHT_M, 0.08))
		var board_y := PANEL_HEIGHT_M + PANEL_SIZE.y * 0.5
		_mesh(root, "panel", Vector3(0.0, board_y, 0.0), PANEL_SIZE)
		var text := _label(root, mark["lines"], Vector3(0.0, board_y, PANEL_SIZE.z * 0.5 + 0.005), PANEL_SIZE.x,
			PANEL_SIZE.y, Color(0.1, 0.1, 0.1))
		text.outline_size = 0
		return root
	var style: Dictionary = STYLES.get(str(mark.get("style", "")), STYLES["arch"])
	var half := arch_half_m()
	if _tube == null:
		_tube = tube_mesh(half)
		_tube_width_m = road_width_m
	_mesh(root, style["tube"], Vector3.ZERO, Vector3.ONE, _tube)
	for side in [-1.0, 1.0]:
		_mesh(root, "ballast", Vector3(side * half, BALLAST.y * 0.5, 0.0), BALLAST)
	# bandeau suspendu sous la traverse, entre les coins arrondis
	var inner := half - TUBE_RADIUS_M - ARCH_CORNER_M * 0.4
	var banner_y := ARCH_HEIGHT_M - TUBE_RADIUS_M - BANNER_HEIGHT_M * 0.5 - 0.05
	var face := BANNER_DEPTH_M * 0.5 + 0.01
	_mesh(root, style["banner"], Vector3(0.0, banner_y, 0.0), Vector3(2.0 * inner, BANNER_HEIGHT_M, BANNER_DEPTH_M))
	var ink: Color = COLORS[style["ink"]]
	# Bandeau imprimé des deux côtés (demi-tour, lot N17) : le dos porte le texte de back_lines(), tourné d'un
	# demi-tour pour se lire à l'endroit depuis l'autre sens de marche
	for back in [false, true]:
		var lines: Array = back_lines(mark) if back else mark["lines"]
		var turn := Basis(Vector3.UP, PI) if back else Basis()
		var title_h := BANNER_HEIGHT_M * (0.6 if lines.size() > 1 else 0.9)
		var title_y := banner_y + (BANNER_HEIGHT_M - title_h) * 0.5 - 0.04
		var title := _label(root, [str(lines[0]).to_upper()], turn * Vector3(0.0, title_y, face), 2.0 * inner * 0.9, title_h, ink)
		title.basis = turn
		if lines.size() > 1:
			var sub_h := BANNER_HEIGHT_M - title_h
			var sub := _label(root, [" · ".join(lines.slice(1))],
				turn * Vector3(0.0, banner_y - BANNER_HEIGHT_M * 0.5 + sub_h * 0.5 + 0.02, face), 2.0 * inner * 0.85, sub_h, ink, 0.08)
			sub.basis = turn
	if style["finish"]:
		_mesh(root, "strip", Vector3(0.0, banner_y - (BANNER_HEIGHT_M + STRIP_HEIGHT_M) * 0.5, 0.0),
			Vector3(2.0 * inner, STRIP_HEIGHT_M, BANNER_DEPTH_M))
	if not str(style["flag"]).is_empty():
		for side in [-1.0, 1.0]:
			var x: float = side * (half + FLAG_OUT_M)
			_mesh(root, "post", Vector3(x, FLAG_POLE_M * 0.5, 0.0), Vector3(0.05, FLAG_POLE_M, 0.05))
			_mesh(root, style["flag"], Vector3(x - side * FLAG_SIZE.x * 0.5, FLAG_POLE_M - FLAG_SIZE.y * 0.5 - 0.05, 0.0),
				FLAG_SIZE)
	if kind != "arch":
		_mesh(root, "finish_line" if style["finish"] else "line", Vector3(0.0, LINE_LIFT_M, 0.0),
			Vector3(road_width_m, 0.02, FINISH_LINE_DEPTH_M if style["finish"] else LINE_DEPTH_M))
	return root


## Texte du dos d'un bandeau, lu par le cycliste qui roule à rebours (lot N17) : le même que la face, sauf le
## portique de départ d'un parcours en ligne, dont le dos annonce l'arrivée (à rebours, la séance finit au
## départ du parcours, session.py). Une boucle a un seul portique « Départ · Arrivée », juste des deux côtés.
static func back_lines(mark: Dictionary) -> Array:
	if str(mark.get("style", "")) == "route_start":
		return ["Arrivée"]
	return mark["lines"]


func _place(node: Node3D, mark: Dictionary) -> void:
	var s := float(mark["s"])
	var smp: Dictionary = _route.sample(s)
	var h := deg_to_rad(float(smp["heading_deg"]))
	var right := Vector3(cos(h), 0.0, sin(h))
	var fwd := Vector3(sin(h), 0.0, -cos(h))
	var pos := Vector3(smp["x"], smp["y"], smp["z"])
	if int(mark["side"]) != 0:
		pos += right * float(mark["side"]) * (road_width_m * 0.5 + PANEL_OUT_M)
	# +z local (face des panneaux et banderoles) vers le cycliste qui arrive, donc vers -fwd
	node.transform = Transform3D(Basis(Vector3.UP, atan2(-fwd.x, -fwd.z)), pos)
