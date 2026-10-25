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
