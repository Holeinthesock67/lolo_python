shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_back, diffuse_burley, specular_schlick_ggx;

// Uniforms du terrain configurés depuis le thème (Lot E2 / SRS §8.1 / Format .world v1 §9) ; couches,
// décor et ombre des nuages dans terrain_shade.gdshaderinc (partagé avec terrain_biomes.gdshader, lot U6)
uniform vec4 grass_color : source_color = vec4(0.435, 0.604, 0.290, 1.0);
uniform float grass_inv_scale : hint_range(0.0001, 10.0) = 0.16666667;
uniform sampler2D grass_texture : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform bool has_grass_texture = false;

uniform vec4 rock_color : source_color = vec4(0.604, 0.580, 0.533, 1.0);
uniform float rock_inv_scale : hint_range(0.0001, 10.0) = 0.08333333;
uniform sampler2D rock_texture : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform bool has_rock_texture = false;

uniform vec4 snow_color : source_color = vec4(0.949, 0.961, 0.973, 1.0);
uniform float snow_inv_scale : hint_range(0.0001, 10.0) = 0.125;
uniform sampler2D snow_texture : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform bool has_snow_texture = false;

uniform float slope_threshold_deg : hint_range(0.0, 90.0) = 22.0;
uniform float snow_line_m = 2200.0;
uniform float blend_sharpness : hint_range(0.1, 32.0) = 4.0;

#include "res://shaders/terrain_shade.gdshaderinc"

void vertex() {
	v_world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	v_world_normal = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
}

void fragment() {
	vec3 n = normalize(v_world_normal);
	vec3 tri_weights = triplanar_weights(n, blend_sharpness);
	vec3 w = layer_weights(n, v_world_pos.y, slope_threshold_deg, snow_line_m, blend_sharpness);

	// Échantillonnage des seules couches visibles, ou repli sur couleur unie
	vec3 grass_c = vec3(0.0);
	if (w.x > MIN_LAYER_WEIGHT) {
		grass_c = (has_grass_texture ? sample_triplanar(grass_texture, v_world_pos, grass_inv_scale, tri_weights) : grass_color).rgb;
	}
	vec3 rock_c = vec3(0.0);
	if (w.y > MIN_LAYER_WEIGHT) {
		rock_c = (has_rock_texture ? sample_triplanar(rock_texture, v_world_pos, rock_inv_scale, tri_weights) : rock_color).rgb;
	}
	vec3 snow_c = vec3(0.0);
	if (w.z > MIN_LAYER_WEIGHT) {
		snow_c = (has_snow_texture ? sample_triplanar(snow_texture, v_world_pos, snow_inv_scale, tri_weights) : snow_color).rgb;
	}
	vec3 normal_out;
	ALBEDO = shade_layers(grass_c, rock_c, snow_c, w, n, tri_weights, VERTEX, VIEW_MATRIX, normal_out);
	NORMAL = normal_out;
	ROUGHNESS = roughness;
}
