---
description: Lance toutes les suites de tests d'OpenRide (core, compilateur, Godot) et résume le résultat
---

Lance les trois suites de tests depuis `Open_ride_linux/`, en activant d'abord `core/.venv` :

1. `(cd core && pytest -q)`
2. `(cd compiler && pytest -q)`
3. `GODOT=~/Applications/godot/Godot_v4.3-stable_linux.x86_64 engine/tests/run_engine_tests.sh`
4. `python -m openride_core.tools.route_vectors --check` (vecteurs de route à jour)

Si un environnement ou Godot manque, donne la commande d'installation (voir `CLAUDE.md`) au lieu d'abandonner.

Réponds en français avec un tableau court : suite, résultat (nombre de tests passés et en échec), durée. Pour chaque échec, la cause probable et le fichier en cause. Ne corrige rien sans le demander, sauf si $ARGUMENTS contient « corrige ».
