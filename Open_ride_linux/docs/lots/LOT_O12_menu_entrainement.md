# Lot O12 – Menu : plans d'entraînement, test de FTP et bibliothèque de parcours

## 1. Objectif

Rendre accessibles depuis le menu, au Click et au clavier, les ajouts côté core de la série O : la séance du jour d'un plan (O11), le test de FTP avec l'acceptation de la nouvelle FTP (O10), et la bibliothèque de parcours avec ses fiches, tris et filtres (O15). Les entraînements `.erg` et `.mrc` (O9) apparaissent dans la liste existante.

**Lot interne :** il ajoute des messages au contrat IPC (décision du propriétaire) et des écrans au menu de N6 ; recette visuelle au Click.

## 2. À lire

`docs/contracts/ipc_v1.md` (révision 1.1, ajouts de N13 et O4), cahiers N6, N13, O4, O9, O10, O11, O15 et leurs « Livraison » ; code : `menu_model.gd`, vues du menu de N6, `ipc_server.py`.

## 3. Prérequis

N6, O4 (même révision de contrat, l'un après l'autre), O10, O11 et O15 fusionnés ; chaque partie peut être livrée séparément si un prérequis manque.

## 4. Proposition de contrat (ajouts compatibles)

| Message | Sens | Champs |
| --- | --- | --- |
| `list_plans` / `plans` | engine → core / core → engine | plans : `id`, `name`, `weeks`, `active`, `error` ; plan actif : semaine, séance du jour, en retard, % fait |
| `start_plan`, `stop_plan` | engine → core | `id`, `start_date` |
| `start` (arguments ajoutés) | engine → core | `plan_day` (lance la séance du jour) ou `ftp_test` (`ramp` ou `20min`) |
| `summary` (champ ajouté) | core → engine | `ftp_test` : `{method, ftp_w, previous_ftp_w, warnings}` |
| `accept_ftp` | engine → core | — ; réponse `ack` ou `error` |
| `routes` (champs ajoutés) | core → engine | `stats` (distance, dénivelé, pente max, durée estimée, difficulté, montée principale) et `library` (`description`, `region`, `tags`) |
| `workouts` (champ ajouté) | core → engine | `unit` du `profile` : `ftp` (défaut) ou `watts` (`.erg`, O9) |

## 5. Travail demandé

- Accueil : entrée « Séance du jour » quand un plan est actif (nom, durée, TSS), sinon « Choisir un plan ».
- Écran « Plans » : liste, aperçu par semaine (durée, TSS), démarrer et arrêter un plan.
- Écran « Test de FTP » : choix rampe ou 20 min, explications courtes, lancement ; au bilan, « Nouvelle FTP : 262 W (avant 250 W) – Accepter / Garder » ; avertissements affichés.
- Bibliothèque : fiche du parcours sur l'écran « Prêt » (profil d'altitude, dénivelé, montée principale, durée estimée), tri et filtres au Click (cycle sur quelques choix fixes), étiquettes.
- Liste des entraînements : `.erg` et `.mrc` avec un aperçu juste (watts absolus).
- Tests : modèle du menu sans écran, core (messages), schémas, captures graphiques.

## 6. Critères d'acceptation

1. Toutes les suites passent (core, compilateur, engine sans écran, `run_e2e.sh`, tests graphiques).
2. Au Click : démarrer un plan, lancer la séance du jour, la finir, la voir comptée ; lancer une rampe simulée, accepter la nouvelle FTP, la retrouver dans les réglages (O4).
3. Filtrer les parcours « col » triés par dénivelé et lancer le premier.

**Sur le PC cible (le propriétaire) :** lisibilité à 2 m, une rampe réelle jusqu'à l'acceptation de la FTP.

## 7. Hors périmètre

- Saisie de texte (recherche par nom) : pas de clavier complet au Click.

## 9. Livraison

**Partie core, 27 octobre 2026** (thread « Développer les lots O restants », PR #395) ; **écrans de l'engine, 27 octobre 2026** (PR #396 ; lot interne, sans issue).

- Contrat : révision 1.3, décision du propriétaire du 27 octobre (tous les ajouts jusqu'à la v1.0.0 y entrent). Ajouts compatibles : commandes `list_plans`, `start_plan`, `stop_plan`, `accept_ftp` ; arguments `ftp_test` et `plan_day` de `start` ; message `plans` (`plans.schema.json`) ; `summary.ftp_test` ; champs `stats` et `library` des parcours ; `unit` des entraînements ; codes `plan_invalid`, `ftp_result_missing`, `ftp_result_doubtful`.
- Écarts avec la proposition du §4, pour la cohérence :
  - `accept_ftp` répond par `settings`, comme `set_setting`, au lieu d'un `ack` qui n'existe pas dans le contrat ;
  - `summary.ftp_test` donne `test` (le test dit la méthode) et `reliable` ; un résultat douteux demande `force` vrai, comme `--force` en ligne de commande ;
  - `workouts` : `profile` reste en fraction de la FTP (un engine plus ancien l'affiche juste) et `unit` = `watts` dit seulement d'afficher des watts ;
  - le profil d'altitude de l'écran « Prêt » vient du parcours chargé par `select_route`, pas d'une liste du contrat.
- Core : `ipc_lists.build_plans_message`, `plan_day_entry`, `route_stats_to_dict` ; `session.py` : `_choose_start_workout`, `_on_plan_command`, `_accept_ftp`, dossiers des plans réglables (`plans_dir`, `plan_state_path`, `activities_dir`) ; `plans.active_tag` prend les mêmes dossiers.
- Tests : `core/tests/test_menu_o12.py` (plans listés, démarrés, séance du jour lancée et marquée dans le journal ; test de FTP lancé depuis le menu, résultat au bilan, acceptation avec et sans `force` ; fiche des parcours ; unité des entraînements ; schémas).

**Écrans de l'engine :**

- Accueil (`menu_model.gd`) : après les modes, « Séance du jour : nom » (détail : durée, TSS, « en retard ») quand le plan actif a une séance à faire, sinon « Plan : nom » (semaine, % fait) ou « Choisir un plan » ; puis « Test de FTP ». `prepare_start()` prépare une séance démarrée avec des arguments de `start` (`plan_day` ou `ftp_test`) : écran Prêt (titre « Prêt : séance du jour (…) » ou « Prêt : test de FTP (…) »), en passant d'abord par les parcours sans monde choisi ; choisir un entraînement, la session libre ou une nouvelle séance l'annule.
- Écran « Plans » (`menu_flow.gd`, `list_plans` à l'ouverture) : séance du jour, suivi du plan actif (semaine, % fait, prochaine séance), « Arrêter le plan » (confirmé), puis la liste (plan invalide désactivé avec sa raison). Écran d'un plan : semaines et séances, « Démarrer ce plan aujourd'hui » (`start_plan`, remplacement d'un autre plan confirmé) ou « Arrêter ce plan ». Réponse `plans` et erreurs `plan_invalid`, `busy` sur la ligne d'état. Les listes redemandées après une séance (« Nouvelle séance ») comprennent `list_plans` : la séance faite est comptée.
- Écran « Test de FTP » : rampe ou 20 minutes avec une explication courte, conseil « sur une boucle » ; puis écran Prêt et `start` avec `ftp_test`. Au bilan : « Nouvelle FTP : 262 W (avant 250 W) » et les avertissements sur la ligne d'état, « Accepter 262 W » et « Garder 250 W » en tête ; `accept_ftp`, résultat douteux confirmé puis `accept_ftp` avec `force` ; la réponse `settings` met à jour les réglages (O4).
- Parcours (`catalog_model.gd`) : dénivelé dans le libellé, étiquettes en détail ; en fin de liste « Trier par : … » (nom, distance, dénivelé, difficulté, durée estimée ; croissant, comme `openride-core library --sort`) et « Étiquette : … » (toutes, puis chaque étiquette), en cycle par A long ; le focus reste dessus, + depuis le dernier élément revient au premier parcours. Écran Prêt : fiche du parcours (distance, dénivelé, pente max, difficulté, durée estimée ; montée principale ; région, étiquettes, description) au-dessus des choix (`menu_view.gd`).
- Entraînements en watts (`unit` = `watts`, .erg et .mrc) : détail « watts fixes, jusqu'à 300 W » à la FTP des réglages.
- `ipc_client.gd` : `list_plans`, `start_plan`, `stop_plan`, `accept_ftp`, signal `plans_received` ; `main.gd` : `start` avec ses arguments.
- Écart : pas d'aperçu par semaine (durée, TSS) sur l'écran d'un plan, le message `plans` ne le porte pas ; l'écran montre semaines et séances, et le suivi du plan actif (séance du jour, prochaine séance). L'accueil compte deux entrées de plus : les captures et `menu_bench.py` attendent « Choisir un plan » à la place de « Session simulée » dans la fenêtre de quatre éléments.
- Tests : `test_menu_model.gd` (accueil à huit entrées, `prepare_start`, tri renvoyé à menu_flow), `test_menu_flow.gd` (plans : choisir, démarrer, séance du jour, comptée, arrêter ; test de FTP : rampe, Accepter avec confirmation du résultat douteux, Garder, sans FTP calculable ; bibliothèque : filtre « col », tri par dénivelé, premier parcours lancé, fiche sur Prêt, entraînement en watts).
