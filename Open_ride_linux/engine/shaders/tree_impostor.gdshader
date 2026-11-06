shader_type spatial;
render_mode cull_disabled, diffuse_lambert, specular_disabled, shadows_disabled;

// Forêts lointaines en imposteurs (lot Y5), écrites par nous, sans texture ni extension.
// Une instance = un bouquet de quatre arbres d'une espèce, dessiné sur un seul quadrilatère tourné vers la
// caméra autour de l'axe vertical (même calcul que le panneau « billboard Y » de Godot). La silhouette est
// calculée dans fragment() : houppiers ronds (feuillus, palmiers) ou en cône (résineux), tronc sombre dessous,
// dessin tiré de la graine de l'instance. Au-delà de 1,5 km un arbre fait quelques pixels : un atlas d'images
// capturées sous plusieurs angles n'apporterait rien de visible, et une silhouette calculée ne « tourne » pas.
// Données d'instance (forest_impostors.gd) : transformation = position du pied, largeur (x) et hauteur (y) du
// bouquet en mètres ; COLOR.rgb = couleur sRGB du houppier ; INSTANCE_CUSTOM = (graine, forme 0 rond / 1 cône,
// pied de la couronne en part de la hauteur, demi-largeur d'un houppier en part de la largeur).
// Affiché de begin_m à end_m de la caméra (distance horizontale du pied) : en deçà, les arbres proches de
// tree_renderer.gd ; l'entrée se fait sur fade_m, chaque bouquet à sa distance (tirage par la graine), en
// grandissant. Hors de la plage, le quadrilatère est replié en un point (aucun pixel). Sans ombre portée ni
// reçue (au-delà de la distance des ombres), sans reflet : feuillage mat éclairé comme celui des arbres proches.

#include "res://shaders/couleur_srgb.gdshaderinc"

uniform float begin_m = 1500.0;
uniform float fade_m = 250.0;
uniform float end_m = 6000.0;

varying float v_seed;
varying float v_shape;
varying float v_crown_base;
varying float v_crown_half;
varying float v_aspect;   // largeur / hauteur du bouquet

void vertex() {
	vec3 origin = MODEL_MATRIX[3].xyz;
	float d = distance(origin.xz, INV_VIEW_MATRIX[3].xz);
	v_seed = INSTANCE_CUSTOM.x;
	v_shape = INSTANCE_CUSTOM.y;
	v_crown_base = INSTANCE_CUSTOM.z;
	v_crown_half = INSTANCE_CUSTOM.w;
	float sx = length(MODEL_MATRIX[0].xyz);
	float sy = length(MODEL_MATRIX[1].xyz);
	v_aspect = sx / max(sy, 0.01);
	// Entrée progressive : chaque bouquet a son seuil dans [begin_m, begin_m + fade_m], puis grandit sur 60 m
	float pick = fract(v_seed * 7.31);
	float grow = clamp((d - begin_m - pick * fade_m) / 60.0, 0.0, 1.0);
	if (d > end_m) {
		grow = 0.0;
	}
	MODELVIEW_MATRIX = VIEW_MATRIX * mat4(
		vec4(normalize(cross(vec3(0.0, 1.0, 0.0), INV_VIEW_MATRIX[2].xyz)), 0.0),
		vec4(0.0, 1.0, 0.0, 0.0),
		vec4(normalize(cross(INV_VIEW_MATRIX[0].xyz, vec3(0.0, 1.0, 0.0))), 0.0),
		MODEL_MATRIX[3]);
	MODELVIEW_MATRIX = MODELVIEW_MATRIX * mat4(
		vec4(sx * grow, 0.0, 0.0, 0.0),
		vec4(0.0, sy * grow, 0.0, 0.0),
		vec4(0.0, 0.0, 1.0, 0.0),
		vec4(0.0, 0.0, 0.0, 1.0));
	MODELVIEW_NORMAL_MATRIX = mat3(MODELVIEW_MATRIX);
}

float h1(float n) {
	return fract(sin(n * 12.9898 + 4.1414) * 43758.5453);
}

void fragment() {
	// x de -0,5 à 0,5 (gauche à droite), y de 0 (pied) à 1 (cime la plus haute)
	vec2 p = vec2(UV.x - 0.5, 1.0 - UV.y);
	float best = -1.0;      // profondeur du houppier touché (0 au bord, 1 au centre), -1 : rien
	vec2 n2 = vec2(0.0);    // pente de la surface touchée, pour la normale
	float tone = 1.0;
	bool trunk = false;
	float rx = v_crown_half;
	for (int i = 0; i < 4; i++) {
		float fi = float(i);
		float s = v_seed * 13.7 + fi * 3.1;
		float cx = (fi + 0.5) / 4.0 - 0.5 + (h1(s) - 0.5) * 0.18;
		cx = clamp(cx, -0.5 + rx, 0.5 - rx);
		float top = 0.72 + 0.28 * h1(s + 1.0);   // hauteur de cet arbre, en part de la plus haute
		float base = v_crown_base * top;
		float hit = -1.0;
		vec2 slope = vec2(0.0);
		if (v_shape > 0.5) {
			// Cône : demi-largeur rx au pied de la couronne, nulle à la cime
			float t = (p.y - base) / max(top - base, 0.01);
			float half_w = rx * (1.0 - t);
			float dx = p.x - cx;
			if (t >= 0.0 && t <= 1.0 && abs(dx) < half_w) {
				hit = 1.0 - abs(dx) / max(half_w, 1e-4);
				slope = vec2(sign(dx) * 0.6, 0.45);
			}
		} else {
			// Houppier rond : ellipse de demi-largeur rx, du pied de la couronne à la cime
			float ry = (top - base) * 0.5;
			vec2 q = vec2((p.x - cx) / rx, (p.y - base - ry) / max(ry, 0.01));
			float r2 = dot(q, q);
			if (r2 < 1.0) {
				hit = sqrt(1.0 - r2);
				slope = q;
			}
		}
		if (hit > best) {
			best = hit;
			n2 = slope;
			tone = 0.86 + 0.28 * h1(s + 2.0);
			trunk = false;
		}
		// Tronc sous la couronne (part de 4 % de la largeur), derrière les houppiers
		if (best < 0.0 && p.y < base + 0.02 && abs(p.x - cx) < 0.02 / max(v_aspect, 0.2)) {
			trunk = true;
		}
	}
	vec3 col;
	float through = 0.0;
	if (best >= 0.0) {
		// Normale du houppier vu comme un volume, tirée vers le haut comme celle des arbres proches
		vec3 up_view = normalize((VIEW_MATRIX * vec4(0.0, 1.0, 0.0, 0.0)).xyz);
		vec3 right_view = normalize((VIEW_MATRIX * vec4(INV_VIEW_MATRIX[0].xyz, 0.0)).xyz);
		vec3 n = normalize(right_view * n2.x + up_view * n2.y + vec3(0.0, 0.0, 1.0) * max(best, 0.2));
		NORMAL = normalize(mix(n, up_view, 0.35));
		// Dessous et intérieur plus sombres, comme le feuillage de tree_sway.gdshader (moyenne proche de 0,92)
		col = COLOR.rgb * tone * mix(0.6, 1.05, smoothstep(0.0, 1.0, p.y));
		through = v_shape > 0.5 ? 0.25 : 0.5;
	} else if (trunk) {
		col = vec3(0.30, 0.22, 0.15);
	} else {
		discard;
	}
	ALBEDO = lineaire(col);
	if (through > 0.0) {
		BACKLIGHT = lineaire(col) * through;
		EMISSION = lineaire(col) * through * 0.15;
	}
	ROUGHNESS = 1.0;
}
