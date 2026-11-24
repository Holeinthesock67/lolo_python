# Lot NT1 – Nettoyage et intégration des parcours de démonstration (liste finale du jeu de base)

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Liste finale des parcours du jeu de base verrouillée, une fiche (description au menu) pour chaque démonstration, scénario de menus complet, suivi des lots de démonstration remis à jour | Python, JSON | O37, O38, DB1, DB2, DB3, DJ1, SM1, GP13 | Petite | **Livré le 19 novembre** (PR #922, avant J9) |

Bilan des circuits de démonstration (hors dépôt : `/mnt/project-files/statut/BILAN_CIRCUITS_DEMO_2026-11-12.md`, §4 et §5) et point du 19 novembre (§5) : toutes les démonstrations du jeu de base sont dans `main` ; un dernier passage de nettoyage et d'intégration se fait avant l'installateur J9, qui embarque la liste finale.

## 1. Objectif

1. La liste du jeu de base est celle décidée par le propriétaire, et un test la verrouille.
2. Aucune trace de test dans ce qu'un joueur reçoit : aucun lieu « Fictif », aucun nom technique, aucune consigne de test ; les parcours sortis du jeu de base (tour des six paysages, côte, alpin, tour gravel) ne s'installent jamais sur un jeu neuf.
3. Chaque parcours du jeu de base se présente comme les autres contenus livrés (vélodrome, cols du pack) : une fiche avec sa description sur la carte du parcours au menu.
4. Les outils de la recette (captures, banc des menus) suivent la même liste.

## 2. Liste finale du jeu de base

| Identifiant | Nom au menu | Où au menu | Lot |
| --- | --- | --- | --- |
| `demo` | Col du lacet | Parcours | O37 |
| `demo-biomes-paysages` | Tour des nouveaux paysages | Parcours | DB1 |
| `demo-japon` | Route des Érables | Parcours | DJ1 |
| `demo-recif` | Récif des tortues | Parcours | SM1 |
| `demo-volcan` | Volcan en flammes | Parcours | DB2 |
| `demo-biomes-sud` | Route du Sud | Parcours | DB3 |
| `demo-biomes-nord` | Route du Grand Nord | Parcours | DB3 |
| `demo-circuit` | Circuit des Prés | Accueil › Grand Prix | O38, GP13 |
| `demo-corniche` | Boucle de la Corniche | Accueil › Grand Prix | GP13b |
| `demo-vignes` | Route des Vignes | Accueil › Grand Prix | GP13b |
| `velodrome-250` | Vélodrome 250 m | Accueil › Vélodrome | VD10, GP13 |

Plus le pack « Cols célèbres », livré par le paquet (lot PK1, hors de cette liste). Recette seule (`--recette`) : `demo-biomes-tour`, `demo-biomes-gravel`, `demo-biomes-cote`, `demo-biomes-alpin`. Chez un joueur qui les a déjà, ces quatre parcours restent installés (décision du 13 novembre, rappelée au lot DB1) ; seuls ceux d'avant le lot O37 (générateur `make_biome_world`) sont enlevés.

## 3. Inventaire du 19 novembre (avant le code)

- Les sept démonstrations du générateur et le Col du lacet, générés comme sur un jeu neuf, puis toutes leurs valeurs texte relues : aucun « Fictif », aucun mot de banc, d'essai ou de recette ; seuls les identifiants de fichier et le nom du générateur (jamais affichés) sont techniques.
- Écart trouvé : les démonstrations n'avaient pas de fiche, alors que le vélodrome et les cols du pack en ont une (description sur la carte du parcours). C'était une exception, corrigée ici.
- Écart trouvé : le scénario de menus `parcours_demo` s'arrêtait après le volcan (fusions successives de DB1, DJ1 et DB3) : le Récif n'était pas cherché dans la liste, ni la Route du Sud, la Route du Grand Nord et le Vélodrome sur leur écran Prêt.
- Suivi : les cahiers O37, O38, SM1, SM2, DB1, DB2, DJ1 et DB3 et `docs/SUIVI_AVANCEMENT.md` disaient encore « en PR » ; ils sont tous fusionnés.

## 4. Réalisation

- `compiler/src/openride_compiler/demo_biomes.py` : `DEMO_LIBRARY` (fiche entière de chaque démonstration du jeu de base : description, et étiquette `grandprix` du circuit) remplace `DEMO_TAGS` ; `library_of(name)` ; la fiche est écrite dans le manifeste (`library`, champ facultatif du format 1.1 : aucune révision du format ni du contrat IPC). Descriptions reprises du guide d'utilisation.
- `core/src/openride_core/demo_world.py` : `DEMO_LIBRARY` du Col du lacet, écrite par `write_demo_world` (`write_world` et `build_manifest` acceptent une fiche) ; `engine/demo/demo.world/manifest.json` régénéré (seul fichier changé).
- Remplacement sans exception : une démonstration écrite par le générateur avec une autre fiche que celle d'aujourd'hui est remplacée par les contenus de départ (`biome_demo_outdated` compare la fiche entière, et non plus les seules étiquettes du lot GP13) ; le Col du lacet de même (`_demo_needs_rewrite`). Un parcours du joueur (autre générateur) n'est jamais touché. Chez le propriétaire, les sept démonstrations et le Col du lacet sont donc réécrits une fois, en quelques secondes, à la prochaine installation des contenus de départ ou au prochain lancement d'une séance (pour le Col du lacet).
- `engine/tests/menu_scenarios/parcours_demo.json` : liste complète (sept parcours libres, la description du Col du lacet sur la carte de détail), écran Prêt de chacun, Circuit des Prés par l'accueil › Grand Prix, Vélodrome par l'accueil › Vélodrome, absents de la liste générale ; une capture par écran Prêt.
- `core/tests/test_jeu_de_base.py` : le test qui verrouille la liste (§2), les fiches, les modes, et vérifie que `captures_demo.py` et `parcours_demo.json` suivent la même liste.

## 5. Tests

1. `core/tests/test_jeu_de_base.py` (nouveau) ; `test_biome_demo_world.py::test_game_set_has_library_fiche` ; `test_mode_routes.py` (circuit écrit entre GP13 et NT1 remplacé) ; `test_segments.py` (Col du lacet sans fiche remplacé).
2. Banc des menus `parcours_demo` joué dans le cloud (Xvfb, rendu Compatibility) : toutes les étapes passent ; seul le contrôle « rendu Forward+ » échoue faute de Vulkan dans le conteneur (attendu, il passe sur le PC).
3. Aucun changement du rendu ni du décor : pas de banc de performance à refaire (les planches low, medium et high de chaque démonstration ont été validées par leur lot).

## 6. Recette PC

```bash
cd ~/Games/lolo_python/Open_ride_linux
OUT=~/OpenRide/mesures/rNT1_$(date +%F_%H%M)
python3 engine/tests/menu_bench.py --scenario parcours_demo --scenario contenus --captures ecrans --native --out $OUT/menus
```

Environ 5 min, sans le propriétaire, HOME temporaire (aucun parcours réel touché). Attendu : 0 échec ; captures `parcours_liste` (description du Col du lacet sur la carte) et `pret_<id>` des neuf parcours. La planche va au propriétaire avant la fusion.

## 7. Livraison

En PR (19 novembre). Ensuite : J9a (chemins), qui embarque cette liste.
