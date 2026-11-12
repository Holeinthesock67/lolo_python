shader_type spatial;
render_mode unshaded, fog_disabled, cull_back, depth_draw_opaque, shadows_disabled;

// Relief d'horizon (lot JP4, version 6.0) : tuiles de 500 m jusqu'à 40 km (Format .world 1.8 §5), dessinées
// seulement au-delà du terrain lointain (inner_radius_m de la caméra). Pas de brouillard de profondeur : sa propre
// brume, qui dépend de la distance et de la hauteur au-dessus de la caméra. Le relief bas reste dans la brume (même
// teinte que le brouillard du décor), les grands sommets en sortent (le mont Fuji vu de Hakone).
// Couleurs unies : bas (forêt ou prairie du biome du départ), roche en pente, neige au-dessus de snow_line_m.

uniform float inner_radius_m = 4500.0;
uniform float fade_m = 500.0;
uniform float haze_dist_m = 40000.0;
uniform float haze_layer_m = 600.0;
uniform vec4 haze_color : source_color = vec4(0.78, 0.84, 0.9, 1.0);
uniform vec4 low_color : source_color = vec4(0.30, 0.40, 0.24, 1.0);
uniform vec4 rock_color : source_color = vec4(0.45, 0.43, 0.40, 1.0);
uniform vec4 snow_color : source_color = vec4(0.93, 0.95, 0.97, 1.0);
uniform float snow_line_m = 3000.0;
uniform vec3 sun_dir = vec3(0.3, 0.8, 0.5);   // vers le soleil, repère du monde
uniform float ambient = 0.5;
// Brouillard de profondeur du décor (Environment.fog_depth_begin et _end) : en deçà de sa fin, le relief d'horizon
// est au moins aussi visible que le terrain lointain qu'il prolonge, sans marche de teinte entre les deux.
uniform float fog_begin_m = 3600.0;
uniform float fog_end_m = 9000.0;

varying vec3 v_world;
varying vec3 v_normal;

void vertex() {
	v_world = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	v_normal = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
}

void fragment() {
	float d = length(v_world.xz - CAMERA_POSITION_WORLD.xz);
	if (d < inner_radius_m) {
		discard;
	}
	vec3 n = normalize(v_normal);
	float steep = 1.0 - n.y;
	vec3 base = mix(low_color.rgb, rock_color.rgb, smoothstep(0.2, 0.45, steep));
	float snow = smoothstep(snow_line_m - 150.0, snow_line_m + 150.0, v_world.y) * (1.0 - smoothstep(0.55, 0.75, steep));
	base = mix(base, snow_color.rgb, snow);
	float light = ambient + (1.0 - ambient) * max(dot(n, normalize(sun_dir)), 0.0);
	// Visibilité : décroît avec la distance, nulle pour le relief au niveau de la caméra ou plus bas.
	float above = clamp((v_world.y - CAMERA_POSITION_WORLD.y) / haze_layer_m, 0.0, 1.0);
	float vis = exp(-d / haze_dist_m) * above;
	float scene_vis = 1.0 - clamp((d - fog_begin_m) / max(fog_end_m - fog_begin_m, 1.0), 0.0, 1.0);
	vis = max(vis, scene_vis) * smoothstep(inner_radius_m, inner_radius_m + fade_m, d);
	ALBEDO = mix(haze_color.rgb, base * light, vis);
}
