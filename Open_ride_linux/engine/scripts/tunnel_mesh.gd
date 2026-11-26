extends RefCounted

## Tunnels dessinés (lot EA5, série EA, format §8 octies, depuis 1.11) : tube, portails, murs d'approche et lampes.
##
## Entrée : éléments de la couche `tunnels` (osm_layers.gd), coordonnées absolues du repère (monde vivant : déjà
## ramenées du coin du carré) et altitudes affichées (relief exagéré appliqué par l'appelant, comme les ponts).
## Profil en travers (u : écart à l'axe, h : hauteur au-dessus de la chaussée), demi-largeur intérieure
## W = `half_width_m` + SIDEWALK_M :
## - trottoirs de SIDEWALK_H_M de haut entre la chaussée et les piédroits ;
## - piédroits verticaux en u = ± W jusqu'à WALL_H_M, voûte en demi-ellipse de VAULT_RISE_M au-dessus ;
## - coque de SHELL_M d'épaisseur : faces intérieures et extérieures (là où la colline est plus basse que la voûte,
##   le tube sort du sol comme une tranchée couverte), pied enterré de FOOT_M ;
## - tête de portail à chaque bout : mur de PORTAL_DEPTH_M d'épaisseur, PORTAL_SIDE_M au-delà de la coque de chaque
##   côté et PORTAL_ABOVE_M au-dessus, ouverture au profil intérieur ; il cache le bord du trou du terrain ;
## - murs d'approche (APRON_M devant chaque portail, hauteur de WALL_H_M + VAULT_RISE_M au portail à
##   APRON_END_H_M au bout) : la tranchée devant l'entrée ;
## - lampes sur deux rangées sous la naissance de la voûte, tous les LAMP_STEP_M (maillage à part, matériau émissif :
##   pas de vraies lumières, budget GPU).
## `cut` : tronçons du volume où le terrain n'est pas dessiné (tunnel_cut.gd, shader du terrain) : le tube et
## l'approche, bornés au milieu de la coque pour que le bord du trou reste caché dans le béton.
## Calcul pur, dans la tâche de fond d'un tronçon (osm_streamer.gd). Pas de class_name (charger par preload).

const BridgeMesh := preload("res://scripts/bridge_mesh.gd")

const SIDEWALK_M := 1.0
const SIDEWALK_H_M := 0.15
const CURB_DOWN_M := 0.3          # face du trottoir sous la chaussée (talus du ruban caché)
const WALL_H_M := 4.3
const VAULT_RISE_M := 2.0
const VAULT_STEPS := 8
const SHELL_M := 0.6
const FOOT_M := 1.5
const PORTAL_SIDE_M := 3.0
const PORTAL_ABOVE_M := 1.5
const PORTAL_DEPTH_M := 0.8
const APRON_M := 10.0
const APRON_END_H_M := 1.0
const LAMP_STEP_M := 12.0
const LAMP_LEN_M := 1.2
const LAMP_H_M := 0.14
const LAMP_OUT_M := 0.08
const CUT_FLOOR_M := 0.5          # terrain gardé sous la chaussée moins CUT_FLOOR_M (il y est caché)

const INNER_COLOR := Color(0.56, 0.55, 0.52)
const OUTER_COLOR := Color(0.50, 0.49, 0.47)
const PORTAL_COLOR := Color(0.64, 0.63, 0.60)
const SIDEWALK_COLOR := Color(0.47, 0.47, 0.46)
const LAMP_COLOR := Color(1.0, 0.86, 0.58)

## Flottants par tronçon de découpe : a (x, y, z, haut_a), b (x, y, z, haut_b), (demi-largeur, voûte, plancher, 0).
const CUT_FLOATS := 12


static func make_material() -> StandardMaterial3D:
	var mat := BridgeMesh.make_material()
	mat.roughness = 0.95
	return mat


static func make_lamp_material() -> StandardMaterial3D:
	var mat := StandardMaterial3D.new()
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.albedo_color = LAMP_COLOR
	mat.cull_mode = BaseMaterial3D.CULL_BACK
	return mat


static func _new_out() -> Dictionary:
	return {"vertices": PackedVector3Array(), "normals": PackedVector3Array(), "colors": PackedColorArray(),
		"indices": PackedInt32Array()}


## Construit les tunnels. Renvoie {shell: {vertices, normals, colors, indices}, lamps: {…}, cut:
## PackedFloat32Array, built, skipped, lamp_count}.
static func build(items: Array) -> Dictionary:
	var out := {"shell": _new_out(), "lamps": _new_out(), "cut": PackedFloat32Array(), "built": 0, "skipped": 0,
		"lamp_count": 0}
	for item in items:
		if typeof(item) != TYPE_DICTIONARY:
			out["skipped"] = int(out["skipped"]) + 1
			continue
		var pts := BridgeMesh._points(item.get("points", []))
		if pts.size() < 2:
			out["skipped"] = int(out["skipped"]) + 1
			continue
		var hw := float(item.get("half_width_m", 3.0))
		_tunnel(out, pts, hw)
		out["built"] = int(out["built"]) + 1
	return out


## Profil intérieur de gauche à droite : piédroit gauche (du trottoir à la naissance), voûte, piédroit droit.
static func inner_profile(w: float) -> PackedVector2Array:
	var prof := PackedVector2Array([Vector2(-w, SIDEWALK_H_M)])
	for k in range(VAULT_STEPS + 1):
		var a := PI * (1.0 - float(k) / VAULT_STEPS)
		prof.append(Vector2(w * cos(a), WALL_H_M + VAULT_RISE_M * sin(a)))
	prof.append(Vector2(w, SIDEWALK_H_M))
	return prof


## Profil extérieur (coque) : même forme agrandie de SHELL_M, pieds enterrés de FOOT_M.
static func outer_profile(w: float) -> PackedVector2Array:
	var wo := w + SHELL_M
	var prof := PackedVector2Array([Vector2(-wo, -FOOT_M)])
	for k in range(VAULT_STEPS + 1):
		var a := PI * (1.0 - float(k) / VAULT_STEPS)
		prof.append(Vector2(wo * cos(a), WALL_H_M + (VAULT_RISE_M + SHELL_M) * sin(a)))
	prof.append(Vector2(wo, -FOOT_M))
	return prof


static func _at(p: Vector3, r: Vector3, q: Vector2) -> Vector3:
	return p + r * q.x + Vector3.UP * q.y


static func _tunnel(out: Dictionary, pts: PackedVector3Array, hw: float) -> void:
	var shell: Dictionary = out["shell"]
	var rights := BridgeMesh._rights(pts)
	var w := hw + SIDEWALK_M
	var inner := inner_profile(w)
	var outer := outer_profile(w)
	var up := Vector3.UP
	for i in range(pts.size() - 1):
		var p0 := pts[i]
		var p1 := pts[i + 1]
		var r0 := rights[i]
		var r1 := rights[i + 1]
		var pm := (p0 + p1) * 0.5
		var rm := (r0 + r1).normalized()
		# Coque : faces intérieures tournées vers l'axe, extérieures vers le dehors
		for k in range(inner.size() - 1):
			var qa := inner[k]
			var qb := inner[k + 1]
			var mid := (qa + qb) * 0.5
			var c := pm + up * minf(mid.y, WALL_H_M)
			var m := _at(pm, rm, mid)
			BridgeMesh._quad(shell, _at(p0, r0, qa), _at(p0, r0, qb), _at(p1, r1, qb), _at(p1, r1, qa), INNER_COLOR, c - m)
		for k in range(outer.size() - 1):
			var qa := outer[k]
			var qb := outer[k + 1]
			var mid := (qa + qb) * 0.5
			var c := pm + up * clampf(mid.y, 0.0, WALL_H_M)
			var m := _at(pm, rm, mid)
			BridgeMesh._quad(shell, _at(p0, r0, qa), _at(p0, r0, qb), _at(p1, r1, qb), _at(p1, r1, qa), OUTER_COLOR, m - c)
		# Trottoirs : dessus et bordure côté chaussée
		for side in [-1.0, 1.0]:
			var o0: Vector3 = r0 * side
			var o1: Vector3 = r1 * side
			BridgeMesh._quad(shell, p0 + o0 * hw + up * SIDEWALK_H_M, p0 + o0 * w + up * SIDEWALK_H_M,
				p1 + o1 * w + up * SIDEWALK_H_M, p1 + o1 * hw + up * SIDEWALK_H_M, SIDEWALK_COLOR, up)
			BridgeMesh._quad(shell, p0 + o0 * hw - up * CURB_DOWN_M, p1 + o1 * hw - up * CURB_DOWN_M,
				p1 + o1 * hw + up * SIDEWALK_H_M, p0 + o0 * hw + up * SIDEWALK_H_M, SIDEWALK_COLOR, -rm * side)
		_cut_segment(out["cut"], p0, p1, w, WALL_H_M, WALL_H_M, VAULT_RISE_M + SHELL_M * 0.5)
	_lamps(out, pts, rights, w)
	var n := pts.size()
	for end in [0, n - 1]:
		var p := pts[end]
		var r := rights[end]
		var nb := pts[1] if end == 0 else pts[n - 2]
		var away := Vector3(p.x - nb.x, 0.0, p.z - nb.z).normalized()
		var slope := (p.y - nb.y) / maxf(Vector2(p.x - nb.x, p.z - nb.z).length(), 1e-6)
		_portal(shell, p, r, away, w, inner)
		_apron(out, p + away * PORTAL_DEPTH_M + up * slope * PORTAL_DEPTH_M, r, away, slope, w)


## Tête de portail : face avant (vers le dehors) et arrière, tranches, ouverture au profil intérieur.
static func _portal(shell: Dictionary, p: Vector3, r: Vector3, away: Vector3, w: float, inner: PackedVector2Array) -> void:
	var up := Vector3.UP
	var pw := w + SHELL_M + PORTAL_SIDE_M
	var top := WALL_H_M + VAULT_RISE_M + SHELL_M + PORTAL_ABOVE_M
	var front := p + away * PORTAL_DEPTH_M
	for face in [[front, away], [p, -away]]:
		var o: Vector3 = face[0]
		var nrm: Vector3 = face[1]
		for side in [-1.0, 1.0]:
			BridgeMesh._quad(shell, _at(o, r, Vector2(side * w, -FOOT_M)), _at(o, r, Vector2(side * pw, -FOOT_M)),
				_at(o, r, Vector2(side * pw, top)), _at(o, r, Vector2(side * w, top)), PORTAL_COLOR, nrm)
		for k in range(1, inner.size() - 2):   # voûte : de la naissance gauche à la naissance droite
			var qa := inner[k]
			var qb := inner[k + 1]
			BridgeMesh._quad(shell, _at(o, r, qa), _at(o, r, qb), _at(o, r, Vector2(qb.x, top)),
				_at(o, r, Vector2(qa.x, top)), PORTAL_COLOR, nrm)
	# Dessus et côtés de la tête
	BridgeMesh._quad(shell, _at(p, r, Vector2(-pw, top)), _at(p, r, Vector2(pw, top)), _at(front, r, Vector2(pw, top)),
		_at(front, r, Vector2(-pw, top)), PORTAL_COLOR, up)
	for side in [-1.0, 1.0]:
		BridgeMesh._quad(shell, _at(p, r, Vector2(side * pw, -FOOT_M)), _at(front, r, Vector2(side * pw, -FOOT_M)),
			_at(front, r, Vector2(side * pw, top)), _at(p, r, Vector2(side * pw, top)), PORTAL_COLOR, r * side)
	# Tableau de l'ouverture (épaisseur de la tête), tourné vers l'axe
	for k in range(inner.size() - 1):
		var qa := inner[k]
		var qb := inner[k + 1]
		var mid := (qa + qb) * 0.5
		var c := p + up * minf(mid.y, WALL_H_M)
		var m := _at(p, r, mid)
		BridgeMesh._quad(shell, _at(p, r, qa), _at(front, r, qa), _at(front, r, qb), _at(p, r, qb), PORTAL_COLOR, c - m)


## Murs d'approche devant un portail, de `o` (face avant de la tête) sur APRON_M dans la direction `away`, la
## chaussée prolongée à la pente `slope` ; hauteur de la naissance de la voûte… au sommet de la voûte au portail,
## APRON_END_H_M au bout. Ajoute le tronçon de découpe de l'approche.
static func _apron(out: Dictionary, o: Vector3, r: Vector3, away: Vector3, slope: float, w: float) -> void:
	var shell: Dictionary = out["shell"]
	var up := Vector3.UP
	var e := o + away * APRON_M + up * slope * APRON_M
	var h0 := WALL_H_M + VAULT_RISE_M
	var h1 := APRON_END_H_M
	for side in [-1.0, 1.0]:
		var ui: float = side * w
		var uo: float = side * (w + SHELL_M)
		var inward: Vector3 = -r * side
		BridgeMesh._quad(shell, _at(o, r, Vector2(ui, SIDEWALK_H_M)), _at(e, r, Vector2(ui, SIDEWALK_H_M)),
			_at(e, r, Vector2(ui, h1)), _at(o, r, Vector2(ui, h0)), INNER_COLOR, inward)
		BridgeMesh._quad(shell, _at(o, r, Vector2(uo, -FOOT_M)), _at(e, r, Vector2(uo, -FOOT_M)),
			_at(e, r, Vector2(uo, h1)), _at(o, r, Vector2(uo, h0)), OUTER_COLOR, -inward)
		BridgeMesh._quad(shell, _at(o, r, Vector2(ui, h0)), _at(e, r, Vector2(ui, h1)), _at(e, r, Vector2(uo, h1)),
			_at(o, r, Vector2(uo, h0)), PORTAL_COLOR, (up + away * ((h0 - h1) / APRON_M)).normalized())
		BridgeMesh._quad(shell, _at(e, r, Vector2(ui, -FOOT_M)), _at(e, r, Vector2(uo, -FOOT_M)),
			_at(e, r, Vector2(uo, h1)), _at(e, r, Vector2(ui, h1)), PORTAL_COLOR, away)
		# Trottoir de l'approche
		var hw := w - SIDEWALK_M
		BridgeMesh._quad(shell, _at(o, r, Vector2(side * hw, SIDEWALK_H_M)), _at(e, r, Vector2(side * hw, SIDEWALK_H_M)),
			_at(e, r, Vector2(ui, SIDEWALK_H_M)), _at(o, r, Vector2(ui, SIDEWALK_H_M)), SIDEWALK_COLOR, up)
		BridgeMesh._quad(shell, _at(o, r, Vector2(side * hw, -CURB_DOWN_M)), _at(e, r, Vector2(side * hw, -CURB_DOWN_M)),
			_at(e, r, Vector2(side * hw, SIDEWALK_H_M)), _at(o, r, Vector2(side * hw, SIDEWALK_H_M)), SIDEWALK_COLOR, inward)
	# Découpe : de l'arrière de la tête (o − profondeur) au bout de l'approche, sans voûte
	_cut_segment(out["cut"], o - away * PORTAL_DEPTH_M, e, w, h0, h1, 0.0)


## Lampes : deux rangées sous la naissance de la voûte, tous les LAMP_STEP_M de l'abscisse (premier à mi-pas).
static func _lamps(out: Dictionary, pts: PackedVector3Array, rights: PackedVector3Array, w: float) -> void:
	var lamps: Dictionary = out["lamps"]
	var up := Vector3.UP
	var next := LAMP_STEP_M * 0.5
	var acc := 0.0
	var y := WALL_H_M - 0.25
	for i in range(pts.size() - 1):
		var a := pts[i]
		var b := pts[i + 1]
		var seg := Vector2(b.x - a.x, b.z - a.z).length()
		if seg < 1e-6:
			continue
		var fwd := (b - a) / seg
		while next <= acc + seg:
			var t := (next - acc) / seg
			var c := a.lerp(b, t)
			var r := rights[i].lerp(rights[i + 1], t).normalized()
			for side in [-1.0, 1.0]:
				var inward: Vector3 = -r * side
				var face: Vector3 = c + r * side * (w - LAMP_OUT_M) + up * y
				var h := fwd * (LAMP_LEN_M * 0.5)
				BridgeMesh._quad(lamps, face - h, face + h, face + h + up * LAMP_H_M, face - h + up * LAMP_H_M, LAMP_COLOR, inward)
				BridgeMesh._quad(lamps, face - h, face + h, face + h - inward * LAMP_OUT_M, face - h - inward * LAMP_OUT_M, LAMP_COLOR, -up)
			out["lamp_count"] = int(out["lamp_count"]) + 2
			next += LAMP_STEP_M
		acc += seg


## Tronçon de découpe du terrain : de a à b (chaussée), demi-largeur au milieu de la coque, haut des piédroits
## top_a → top_b, voûte `rise` en demi-ellipse au-dessus, plancher CUT_FLOOR_M sous la chaussée.
static func _cut_segment(cut: PackedFloat32Array, a: Vector3, b: Vector3, w: float, top_a: float, top_b: float, rise: float) -> void:
	cut.append_array(PackedFloat32Array([a.x, a.y, a.z, top_a, b.x, b.y, b.z, top_b, w + SHELL_M * 0.5, rise,
		CUT_FLOOR_M, 0.0]))


## Le point p est-il dans le volume de découpe ? Même calcul que tunnel_cut.gdshaderinc (tests).
static func cut_contains(cut: PackedFloat32Array, p: Vector3) -> bool:
	for s in range(0, cut.size(), CUT_FLOATS):
		var ax := cut[s]
		var az := cut[s + 2]
		var abx := cut[s + 4] - ax
		var abz := cut[s + 6] - az
		var l2 := maxf(abx * abx + abz * abz, 1e-6)
		var apx := p.x - ax
		var apz := p.z - az
		var t := (apx * abx + apz * abz) / l2
		if t < -0.01 or t > 1.01:
			continue
		var u := absf(apx * abz - apz * abx) / sqrt(l2)
		var wc := cut[s + 8]
		if u > wc:
			continue
		var tc := clampf(t, 0.0, 1.0)
		var h := p.y - lerpf(cut[s + 1], cut[s + 5], tc)
		var top := lerpf(cut[s + 3], cut[s + 7], tc) + cut[s + 9] * sqrt(maxf(0.0, 1.0 - (u / wc) * (u / wc)))
		if h > -cut[s + 10] and h < top:
			return true
	return false
