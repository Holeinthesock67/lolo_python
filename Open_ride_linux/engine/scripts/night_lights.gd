extends RefCounted

## Lumières de nuit (lot P35, demande du 13 novembre) : à quel point la scène est éclairée de lumières
## artificielles, d'après le jour et la nuit de P19 ; sans nœud. Pas de class_name : charger par
## preload("res://scripts/night_lights.gd").
##
## - `level(daylight)` : 0 de jour ou quand le jour et la nuit est coupé (`daylight.active` faux : image
##   d'aujourd'hui), 1 la nuit ; montée douce entre ON_DEG (le soleil se couche, on allume) et FULL_DEG.
## - `apply(level, on)` : globaux des shaders `night_glow` (fenêtres éclairées de building.gdshader, verre des
##   lampes de night_lamp.gdshader) et `night_lamps` (1 quand le jour et la nuit est actif : lampes, luminaires
##   et phares dessinés ; 0 : rien de neuf à l'écran, même de jour), et `current` / `enabled`, lus par
##   l'éclairage du vélo (bike_lights.gd), les lampes des avatars (avatar_view.gd) et les luminaires publics
##   (street_lights.gd). Une seule règle : les lampes existent dès que le jour et la nuit est actif, elles
##   s'allument au coucher du soleil.
## - `lamp_material()` : matériau partagé des lampes (night_lamp.gdshader) ; la couleur de sommet donne la
##   couleur de la lampe, son alpha la part allumée (0 : boîtier, 1 : verre).

const ON_DEG := 4.0       # soleil encore au-dessus de l'horizon : premières lumières
const FULL_DEG := -5.0    # crépuscule civil presque fini : tout est allumé
const LampShader := preload("res://shaders/night_lamp.gdshader")

static var current := 0.0
static var enabled := false
static var _lamp_mat: ShaderMaterial = null


static func level(daylight: Dictionary) -> float:
	if not bool(daylight.get("active", false)):
		return 0.0
	var el := float(daylight.get("sun_elevation_deg", 90.0))
	return smoothstep(ON_DEG, FULL_DEG, el)


static func apply(value: float, on: bool) -> void:
	enabled = on
	current = clampf(value, 0.0, 1.0) if on else 0.0
	RenderingServer.global_shader_parameter_set("night_glow", current)
	RenderingServer.global_shader_parameter_set("night_lamps", 1.0 if on else 0.0)


static func lamp_material() -> ShaderMaterial:
	if _lamp_mat == null:
		_lamp_mat = ShaderMaterial.new()
		_lamp_mat.shader = LampShader
	return _lamp_mat


## Boîte de `size` centrée en `c` dans `st`, couleur `color` ; `glass_face` : face qui s'allume, −1 avant (−z),
## 1 arrière (+z), 2 dessous, 9 toutes ; 0 : boîtier sombre seulement.
static func box(st: SurfaceTool, c: Vector3, size: Vector3, color: Color, glass_face: int = 0) -> void:
	var h := size * 0.5
	var faces := [
		[Vector3(0, 0, -1), Vector3(1, 0, 0), Vector3(0, 1, 0), -1],
		[Vector3(0, 0, 1), Vector3(-1, 0, 0), Vector3(0, 1, 0), 1],
		[Vector3(1, 0, 0), Vector3(0, 0, 1), Vector3(0, 1, 0), 0],
		[Vector3(-1, 0, 0), Vector3(0, 0, -1), Vector3(0, 1, 0), 0],
		[Vector3(0, 1, 0), Vector3(1, 0, 0), Vector3(0, 0, 1), 0],
		[Vector3(0, -1, 0), Vector3(1, 0, 0), Vector3(0, 0, -1), 2],
	]
	for f in faces:
		var n: Vector3 = f[0]
		var u: Vector3 = f[1]
		var v: Vector3 = f[2]
		var col := color
		col.a = 1.0 if glass_face == 9 or (glass_face != 0 and int(f[3]) == glass_face) else 0.0
		if col.a == 0.0:
			col = Color(0.08, 0.08, 0.09, 0.0)
		var o := c + n * h
		var du := u * h
		var dv := v * h
		var quad := [o - du - dv, o + du - dv, o + du + dv, o - du + dv]
		for i in [0, 2, 1, 0, 3, 2]:
			st.set_normal(n)
			st.set_color(col)
			st.add_vertex(quad[i])


const BIKE_FRONT_LAMP := Vector3(0.0, 0.83, -0.56)   # sous le cintre, devant la potence (avatar_mesh.gd)
const BIKE_REAR_LAMP := Vector3(0.0, 0.82, 0.19)     # sur la tige de selle
const FRONT_COLOR := Color(1.0, 0.97, 0.88)
const REAR_COLOR := Color(1.0, 0.08, 0.05)
const WARM_COLOR := Color(1.0, 0.74, 0.42)          # lanternes, luminaires à lampe chaude
static var _bike_mesh: ArrayMesh = null


## Phare blanc et feu arrière rouge d'un vélo, en un seul maillage (un appel de dessin).
static func bike_lamps_mesh() -> ArrayMesh:
	if _bike_mesh == null:
		var st := SurfaceTool.new()
		st.begin(Mesh.PRIMITIVE_TRIANGLES)
		box(st, BIKE_FRONT_LAMP, Vector3(0.05, 0.035, 0.05), FRONT_COLOR, -1)
		box(st, BIKE_REAR_LAMP, Vector3(0.035, 0.05, 0.025), REAR_COLOR, 1)
		_bike_mesh = st.commit()
	return _bike_mesh
