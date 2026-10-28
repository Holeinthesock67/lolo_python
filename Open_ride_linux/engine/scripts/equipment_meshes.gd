extends RefCounted

## Pièces d'équipement de l'avatar (lot V7), toutes générées par le code : une forme par `look` du
## catalogue du core (`data/progression.toml`, lot V3), cadres, roues, casques, tenues (motifs), chaussettes
## et lunettes. Sans nœud : des spécifications (couleurs, dimensions, posture) et des maillages que
## avatar_view.gd assemble.
##
## - `LOOKS` liste les `look` connus par emplacement ; un test du core vérifie que chaque `look` du catalogue
##   y figure. Un `look` inconnu (ou absent) retombe sur la pièce par défaut de l'emplacement (`resolve`).
## - `equip_looks(equipped, look_of_id)` : identifiants choisis (hello_ack) + `look` de chaque pièce
##   (message `garage`) → `look` résolu par emplacement.
## - Posture : `frame_spec(look)` donne l'inclinaison du buste en plus, l'écartement et l'avance des mains
##   (cadres aéro et contre-la-montre : buste plus bas, bras rapprochés ; prolongateurs).
## - Sons des roues : `wheel_sound(look)` (utilisé par sound_model.gd) ; traînées d'air : AIR_STREAK_KMH.
## Pas de class_name : charger par preload("res://scripts/equipment_meshes.gd").

const LOOKS := {
	"frame": ["frame_round", "frame_light", "frame_aero", "frame_round_light", "frame_tt"],
	"wheels": ["wheels_spoked", "wheels_spoked_light", "wheels_deep", "wheels_disc"],
	"helmet": ["helmet_road", "helmet_aero", "helmet_summit"],
	"kit": ["kit_plain", "kit_stripes", "kit_club", "kit_milestones", "kit_polka", "kit_neon"],
	"socks": ["socks_white", "socks_striped", "socks_tall", "socks_long_distance"],
	"glasses": ["glasses_clear", "glasses_mirror", "glasses_metronome"],
}
const DEFAULT_LOOK := {
	"frame": "frame_round", "wheels": "wheels_spoked", "helmet": "helmet_road",
	"kit": "kit_plain", "socks": "socks_white", "glasses": "glasses_clear",
}
const AIR_STREAK_KMH := 45.0
const WHEEL_R := 0.34
const TEX_SIZE := 32

static var _textures := {}


static func resolve(slot: String, look) -> String:
	if look is String and look in LOOKS.get(slot, []):
		return look
	return str(DEFAULT_LOOK.get(slot, ""))


## `equipped` : {emplacement: identifiant} ; `look_of_id` : {identifiant: look}. Un identifiant inconnu
## ou un emplacement absent donne la pièce par défaut.
static func equip_looks(equipped, look_of_id) -> Dictionary:
	var out := {}
	for slot in LOOKS:
		var id = equipped.get(slot) if equipped is Dictionary else null
		var look = look_of_id.get(id) if (look_of_id is Dictionary and id != null) else null
		out[slot] = resolve(slot, look)
	return out


static func frame_spec(look: String) -> Dictionary:
	var base := {"tube": Vector2(0.032, 0.032), "color": Color(0.16, 0.17, 0.20), "lean_add": 0.0,
		"bar_half_x": 0.19, "bar_z": -0.45, "extensions": false}
	match resolve("frame", look):
		"frame_light":
			base.merge({"tube": Vector2(0.026, 0.026), "color": Color(0.88, 0.89, 0.92)}, true)
		"frame_round_light":
			base.merge({"tube": Vector2(0.028, 0.028), "color": Color(0.20, 0.34, 0.55)}, true)
		"frame_aero":
			base.merge({"tube": Vector2(0.034, 0.078), "color": Color(0.06, 0.06, 0.08), "lean_add": 0.12,
				"bar_half_x": 0.15}, true)
		"frame_tt":
			base.merge({"tube": Vector2(0.038, 0.090), "color": Color(0.62, 0.10, 0.10), "lean_add": 0.22,
				"bar_half_x": 0.10, "bar_z": -0.60, "extensions": true}, true)
	return base


## Roue : `kind` spoked (rayons), deep (jante haute) ou disc (disque plein).
static func wheel_spec(look: String) -> Dictionary:
	match resolve("wheels", look):
		"wheels_spoked_light":
			return {"kind": "spoked", "rim": 0.014, "color": Color(0.80, 0.82, 0.86), "spokes": 10}
		"wheels_deep":
			return {"kind": "deep", "rim": 0.045, "color": Color(0.07, 0.07, 0.09), "spokes": 0}
		"wheels_disc":
			return {"kind": "disc", "rim": 0.0, "color": Color(0.05, 0.05, 0.06), "spokes": 0}
	return {"kind": "spoked", "rim": 0.014, "color": Color(0.40, 0.42, 0.46), "spokes": 10}


## Son de la roue (sound_model.gd) : `hum` grave (lenticulaire), `whistle` léger (jantes hautes), `none`.
static func wheel_sound(look: String) -> String:
	match resolve("wheels", look):
		"wheels_disc":
			return "hum"
		"wheels_deep":
			return "whistle"
	return "none"


static func helmet_spec(look: String) -> Dictionary:
	match resolve("helmet", look):
		"helmet_aero":
			return {"scale": Vector3(1.0, 0.95, 1.55), "shift": Vector3(0.0, 0.0, 0.05), "visor": false, "color_kit": false}
		"helmet_summit":
			return {"scale": Vector3(1.0, 1.0, 1.05), "shift": Vector3.ZERO, "visor": true, "color_kit": true}
	return {"scale": Vector3.ONE, "shift": Vector3.ZERO, "visor": false, "color_kit": true}


## `length` : part de la jambe couverte (du pied vers le genou).
static func socks_spec(look: String) -> Dictionary:
	match resolve("socks", look):
		"socks_striped":
			return {"length": 0.38, "striped": true, "color": Color(0.95, 0.95, 0.95)}
		"socks_tall":
			return {"length": 0.62, "striped": false, "color": Color(0.95, 0.95, 0.95)}
		"socks_long_distance":
			return {"length": 0.80, "striped": false, "color": Color(0.30, 0.32, 0.36)}
	return {"length": 0.36, "striped": false, "color": Color(0.95, 0.95, 0.95)}


static func glasses_spec(look: String) -> Dictionary:
	match resolve("glasses", look):
		"glasses_mirror":
			return {"color": Color(0.75, 0.78, 0.85, 0.95), "metallic": 0.9}
		"glasses_metronome":
			return {"color": Color(0.95, 0.60, 0.10, 0.65), "metallic": 0.0}
	return {"color": Color(0.85, 0.92, 1.0, 0.32), "metallic": 0.0}


## Motif de la tenue (texture de TEX_SIZE × TEX_SIZE, répétée) ; `v` de haut en bas du tronc.
static func kit_texture(look: String, primary: Color, secondary: Color) -> ImageTexture:
	look = resolve("kit", look)
	var key := "%s|%s|%s" % [look, primary.to_html(), secondary.to_html()]
	if _textures.has(key):
		return _textures[key]
	var img := Image.create(TEX_SIZE, TEX_SIZE, false, Image.FORMAT_RGB8)
	img.fill(primary)
	match look:
		"kit_stripes":
			_rows(img, 10, 14, secondary)
			_rows(img, 20, 22, secondary)
		"kit_club":
			_rows(img, 4, 14, secondary)
			_rows(img, 16, 17, secondary)
		"kit_milestones":
			for x in range(0, TEX_SIZE, 8):
				for y in range(12, 18):
					for dx in range(4):
						img.set_pixel(x + dx, y, secondary)
		"kit_polka":
			for c in [Vector2(8, 8), Vector2(24, 8), Vector2(16, 16), Vector2(8, 24), Vector2(24, 24)]:
				for y in range(TEX_SIZE):
					for x in range(TEX_SIZE):
						if Vector2(x, y).distance_to(c) <= 3.2:
							img.set_pixel(x, y, secondary)
	var tex := ImageTexture.create_from_image(img)
	_textures[key] = tex
	return tex


static func _rows(img: Image, y0: int, y1: int, color: Color) -> void:
	for y in range(y0, y1):
		for x in range(TEX_SIZE):
			img.set_pixel(x, y, color)


static func is_emissive_kit(look: String) -> bool:
	return resolve("kit", look) == "kit_neon"


static func _box(size: Vector3) -> BoxMesh:
	var m := BoxMesh.new()
	m.size = size
	return m


static func _torus(radius: float, tube: float, rings: int, segs: int) -> TorusMesh:
	var m := TorusMesh.new()
	m.inner_radius = radius - tube
	m.outer_radius = radius + tube
	m.rings = rings
	m.ring_segments = segs
	return m


static func _cylinder(radius: float, height: float, radial: int) -> CylinderMesh:
	var m := CylinderMesh.new()
	m.top_radius = radius
	m.bottom_radius = radius
	m.height = height
	m.radial_segments = radial
	m.rings = 1
	return m


static func _capsule(radius: float, length: float, radial: int, rings: int) -> CapsuleMesh:
	var m := CapsuleMesh.new()
	m.radius = radius
	m.height = length + radius
	m.radial_segments = radial
	m.rings = rings
	return m


## Maillages des pièces d'un équipement pour un niveau de détail 0 ou 1 : {nom : {"mesh", "count"}}.
## `looks` : sortie de equip_looks ; `d` : dimensions de avatar_mesh.dims().
static func build(lod: int, looks: Dictionary, d: Dictionary) -> Dictionary:
	var parts := {}
	var fs := frame_spec(str(looks.get("frame", "")))
	var tube: Vector2 = fs["tube"]
	parts["frame"] = {"mesh": _box(Vector3(tube.x, 1.0, tube.y)), "count": 3}
	if fs["extensions"]:
		parts["extension"] = {"mesh": _box(Vector3(0.035, 0.34, 0.035)), "count": 2}
		parts["pad"] = {"mesh": _box(Vector3(0.07, 0.03, 0.12)), "count": 2}
	var ws := wheel_spec(str(looks.get("wheels", "")))
	var fine := lod == 0
	parts["tyre"] = {"mesh": _torus(WHEEL_R - 0.015, 0.015, 24 if fine else 8, 6 if fine else 3), "count": 2}
	match ws["kind"]:
		"spoked":
			parts["rim"] = {"mesh": _torus(WHEEL_R - 0.034, float(ws["rim"]), 24 if fine else 8, 4 if fine else 3), "count": 2}
			if fine:   # niveau intermédiaire : jante seule, sans rayons
				parts["spoke"] = {"mesh": _box(Vector3(0.006, WHEEL_R - 0.05, 0.006)), "count": int(ws["spokes"]) * 2}
		"deep":
			parts["rim"] = {"mesh": _torus(WHEEL_R - 0.04, float(ws["rim"]), 24 if fine else 8, 6 if fine else 3), "count": 2}
		"disc":
			parts["rim"] = {"mesh": _cylinder(WHEEL_R - 0.03, 0.028, 32 if fine else 16), "count": 2}
	var hs := helmet_spec(str(looks.get("helmet", "")))
	parts["helmet"] = {"mesh": _sphere(float(d["r_head"]) * 1.12, 20 if fine else 10, 8 if fine else 4, 0.8), "count": 1}
	if hs["visor"]:
		parts["visor"] = {"mesh": _box(Vector3(0.17, 0.01, 0.11)), "count": 1}
	var ss := socks_spec(str(looks.get("socks", "")))
	parts["sock"] = {"mesh": _capsule(float(d["r_shin"]) * 1.12, float(d["shin"]) * float(ss["length"]), 10 if fine else 6, 2 if fine else 1), "count": 2}
	parts["glasses"] = {"mesh": _box(Vector3(float(d["r_head"]) * 1.7, 0.034, 0.02)), "count": 1}
	return parts


static func _sphere(radius: float, radial: int, rings: int, squash := 1.0) -> SphereMesh:
	var m := SphereMesh.new()
	m.radius = radius
	m.height = 2.0 * radius * squash
	m.radial_segments = radial
	m.rings = rings
	return m
