# Lot O29 – Thèmes, packs de biomes et packs de parcours depuis « Réglages › Contenus »

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Thèmes, packs de biomes et packs de parcours depuis « Réglages › Contenus » : pack « Cols célèbres » construit et compilé avec avancement, archives `.zip` de Téléchargements, thèmes installés, place disque | Python + GDScript | O25, O16, U15 | Moyenne | Audit des options du 31 octobre, accepté par le propriétaire ; en PR (après O25) |

## 1. Objectif

Audit des options du 31 octobre (`docs/AUDIT_OPTIONS_MENUS_2026-10-31.md`, §3.4 et §5), accepté par le propriétaire le 31 octobre : plus de `theme-install`, `theme-list`, `route-pack-install` ni `route-pack-build` à taper. Le lot complète l'écran « Réglages › Contenus » du lot O25 : même message `contents`, mêmes règles (jamais d'écrasement, une installation à la fois, hors séance).

## 2. Spécification

| # | Règle |
| --- | --- |
| O29-1 | **Pack « Cols célèbres »** (lot O16) : une ligne « à installer », « en partie installé » (cols refusés) ou « installé », avec sa taille une fois là. Il télécharge : confirmation d'abord, « Non » par défaut. Le core lance `route-pack-build cols_celebres --install`, compte l'avancement col par col (0 à 80 %), puis compile (`build-all`, 80 à 100 %) : les parcours arrivent dans la liste sans relancer. Compte rendu : « Pack installé : 15 col(s) sur 16, 1 refusé(s). » |
| O29-2 | **Archives trouvées** : les `.zip` des dossiers de l'import ERG (Téléchargements, Bureau, `~/OpenRide/Import`, dossier personnel), 12 au plus, les plus récentes d'abord. Une archive qui contient `theme.json` est un thème ou un pack de biomes (« Thème « Forêt » », installé par `theme-install`) ; une archive avec `pack.toml` est un pack de parcours (installé par `route-pack-install` puis compilé). Les autres `.zip` sont ignorés. Taille décompressée affichée ; rien n'est téléchargé. |
| O29-3 | **Thèmes et packs installés** : une ligne d'information par thème de `~/OpenRide/Themes` (nom de son `theme.json`, taille, dernière utilisation) et par pack de parcours installé ; une archive déjà installée n'a plus sa propre ligne. Un thème se choisit dans « Réglages › Graphisme » (inchangé). |
| O29-4 | **Taille et place disque** : la ligne ne porte que l'état (« à installer », « à télécharger », « installé ») ; la carte de détail du contenu sous le focus donne sa taille et « Place libre : 120 Go ; thèmes : 0,8 Go sur 5,0 Go » (plafond `[render] theme_library_gb`, qui reste géré par `theme-install`). |
| O29-5 | Un échec du compilateur s'affiche en rouge sur la ligne d'état avec son message (« archive refusée : … »). Sans compilateur, le pack des cols n'est pas proposé et une archive donne « compilateur absent ». |
| O29-6 | Le core ne dépend pas du compilateur : il l'appelle en sous-processus (`launch_compile.compiler_base_cmd`), comme la compilation au lancement. |

**Avec O23 (import de traces, fil du monde ouvert) :** O23 garde l'import des traces GPX une par une (et leur fiche). Si O23 passe par le même écran, il y ajoute des éléments de `contents` d'un nouveau `kind` ; l'engine affiche déjà tout `kind`. Aucune adresse `https://` n'est proposée : le dépôt n'a pas de pack de biomes publié (la recette `docs/3.0/PACK_BIOMES_CC0.md` le fabrique hors du dépôt).

## 3. Contrat

`docs/contracts/ipc_v1.md`, révision 1.5 : valeurs `route_pack` et `theme` de `contents.items[].kind`, identifiants `routes:<pack>`, `archive:<n>` et `theme:<nom>`, champs facultatifs `disk_free_mb`, `themes_mb` et `themes_max_mb`. Aucun nouveau message ni nouvelle commande.

## 4. Fichiers

- Core : `contents.py` (pack des cols, archives, thèmes installés, place disque, appels au compilateur), `launch_compile.py` (`compiler_base_cmd`), `session.py` (dossiers passés au service).
- Engine : `contents_view_model.gd` (tailles en Mo et Go, ligne de la place disque).
- Tests : `core/tests/test_contenus_packs.py` (faux compilateur, sans réseau), `engine/tests/unit/test_contents_view_model.gd`, scénario `engine/tests/menu_scenarios/packs.json` du banc des menus (archive d'un thème construite par la nouvelle clé `archives`, installée par le vrai compilateur ; pack des cols refusé à la confirmation, rien n'est téléchargé).
- Docs : contrat et schéma `contents`, guide d'utilisation (« Thèmes » et « Packs de parcours » passent par le menu).

## 5. Critères d'acceptation

1. `pytest -q` dans `core/` : liste (pack, archives, thèmes, place), construction du pack avec avancement et compilation, installation des deux sortes d'archives, erreur du compilateur, compilateur absent.
2. Tests Godot de l'écran : tailles, place disque, thème installé non choisissable.
3. Captures de l'écran montrées au propriétaire avant la fusion.

**Sur le PC (via le fil de fusion, réseau nécessaire) :** installer le pack « Cols célèbres » depuis le menu, vérifier l'avancement, l'Alpe d'Huez dans la liste des parcours sans relancer.
