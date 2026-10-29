# Lot X41 – Banc visuel du mode Cyber-Rogue

## 1. Objectif

Les tests de la série R vérifient la scène du mode par morceaux (modèles sans écran, `test_rogue_host.gd`, rendu de la charte R17). Aucun test ne regardait une run entière telle que l'engine la dessine, de l'échauffement au bilan. Le fil de la série R a proposé cet outil le 28 octobre (outil 2). Le banc rejoue la trace d'une vraie run du core (lot X40) dans la vraie scène, prend des captures aux moments clés et vérifie l'image et ce que la scène affiche. Les captures servent aussi au contrôle visuel des lots R10 à R13 sur le PC.

## 2. À lire

`engine/tests/visual_check.py` (faux core, capture `_test`, rapport HTML), `engine/scripts/rogue/rogue_host.gd` et `rogue_scene.gd`, `engine/scripts/main.gd` (`_test_screenshot`), le cahier X40 et `docs/contracts/ipc_v1.md` (objet `rogue`).

## 3. Travail demandé

- **`python3 engine/tests/rogue_bench.py --godot GODOT [--objective threshold|endurance|vo2max] [--seed 5] [--trace F.jsonl] [--size 1280x720] [--quality low] [--speed 20] [--native] [--out DOSSIER]`**.
- Sans `--trace`, le banc joue d'abord la run dans la vraie séance du core (`rogue_bout_en_bout --trace`, lot X40). Il lance ensuite `main.tscn` en `--test-mode`, sous Xvfb ou à l'écran, et rejoue la trace face à un faux core, `--speed` fois plus vite. Les messages `room` et `loot` partent avant les trames qui s'y rapportent, comme avec le vrai core.
- **Moments capturés :**
  - l'échauffement ;
  - chaque salle à 120 m de son début ;
  - la pause ;
  - le couloir avec ses cartes ;
  - le boss ;
  - le retour au calme ;
  - les résultats ;
  - le bilan.

  À chaque moment, la trame est figée 1,5 s, puis la capture est demandée.
- **Côté engine :**
  - `rogue_scene.test_info()` et `rogue_host.test_info()` décrivent ce qui est affiché : salle, ruban, repères, Firewall, ennemi et son archétype, écran de couloir, hologramme, jauges, bandeau, demandes de resynchronisation ;
  - la ligne `screenshot` du mode test les porte sous `rogue`.
- **Vérifications par capture :**
  - taille de l'image ;
  - image ni noire ni uniforme ;
  - bandeau sans message d'erreur ;
  - scène du mode active pendant la run et quittée au bilan ;
  - néons dessinés ;
  - en salle et au boss : salle affichée = salle de la trame, ruban, repères, Firewall et ennemi ;
  - hologramme du HUD pendant la run ;
  - écran des cartes au couloir ;
  - menu de pause et menu de bilan.
- **Vérifications sur la run :**
  - tous les moments sont capturés ;
  - deux salles de suite ne donnent pas la même image ;
  - aucune demande `rogue_resync` ;
  - journal Godot sans erreur ni avertissement de script.
- **Sortie :**
  - une ligne [OK] / [ÉCHEC] par vérification ;
  - `rapport.html` (planche des captures et tableau), les PNG, `trace.jsonl` et `engine.log` ;
  - codes de sortie 0, 1 si une vérification échoue, 2 si Godot ou xvfb-run manque.

## 4. Fichiers

- **Nouveaux :** `engine/tests/rogue_bench.py`, ce cahier.
- **Modifiés :**
  - `engine/scripts/rogue/rogue_scene.gd` et `rogue_host.gd` (`test_info`) ;
  - `engine/scripts/main.gd` (ligne `screenshot`) ;
  - corrections du §7 (`rogue_sound_model.gd`, `session.py`, `rogue/mode.py` et leurs tests) ;
  - `.github/workflows/openride.yml` (étape du banc) ;
  - `docs/OUTILS_DE_TEST.md`, `00_INDEX.md`.

## 5. Critères d'acceptation

1. La run de référence (threshold, 30 min, graine 5) passe toutes les vérifications au cloud, sous Xvfb, en moins de 5 min.
2. Un défaut d'affichage, comme une salle non montrée, une erreur de script ou un bandeau d'erreur, fait échouer le banc et le nomme.
3. Le banc tourne dans la CI de l'engine. Il garde son rapport en artefact quand il échoue.

## 6. Hors périmètre

Le jugement esthétique et la lisibilité à l'effort restent au contrôle visuel du propriétaire sur la GTX 1060, avec les captures du banc. Les performances du mode relèvent de X19.

## 7. Livraison

Livré le 28 octobre (branche `claude/project-thread-818r6t-x41`, issue #544).

- **Défauts trouvés à la mise en service et corrigés :**
  - **Le son de victoire du boss n'était jamais joué.** Dans la trame qui porte `room_won`, le core a déjà quitté la salle : `archetype` vaut `null` et la phase est déjà la suivante. `rogue_sound_model.gd` lisait `String(archetype)`, ce qui provoquait une erreur de script à chaque salle gagnée. Les autres sons de la trame étaient perdus, et la fanfare du boss ne sortait jamais. Le modèle se fie désormais à la phase de la trame précédente (`BOSS`). Son test rejoue les trames telles que le core les envoie.
  - **Bandeau « Parcours « rogue » introuvable » à chaque run.** Le core envoyait `route_id = "rogue"`, alors que le contrat IPC demande `null` en mode `ROGUE`. L'engine cherchait donc `rogue.world` et affichait une erreur pendant toute la run et au bilan. La trame porte maintenant `null`. Le journal garde « rogue » (`rogue_mode.JOURNAL_ROUTE_ID`), ce qui assure la reprise après un plantage et l'export FIT.
- **Mesuré au cloud :** 77 vérifications sur 77. La run threshold de 30 min donne 9 captures (2 salles, boss, couloir) en 3 min environ, sous Xvfb et en OpenGL logiciel.
- **Constats à trancher par la série R** (vus sur les captures, non bloquants pour le banc) :
  - en vue subjective, l'hologramme et la ligne des jauges se superposent au centre de l'écran et se lisent mal ;
  - le HUD classique reste affiché pendant la run, y compris le profil d'altitude du parcours de démo ;
  - au couloir, les cartes et les portes recouvrent le profil, et les portes sont coupées en bas de l'écran en 1280×720.
