# Lot Y20 – Préchauffage du mode WTF et sons du Cyber-Rogue hors du fil principal

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série Y (rendu) : objets WTF et scène du Cyber-Rogue dessinés pendant l'écran d'attente du départ ; synthèse des sons et de la musique du Cyber-Rogue sur un fil de travail | GDScript | Y19, WTF5, WTF6, R18 | Petite | **En PR** (2.0) ; banc PC à refaire en low, medium et high |

## 1. Objectif

Banc PC du 2 novembre (main 6f61a33e, plan « préchauffage généralisé ») :

- WTF, medium : premier tirage de la tornade 776 ms puis 155 ms, du fromage 310 ms puis 122 ms ; tirages suivants et autres gags ~35 à 52 ms. Construire les objets coûte moins de 25 ms (mesure cloud) : c'est le premier dessin de leurs matériaux.
- Cyber-Rogue : gel de ~3,1 à 3,3 s juste après RUNNING en low, medium et high, sur le fil principal. La synthèse des 25 sons et des 4 couches de musique prend ~0,7 s (mesure cloud) et se faisait sur ce fil, à la première trame du mode.

## 2. Spécification

| # | Règle |
| --- | --- |
| Y20-1 | `wtf_scene.gd` : sur l'écran d'attente du départ d'une séance WTF (`main.gd`, menu en mode « wtf »), ou à défaut au premier état actif (départ immédiat), `warm_up(camera)` pose sous la caméra, à 2 m devant elle et réduit à 1/2000, un exemplaire des seuls objets mesurés (`WARM_KINDS` : fromage, vache, tornade) ; retirés après 3 images, une seule fois par instance. |
| Y20-3 | `rogue_host.gd` : en mode ROGUE, la scène entre dès que la trame porte `start_wait` (écran d'attente du départ) ; `rogue_scene.warm_up()` y pose un bout de ruban plat et un repère de chaque sorte, retirés au premier `state.rogue`. Départ annulé : la scène est retirée. |
| Y20-4 | Départ au pédalage d'une run Cyber-Rogue : l'engine envoie `scene_ready {"route_id": "rogue"}` quand la scène préchauffée a passé ses premières images (`start_wait_model.gd`) ; le core (`ROGUE_SCENE_ID`) attend cette scène avant de compter le pédalage, au plus `[depart] attente_decor_s` comme un décor. |
| Y20-2 | `rogue_audio.gd` : `prepare()` lance la synthèse sur `WorkerThreadPool` (fonctions statiques pures, aucun nœud touché) ; `_process` installe les flux et démarre la musique quand elle est finie. Les sons demandés avant sont notés mais pas joués. `threaded = false` garde l'ancien chemin. Les `.ogg` de l'utilisateur sont lus sur le fil principal. |

### Mesures de la première version (branche 2bbbf510, 2 novembre)

- Cyber-Rogue : gel ramené de 3,06–3,29 s à 2,31–2,41 s (sons hors du fil principal). Le reste ne vient d'aucun script minuté (tous sous 1 ms, `_enter` 9 à 11 ms) : premier dessin, d'où Y20-3.
- WTF : premier tirage de la tornade 54 à 62 ms et du fromage 43 à 47 ms, mais le préchauffage fait à RUNNING gelait l'image ~1,7 s + 0,4 s en roulant (+0,05 à +2,28 s). Il est donc déplacé sur l'écran d'attente (départ à −6,6 s).

### Mesures de la deuxième version (cca3dacb, 2 novembre)

- Cyber-Rogue : gel de 3,1 à 3,3 s commencé pendant l'attente, mais le core comptait déjà les 3 s de pédalage : RUNNING tombait dedans (fin 0,15 à 0,33 s après), d'où Y20-4.
- WTF : plus rien au-dessus de 100 ms dans les 5 s après RUNNING ; tornade 58 à 70 ms, fromage sous 50 ms. Mais préchauffer 17 objets gelait l'écran d'attente 2,1 s (low) à 7,9 s (high) : seuls les trois objets mesurés restent.

## 3. Fichiers

- `engine/scripts/wtf/wtf_scene.gd`, `engine/tests/unit/test_wtf_scene.gd` ;
- `engine/scripts/rogue/rogue_audio.gd`, `engine/scripts/rogue/rogue_host.gd`, `engine/scripts/rogue/rogue_scene.gd`, `engine/scripts/main.gd`, `engine/tests/unit/test_rogue_host.gd` ;
- `core/src/openride_core/session.py`, `core/tests/test_start_gate.py`, `docs/contracts/ipc_v1.md`.

## 4. Critères d'acceptation

1. Cloud : `test_wtf_scene` et `test_rogue_host` passent.
2. PC, low, medium et high : premier tirage de la tornade et du fromage sous 60 ms ; aucune image au-dessus de 100 ms dans les 5 s après RUNNING, en WTF comme en Cyber-Rogue ; les gels du préchauffage tombent pendant l'écran d'attente.

## 5. Suite : à-coups au départ (relevé du 4 novembre)

Défauts restants, à traiter ensemble (basse priorité, après la 1.0) :

- Cyber-Rogue : une image de 154 à 186 ms environ 0,2 s après RUNNING (suivi du préchauffage, #700).
- Séance sur route, high, demo compilée : une à deux images de 117 à 147 ms vers 23 à 24 s, cycliste encore à 0 m. Cause notée par la sonde : arbres des premières tuiles posés sur le fil principal (`arbres near:-1:0 33 ms`, `arbres near:0:0 32 ms`). Relevé du banc de #710 dans `/mnt/project-files/mesures/2026-11-04-saccades-40m/r710-fix/compilee_high_saccades.csv`.

Garde-fou : la ligne « à-coups : départ » de `perf_probe.py` (#710, bloc `hitches` de `perf_targets.json`) refuse toute image de plus de 150 ms entre la fin du chargement et 30 s, en low, medium et high. Le seuil se resserrera quand ces à-coups seront corrigés.
