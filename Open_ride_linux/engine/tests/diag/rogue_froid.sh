#!/usr/bin/env bash
# Diagnostic temporaire (fil « Corriger l'échec du test de rendu rogue », retiré avant la fusion) : lance le test
# de rendu rogue à froid (caches de shaders vidés avant chaque essai), 2 fois dans sa version de main puis 3 fois
# corrigé. Usage : GODOT=/chemin/godot tests/diag/rogue_froid.sh   (≈ 5 min au pire, sans vélo)
ENGINE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
USER_DIR="$("$GODOT" --headless --path "$ENGINE_DIR" --script res://tests/diag/user_dir.gd 2>/dev/null | grep '^USER_DIR=' | cut -d= -f2-)"
git -C "$ENGINE_DIR" show origin/main:Open_ride_linux/engine/tests/render/test_rogue_style_sheet_render.gd \
  > "$ENGINE_DIR/tests/diag/rogue_main.gd"
run() {
  rm -rf "$USER_DIR/shader_cache" "$ENGINE_DIR/.godot/shader_cache" "$HOME/.cache/nvidia/GLCache" "$HOME/.cache/mesa_shader_cache"
  local t0 rc
  t0=$(date +%s.%N)
  timeout -k 5 120 xvfb-run -a "$GODOT" --path "$ENGINE_DIR" --rendering-driver vulkan --rendering-method forward_plus \
    --audio-driver Dummy --script "$2" > /tmp/rogue_froid.log 2>&1
  rc=$?
  printf '%-9s rc=%-3s %6.1f s  %s\n' "$1" "$rc" "$(echo "$(date +%s.%N) - $t0" | bc)" \
    "$(grep -E 'compilations|vérifications|ERROR|WARNING' /tmp/rogue_froid.log | tr '\n' ' ' | cut -c1-160)"
}
echo "user:// = ${USER_DIR:-introuvable}"
run main res://tests/diag/rogue_main.gd
run main res://tests/diag/rogue_main.gd
for i in 1 2 3; do run corrige res://tests/render/test_rogue_style_sheet_render.gd; done
rm -f "$ENGINE_DIR/tests/diag/rogue_main.gd" "$ENGINE_DIR/tests/diag/rogue_main.gd.uid"
