# Lot ML2 – Lag de la liste des parcours pendant le chargement du décor de fond

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Lag restant de la liste des parcours (banc rML2) : mesure à chaud des caches de rendu, touche simulée sans blocage, longue liste et sonde au banc des menus | GDScript, Python | ML1, W22 (livrés) | Petite | **Livré le 20 novembre** (PR #934) |

## 1. Objectif

Suite du lot ML1 (#897) et de W22 (#906). Le banc rML1 du 15 novembre voyait la liste des parcours à ~10 images/s
pendant les 30 à 45 s du chargement du parcours de fond. Avant de coder : confirmer sur main ce qui reste, puis le
supprimer.

## 2. Constat (banc rML2 du 17 novembre, main c40b044e, low, medium et high)

- Une fois le décor chargé, la liste tient 52 à 54 images/s, mais chaque pas dans la liste donne une image de
  140 à 150 ms (p99 143 ms dans toutes les lignes `[perf-rendu]`), cause « inconnue » dans `saccades.csv`.
- Au démarrage, l'engine ne rend aucune image pendant ~15 s (aucune ligne de la sonde de 6,5 à 21,9 s, « engine muet
  13 s »), puis des images de 1 à 4 s (CPU de la vue 4 354 ms, 1 155 ms) et le préchauffage des cyclistes du décor
  (~1 s).
- La sonde mesure avec le `delta` de Godot, plafonné : « 133-150 ms » veut dire « au moins 133 ms » (fil global
  « pire image »).

## 3. Causes (mesures à l'horloge au cloud, Godot 4.7.2, rendu logiciel, mêmes étapes que rML2)

1. **Image lente à chaque pas : l'outil de banc lui-même.** Le message de test `key` tenait la touche par
   `OS.delay_usec(hold_ms)` sur le fil principal : 150 ms d'image figée à chaque appui court, 1,1 s à chaque appui
   long. Le dépouillement de `ipc_client._process` par message le montre : « _test key » 151 ms à chaque pas, le reste
   du menu (traitement de l'appui 0,1 ms, mise à jour de l'affichage 0,3 à 10 ms, bip 0,6 ms) est négligeable. Le jeu
   (Click, clavier réel) n'a pas ce défaut.
2. **Gel du démarrage : compilation des shaders et des pipelines à froid.** Tout le temps perdu est entre
   `frame_pre_draw` et `frame_post_draw` (13,6 s puis 18,5, 19,7 et 14,7 s au cloud). Le banc donne à chaque passage
   un HOME neuf : les caches de rendu (`~/.local/share/godot/app_userdata/OpenRide Engine/shader_cache` et `vulkan`,
   `~/.cache/nvidia`, `~/.cache/mesa_shader_cache`) sont vides, et chaque banc mesure un tout premier lancement.
   Même scénario avec les caches du passage précédent : 102 s → 43 s, engine muet 12,5 → 3,0 s, plus de gel de
   plus de 4,1 s au cloud. Le jeu garde ces caches d'un lancement à l'autre : seul le premier lancement (et le
   premier après une mise à jour de Godot, du pilote ou des shaders) les paie.

## 4. Correction

- `main.gd`, `_test_key` : la touche simulée ne bloque plus l'image ; l'attente se compte à l'horloge pendant que les
  images continuent. Le relâchement est classé avec la durée demandée (`key_map.pressed_at` + `hold_ms`), comme avant
  même à 1 image/s sous Xvfb ; les messages de test reçus pendant l'appui attendent le relâchement, dans l'ordre (même
  séquence qu'avant pour les bancs).
- `main.gd` : étapes de la sonde `menu appui …`, `menu affichage <écran>` et `bip …` dans `saccades.csv`.
- `menu_bench.py` :
  - `--caches-rendu DOSSIER` : caches de rendu repris de DOSSIER au départ et rangés dedans à la fin (démarrage à
    chaud, comme le jeu) ; sans l'option, HOME neuf, démarrage à froid comme avant ;
  - `--sonde` : sonde de performance de l'engine (`sonde/moteur.csv`, `saccades.csv`, `taches.csv`) de chaque passage ;
  - en-tête de scénario `parcours_copies: N` : N copies de la démo (« Copie 01 »…), parcours libres ;
  - scénario `liste_parcours` : démo et 20 copies, 12 pas vers le bas puis 12 vers le haut, une seconde entre deux,
    pendant puis après le chargement du décor de fond (remplace le scénario local `ml1_parcours` du PC).

Hors lot : le préchauffage des cyclistes du décor (~1 s d'un bloc au chargement) et la compilation à froid du tout
premier lancement relèvent du fil global « pire image » (préchauffage unique au chargement, cache des pipelines).

## 5. Tests

- `core/tests/test_menu_bench_ml2.py` : copies de la démo, aller-retour des caches de rendu (rien du profil n'est
  copié), options et scénario présents.
- Banc des menus au cloud, voie clavier, caches gardés : `liste_parcours`, `reglages`, `pause` au vert (appuis courts
  et longs) ; `parcours_demo` bute sur le compilateur absent de la machine, sans lien avec le lot.

## 6. Recette sur le PC

Pour chaque qualité (low, medium, high), scénario `liste_parcours`, avec la sonde :

```bash
cd /home/utilisateur/Games/lolo_python/Open_ride_linux
for q in low medium high; do
  for passage in froid chaud; do   # 1er passage : caches vides (à froid), qu'il remplit ; 2e : à chaud, comme le jeu
    python3 engine/tests/menu_bench.py --scenario liste_parcours --voies clavier --qualite $q --sonde \
      --caches-rendu ~/mesures-ml2/caches-$q --out ~/mesures-ml2/$passage-$q
  done
done
```

Attendu : plus d'image de 140-150 ms à chaque pas de la liste (saccades « inconnue » alignées sur les appuis) ; à
chaud (`chaud-*`), plus de silence de 15 s au démarrage. Donner aussi les images de plus
de 50 et 100 ms et leur instant. Budgets GPU 8, 13 et 16 ms inchangés.

## 7. Livraison

Fusionné le 20 novembre 2026 (PR #934 : touche simulée sans blocage, caches de rendu et sonde au banc des menus). Détail des écarts et de la recette : description de la PR.
