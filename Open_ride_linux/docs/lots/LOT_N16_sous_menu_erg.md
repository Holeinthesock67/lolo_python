# Lot N16 – Sous-menu ERG : choisir, créer ou importer un entraînement

## 1. Objectif

Demande du propriétaire du 26 octobre : « Si on choisit le mode ERG il faudra un sous-menu pour configurer ou importer un exercice. » Ce lot complète « Session ERG » du menu principal (lot N15), au Click et au clavier, sans clavier complet ni souris.

**Lot interne, contrat IPC révision 1.2** (décision D4 de l'audit IPC, option 2, choisie par le propriétaire le 26 octobre) : l'engine n'écrit et ne lit aucun fichier. Il envoie `create_workout` (les sept paramètres), `list_imports` (réponse `imports`, en parties comme `routes`) et `import_workout` (`path` pris dans la dernière réponse `imports`) ; le core écrit dans `~/OpenRide/Workouts/` et répond `workout_saved` (`workout_id` final, `name`, `created`) ou `error` (`bad_args`, `busy`, `workout_invalid`, `workout_write_failed`). L'engine redemande ensuite la liste (`list_workouts`). Côté core : PR #288 (audit IPC).

## 2. Écrans

| Écran | Contenu |
| --- | --- |
| « Session ERG : entraînement » | « Sans entraînement (SIM) », les entraînements du dossier (`.zwo`, `.erg`, `.mrc`, durée), puis « Créer un entraînement (intervalles) » et « Importer un fichier (.zwo, .erg, .mrc) » ; ligne d'état sous le titre après une création ou un import |
| « Créer un entraînement » | Échauffement (0 à 30 min), répétitions (1 à 20), effort (15 s à 20 min, pas de 15 s), puissance de l'effort (50 à 200 % de la FTP), récupération, puissance de la récupération (30 à 100 %), retour au calme ; chaque valeur se règle sur l'écran de modification des réglages (lot O4 : + / −, appui long + pour garder, appui long − pour annuler) ; « Enregistrer et choisir » (détail : nom et durée totale) |
| « Importer un entraînement » | Fichiers `.zwo`, `.erg` et `.mrc` de `~/Téléchargements`, `~/Downloads`, `~/Bureau`, `~/Desktop`, `~/OpenRide/Import` et du dossier personnel (sans sous-dossiers), les plus récents d'abord (30 au plus), avec le dossier d'origine et « déjà importé » |

Création (écrite par le core) : le fichier `intervalles_<répétitions>x<effort en s>s_<puissance>.zwo` (par exemple `intervalles_5x240s_105.zwo`, nommé « Intervalles 5 × 4 min à 105 % ») contient un `Warmup`, un `IntervalsT` et un `Cooldown` en % de la FTP : il suit la FTP des réglages. Les mêmes réglages réécrivent le même fichier.

Import (par le core) : copie dans le dossier des entraînements ; le fichier est relu d'abord (invalide : `workout_invalid`, rien n'est écrit) ; le même fichier n'est pas copié deux fois ; un entraînement différent du même nom (toute extension, le core préférant `.zwo`, puis `.erg`, puis `.mrc`) n'est jamais écrasé : la copie prend le suffixe `_2`, `_3`…

Après `workout_saved`, retour à la liste, ligne « Créé : … » ou « Importé : … », focus sur le nouvel entraînement dès que la liste arrive ; un appui long + le choisit (puis écran « Prêt », ou liste des mondes si aucun n'est choisi).

## 3. Réalisation côté engine (26 octobre 2026)

- `engine/scripts/workout_builder.gd` (paramètres, bornes, nom et identifiant affichés) ; `ipc_client.gd` (`create_workout`, `list_imports` avec relances, `import_workout`, signaux `imports_received` et `workout_saved_received`) ; `menu_model.gd` (« Créer » et « Importer » en fin de liste) ; `menu_flow.gd` (écrans « Créer un entraînement » et « Importer un entraînement », `on_workout_saved`, erreurs du core sur la ligne d'état) ; `settings_view_model.gd` (écran de modification réutilisé, action `builder_set`) ; `main.gd`.
- Tests : `engine/tests/unit/test_workout_builder.gd` (12 vérifications : paramètres, bornes, nom et identifiant), `test_menu_flow.gd` (créer, modifier, create_workout, workout_saved, focus sur l'entraînement créé, list_imports, import, erreurs du core, fichier invalide), `test_menu_model.gd`, banc des menus `engine/tests/menu_bench.py`, parcours `erg` (vrai core : entraînement créé lu par le core et séance démarrée, fichier de `~/Téléchargements` importé puis proposé), à repasser avec le core de la D4.
- Reste (propriétaire) : essai au Click réel ; import d'un fichier GoldenCheetah ou Zwift réel (il reste sur le PC, jamais dans le dépôt).
