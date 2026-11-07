shader_type spatial;
render_mode cull_back;

// Public des tribunes du vélodrome (série VD, lot VD5) : personne assise de velodrome_hall.gd (person_mesh),
// couleur de sommet r = maillot, g = peau, b = pantalon ; INSTANCE_CUSTOM.rgb = maillot de la personne,
// a = teinte de peau (0 claire, 1 foncée). Couleurs en sRGB, converties une fois (couleur_srgb.gdshaderinc).
#include "res://shaders/couleur_srgb.gdshaderinc"

varying vec3 v_shirt;
varying float v_skin;

void vertex() {
	v_shirt = INSTANCE_CUSTOM.rgb;
	v_skin = INSTANCE_CUSTOM.a;
}

void fragment() {
	vec3 skin = mix(vec3(0.93, 0.74, 0.60), vec3(0.40, 0.27, 0.18), v_skin);
	vec3 trousers = vec3(0.14, 0.15, 0.20);
	vec3 c = COLOR.r * v_shirt + COLOR.g * skin + COLOR.b * trousers;
	ALBEDO = lineaire(c);
	ROUGHNESS = 0.85;
}
