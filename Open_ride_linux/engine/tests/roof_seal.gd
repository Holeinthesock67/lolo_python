extends RefCounted

## Contrôle « toit fermé » d'un bâtiment maillé par building_mesh.gd (fil « Fermer les toits des maisons »,
## retour d'essai du 21/11 : pignon resté plat sous un toit à deux pans, le ciel se voyait sous le toit).
## Un seul bâtiment par maillage. Deux conditions, lues sur le maillage seul (sans les plans du toit) :
## - couverture : tout point de l'empreinte a au-dessus de lui une face de toit tournée vers le ciel ;
## - couture : le haut de chaque mur (hors poteaux des pilotis) touche la surface du toit à SEAM_TOL_M près,
##   donc ni pignon ni croupe ne laissent de jour entre le mur et le toit.
## Rend la liste des défauts (vide : toit fermé).
## Pas de class_name : preload("res://tests/roof_seal.gd").

const ROOF_BIT := 1024
const SEAM_TOL_M := 0.02
## Poteaux des pilotis (0,22 m de côté) : murs plus courts que ce seuil ignorés pour la couture
const MIN_WALL_M := 0.3
## Point sur le bord d'un triangle de toit : tolérance (m)
const EDGE_TOL_M := 0.001
## Couverture : points à moins de BORDER_SKIP_M du contour ignorés
const BORDER_SKIP_M := 0.05


static func _is_roof(uv2: PackedVector2Array, i: int) -> bool:
	return (int(uv2[i].y) & ROOF_BIT) != 0


## Faces de toit tournées vers le haut (face avant de Godot : sens horaire vu de devant).
static func _roof_up(out: Dictionary) -> Array:
	var v: PackedVector3Array = out["vertices"]
	var idx: PackedInt32Array = out["indices"]
	var uv2: PackedVector2Array = out["uvs2"]
	var tris := []
	for t in range(0, idx.size(), 3):
		if not _is_roof(uv2, idx[t]):
			continue
		var a := v[idx[t]]
		var b := v[idx[t + 1]]
		var c := v[idx[t + 2]]
		if (c - a).cross(b - a).y > 1e-9:
			tris.append([a, b, c])
	return tris


## Hauteurs du toit (faces tournées vers le haut) à la verticale de `q`, bord des triangles compris (à
## EDGE_TOL_M près). Calcul en flottants 64 bits, relatif à `q` : Vector2 calcule en 32 bits, trop peu à
## quelques kilomètres de l'origine.
static func roof_heights(q: Vector2, roof_up: Array) -> Array:
	var ys := []
	var qx := float(q.x)
	var qz := float(q.y)
	for tr in roof_up:
		var a: Vector3 = tr[0]
		var b: Vector3 = tr[1]
		var c: Vector3 = tr[2]
		var ax := float(a.x) - qx
		var az := float(a.z) - qz
		var bx := float(b.x) - qx
		var bz := float(b.z) - qz
		var cx := float(c.x) - qx
		var cz := float(c.z) - qz
		var d := (bx - ax) * (cz - az) - (bz - az) * (cx - ax)
		if absf(d) < 1e-12:
			continue
		# Aires signées des sous-triangles opposés à a, b, c (q à l'origine)
		var wa := bx * cz - bz * cx
		var wb := cx * az - cz * ax
		var wc := ax * bz - az * bx
		var sgn := signf(d)
		var la := wa / d
		var lb := wb / d
		var lc := wc / d
		# Distance signée de q à chaque côté : aire / longueur du côté
		var da := wa * sgn / maxf(Vector2(cx - bx, cz - bz).length(), 1e-9)
		var db := wb * sgn / maxf(Vector2(ax - cx, az - cz).length(), 1e-9)
		var dc := wc * sgn / maxf(Vector2(bx - ax, bz - az).length(), 1e-9)
		if da >= -EDGE_TOL_M and db >= -EDGE_TOL_M and dc >= -EDGE_TOL_M:
			ys.append(float(a.y) * la + float(b.y) * lb + float(c.y) * lc)
	return ys


## Pieds des murs (hors poteaux des pilotis) : segments [a, b] de l'empreinte réellement maillée, contour et
## cours (une case ronde remplace le contour par un polygone régulier, building_mesh.round_ring).
static func _wall_feet(out: Dictionary) -> Array:
	var v: PackedVector3Array = out["vertices"]
	var nrm: PackedVector3Array = out["normals"]
	var uv2: PackedVector2Array = out["uvs2"]
	var segs := []
	var i := 0
	while i + 3 < v.size():
		if _is_wall_quad(v, nrm, uv2, i):
			var a := Vector2(v[i].x, v[i].z)
			var b := Vector2(v[i + 1].x, v[i + 1].z)
			if a.distance_to(b) > MIN_WALL_M:
				segs.append([a, b])
			i += 4
		else:
			i += 1
	return segs


static func _is_wall_quad(v: PackedVector3Array, nrm: PackedVector3Array, uv2: PackedVector2Array, i: int) -> bool:
	return not _is_roof(uv2, i) and absf(nrm[i].y) < 1e-6 \
		and absf(v[i].x - v[i + 3].x) < 1e-5 and absf(v[i].z - v[i + 3].z) < 1e-5 \
		and absf(v[i + 1].x - v[i + 2].x) < 1e-5 and absf(v[i + 1].z - v[i + 2].z) < 1e-5


## Point dans l'empreinte (pair-impair sur les pieds des murs) et à plus de BORDER_SKIP_M de tout mur : le bord
## est contrôlé par la couture, pas par la couverture.
static func _inside(q: Vector2, segs: Array) -> bool:
	var crossings := 0
	for sg in segs:
		var a: Vector2 = sg[0]
		var b: Vector2 = sg[1]
		if Geometry2D.get_closest_point_to_segment(q, a, b).distance_to(q) < BORDER_SKIP_M:
			return false
		if (a.y > q.y) != (b.y > q.y):
			var x := a.x + (q.y - a.y) * (b.x - a.x) / (b.y - a.y)
			if x > q.x:
				crossings += 1
	return crossings % 2 == 1


## Défauts du toit du maillage `out` d'un seul bâtiment (liste vide : toit fermé).
static func defects(out: Dictionary, grid: int = 16) -> PackedStringArray:
	var errs := PackedStringArray()
	var roof_up := _roof_up(out)
	if roof_up.is_empty():
		errs.append("aucune face de toit tournée vers le ciel")
		return errs
	var segs := _wall_feet(out)
	if segs.is_empty():
		errs.append("aucun mur")
		return errs
	# Couverture
	var mn := Vector2(INF, INF)
	var mx := Vector2(-INF, -INF)
	for sg in segs:
		mn = mn.min(sg[0])
		mx = mx.max(sg[0])
	var miss := 0
	for i in range(grid):
		for j in range(grid):
			var q := mn + (mx - mn) * Vector2((i + 0.5) / grid, (j + 0.5) / grid)
			if _inside(q, segs) and roof_heights(q, roof_up).is_empty():
				miss += 1
	if miss > 0:
		errs.append("%d points de l'empreinte sans toit au-dessus" % miss)
	# Couture : quadrilatères des murs (4 sommets, normale horizontale, sommets 0 et 3 à la verticale)
	var v: PackedVector3Array = out["vertices"]
	var nrm: PackedVector3Array = out["normals"]
	var uv2: PackedVector2Array = out["uvs2"]
	var worst := 0.0
	var worst_at := Vector3.ZERO
	var i := 0
	while i + 3 < v.size():
		if not _is_wall_quad(v, nrm, uv2, i):
			i += 1
			continue
		if Vector2(v[i + 1].x - v[i].x, v[i + 1].z - v[i].z).length() > MIN_WALL_M:
			for s in range(0, 11):
				var p := v[i + 3].lerp(v[i + 2], s / 10.0)
				var best := INF
				for y in roof_heights(Vector2(p.x, p.z), roof_up):
					best = minf(best, absf(float(y) - p.y))
				if best > worst:
					worst = best
					worst_at = p
		i += 4
	if worst > SEAM_TOL_M:
		errs.append("jour entre mur et toit : %.2f m en %s" % [worst, worst_at])
	return errs
