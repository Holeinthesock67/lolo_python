# Lot PI2 – Préchauffage unique, une étape par image dès le menu

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Pire image (fil global du 17 novembre, étape 3) : un seul plan de préchauffage lancé dès le chargement du parcours, une étape par image, et le départ attend la fin du plan | GDScript | PI1, Y5, Y19, Y20, Y21, AS7 | Petite | En cours (codé le 20 novembre, banc PC à faire) |

## 1. Objectif

Le banc rPI1 (19-20 novembre) a mesuré environ 25 s de gel du fil principal au chargement, dans tous les modes et en low, medium et high. La première image, de 14 s, tombe pendant le préchauffage des cyclistes du décor. Avant ce lot, `main.gd` faisait tous les préchauffages dans la **même image**, à la fin de `_poll_route_job` : portiques, spectateurs, passants, cyclistes du décor et forêts lointaines. Le WTF préchauffait de son côté, sous l'écran d'attente.

Le propriétaire a demandé le 20 novembre que le préchauffage vienne plus tôt, et non à la fin du projet.

## 2. Spécification

| # | Règle |
| --- | --- |
| PI2-1 | `warmup_plan.gd` : une liste d'étapes `[nom, Callable]`. `start(étapes)` remplace le plan (un nouveau parcours abandonne les étapes non jouées), `add(nom, Callable)` ajoute une étape à la fin, `step()` joue **une étape par image**, `pending()` compte les étapes restantes. Une étape dont le nœud a été libéré est sautée. |
| PI2-2 | `main.gd` remplit le plan dès que le parcours est chargé, donc dans le menu : portiques (avec celui d'élimination si le mode Dernier survivant est préparé), spectateurs, passants, cyclistes du décor (s'il y en a au préréglage), forêts lointaines. Chaque compilation de shaders tombe ainsi dans son image, et le menu reste animé entre deux. |
| PI2-3 | Mode WTF : le préchauffage des gags devient une étape du même plan, ajoutée sous l'écran d'attente du départ. |
| PI2-4 | Le départ attend la fin du plan : `pending()` s'ajoute aux tuiles en attente dans `start_wait_model.frame`, avant `scene_ready`. |
| PI2-5 | Chaque étape est notée dans la sonde (étape « préchauffage » et son nom, cause d'une saccade), et le journal de l'engine écrit « Préchauffage fini (ms) : portiques …, spectateurs …, … ». La phase de chargement `prechauffage_plan` remplace les trois phases `prechauffage_*` de PI1-9. |
| PI2-6 | Hors de ce lot : le Grand Prix (objets et effets préchauffés à sa première trame, sous son nœud qui reste caché hors du mode) et le Cyber-Rogue (scène créée sous l'écran d'attente) gardent leur préchauffage ; leurs pires images mesurées ne sont pas des compilations (Z du GP sans pipeline, banc rPI1). Le cache des pipelines sur disque est déjà gardé par le banc en mode chaud (PI1-8) ; le premier lancement à froid relève de l'installateur (J9). |

## 3. Fichiers

- `engine/scripts/warmup_plan.gd`, `engine/tests/unit/test_warmup_plan.gd` ;
- `engine/scripts/main.gd` (`_warmup_steps`, `_poll_route_job`, `_step_start_wait`, attente du WTF).

## 4. Critères d'acceptation

1. Cloud : `test_warmup_plan.gd`, les tests de l'engine et le bout en bout passent.
2. PC, branche et main, en low, medium et high, caches de shaders froids puis chauds (`sim_bench.py --shaders froid|chaud`) : fumée demo, ERG avec demi-tour, `grand_prix`. Le gel du chargement (somme et pire image avant le départ) baisse, chaque étape « préchauffage » est une image à elle, et le délai jusqu'à `scene_ready` est donné.
