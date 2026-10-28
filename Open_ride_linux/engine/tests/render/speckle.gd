extends RefCounted

## Détecteur de points parasites pour les tests de rendu (outil commun à tous les shaders, lot Y8).
## Un pixel est « isolé » quand sa luminance dépasse de plus de `threshold` celle de ses quatre voisins
## directs, ou leur est inférieure de plus de `threshold` : un point seul, plus clair ou plus sombre que tout
## ce qui l'entoure. Un bord net (fenêtre, poutre) ou une ligne d'un pixel (petit bois) ne compte pas : le
## long du bord ou de la ligne, les voisins ont la même valeur. Un semis serré de points compte, même quand
## les voisins eux-mêmes sont bruités. Causes typiques : hachage d'une valeur interpolée (tirage différent
## par pixel), dérivées d'écran (dFdx, fwidth) prises dans une branche non uniforme, division par zéro.
## Ordre de grandeur sur des façades : 0 à 0,0006 sain, 0,0015 à 0,003 avec des tirages par pixel.
## Pas de class_name : charger par preload("res://tests/render/speckle.gd").


static func _lum(c: Color) -> float:
	return 0.299 * c.r + 0.587 * c.g + 0.114 * c.b


## Part des pixels isolés de `img`, bord d'un pixel exclu ; `rect` limite la recherche (toute l'image par défaut).
static func isolated_ratio(img: Image, threshold: float = 0.12, rect: Rect2i = Rect2i()) -> float:
	var r := rect if rect.size != Vector2i.ZERO else Rect2i(Vector2i.ZERO, img.get_size())
	var w := img.get_width()
	var x0 := maxi(r.position.x, 1)
	var y0 := maxi(r.position.y, 1)
	var x1 := mini(r.end.x, w - 1)
	var y1 := mini(r.end.y, img.get_height() - 1)
	var lum := PackedFloat32Array()
	lum.resize(w * img.get_height())
	for y in range(img.get_height()):
		for x in range(w):
			lum[y * w + x] = _lum(img.get_pixel(x, y))
	var isolated := 0
	var total := 0
	for y in range(y0, y1):
		for x in range(x0, x1):
			var c := lum[y * w + x]
			var n0 := lum[(y - 1) * w + x]
			var n1 := lum[(y + 1) * w + x]
			var n2 := lum[y * w + x - 1]
			var n3 := lum[y * w + x + 1]
			total += 1
			if c - maxf(maxf(n0, n1), maxf(n2, n3)) > threshold or minf(minf(n0, n1), minf(n2, n3)) - c > threshold:
				isolated += 1
	return float(isolated) / float(maxi(total, 1))
