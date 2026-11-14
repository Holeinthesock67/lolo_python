shader_type spatial;
render_mode cull_back;

// Plages (lot U9, sea_mesh.gd build_beaches) : sable ou galets drapés sur le terrain, couleur de sommet COLOR
// (sRGB) ; grain doux par deux réseaux d'ondes en position (aucune valeur aléatoire : rien ne clignote).
#include "res://shaders/couleur_srgb.gdshaderinc"

varying vec3 world_pos;

void vertex() {
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
	vec2 p = world_pos.xz;
	float grain = 0.5 * sin(p.x * 1.3 + 0.7 * sin(p.y * 0.9)) * sin(p.y * 1.1 + 0.6 * sin(p.x * 0.8))
		+ 0.5 * sin(p.x * 0.21 + p.y * 0.37);
	ALBEDO = lineaire(COLOR.rgb * (1.0 + 0.06 * grain));
	ROUGHNESS = 0.95;
	SPECULAR = 0.2;
}
