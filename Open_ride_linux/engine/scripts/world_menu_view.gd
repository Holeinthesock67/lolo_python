extends Control

## Affichage du menu « Monde ouvert » (lot W11) : globe en SphereMesh texturée avec côtes, régions du cache
## en surbrillance et régions épinglées marquées, recherche, carte régionale 2D, réglage du cap, écran de
## préchargement. Dessine ce que `world_menu_model.gd` décrit ; ne reçoit pas la souris. Lot O22 : chaque
## état explique ce qu'il fait (STATE_HELP, NAV_HELP) et le bandeau des boutons des autres menus
## (button_bar.gd, aide de button_help.gd) donne en bas les boutons du Click et les touches du clavier.
## Pas de class_name (charger par preload).

const UiTheme := preload("res://scripts/ui_theme.gd")
const ButtonBar := preload("res://scripts/button_bar.gd")
const ButtonHelp := preload("res://scripts/button_help.gd")
const Model := preload("res://scripts/world_menu_model.gd")

const GLOBE_DIR := "res://assets/globe/"
const GLOBE_PX := 560
const BG := UiTheme.GLOBE_BG
const TEXT := UiTheme.GLOBE_TEXT
const DIM := UiTheme.GLOBE_DIM
const ACCENT := UiTheme.PICK
const COAST_COLOR := UiTheme.COAST
const BORDER_COLOR := UiTheme.BORDER
const REGION_COLOR := UiTheme.REGION
const PINNED_COLOR := UiTheme.PINNED
const ROAD_COLORS := {"p": UiTheme.ROAD_P, "s": UiTheme.ROAD_S, "t": UiTheme.PALE,
	"m": UiTheme.ROAD_M, "c": UiTheme.ROAD_C, "k": UiTheme.ROAD_K}
## Rotation de la sphère qui amène la longitude 0 face à la caméra (réglée sur le rendu, tests/render).
const TEXTURE_LON_OFFSET_DEG := 180.0
const MAX_RESULTS := 8
## Explication de chaque état, sous ses lignes (lot O22). Textes alignés sur docs/GUIDE_UTILISATION.md
## §4 bis et sur le plan W (cache, épinglage, Nominatim, carrefours).
const STATE_HELP := {
	Model.GLOBE: "Le monde ouvert crée la route en roulant, d'après les cartes OpenStreetMap. Fais tourner le globe jusqu'à ta région, ou tape un nom de lieu au clavier. Les régions en cache, déjà téléchargées, sont surlignées ; une région épinglée reste toujours dans le cache.",
	Model.SEARCH: "Lieux de la liste fournie avec OpenRide, puis d'OpenStreetMap quand Internet répond.",
	Model.MAP: "Le curseur reste accroché à la route la plus proche : c'est le point de départ.",
	Model.SETUP: "En roulant, un panneau annonce chaque carrefour : ◀ ▶ ou A choisissent la branche, A maintenu la valide, jusqu'à 30 m avant ; sinon la navigation choisit.",
	Model.LOADING: "Le monde se télécharge et se prépare autour du départ. Au même endroit la prochaine fois, rien n'est retéléchargé.",
}
const NAV_HELP := {
	"ride": "Balade : le jeu garde le cap et préfère les petites routes.",
	"destination": "Destination : la navigation te mène au lieu choisi (A le cherche).",
	"loop": "Boucle : retour au départ après la longueur choisie.",
}

var vm := Model.new()
var globe_viewport: SubViewport
var globe_root: Node3D
var globe_view: TextureRect
var title_label: Label
var body_label: Label
var hint_label: Label
var help_label: Label
var button_bar: PanelContainer
var _marker_signature := ""
var _markers: Node3D
var _canvas: Control


func _init() -> void:
	set_anchors_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	visible = false
	var bg := ColorRect.new()
	bg.color = BG
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	bg.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(bg)
	_build_globe()
	_canvas = Control.new()
	_canvas.set_anchors_preset(Control.PRESET_FULL_RECT)
	_canvas.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_canvas.draw.connect(_draw_canvas)
	add_child(_canvas)
	title_label = _label(34, TEXT, Vector2(40.0, 24.0))
	body_label = _label(24, TEXT, Vector2(40.0, 90.0))
	body_label.custom_minimum_size = Vector2(440.0, 0.0)
	body_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	help_label = _label(UiTheme.HELP_SIZE, DIM, Vector2(40.0, 0.0))
	help_label.custom_minimum_size = Vector2(440.0, 0.0)
	help_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	# Attributions (préchargement), au-dessus du bandeau des boutons.
	hint_label = _label(UiTheme.SMALL_SIZE, DIM, Vector2(40.0, 0.0))
	hint_label.anchor_top = 1.0
	hint_label.anchor_bottom = 1.0
	hint_label.offset_top = -UiTheme.HELP_H - 40.0
	hint_label.offset_bottom = -UiTheme.HELP_H - 12.0
	button_bar = ButtonBar.new()
	button_bar.mouse_filter = Control.MOUSE_FILTER_IGNORE
	button_bar.anchor_left = 0.0
	button_bar.anchor_right = 1.0
	button_bar.anchor_top = 1.0
	button_bar.anchor_bottom = 1.0
	button_bar.offset_top = -UiTheme.HELP_H
	add_child(button_bar)


func _label(size: int, color: Color, pos: Vector2) -> Label:
	var l := Label.new()
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", color)
	l.position = pos
	l.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(l)
	return l


# --- globe -------------------------------------------------------------------------------------

static func lonlat_to_vec(lon_deg: float, lat_deg: float, radius: float = 1.0) -> Vector3:
	var lon := deg_to_rad(lon_deg)
	var lat := deg_to_rad(lat_deg)
	return Vector3(cos(lat) * sin(lon), sin(lat), cos(lat) * cos(lon)) * radius


func _build_globe() -> void:
	globe_viewport = SubViewport.new()
	globe_viewport.size = Vector2i(GLOBE_PX, GLOBE_PX)
	globe_viewport.transparent_bg = true
	globe_viewport.own_world_3d = true
	globe_viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	add_child(globe_viewport)
	var cam := Camera3D.new()
	cam.position = Vector3(0.0, 0.0, 4.2)
	cam.fov = 32.0
	globe_viewport.add_child(cam)
	globe_root = Node3D.new()
	globe_viewport.add_child(globe_root)
	var sphere := MeshInstance3D.new()
	var mesh := SphereMesh.new()
	mesh.radius = 1.0
	mesh.height = 2.0
	mesh.radial_segments = 96
	mesh.rings = 48
	sphere.mesh = mesh
	sphere.rotation_degrees.y = TEXTURE_LON_OFFSET_DEG
	var mat := StandardMaterial3D.new()
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	var tex := _load_texture(GLOBE_DIR + "globe.jpg")
	if tex != null:
		mat.albedo_texture = tex
	else:
		mat.albedo_color = UiTheme.GLOBE_SEA
	sphere.material_override = mat
	globe_root.add_child(sphere)
	globe_root.add_child(_coast_node())
	_markers = Node3D.new()
	globe_root.add_child(_markers)
	globe_view = TextureRect.new()
	globe_view.texture = globe_viewport.get_texture()
	globe_view.custom_minimum_size = Vector2(GLOBE_PX, GLOBE_PX)
	globe_view.anchor_left = 1.0
	globe_view.anchor_right = 1.0
	globe_view.anchor_top = 0.5
	globe_view.anchor_bottom = 0.5
	globe_view.offset_left = -GLOBE_PX - 40.0
	globe_view.offset_right = -40.0
	globe_view.offset_top = -GLOBE_PX * 0.5
	globe_view.offset_bottom = GLOBE_PX * 0.5
	globe_view.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(globe_view)


## Image lue à l'exécution (le projet est lancé sans passage par l'éditeur : pas de fichiers .import).
static func _load_texture(path: String) -> Texture2D:
	var img := Image.load_from_file(ProjectSettings.globalize_path(path))
	return ImageTexture.create_from_image(img) if img != null else null


func _coast_node() -> MeshInstance3D:
	var node := MeshInstance3D.new()
	var doc = JSON.parse_string(FileAccess.get_file_as_string(GLOBE_DIR + "coast.json")) \
		if FileAccess.file_exists(GLOBE_DIR + "coast.json") else null
	if typeof(doc) != TYPE_DICTIONARY:
		return node
	# Une surface par couche (le moteur en accepte 256 au plus) : segments isolés (PRIMITIVE_LINES).
	var mesh := ArrayMesh.new()
	for pair in [["borders", BORDER_COLOR], ["coast", COAST_COLOR]]:
		var verts := PackedVector3Array()
		for line in doc.get(pair[0], []):
			for i in range(0, line.size() - 3, 2):
				verts.append(lonlat_to_vec(line[i], line[i + 1], 1.002))
				verts.append(lonlat_to_vec(line[i + 2], line[i + 3], 1.002))
		if verts.is_empty():
			continue
		var arrays := []
		arrays.resize(Mesh.ARRAY_MAX)
		arrays[Mesh.ARRAY_VERTEX] = verts
		mesh.add_surface_from_arrays(Mesh.PRIMITIVE_LINES, arrays)
		var mat := StandardMaterial3D.new()
		mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		mat.albedo_color = pair[1]
		mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		mesh.surface_set_material(mesh.get_surface_count() - 1, mat)
	node.mesh = mesh
	return node


func _rebuild_markers() -> void:
	for c in _markers.get_children():
		_markers.remove_child(c)
		c.free()
	for r in vm.regions:
		var b = r.get("bbox")
		if typeof(b) != TYPE_ARRAY or b.size() != 4:
			continue
		var pinned := bool(r.get("pinned", false))
		var dot := MeshInstance3D.new()
		var sm := SphereMesh.new()
		var size := 0.03 if not pinned else 0.045
		sm.radius = size
		sm.height = 2.0 * size
		dot.mesh = sm
		var mat := StandardMaterial3D.new()
		mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		mat.albedo_color = PINNED_COLOR if pinned else REGION_COLOR
		dot.material_override = mat
		dot.position = lonlat_to_vec((float(b[0]) + float(b[2])) * 0.5, (float(b[1]) + float(b[3])) * 0.5, 1.01)
		_markers.add_child(dot)


## Tourne le globe pour que (lat, lon) fasse face à la caméra.
func _orient_globe() -> void:
	globe_root.basis = Basis(Vector3.RIGHT, deg_to_rad(vm.globe_lat)) * Basis(Vector3.UP, deg_to_rad(-vm.globe_lon))


# --- affichage ---------------------------------------------------------------------------------

func open() -> void:
	vm.reset()
	visible = true
	update_display()


func close() -> void:
	visible = false


## Met l'affichage à jour (à chaque événement ou réponse du core, et une fois par image pendant le préchargement).
func update_display() -> void:
	if not visible:
		return
	var sig := JSON.stringify(vm.regions)
	if sig != _marker_signature:
		_marker_signature = sig
		_rebuild_markers()
	_orient_globe()
	var show_globe: bool = vm.state in [Model.GLOBE, Model.SEARCH]
	globe_view.visible = show_globe
	title_label.text = "Monde ouvert"
	body_label.text = _body_text()
	help_label.text = _help_text()
	hint_label.text = Model.ATTRIBUTIONS if vm.state == Model.LOADING else ""
	button_bar.update_display(ButtonHelp.WORLD_PREFIX + str(vm.state))
	_canvas.queue_redraw()


func _body_text() -> String:
	match vm.state:
		Model.GLOBE:
			var r := vm.region_at(vm.globe_lat, vm.globe_lon)
			var lines := ["Centre : %.1f°, %.1f°" % [vm.globe_lat, vm.globe_lon]]
			if not r.is_empty():
				lines.append("Région en cache : %s%s" % [r.get("name", r.get("id", "")), "  (épinglée)" if r.get("pinned", false) else ""])
			return "\n".join(lines)
		Model.SEARCH:
			var lines := ["Recherche : " + vm.query + "_"]
			for i in range(mini(vm.places.size(), MAX_RESULTS)):
				var p: Dictionary = vm.places[i]
				lines.append("%s %s%s" % ["▶" if i == vm.place_index else "  ", p.get("name", "?"), "  (en cache)" if p.get("cached", false) else ""])
			if vm.places.is_empty() and vm.query.length() >= 2:
				lines.append("  aucun résultat")
			return "\n".join(lines)
		Model.MAP:
			return "Choisis le point de départ sur une route" + ("" if vm.map_ready else "\nChargement de la carte…")
		Model.SETUP:
			var rows := ["Cap : %d°" % int(vm.heading_deg), "Navigation : " + Model.NAV_LABELS[vm.nav], _extra_text()]
			for i in range(rows.size()):
				rows[i] = ("▶ " if i == vm.field_index else "   ") + rows[i]
			if vm.last_error != "":
				rows.append("\n" + vm.last_error)
			return "\n".join(rows)
		Model.LOADING:
			return vm.loading_text()
	return ""


func _extra_text() -> String:
	match vm.nav:
		"loop":
			return "Longueur : %d km" % int(vm.loop_km)
		"destination":
			return "Destination : " + ("à choisir (A)" if vm.target == null else "%.3f°, %.3f°" % [vm.target["lat"], vm.target["lon"]])
	return "Cap gardé, petites routes"


## Explication de l'état affiché, sous les lignes (au réglage du cap, aussi celle de la navigation).
func _help_text() -> String:
	var text := str(STATE_HELP.get(vm.state, ""))
	if vm.state == Model.SETUP:
		text = str(NAV_HELP.get(vm.nav, "")) + "\n" + text
	return text


## Aide des boutons en une ligne (tests graphiques, journal).
func hint_text() -> String:
	return ButtonHelp.text(ButtonHelp.WORLD_PREFIX + str(vm.state))


func _draw_canvas() -> void:
	var size := _canvas.size
	match vm.state:
		Model.MAP, Model.SETUP:
			_draw_map(Rect2(size.x * 0.40, 80.0, size.x * 0.56, size.y - 150.0))
		Model.LOADING:
			var bar := Rect2(size.x * 0.2, size.y * 0.5, size.x * 0.6, 22.0)
			_canvas.draw_rect(bar, UiTheme.TRACK_FAINT)
			_canvas.draw_rect(Rect2(bar.position, Vector2(bar.size.x * vm.loading_fraction(), bar.size.y)), ACCENT)
			body_label.position = Vector2(size.x * 0.2, size.y * 0.5 - 48.0)
	if vm.state != Model.LOADING:
		body_label.position = Vector2(40.0, 90.0)
	# Explication sous les lignes, sans déborder sur la carte (qui commence à 40 % de la largeur).
	var help_w := minf(440.0, size.x * 0.40 - 60.0) if vm.state != Model.LOADING else size.x * 0.6
	help_label.custom_minimum_size.x = help_w
	help_label.size.x = help_w
	help_label.position = body_label.position + Vector2(0.0, body_label.get_combined_minimum_size().y + 18.0)


## Carte régionale : routes en mètres depuis le centre (x est, z sud), curseur et flèche du cap.
func _draw_map(area: Rect2) -> void:
	_canvas.draw_rect(area, UiTheme.GLOBE_PANEL)
	var scale_px := minf(area.size.x, area.size.y) * 0.5 / Model.MAP_RADIUS_M
	var centre := area.get_center()
	for road in vm.roads:
		var xz: Array = road.get("xz", [])
		var color: Color = ROAD_COLORS.get(str(road.get("c", "m")), DIM)
		var pts := PackedVector2Array()
		for i in range(0, xz.size() - 1, 2):
			pts.append(centre + Vector2(xz[i], xz[i + 1]) * scale_px)
		if pts.size() >= 2:
			_canvas.draw_polyline(pts, color, 1.5)
	if vm.map_ready:
		var c := centre + vm.cursor * scale_px
		_canvas.draw_circle(c, 7.0, ACCENT)
		if vm.state == Model.SETUP:
			var h := deg_to_rad(vm.heading_deg)
			var d := Vector2(sin(h), -cos(h))
			_canvas.draw_line(c, c + d * 46.0, ACCENT, 3.0)
			var side := Vector2(-d.y, d.x)
			_canvas.draw_colored_polygon(PackedVector2Array([c + d * 56.0, c + d * 40.0 + side * 8.0, c + d * 40.0 - side * 8.0]), ACCENT)
	_canvas.draw_rect(area, DIM, false, 1.0)
