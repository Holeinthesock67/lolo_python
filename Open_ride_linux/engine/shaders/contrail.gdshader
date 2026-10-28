shader_type spatial;
render_mode unshaded, blend_mix, cull_disabled, depth_draw_never, fog_disabled;

// Traînées de condensation du Lot P26 (sky_mesh.gd `contrail`) : rubans blancs qui s'effacent vers leur
// bout (UV.y de 0 au réacteur à 1 au bout) et sur leurs bords (UV.x de 0 à 1 en travers). `opacity` :
// opacité au départ (sky_traffic_renderer.gd), plus faible quand le soleil est bas.
uniform vec3 color : source_color = vec3(0.97, 0.97, 0.98);
uniform float opacity = 0.75;

void fragment() {
	float along = 1.0 - UV.y;
	float edge = 1.0 - abs(UV.x * 2.0 - 1.0);
	ALBEDO = color;
	ALPHA = opacity * along * along * smoothstep(0.0, 0.6, edge) * smoothstep(0.0, 0.02, UV.y);
}
