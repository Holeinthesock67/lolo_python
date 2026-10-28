extends RefCounted

## Tri de ce que la caméra peut voir (lot S1), sans nœud ni affichage : le monde est vu de dessus
## (plan x, z) et chaque vue est un secteur (« cône ») de sommet la caméra, d'axe son regard et de
## demi-angle le champ horizontal plus VIEW_MARGIN_DEG.
##
## Une vue est un dictionnaire {pos: Vector2, fwd: Vector2 (unitaire), half: float (rad)}.
## - `view_of(caméra)` : vue de la caméra active (subjective ou autre vue de V12, jamais le cycliste seul).
## - `route_views(caméra, route, s, v)` : vue active plus les vues que la même caméra aura le long de la
##   route dans les LOOKAHEAD_M (au moins) prochains mètres, même écart de cap à la route : une tuile qui
##   entrera dans le champ (virage serré, épingle) est demandée avant d'être visible.
## - `rect_in_view(rect, vue, extra)` : faux seulement si le rectangle est entièrement hors du secteur
##   (test prudent : dans le doute, la tuile est gardée).
## - `rect_wanted(rect, vues, rayon_vue, rayon_gardé, extra)` : tuile à moins de `rayon_gardé` de la
##   caméra (ombres portées, demi-tour de la caméra), ou à moins de `rayon_vue` d'une vue et dans son
##   secteur. `extra` (rad) élargit les secteurs : marge de maintien des tuiles déjà chargées, pour
##   qu'une tuile au bord du champ ne soit pas libérée puis reconstruite au moindre balancement.
## Pas de class_name : charger par preload("res://scripts/view_culling.gd").

## Marge ajoutée au demi-champ horizontal : tangage de Q2, balancement de la caméra, bord des arbres.
const VIEW_MARGIN_DEG := 15.0
## Marge supplémentaire pour garder une tuile déjà chargée (hystérésis).
const KEEP_MARGIN_DEG := 10.0
## Le secteur reste convexe (et le test du demi-plan arrière juste) sous 90°.
const MAX_HALF_DEG := 85.0
## Distance de route parcourue par les vues futures : au moins LOOKAHEAD_MIN_M, sinon v × LOOKAHEAD_S.
const LOOKAHEAD_S := 10.0
const LOOKAHEAD_MIN_M := 400.0
const LOOKAHEAD_STEP_M := 100.0
const LOOKAHEAD_MAX_VIEWS := 8
## Rayon gardé autour de la caméra quelle que soit la direction : distance des ombres du préréglage plus
## une case d'arbres (250 m), pour que les ombres des arbres et du relief juste derrière restent justes.
const KEEP_EXTRA_M := 250.0
## Écart maximal entre la caméra active et la position donnée au streamer : au-delà, la caméra n'est pas
## encore placée (chargement d'un parcours) et rien n'est écarté.
const CAMERA_MATCH_M := 50.0


static func keep_radius_for(shadow_distance_m: float) -> float:
	return shadow_distance_m + KEEP_EXTRA_M


## Demi-angle horizontal (rad) d'une caméra de champ vertical `fov_deg` (keep_height, défaut de Godot)
## pour un rapport largeur / hauteur `aspect`, marge comprise.
static func half_angle_rad(fov_deg: float, aspect: float) -> float:
	var h := atan(tan(deg_to_rad(fov_deg) * 0.5) * maxf(aspect, 0.1))
	return minf(h + deg_to_rad(VIEW_MARGIN_DEG), deg_to_rad(MAX_HALF_DEG))


static func view_at(pos: Vector2, fwd: Vector2, half: float) -> Dictionary:
	var f := fwd.normalized() if fwd.length_squared() > 1e-12 else Vector2(0.0, -1.0)
	return {"pos": pos, "fwd": f, "half": minf(half, deg_to_rad(MAX_HALF_DEG))}


## Vue de la caméra donnée (position et regard projetés sur le plan x, z) ; hors de l'arbre de scène
## (tests sans écran), sa transformation locale.
static func view_of(cam: Camera3D) -> Dictionary:
	var t := cam.global_transform if cam.is_inside_tree() else cam.transform
	var f := -t.basis.z
	var aspect := 16.0 / 9.0
	if cam.is_inside_tree():
		var size := cam.get_viewport().get_visible_rect().size
		if size.y > 0.0:
			aspect = size.x / size.y
	return view_at(Vector2(t.origin.x, t.origin.z), Vector2(f.x, f.z), half_angle_rad(cam.fov, aspect))


## Direction de la route en s sur le plan x, z (différence finie, indépendante de la convention du cap).
static func route_dir(route, s_pos: float) -> Vector2:
	var a: Vector3 = route.sample_point(route.wrap_s(s_pos - 2.0))
	var b: Vector3 = route.sample_point(route.wrap_s(s_pos + 2.0))
	var d := Vector2(b.x - a.x, b.z - a.z)
	return d.normalized() if d.length_squared() > 1e-9 else Vector2.ZERO


## Vue active `view` en s, plus les vues futures le long de la route (même écart entre le regard et la
## route, même décalage de la caméra par rapport au point de route).
static func route_views(view: Dictionary, route, s_pos: float, v: float) -> Array:
	var out := [view]
	if route == null:
		return out
	var d0 := route_dir(route, s_pos)
	if d0 == Vector2.ZERO:
		return out
	var offset_angle := d0.angle_to(view["fwd"])
	var p0: Vector3 = route.sample_point(route.wrap_s(s_pos))
	var cam_offset: Vector2 = (view["pos"] as Vector2) - Vector2(p0.x, p0.z)
	var dist := maxf(maxf(v, 0.0) * LOOKAHEAD_S, LOOKAHEAD_MIN_M)
	var n := mini(LOOKAHEAD_MAX_VIEWS, ceili(dist / LOOKAHEAD_STEP_M))
	for i in range(1, n + 1):
		var s := s_pos + dist * float(i) / float(n)
		if not route.is_loop() and s > route.length_m:
			break
		var d := route_dir(route, s)
		if d == Vector2.ZERO:
			continue
		var p: Vector3 = route.sample_point(route.wrap_s(s))
		var rot := d0.angle_to(d)
		out.append(view_at(Vector2(p.x, p.z) + cam_offset.rotated(rot), d.rotated(offset_angle), view["half"]))
	return out


static func _cross(a: Vector2, b: Vector2) -> float:
	return a.x * b.y - a.y * b.x


static func _corners(rect: Rect2) -> Array:
	return [rect.position, rect.position + Vector2(rect.size.x, 0.0), rect.end,
		rect.position + Vector2(0.0, rect.size.y)]


## Faux seulement si le rectangle est entièrement d'un même côté d'un bord du secteur ou entièrement
## derrière la caméra. `extra` (rad) élargit le secteur.
static func rect_in_view(rect: Rect2, view: Dictionary, extra: float = 0.0) -> bool:
	var apex: Vector2 = view["pos"]
	if rect.has_point(apex):
		return true
	var fwd: Vector2 = view["fwd"]
	var half := minf(float(view["half"]) + extra, deg_to_rad(MAX_HALF_DEG))
	var left := fwd.rotated(half)
	var right := fwd.rotated(-half)
	var out_left := true
	var out_right := true
	var behind := true
	for c in _corners(rect):
		var rel: Vector2 = c - apex
		if _cross(left, rel) <= 0.0:
			out_left = false
		if _cross(right, rel) >= 0.0:
			out_right = false
		if rel.dot(fwd) >= 0.0:
			behind = false
	return not (out_left or out_right or behind)


## Distance d'un point au rectangle (0 dedans).
static func rect_distance(rect: Rect2, p: Vector2) -> float:
	var dx := maxf(maxf(rect.position.x - p.x, 0.0), p.x - rect.end.x)
	var dz := maxf(maxf(rect.position.y - p.y, 0.0), p.y - rect.end.y)
	return Vector2(dx, dz).length()


static func rect_wanted(rect: Rect2, views: Array, view_radius_m: float, keep_radius_m: float,
		extra: float = 0.0) -> bool:
	if views.is_empty():
		return true
	if rect_distance(rect, views[0]["pos"]) <= keep_radius_m:
		return true
	for view in views:
		if rect_distance(rect, view["pos"]) <= view_radius_m and rect_in_view(rect, view, extra):
			return true
	return false
