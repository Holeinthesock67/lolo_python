shader_type spatial;
render_mode unshaded, blend_add, depth_draw_never, cull_disabled;

// Grille infinie au sol (lot R17) : lignes antialiasées tous les `cell_m` mètres, fondu avec la distance à
// la caméra, défilement selon la vitesse du joueur (`scroll`, avancé par le code).
uniform vec3 line_color : source_color = vec3(0.12, 0.42, 1.0);
uniform float line_intensity = 0.6;
uniform float cell_m = 10.0;
uniform float fade_start_m = 80.0;
uniform float fade_end_m = 600.0;
uniform vec2 scroll = vec2(0.0);

varying vec3 world_pos;

void vertex() {
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
	vec2 p = (world_pos.xz + scroll) / cell_m;
	vec2 g = abs(fract(p - 0.5) - 0.5) / max(fwidth(p), vec2(0.00001));
	float line = 1.0 - min(min(g.x, g.y), 1.0);
	float dist = length(world_pos.xz - CAMERA_POSITION_WORLD.xz);
	float fade = 1.0 - smoothstep(fade_start_m, fade_end_m, dist);
	ALBEDO = line_color * line_intensity * line * fade;
}
