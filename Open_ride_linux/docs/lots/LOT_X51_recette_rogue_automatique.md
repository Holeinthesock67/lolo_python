# Lot X51 – Partie automatique de la recette du Cyber-Rogue

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série X (outils de test) : partie automatique de la recette du Cyber-Rogue : `rogue_recette` (calendrier, IF et FIT ; abandon ; Click coupé 30 s ; core tué puis relancé), niveaux et aigus des sons (`test_rogue_sound_levels.gd`, sons ramenés sous le vent), page d'écoute `rogue_ecoute.py`, galerie low/medium/high `rogue_galerie.py` | Python, GDScript | X40, X41, R14, R18 | Petite | Livré le 30 octobre (PR #620) |

## 1. Objectif

Demande du propriétaire du 30 octobre : automatiser une partie de la recette du mode Cyber-Rogue (fiche R14, écoute R18, contrôle visuel R10 à R13, charte R17). Ce lot fait vérifier par des bancs, sans vélo, tout ce qui ne demande ni le ressenti ni le vrai matériel. Il prépare aussi deux pages qui réduisent l'écoute et le regard du propriétaire à quelques minutes. Ce qui touche à la consigne et à la résistance du trainer reste à la main sur le vélo (règle du propriétaire du 29 octobre), comme le délai du frein R0.

## 2. À lire

`docs/lots/LOT_R14_recette.md` (§4.1, fiche des 10 essais), `LOT_R18_bruitages_rogue.md` (principe « doux d'abord », §4.1), les cahiers X40 (`rogue_bout_en_bout`) et X41 (`rogue_bench.py`), `core/src/openride_core/tools/fit_check.py` (lot X11).

## 3. Travail demandé

### 3.1 Essais de la fiche R14 dans la vraie séance du core

- **`python -m openride_core.tools.rogue_recette [--essai calendrier|abandon|click|plantage|tous] [--seed 5] [--profil moyen] [--json]`**. Chaque essai joue une run dans `CoreSession`, en temps accéléré, avec le cycliste simulé du lot X40 sur le trainer simulé.
- **calendrier** (essais 2, 3, 4 et 10) : endurance 30 min, seuil 45 min et VO2max 45 min.
  - IF de la run (au centième) dans la plage de l'objectif (R7 §4.3) : 0,62–0,72, 0,80–0,88 ou 0,80–0,90.
  - Boss atteint à ± 1 min du calendrier prévu.
  - Résultats à ± 1 min de la durée choisie.
  - FIT décodé par le SDK officiel de Garmin, sans échec de `fit-check`, avec un tour par salle et par phase du boss.
- **abandon** (essai 8) : Y dans la première salle, puis « Terminer » depuis la pause. Bilan `abandoned`, FIT lisible, ligne `rogue_run` abandonnée au journal.
- **click** (essai 6) : le Click se coupe 30 s pendant le combat d'une salle. La séance signale le Click perdu et le Firewall ne bouge plus. Il repart au retour du Click, et la run va jusqu'aux résultats.
- **plantage** (essai 7) : le core est tué au milieu de la deuxième salle. Seul ce qui est déjà écrit sur le disque reste du journal. Relancé, le core reprend en pause (`core_restarted`) au début de la même salle. Il repart sur `resume` et finit la run dans le même journal, avec un FIT lisible.

### 3.2 Sons du mode

- **`engine/tests/unit/test_rogue_sound_levels.gd`** mesure chaque son et la musique au niveau joué avec les réglages par défaut :
  - Niveau court terme (fenêtre de 100 ms la plus forte) sous celui du vent à 60 km/h (boucle de `sound_player.gd` à `WIND_MAX_DB`).
  - Au plus 10 % de l'énergie au-dessus de 4 kHz (passe-haut du 2e ordre, deux passes).
  - Les deux mesures sont elles-mêmes vérifiées sur des sinus.
- **`engine/tests/rogue_ecoute.py --godot GODOT [--out DOSSIER]`** écrit une page d'écoute autonome (`ecoute.html`, sons inclus, exportés par `tests/rogue_sound_export.gd`). Elle contient :
  - une scène de salle de 20 s (vent à 35 km/h, deux couches de musique, bruitages d'une salle) ;
  - le vent à 30 et 60 km/h ;
  - la musique du boss ;
  - chaque son avec son événement et sa description, lus dans le tableau §4.1 de R18.

### 3.3 Galerie des captures

- **`engine/tests/rogue_galerie.py --godot GODOT [--qualites low,medium,high] [--native] [--out DOSSIER]`** joue une seule run (trace X40) et la fait rejouer par `rogue_bench.py` à chaque qualité.
- La page `galerie.html` met les captures d'un même moment sur une ligne, avec une colonne par qualité. Elle donne aussi le verdict du banc de chaque qualité et les cinq questions du contrôle visuel (R10, R11, R12, R13, R17).

## 4. Constats à la mise en service (30 octobre)

- **Sons trop forts :** le niveau de départ bas de R18 (−18 dB) n'était pas appliqué. 20 sons sur 25, ainsi que la musique du boss, dépassaient le vent à 60 km/h (−22,8 dB), jusqu'à −14,8 dB pour la défaite. Correction : `MODE_DB = −12 dB` sur tous les lecteurs du mode (`rogue_sound_model.gd`, `rogue_audio.gd`). Avec le bus RogueSfx à 70 %, les bruitages sont à −18 dB du plein niveau, entre −26,8 et −40,7 dB. La musique est à −31,9 dB.
- **Deux sons trop aigus :** le piratage avait 24 % de son énergie au-dessus de 4 kHz, et la relance de carte 35 %. Leur bruit est filtré comme celui du bouclier touché (coefficient 0,15) : ils passent à 6 % et 8 %. Durées, crêtes et déterminisme sont inchangés (`test_rogue_sound_synth.gd`).
- **Firewall trop faible** (écoute du propriétaire, 30 octobre) : le ronflement n'avait que 50 et 100 Hz, peu rendus par des enceintes de PC. On ajoute des harmoniques à 150 et 200 Hz, et `HUM_MAX_DB` passe de −6 à 0 dB au contact : −28,6 dB, toujours sous le vent.
- **IF du seuil 45 min :** 0,80 avec la graine 5 (0,7998), et 0,81 en moyenne sur 60 runs de `rogue_sim`. Le calendrier tient au bas de la plage. À juger au ressenti sur le vélo, sans retouche ici.

## 5. Fichiers

- **Créés :**
  - `core/src/openride_core/tools/rogue_recette.py`, `core/tests/test_rogue_recette.py` ;
  - `engine/tests/unit/test_rogue_sound_levels.gd`, `engine/tests/rogue_sound_export.gd`, `engine/tests/rogue_ecoute.py`, `engine/tests/rogue_galerie.py`.
- **Modifiés :**
  - `rogue_bout_en_bout.py` : `new_session` et `bot_step` partagés ;
  - `rogue_sim.py` : `normalized_power` ;
  - `rogue_sound_model.gd`, `rogue_audio.gd`, `rogue_sound_synth.gd` ;
  - les cahiers R14 et R18, `00_INDEX.md` et `SUIVI_AVANCEMENT.md`.

## 6. Critères d'acceptation

1. `rogue_recette --essai tous` passe (code 0) en moins de 30 s, et `pytest core/tests/test_rogue_recette.py` passe. Les tests vérifient aussi qu'un Firewall qui roule sans Click et qu'une reprise au milieu de la salle font échouer l'essai.
2. `test_rogue_sound_levels.gd` passe dans la suite de l'engine.
3. `rogue_ecoute.py` et `rogue_galerie.py` produisent leur page dans le cloud (Xvfb) ; la galerie se refait sur la GTX 1060 avec `--native`, en low, medium et high.

## 7. Reste au propriétaire

- **Sur le vélo**, en deux blocs de 10 min :
  - le ressenti de la surchauffe, des bosses et de la difficulté ;
  - les vrais appuis sur le Click (essai 5) ;
  - la tenue du seuil.
- **À part :** l'essai du délai du frein R0.
- **Sans vélo :**
  - l'écoute sur la page (environ 3 min) ;
  - le regard sur la galerie et l'accord sur la charte R17 ;
  - l'import d'un FIT de démonstration dans Garmin Connect et GoldenCheetah (essai 10).

## Livraison

PR #620, fusionnée le 30 octobre 2026. Statut remis à jour par la passe documentaire du 1er novembre, d'après les PR fusionnées ; statut précédent : « Demande du 30 octobre ; en PR ».
