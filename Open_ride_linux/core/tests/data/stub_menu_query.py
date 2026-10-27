"""Doublure de `openride_compiler.worldgen.menu_query` pour les essais du menu (lot W11) : bibliothèque standard seulement."""

import json
import sys

args = sys.argv[1:]
if "--config" in args:
    i = args.index("--config")
    del args[i:i + 2]
cmd = args[0]
if cmd == "search":
    text = args[args.index("--text") + 1].lower()
    items = [{"name": "Col de la Bonette", "kind": "mountain_pass", "lat": 44.32, "lon": 6.8, "cached": True, "source": "base"}]
    print(json.dumps({"items": [i for i in items if text in i["name"].lower()]}))
elif cmd == "map":
    roads = [{"c": "t", "xz": [0, 0, 100, 5, 250, -20 + k]} for k in range(400)]   # assez pour plusieurs parties
    print(json.dumps({"roads": roads}))
elif cmd == "pin":
    print(json.dumps({"cache_bytes": 10, "cache_max_bytes": 100, "items": [
        {"id": args[args.index("--region") + 1], "name": "Provence", "bytes": 10,
         "pinned": args[args.index("--pinned") + 1] == "1", "last_used": "2026-10-20T10:00:00Z", "bbox": [4.2, 42.9, 7.7, 45.2]}]}))
elif cmd == "regions":
    print(json.dumps({"cache_bytes": 10, "cache_max_bytes": 100, "items": [
        {"id": "provence", "name": "Provence", "bytes": 10, "pinned": False, "last_used": "2026-10-20T10:00:00Z", "bbox": [4.2, 42.9, 7.7, 45.2]}]}))
else:
    print(json.dumps({"error": "commande inconnue"}))
    sys.exit(1)
