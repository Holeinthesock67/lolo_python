extends RefCounted

## Détecteur de points parasites pour les tests de rendu (outil commun à tous les shaders, lot Y8).
## Un pixel est « isolé » quand sa luminance s'écarte de plus de `threshold` de la moyenne de ses 8 voisins
## alors que ces voisins sont proches entre eux (écart max − min sous `threshold`) : un point seul dans une
## zone unie. Les bords nets entre deux zones (fenêtre, poutre, ligne) ne comptent pas, leurs voisins
## n'étant pas homogènes. Causes typiques : hachage d'une valeur interpolée (tirage différent par pixel),
## dérivées d'écran (dFdx, fwidth) prises dans une branche non uniforme, division par zéro dans le relief.
## Pas de class_name : charger par preload("res://tests/render/speckle.gd").


static func _lum(c: Color) -> float:
	return 0.299 * c.r + 0.587 * c.g + 0.114 * c.b


## Part des pixels isolés de `img`, bord d'un pixel exclu ; `rect` limite la recherche (toute l'image par défaut).
static func isolated_ratio(img: Image, threshold: float = 0.12, rect: Rect2i = Rect2i()) -> float:
	var r := rect if rect.size != Vector2i.ZERO else Rect2i(Vector2i.ZERO, img.get_size())
	var x0 := maxi(r.position.x, 1)
	var y0 := maxi(r.position.y, 1)
	var x1 := mini(r.end.x, img.get_width() - 1)
	var y1 := mini(r.end.y, img.get_height() - 1)
	var lum := PackedFloat32Array()
	lum.resize(img.get_width() * img.get_height())
	for y in range(img.get_height()):
		for x in range(img.get_width()):
			lum[y * img.get_width() + x] = _lum(img.get_pixel(x, y))
	var w := img.get_width()
	var isolated := 0
	var total := 0
	for y in range(y0, y1):
		for x in range(x0, x1):
			var lo := INF
			var hi := -INF
			var sum := 0.0
			for dy in [-1, 0, 1]:
				for dx in [-1, 0, 1]:
					if dx == 0 and dy == 0:
						continue
					var v := lum[(y + dy) * w + x + dx]
					lo = minf(lo, v)
					hi = maxf(hi, v)
					sum += v
			total += 1
			if hi - lo < threshold and absf(lum[y * w + x] - sum / 8.0) > threshold:
				isolated += 1
	return float(isolated) / float(maxi(total, 1))
