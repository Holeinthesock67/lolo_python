shader_type spatial;
render_mode unshaded, blend_mix, cull_disabled, depth_draw_never;

// Sillage des bateaux du Lot P29 (boat_mesh.gd `wake`) : ruban d'écume posé sur l'eau qui s'efface vers son
// bout (UV.y de 0 à la poupe à 1 au bout) et sur ses bords (UV.x de 0 à 1 en travers), plus marqué sur ses
// deux bras qu'au milieu. Suit le brouillard, contrairement aux traînées des avions (contrail.gdshader).
uniform vec3 color : source_color = vec3(0.92, 0.95, 0.96);
uniform float opacity = 0.6;

void fragment() {
	float along = 1.0 - UV.y;
	float across = abs(UV.x * 2.0 - 1.0);
	float arms = mix(0.45, 1.0, smoothstep(0.2, 0.75, across));
	ALBEDO = color;
	ALPHA = opacity * along * along * arms * (1.0 - smoothstep(0.8, 1.0, across)) * smoothstep(0.0, 0.03, UV.y);
}
