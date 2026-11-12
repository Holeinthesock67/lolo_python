shader_type spatial;
render_mode cull_disabled;

// Public des tribunes du vélodrome (série VD, lot VD5) : personne assise de velodrome_hall.gd (person_mesh),
// couleur de sommet r = maillot, g = peau, b = pantalon, a = cheveux ; INSTANCE_CUSTOM.rgb = maillot de la
// personne, a = tirage de la peau (0 claire, 1 foncée) et des cheveux (noirs, bruns, châtains, blonds, gris). Couleurs en sRGB, converties une fois (couleur_srgb.gdshaderinc).
#include "res://shaders/couleur_srgb.gdshaderinc"

varying vec3 v_shirt;
varying float v_skin;

void vertex() {
	v_shirt = INSTANCE_CUSTOM.rgb;
	v_skin = INSTANCE_CUSTOM.a;
}

void fragment() {
	if (!FRONT_FACING) {
		NORMAL = -NORMAL;
	}
	vec3 skin = mix(vec3(0.93, 0.74, 0.60), vec3(0.40, 0.27, 0.18), v_skin);
	float th = fract(v_skin * 7.31);
	vec3 trousers = mix(vec3(0.12, 0.13, 0.18), vec3(0.32, 0.36, 0.48), step(0.6, th));   // sombre ou jean
	float hh = fract(v_skin * 13.7);
	vec3 hair = hh < 0.35 ? vec3(0.07, 0.06, 0.05) : hh < 0.65 ? vec3(0.25, 0.16, 0.09)
		: hh < 0.85 ? vec3(0.62, 0.48, 0.26) : vec3(0.62, 0.62, 0.60);
	vec3 c = COLOR.r * v_shirt + COLOR.g * skin + COLOR.b * trousers + COLOR.a * hair;
	ALBEDO = lineaire(c);
	ROUGHNESS = 0.85;
}
