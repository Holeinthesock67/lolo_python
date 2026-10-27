# Données embarquées du menu globe (lot W11)

Produites par `scripts/prepare_globe_assets.py` (non exécuté à l'installation).

| Fichier | Contenu | Source | Licence |
| --- | --- | --- | --- |
| `globe.jpg` | Texture équirectangulaire 2 048 × 1 024 | Terres de Natural Earth 1:110 m, dessinées par le script (océan, terres teintées selon la latitude). Le script accepte à la place une image NASA Blue Marble réduite (`--texture`) : domaine public | Domaine public |
| `coast.json` | Côtes et frontières terrestres, polylignes au centième de degré | Natural Earth 1:110 m (`ne_110m_coastline`, `ne_110m_admin_0_boundary_lines_land`) | Domaine public |
| `../../../core/src/openride_core/data/places.json` | Villes de plus de 50 000 habitants et cols célèbres | Natural Earth `ne_10m_populated_places_simple` (villes) et pack O16 (cols) | Domaine public ; cols : projet |

Natural Earth : <https://www.naturalearthdata.com/>, copie `nvkelso/natural-earth-vector`. La liste des lieux n'est pas celle de GeoNames (CC BY) prévue au cahier : elle donne la même chose (villes de plus de 50 000 habitants) sans obligation d'attribution et se récupère sans compte. Le menu cite quand même les sources dans l'écran de préchargement.

Taille totale des trois fichiers : moins de 3 Mo (essai `core/tests/test_world_menu_ipc.py`).
