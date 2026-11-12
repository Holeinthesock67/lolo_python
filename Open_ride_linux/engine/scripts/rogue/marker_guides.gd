extends RefCounted

## Repères lisibles des objets de salle du Cyber-Rogue (lot R22, maquettes validées le 12 novembre) :
## - une étiquette flottante au-dessus de chaque objet (« Z ! », « 90 rpm », « ▲ + »…), montrée à l'approche ;
## - au sol, la zone où Z est accepté (cible, balise de purge, rocher) : bande dont la longueur suit la vitesse du
##   joueur, exactement la fenêtre du core (± largeur / 2 × vitesse, au moins ± 3 m, combat.py `_window`) ;
## - l'arche de Perfect Shift en vrai portique au-dessus du ruban, avec le signe géant (+ ou −) et un anneau
##   d'approche qui se resserre jusqu'à toucher l'arche au bon instant.
## Primitives Godot et matériaux de la charte R17. Pas de class_name : preload("res://scripts/rogue/marker_guides.gd").

const Materials := preload("res://scripts/rogue/neon_materials.gd")
const Palette := preload("res://scripts/rogue/neon_palette.gd")
const GuideModel := preload("res://scripts/rogue/rogue_guide_model.gd")
const RibbonBuilder := preload("res://scripts/rogue/ribbon_builder.gd")

## Fenêtres du core (balance.toml) : cible et balise ± 0,5 s, rocher ± 0,75 s ; plancher ± 3 m.
const WINDOW_S := {"strike_target": 1.0, "purge": 1.0, "rock": 1.5}
const WINDOW_MIN_HALF_M := 3.0
const TAG_SHOW_M := 150.0          # étiquette montrée à moins de 150 m devant
const TAG_TOKENS := {"strike_target": "danger", "purge": "glitch", "rock": "gold", "parry_zone": "parry",
	"tunnel": "energy", "pad": "gold", "arch": "player"}
const ARCH_W := RibbonBuilder.WIDTH_M + 1.2
const ARCH_H := 4.4
const APPROACH_S := 3.0            # l'anneau d'approche paraît 3 s avant l'arche
const APPROACH_GROW := 2.2         # rayon de l'anneau à 3 s, en multiples du rayon final


static func half_window_m(kind: String, v_mps: float) -> float:
	return maxf(0.5 * float(WINDOW_S.get(kind, 1.0)) * maxf(v_mps, 0.0), WINDOW_MIN_HALF_M)


## Ajoute les repères lisibles au nœud d'un objet (centré sur l'objet). Renvoie {tag, zone, ring} (nœuds ou null).
static func decorate(node: Node3D, kind: String, param: Variant, len_m: float, preset: String, adapted: bool) -> Dictionary:
	var out := {"tag": null, "zone": null, "ring": null}
	var token: String = TAG_TOKENS.get(kind, "neutral")
	var text := GuideModel.marker_tag(kind, param)
	if kind == "arch":
		token = "player" if str(param) == "up" else "glitch"
		var body := node.get_node_or_null("Body")
		if body != null:
			body.visible = false
		node.add_child(_gate(token, preset, adapted))
		var sign := Label3D.new()
		sign.name = "Sign"
		sign.text = "+" if str(param) == "up" else "−"
		sign.font_size = 160
		sign.pixel_size = 0.012
		sign.outline_size = 18
		sign.modulate = Palette.color(token, adapted)
		sign.outline_modulate = Palette.color("void", false)
		sign.position = Vector3(0.0, ARCH_H * 0.62, 0.0)
		node.add_child(sign)
		var ring := MeshInstance3D.new()
		ring.name = "ApproachRing"
		var t := TorusMesh.new()
		t.inner_radius = 1.25
		t.outer_radius = 1.4
		t.rings = 24
		t.ring_segments = 6
		ring.mesh = t
		ring.rotation.x = PI * 0.5
		ring.position = sign.position
		ring.material_override = Materials.edge(token, 2.0, preset, adapted)
		ring.visible = false
		node.add_child(ring)
		out["ring"] = ring
	if text != "":
		var tag := Label3D.new()
		tag.name = "Tag"
		tag.text = text
		tag.font_size = 72
		tag.pixel_size = 0.014
		tag.billboard = BaseMaterial3D.BILLBOARD_ENABLED
		tag.no_depth_test = true
		tag.outline_size = 14
		tag.modulate = Palette.color(token, adapted)
		tag.outline_modulate = Palette.color("void", false)
		tag.position = Vector3(0.0, ARCH_H + 0.8 if kind == "arch" else 3.2, 0.0)
		tag.visible = false
		node.add_child(tag)
		out["tag"] = tag
	if WINDOW_S.has(kind):
		var zone := MeshInstance3D.new()
		zone.name = "ZZone"
		var ring_mesh := TorusMesh.new()      # anneau à plat, étiré en bande le long de la route
		ring_mesh.inner_radius = 0.86
		ring_mesh.outer_radius = 1.0
		ring_mesh.rings = 32
		ring_mesh.ring_segments = 4
		zone.mesh = ring_mesh
		zone.position = Vector3(0.0, 0.08, 0.0)         # le nœud est au milieu de l'objet : la fenêtre aussi
		zone.material_override = Materials.edge(token, 2.0, preset, adapted)
		zone.scale = Vector3(RibbonBuilder.WIDTH_M * 0.5, 0.05, WINDOW_MIN_HALF_M)
		node.add_child(zone)
		out["zone"] = zone
	return out


static func _gate(token: String, preset: String, adapted: bool) -> Node3D:
	var gate := Node3D.new()
	gate.name = "Gate"
	var mat := Materials.edge(token, 2.0, preset, adapted)
	for x in [-ARCH_W * 0.5, ARCH_W * 0.5]:
		var post := MeshInstance3D.new()
		var b := BoxMesh.new()
		b.size = Vector3(0.25, ARCH_H, 0.25)
		post.mesh = b
		post.position = Vector3(x, ARCH_H * 0.5, 0.0)
		post.material_override = mat
		gate.add_child(post)
	var beam := MeshInstance3D.new()
	var bb := BoxMesh.new()
	bb.size = Vector3(ARCH_W + 0.25, 0.25, 0.25)
	beam.mesh = bb
	beam.position = Vector3(0.0, ARCH_H, 0.0)
	beam.material_override = mat
	gate.add_child(beam)
	return gate


## Met à jour les repères d'un objet : `d_m` distance de l'objet devant le joueur (négative derrière),
## `v_mps` vitesse du joueur, `inside` roue dans la zone.
static func update(parts: Dictionary, kind: String, s_m: float, len_m: float, s_player: float, v_mps: float) -> void:
	var d := s_m - s_player
	var tag = parts.get("tag", null)
	if tag != null:
		(tag as Label3D).visible = d > -len_m - 5.0 and d < TAG_SHOW_M
	var zone = parts.get("zone", null)
	if zone != null:
		var half := half_window_m(kind, v_mps)
		var z := zone as MeshInstance3D
		z.scale = Vector3(RibbonBuilder.WIDTH_M * 0.5, 0.05, half + len_m * 0.5)
		var inside := s_player >= s_m - half and s_player <= s_m + len_m + half
		z.transparency = 0.0 if inside else 0.35
	var ring = parts.get("ring", null)
	if ring != null:
		var t := d / maxf(v_mps, 0.5)
		var r := ring as MeshInstance3D
		r.visible = t > 0.0 and t < APPROACH_S
		if r.visible:
			r.scale = Vector3.ONE * (1.0 + (APPROACH_GROW - 1.0) * t / APPROACH_S)
