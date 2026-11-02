# Lot Y20 – Préchauffage du mode WTF et sons du Cyber-Rogue hors du fil principal

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série Y (rendu) : un exemplaire de chaque objet WTF dessiné hors de vue au début du mode ; synthèse des sons et de la musique du Cyber-Rogue sur un fil de travail | GDScript | Y19, WTF5, WTF6, R18 | Petite | **En PR** (2.0) ; banc PC à refaire en low, medium et high |

## 1. Objectif

Banc PC du 2 novembre (main 6f61a33e, plan « préchauffage généralisé ») :

- WTF, medium : premier tirage de la tornade 776 ms puis 155 ms, du fromage 310 ms puis 122 ms ; tirages suivants et autres gags ~35 à 52 ms. Construire les objets coûte moins de 25 ms (mesure cloud) : c'est le premier dessin de leurs matériaux.
- Cyber-Rogue : gel de ~3,1 à 3,3 s juste après RUNNING en low, medium et high, sur le fil principal. La synthèse des 25 sons et des 4 couches de musique prend ~0,7 s (mesure cloud) et se faisait sur ce fil, à la première trame du mode.

## 2. Spécification

| # | Règle |
| --- | --- |
| Y20-1 | `wtf_scene.gd` : dès que le mode WTF devient actif, `warm_up(camera)` pose sous la caméra, à 2 m devant elle et réduit à 1/2000, un exemplaire de chaque objet (`WARM_KINDS`) et d'un costume, éteint et allumé ; retirés après 3 images, une seule fois par instance. |
| Y20-2 | `rogue_audio.gd` : `prepare()` lance la synthèse sur `WorkerThreadPool` (fonctions statiques pures, aucun nœud touché) ; `_process` installe les flux et démarre la musique quand elle est finie. Les sons demandés avant sont notés mais pas joués. `threaded = false` garde l'ancien chemin. Les `.ogg` de l'utilisateur sont lus sur le fil principal. |

## 3. Fichiers

- `engine/scripts/wtf/wtf_scene.gd`, `engine/tests/unit/test_wtf_scene.gd` ;
- `engine/scripts/rogue/rogue_audio.gd`, `engine/tests/unit/test_rogue_host.gd`.

## 4. Critères d'acceptation

1. Cloud : `test_wtf_scene` et `test_rogue_host` passent.
2. PC, low, medium et high : premier tirage de la tornade et du fromage sous 60 ms ; gel du départ du Cyber-Rogue réduit d'au moins 0,5 s. Le reste du gel (scène, matériaux, environnement) est mesuré et fait l'objet d'un lot à part s'il dépasse 1 s.
