// Couche de surface procédurale commune à la route et au terrain (Lot Y11, « un seul principe ») :
// bruits sans texture, faux relief par perturbation de la normale (bump à partir des dérivées
// d'écran) et fondu du détail quand il devient plus fin qu'un pixel (pas de scintillement au loin).
// Aucune texture : un pack de thème (normal, roughness) pourra remplacer ces bruits plus tard.

float sd_hash(vec2 p) {
	p = fract(p * vec2(123.34, 456.21));
	p += dot(p, p + 45.32);
	return fract(p.x * p.y);
}

vec2 sd_hash2(vec2 p) {
	return vec2(sd_hash(p), sd_hash(p + vec2(17.13, 3.71)));
}

// Bruit de valeur 2D, de 0 à 1
float sd_noise(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	f = f * f * (3.0 - 2.0 * f);
	return mix(mix(sd_hash(i), sd_hash(i + vec2(1.0, 0.0)), f.x),
		mix(sd_hash(i + vec2(0.0, 1.0)), sd_hash(i + vec2(1.0, 1.0)), f.x), f.y);
}

// Cailloux : distance au centre de la cellule la plus proche (cellules de Voronoï, 0 au centre d'un
// caillou, environ 1 entre deux) et numéro aléatoire du caillou dans .y
vec2 sd_pebbles(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	float best = 8.0;
	float id = 0.0;
	for (int y = -1; y <= 1; y++) {
		for (int x = -1; x <= 1; x++) {
			vec2 g = vec2(float(x), float(y));
			vec2 o = sd_hash2(i + g) * 0.8 + 0.1;
			vec2 d = g + o - f;
			float dd = dot(d, d);
			if (dd < best) {
				best = dd;
				id = sd_hash(i + g + vec2(7.7, 1.3));
			}
		}
	}
	return vec2(sqrt(best), id);
}

// Part du détail de période `period` (même unité que `p`) encore visible : 1 tant qu'une période couvre
// plusieurs pixels, 0 quand elle tient dans moins de deux pixels.
float sd_visible(vec2 p, float period) {
	vec2 w = fwidth(p) / period;
	return 1.0 - smoothstep(0.25, 0.6, max(w.x, w.y));
}

// Normale perturbée par la hauteur `h` (mètres) : méthode des dérivées d'écran (Mikkelsen 2010),
// dans l'espace de la vue (VERTEX et NORMAL de fragment()).
vec3 sd_bump(vec3 n, vec3 view_pos, float h) {
	vec3 dpdx = dFdx(view_pos);
	vec3 dpdy = dFdy(view_pos);
	vec3 r1 = cross(dpdy, n);
	vec3 r2 = cross(n, dpdx);
	float det = dot(dpdx, r1);
	vec3 grad = sign(det) * (dFdx(h) * r1 + dFdy(h) * r2);
	return normalize(abs(det) * n - grad);
}
