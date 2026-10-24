shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_back, diffuse_burley, specular_schlick_ggx;

// Uniforms du terrain configurés depuis le thème (Lot E2 / SRS §8.1 / Format .world v1 §9)
uniform vec4 grass_color : source_color = vec4(0.435, 0.604, 0.290, 1.0);
uniform float grass_inv_scale : hint_range(0.0001, 10.0) = 0.16666667;
uniform sampler2D grass_texture : source_color, filter_linear_mipmap, repeat_enable;
uniform bool has_grass_texture = false;

uniform vec4 rock_color : source_color = vec4(0.604, 0.580, 0.533, 1.0);
uniform float rock_inv_scale : hint_range(0.0001, 10.0) = 0.08333333;
uniform sampler2D rock_texture : source_color, filter_linear_mipmap, repeat_enable;
uniform bool has_rock_texture = false;

uniform vec4 snow_color : source_color = vec4(0.949, 0.961, 0.973, 1.0);
uniform float snow_inv_scale : hint_range(0.0001, 10.0) = 0.125;
uniform sampler2D snow_texture : source_color, filter_linear_mipmap, repeat_enable;
uniform bool has_snow_texture = false;

uniform float slope_threshold_deg : hint_range(0.0, 90.0) = 22.0;
uniform float snow_line_m = 2200.0;
uniform float blend_sharpness : hint_range(0.1, 32.0) = 4.0;
uniform float roughness : hint_range(0.0, 1.0) = 1.0;

varying vec3 v_world_pos;
varying vec3 v_world_normal;

void vertex() {
	v_world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	v_world_normal = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
}

vec4 sample_triplanar(sampler2D tex, vec3 pos, float inv_scale, vec3 weights) {
	vec2 uv_x = pos.zy * inv_scale;
	vec2 uv_y = pos.xz * inv_scale;
	vec2 uv_z = pos.xy * inv_scale;
	return texture(tex, uv_x) * weights.x + texture(tex, uv_y) * weights.y + texture(tex, uv_z) * weights.z;
}

void fragment() {
	vec3 n = normalize(v_world_normal);

	// Poids triplanaires YZ (axe x), XZ (axe y), XY (axe z)
	vec3 tri_p = pow(max(abs(n), vec3(1e-6)), vec3(max(blend_sharpness, 0.01)));
	float tri_tot = tri_p.x + tri_p.y + tri_p.z;
	vec3 tri_weights = tri_p / max(tri_tot, 1e-6);

	// Échantillonnage de chaque couche ou repli sur couleur unie
	vec4 grass_sample = has_grass_texture ? sample_triplanar(grass_texture, v_world_pos, grass_inv_scale, tri_weights) : grass_color;
	vec4 rock_sample = has_rock_texture ? sample_triplanar(rock_texture, v_world_pos, rock_inv_scale, tri_weights) : rock_color;
	vec4 snow_sample = has_snow_texture ? sample_triplanar(snow_texture, v_world_pos, snow_inv_scale, tri_weights) : snow_color;

	// Calcul de pente en degrés depuis la normale monde (n.y = cos(pente))
	float cos_n = clamp(n.y, -1.0, 1.0);
	float slope_deg = degrees(acos(cos_n));

	// Demi-largeur de transition herbe/roche (Lot L3 / SRS §8.1)
	float half_band = clamp(12.0 / max(blend_sharpness, 1.0), 1.5, 3.0);
	float t_rock = smoothstep(slope_threshold_deg - half_band, slope_threshold_deg + half_band, slope_deg);

	// Neige au-dessus de snow_line_m, fondue sur 50 m, absente sur la roche raide (> 50°)
	float snow_alt = smoothstep(snow_line_m, snow_line_m + 50.0, v_world_pos.y);
	float snow_slope = 1.0 - smoothstep(44.0, 50.0, slope_deg);
	float w_snow = clamp(snow_alt * snow_slope, 0.0, 1.0);

	float rem = 1.0 - w_snow;
	float w_rock = rem * t_rock;
	float w_grass = rem * (1.0 - t_rock);

	vec4 final_color = grass_sample * w_grass + rock_sample * w_rock + snow_sample * w_snow;
	ALBEDO = final_color.rgb;
	ROUGHNESS = roughness;
}
