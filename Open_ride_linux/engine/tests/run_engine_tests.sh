#!/usr/bin/env bash
# Tests de l'engine sans écran (lots D6, E1, E2, K1 et K4) : tests unitaires découverts dans tests/unit/,
# couches OSM (données produites par le compilateur installé), rendu hors écran du shader (tests/render/,
# sous Xvfb), rendu par tronçons, puis scénarios IPC face au faux core (parcours de démonstration avec
# terrain synthétique).
#
#   GODOT=/chemin/vers/Godot_v4.3-stable_linux.x86_64 engine/tests/run_engine_tests.sh
#
# Variables : GODOT (exécutable Godot 4.3), STATE_PORT / CMD_PORT (ports de test, défaut 15005 / 15006),
# SCENARIOS (ex. « 1,2,3 »), ENGINE_LOG (journal de l'engine, défaut : fichier temporaire),
# REQUIRE_RENDER (1 : échec si xvfb-run manque, au lieu de sauter les tests de rendu),
# UNIT (ex. « test_route_vectors » : ne lance que ce test unitaire et saute les autres étapes),
# UNIT_TIMEOUT (durée maximale d'un test unitaire en secondes, défaut 120 : une erreur de script dans
# _init laisse Godot tourner sans quitter),
# VISUAL_CONFIGS (configurations des tests graphiques de la scène principale, défaut « 1280x720:low » ;
# « none » pour les sauter ; matrice complète et rapport : run_visual_tests.sh),
# OPENRIDE_PERF (budgets de temps, lot X2 : « report » par défaut, un dépassement est signalé sans
# échec ; « strict » le compte comme un échec ; budgets dans tests/perf_budgets.json),
# PERF_CSV (fichier où ajouter les mesures « date;nom;ms;budget;dépassé », facultatif),
# ENGINE_JUNIT (fichier JUnit XML à écrire, lot X3 : une entrée par test du résumé, avec son statut et
# sa durée, temps écoulé depuis l'entrée précédente ; facultatif, rien n'est écrit sans).
# Code de sortie : 0 si tout passe.
set -u
ENGINE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GODOT="${GODOT:-$HOME/Applications/godot/Godot_v4.3-stable_linux.x86_64}"
STATE_PORT="${STATE_PORT:-15005}"
CMD_PORT="${CMD_PORT:-15006}"
ENGINE_LOG_TEMP=$([ -z "${ENGINE_LOG:-}" ] && echo 1 || echo 0)   # journal temporaire : supprimé si tout passe
ENGINE_LOG="${ENGINE_LOG:-$(mktemp -t openride-engine-test.XXXXXX.log)}"
ROUTES_DIR="$(mktemp -d -t openride-routes.XXXXXX)"   # reçoit demo.world avec terrain synthétique
UNIT_TIMEOUT="${UNIT_TIMEOUT:-120}"
CORE_SRC="$(cd "$ENGINE_DIR/../core/src" && pwd)"

if [ ! -x "$GODOT" ]; then
  echo "Godot introuvable : $GODOT (définir GODOT=/chemin/vers/godot)"; exit 2
fi

status=0
PERF_FILE="$(mktemp -t openride-perf.XXXXXX)"   # lignes [PERF] de tous les tests (lot X2)

# Résumé final : une ligne par test (fichier ou étape) et son résultat ; JUnit (lot X3) : nom, statut,
# durée depuis l'entrée précédente, détail.
SUMMARY=()
JUNIT_CASES=()
JUNIT_LAST="$(date +%s.%N)"
JUNIT_START="$JUNIT_LAST"
record() {  # record <nom> <0 si réussi> [détail]
  if [ "$2" -eq 0 ]; then SUMMARY+=("OK     $1${3:+ : $3}"); else SUMMARY+=("ÉCHEC  $1${3:+ : $3}"); status=1; fi
  local now
  now="$(date +%s.%N)"
  JUNIT_CASES+=("$1"$'\t'"$2"$'\t'"$(awk -v a="$JUNIT_LAST" -v b="$now" 'BEGIN { printf "%.3f", b - a }')"$'\t'"${3:-}")
  JUNIT_LAST="$now"
}

xml_escape() {
  printf '%s' "$1" | sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g' -e 's/"/\&quot;/g'
}

# Rapport JUnit XML (lot X3) si ENGINE_JUNIT est donné : une entrée <testcase> par appel de record.
write_junit() {
  [ -n "${ENGINE_JUNIT:-}" ] || return 0
  local failures=0 total name rc secs detail
  for c in "${JUNIT_CASES[@]}"; do [ "$(cut -f2 <<<"$c")" = 0 ] || failures=$((failures + 1)); done
  total="$(awk -v a="$JUNIT_START" -v b="$(date +%s.%N)" 'BEGIN { printf "%.3f", b - a }')"
  mkdir -p "$(dirname "$ENGINE_JUNIT")"
  {
    echo '<?xml version="1.0" encoding="utf-8"?>'
    echo "<testsuites><testsuite name=\"engine\" tests=\"${#JUNIT_CASES[@]}\" failures=\"$failures\" errors=\"0\" skipped=\"0\" time=\"$total\">"
    for c in "${JUNIT_CASES[@]}"; do
      IFS=$'\t' read -r name rc secs detail <<<"$c"
      printf '  <testcase classname="engine" name="%s" time="%s"' "$(xml_escape "$name")" "$secs"
      if [ "$rc" = 0 ]; then echo '/>'; else
        printf '><failure message="%s"/></testcase>\n' "$(xml_escape "${detail:-échec}")"
      fi
    done
    echo "</testsuite></testsuites>"
  } >"$ENGINE_JUNIT"
}

# Filtre commun (lot X34) : toute ligne SCRIPT ERROR, ERROR ou WARNING est une erreur, sauf
# - les objets non libérés à la sortie (ObjectDB instances leaked, resources still in use at exit) ;
# - une erreur dont la ligne « at: » suivante vient du serveur de rendu factice de --headless
#   (servers/rendering/dummy/ : « Parameter "m" is null » de mesh_get_surface_count, il ne garde aucun maillage).
# Avant le lot X34, toute ligne contenant « mesh … null » était tolérée, d'où qu'elle vienne.
godot_issues() {
  awk '
    /SCRIPT ERROR|ERROR:|WARNING:/ { if (pending != "") print pending; pending = $0; next }
    pending != "" { if ($0 !~ /servers\/rendering\/dummy\//) print pending; pending = "" }
    END { if (pending != "") print pending }
  ' | grep -v -E "ObjectDB instances leaked|resources still in use at exit" || true
}

echo "== Tests unitaires (tests/unit/, lot K1) =="
# Contrat d'un test unitaire : tests/README.md. Chaque fichier tests/unit/test_*.gd est lancé par ordre alphabétique.
unit_found=0
while IFS= read -r unit_file; do
  unit_name="$(basename "$unit_file" .gd)"
  if [ -n "${UNIT:-}" ] && [ "$unit_name" != "${UNIT%.gd}" ]; then continue; fi
  unit_found=1
  echo "-- $unit_name"
  UNIT_OUT="$(timeout -k 5 "$UNIT_TIMEOUT" "$GODOT" --headless --path "$ENGINE_DIR" \
    --script "res://tests/unit/$unit_name.gd" 2>&1)"
  unit_rc=$?
  if [ "$unit_rc" -eq 124 ] || [ "$unit_rc" -eq 137 ]; then UNIT_OUT="$UNIT_OUT
Test arrêté au bout de $UNIT_TIMEOUT s"; fi
  echo "$UNIT_OUT" | grep -v "^Godot Engine" || true
  echo "$UNIT_OUT" | grep "^\[PERF\]" >>"$PERF_FILE" || true
  unit_issues="$(echo "$UNIT_OUT" | godot_issues)"
  unit_count="$(echo "$UNIT_OUT" | grep -E "^$unit_name : [0-9]+ vérifications, [0-9]+ échecs$" | tail -1)"
  if [ "$unit_rc" -ne 0 ] || [ -n "$unit_issues" ] || [ -z "$unit_count" ]; then
    reason="code $unit_rc"
    if [ -n "$unit_issues" ]; then echo "$unit_issues"; reason="$reason, erreurs ou avertissements Godot"; fi
    if [ -z "$unit_count" ]; then reason="$reason, ligne finale absente"; fi
    record "unit/$unit_name" 1 "$reason${unit_count:+, ${unit_count#*: }}"
  else
    record "unit/$unit_name" 0 "${unit_count#*: }"
  fi
done < <(find "$ENGINE_DIR/tests/unit" -maxdepth 1 -name 'test_*.gd' | LC_ALL=C sort)
if [ -n "${UNIT:-}" ] && [ "$unit_found" -eq 0 ]; then
  record "unit/${UNIT%.gd}" 1 "introuvable dans tests/unit/"
fi

# Budgets de temps (lot X2) : mesures relevées par tests/perf_budget.gd, hors résultat des tests en mode report.
perf_summary() {
  [ -s "$PERF_FILE" ] || { rm -f "$PERF_FILE"; return; }
  local over
  over="$(grep -c "DÉPASSÉ" "$PERF_FILE")"
  echo "Budgets de temps (OPENRIDE_PERF=${OPENRIDE_PERF:-report}) : $(wc -l <"$PERF_FILE") mesures, $over dépassement(s)"
  sed 's/^\[PERF\] /  /' "$PERF_FILE"
  if [ -n "${PERF_CSV:-}" ]; then
    sed -E "s/^\[PERF\] ([^ ]+) : ([0-9.]+) [^ ,]+, budget ([0-9.inf]+) [^ ]+( \(DÉPASSÉ\))?$/$(date +%F_%T);\1;\2;\3;\4/" "$PERF_FILE" \
      | sed 's/; (DÉPASSÉ)$/;oui/; s/;$/;non/' >>"$PERF_CSV"
  fi
  rm -f "$PERF_FILE"
}

if [ -n "${UNIT:-}" ]; then
  echo "UNIT=${UNIT} : rendu, ERG et scénarios IPC sautés"
  rm -rf "$ROUTES_DIR"
  perf_summary
  echo "Résumé :"
  for line in "${SUMMARY[@]}"; do echo "  $line"; done
  if [ "$status" -eq 0 ]; then echo "RÉSULTAT : tous les tests de l'engine passent"; else echo "RÉSULTAT : ÉCHEC"; fi
  write_junit
  exit "$status"
fi

echo "== Couches OSM (lot K4) =="
# Données produites par le vrai compilateur (installé), sans réseau, puis lues par osm_layers.gd.
OSM_DIR="$(mktemp -d -t openride-osm.XXXXXX)"
if python3 "$ENGINE_DIR/tests/make_osm_world.py" --out "$OSM_DIR"; then
  OSM_OUT="$(timeout -k 5 "$UNIT_TIMEOUT" "$GODOT" --headless --path "$ENGINE_DIR" --script res://tests/test_osm_layers.gd \
    -- "$OSM_DIR/osm-test.world" "$OSM_DIR/expected.json" 2>&1)"
  osm_rc=$?
  echo "$OSM_OUT" | grep -v "^Godot Engine" || true
  echo "$OSM_OUT" | grep "^\[PERF\]" >>"$PERF_FILE" || true
  osm_issues="$(echo "$OSM_OUT" | godot_issues)"
  if [ -n "$osm_issues" ]; then echo "$osm_issues"; osm_rc=1; fi
  record "test_osm_layers (couches OSM K4)" "$osm_rc" "$(echo "$OSM_OUT" | grep -E "^test_osm_layers : " | tail -1 | sed 's/^test_osm_layers : //')"
else
  record "test_osm_layers (couches OSM K4)" 1 "données non produites par make_osm_world.py (compilateur installé ?)"
fi
rm -rf "$OSM_DIR"

echo "-- test_osm_streamer (streaming OSM E4)"
STREAMER_OUT="$(timeout -k 5 "$UNIT_TIMEOUT" "$GODOT" --headless --path "$ENGINE_DIR" --script res://tests/test_osm_streamer.gd 2>&1)"
streamer_rc=$?
echo "$STREAMER_OUT" | grep -v "^Godot Engine" || true
streamer_issues="$(echo "$STREAMER_OUT" | godot_issues)"
streamer_count="$(echo "$STREAMER_OUT" | grep -E "^test_osm_streamer : [0-9]+ vérifications, [0-9]+ échecs$" | tail -1)"
if [ "$streamer_rc" -ne 0 ] || [ -n "$streamer_issues" ] || [ -z "$streamer_count" ]; then
  reason="code $streamer_rc"
  if [ -n "$streamer_issues" ]; then echo "$streamer_issues"; reason="$reason, erreurs ou avertissements Godot"; fi
  if [ -z "$streamer_count" ]; then reason="$reason, ligne finale absente"; fi
  record "test_osm_streamer (streaming OSM E4)" 1 "$reason${streamer_count:+, ${streamer_count#*: }}"
else
  record "test_osm_streamer (streaming OSM E4)" 0 "${streamer_count#*: }"
fi

echo "== Rendu hors écran du shader (tests/render/, lot E2) =="
# Vraie image rendue (Xvfb, OpenGL logiciel de Mesa) : le shader compilé reproduit la fonction de L3.
# Sans xvfb-run, l'étape est sautée, sauf si REQUIRE_RENDER=1 (intégration continue) : elle échoue alors.
if command -v xvfb-run >/dev/null 2>&1; then
  while IFS= read -r render_file; do
    render_name="$(basename "$render_file" .gd)"
    echo "-- $render_name"
    RENDER_OUT="$(timeout -k 5 "$UNIT_TIMEOUT" xvfb-run -a "$GODOT" --path "$ENGINE_DIR" --rendering-driver opengl3 \
      --rendering-method gl_compatibility --audio-driver Dummy --script "res://tests/render/$render_name.gd" 2>&1)"
    render_rc=$?
    echo "$RENDER_OUT" | grep -v "^Godot Engine" || true
    # Avertissement connu sous Xvfb : synchronisation verticale non réglable.
    render_issues="$(echo "$RENDER_OUT" | grep -v -E "V-Sync|set_use_vsync" | godot_issues)"
    render_count="$(echo "$RENDER_OUT" | grep -E "^$render_name : [0-9]+ vérifications, [0-9]+ échecs$" | tail -1)"
    if [ -n "$render_issues" ]; then echo "$render_issues"; render_rc=1; fi
    if [ -z "$render_count" ]; then render_rc=1; fi
    record "render/$render_name" "$render_rc" "${render_count#*: }"
  done < <(find "$ENGINE_DIR/tests/render" -maxdepth 1 -name 'test_*.gd' | LC_ALL=C sort)
elif [ "${REQUIRE_RENDER:-0}" = "1" ]; then
  record "render (tests/render/)" 1 "xvfb-run introuvable alors que REQUIRE_RENDER=1"
else
  echo "xvfb-run introuvable : tests de rendu sautés (installer xvfb, ou REQUIRE_RENDER=1 pour échouer)"
fi

echo "== Tests graphiques de la scène principale (visual_check.py) =="
# Vraie scène sous Xvfb face au faux core : captures d'écran analysées (HUD, bandeau, ciel et sol, caméra).
VISUAL_CONFIGS="${VISUAL_CONFIGS:-1280x720:low}"
if [ "$VISUAL_CONFIGS" = "none" ]; then
  echo "VISUAL_CONFIGS=none : tests graphiques sautés"
elif command -v xvfb-run >/dev/null 2>&1; then
  VISUAL_DIR="$(mktemp -d -t openride-visual.XXXXXX)"
  VISUAL_OUT="$(timeout -k 5 600 python3 "$ENGINE_DIR/tests/visual_check.py" --godot "$GODOT" \
    --configs "$VISUAL_CONFIGS" --out "$VISUAL_DIR" 2>&1)"
  visual_rc=$?
  echo "$VISUAL_OUT" | grep -E "^\[ÉCHEC\]|^Tests graphiques|introuvable" || true
  if [ "$visual_rc" -eq 0 ]; then rm -rf "$VISUAL_DIR"; else echo "Captures, journaux et rapport gardés : $VISUAL_DIR/rapport.html"; fi
  record "tests graphiques ($VISUAL_CONFIGS)" "$visual_rc" "$(echo "$VISUAL_OUT" | grep -E "^Tests graphiques" | tail -1 | sed 's/^Tests graphiques : //')"
elif [ "${REQUIRE_RENDER:-0}" = "1" ]; then
  record "tests graphiques" 1 "xvfb-run introuvable alors que REQUIRE_RENDER=1"
else
  echo "xvfb-run introuvable : tests graphiques sautés"
fi

echo "== Rendu par tronçons (lot E1) =="
# Démo commune avec couche terrain synthétique (bibliothèque standard de Python seulement).
if ! PYTHONPATH="$CORE_SRC" python3 -m openride_core.tools.fake_world --demo --terrain --out "$ROUTES_DIR" >/dev/null; then
  echo "Génération du terrain synthétique impossible"; status=1
fi
STREAM_LOG="$(mktemp -t openride-stream-test.XXXXXX.log)"
"$GODOT" --headless --path "$ENGINE_DIR" --script res://tests/test_world_streamer.gd -- "$ROUTES_DIR/demo.world" \
  >"$STREAM_LOG" 2>&1
stream_status=$?
grep -v "^Godot Engine" "$STREAM_LOG"
stream_ok=0
if [ "$stream_status" -ne 0 ] || grep -q -E "SCRIPT ERROR|ERROR:|WARNING:" "$STREAM_LOG"; then stream_ok=1; fi
record "test_world_streamer (rendu E1)" "$stream_ok"
rm -f "$STREAM_LOG"

echo "== Coutures du sol multi-biome en scène réelle (série U) =="
# Démo ci-dessus avec une couche biome prairie → sable ; world_streamer.gd charge les tuiles (Xvfb).
if command -v xvfb-run >/dev/null 2>&1; then
  SEAMS_OUT="$(timeout -k 5 "$UNIT_TIMEOUT" xvfb-run -a "$GODOT" --path "$ENGINE_DIR" --rendering-driver opengl3 \
    --rendering-method gl_compatibility --audio-driver Dummy --script res://tests/test_biome_seams.gd -- "$ROUTES_DIR/demo.world" 2>&1)"
  seams_rc=$?
  echo "$SEAMS_OUT" | grep -v "^Godot Engine" || true
  seams_issues="$(echo "$SEAMS_OUT" | grep -v -E "V-Sync|set_use_vsync" | godot_issues)"
  seams_count="$(echo "$SEAMS_OUT" | grep -E "^test_biome_seams : [0-9]+ vérifications, [0-9]+ échecs$" | tail -1)"
  if [ -n "$seams_issues" ]; then echo "$seams_issues"; seams_rc=1; fi
  if [ -z "$seams_count" ]; then seams_rc=1; fi
  record "test_biome_seams (coutures des biomes)" "$seams_rc" "${seams_count#*: }"
elif [ "${REQUIRE_RENDER:-0}" = "1" ]; then
  record "test_biome_seams (coutures des biomes)" 1 "xvfb-run introuvable alors que REQUIRE_RENDER=1"
fi

echo "== ERG (lot I6) =="
python3 "$ENGINE_DIR/tests/fake_core.py" --erg-workout --state-port "$STATE_PORT" --cmd-port "$CMD_PORT" &
ERG_FAKE_PID=$!
sleep 0.2
ERG_OUT="$("$GODOT" --headless --path "$ENGINE_DIR" --script res://tests/test_erg_view_model.gd -- --ipc-state-port="$STATE_PORT" --ipc-cmd-port="$CMD_PORT" 2>&1)"
erg_rc=$?
wait "$ERG_FAKE_PID"
erg_fake_rc=$?
echo "$ERG_OUT" | grep -v "^Godot Engine" || true
erg_ok=0
if [ "$erg_rc" -ne 0 ] || [ "$erg_fake_rc" -ne 0 ]; then erg_ok=1; fi
erg_issues="$(echo "$ERG_OUT" | godot_issues)"
if [ -n "$erg_issues" ]; then echo "$erg_issues"; erg_ok=1; fi
record "test_erg_view_model (ERG I6, faux core)" "$erg_ok" "$(echo "$ERG_OUT" | grep -E "^Tests ERG vérifiés" | tail -1)"

# Deux passages : réponses normales, puis 1re réponse perdue et listes en deux parties (critère 3 du lot N3).
for menu_variant in normal perte-et-parties; do
  if [ "$menu_variant" = normal ]; then MENU_FAKE_ARGS=(); else MENU_FAKE_ARGS=(--drop-first-catalog --split-catalog); fi
  echo "== Menu et listes v1.1 (lot N3, $menu_variant) =="
  python3 "$ENGINE_DIR/tests/fake_core.py" --catalog "$ENGINE_DIR/tests/data/catalog_test.json" "${MENU_FAKE_ARGS[@]}" --state-port "$STATE_PORT" --cmd-port "$CMD_PORT" &
  MENU_FAKE_PID=$!
  sleep 0.2
  MENU_OUT="$("$GODOT" --headless --path "$ENGINE_DIR" --script res://tests/test_menu_ipc.gd -- --ipc-state-port="$STATE_PORT" --ipc-cmd-port="$CMD_PORT" 2>&1)"
  menu_rc=$?
  wait "$MENU_FAKE_PID"
  menu_fake_rc=$?
  echo "$MENU_OUT" | grep -v "^Godot Engine" || true
  menu_ok=0
  if [ "$menu_rc" -ne 0 ] || [ "$menu_fake_rc" -ne 0 ]; then menu_ok=1; fi
  menu_issues="$(echo "$MENU_OUT" | godot_issues)"
  if [ -n "$menu_issues" ]; then echo "$menu_issues"; menu_ok=1; fi
  record "test_menu_ipc (listes v1.1 et menu N3, faux core, $menu_variant)" "$menu_ok" "$(echo "$MENU_OUT" | grep -E "^test_menu_ipc : " | tail -1 | sed 's/^test_menu_ipc : //')"
done

echo "== Scénarios IPC (journal de l'engine : $ENGINE_LOG) =="
: >"$ENGINE_LOG"
FAKE_ARGS=(--state-port "$STATE_PORT" --cmd-port "$CMD_PORT" --engine-log "$ENGINE_LOG")
if [ -n "${SCENARIOS:-}" ]; then FAKE_ARGS+=(--scenarios "$SCENARIOS"); fi
FAKE_OUT_FILE="$(mktemp -t openride-fake-core.XXXXXX.log)"
python3 "$ENGINE_DIR/tests/fake_core.py" "${FAKE_ARGS[@]}" > >(tee "$FAKE_OUT_FILE") 2>&1 &
FAKE_PID=$!
sleep 0.3
"$GODOT" --headless --path "$ENGINE_DIR" -- --ipc-state-port="$STATE_PORT" --ipc-cmd-port="$CMD_PORT" \
  --routes-dir="$ROUTES_DIR" --test-mode >"$ENGINE_LOG" 2>&1 &
GODOT_PID=$!

wait "$FAKE_PID"
fake_status=$?
sleep 0.1   # laisse tee finir d'écrire
FAKE_OUT="$(cat "$FAKE_OUT_FILE")"; rm -f "$FAKE_OUT_FILE"
if ! kill -0 "$GODOT_PID" 2>/dev/null; then
  echo "L'engine s'est arrêté pendant les scénarios :"; tail -20 "$ENGINE_LOG"; fake_status=1
fi
kill -TERM "$GODOT_PID" 2>/dev/null
for _ in $(seq 50); do kill -0 "$GODOT_PID" 2>/dev/null || break; sleep 0.1; done
kill -KILL "$GODOT_PID" 2>/dev/null
wait "$GODOT_PID" 2>/dev/null
rm -rf "$ROUTES_DIR"
record "scénarios IPC (faux core)" "$fake_status" "$(grep -E "^Scénarios : " <<<"$FAKE_OUT" | tail -1)"

echo "== Parcours affiché pendant les scénarios =="
if grep -q "route_loaded id=demo" "$ENGINE_LOG" && grep -q "terrain présent" "$ENGINE_LOG"; then
  echo "demo avec terrain synthétique chargé"; record "parcours affiché (demo avec terrain)" 0
else
  echo "demo avec terrain non chargé"; record "parcours affiché (demo avec terrain)" 1
fi

echo "== Erreurs et avertissements de Godot =="
issues="$(godot_issues <"$ENGINE_LOG")"
if [ -n "$issues" ]; then
  echo "$issues"; record "journal de l'engine sans erreur Godot" 1
else
  echo "aucun"; record "journal de l'engine sans erreur Godot" 0
fi

perf_summary
echo "Résumé :"
for line in "${SUMMARY[@]}"; do echo "  $line"; done
if [ "$status" -eq 0 ]; then echo "RÉSULTAT : tous les tests de l'engine passent"; else echo "RÉSULTAT : ÉCHEC"; fi
if [ "$status" -eq 0 ] && [ "$ENGINE_LOG_TEMP" = 1 ]; then rm -f "$ENGINE_LOG"; else echo "Journal de l'engine gardé : $ENGINE_LOG"; fi
write_junit
exit "$status"
