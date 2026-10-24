# Lot L7 – Historique des séances : `openride-core history`

## 1. Objectif

Après plusieurs séances, rien ne permet de les retrouver ni de voir sa charge d'entraînement sans ouvrir chaque fichier. Ce lot ajoute une commande qui liste les séances enregistrées et cumule leurs chiffres par semaine, en réutilisant le bilan du lot K7. Elle servira aussi d'écran « Historique » au futur menu (G).

## 2. À lire

1. `docs/lots/00_INDEX.md`, `docs/lots/LOT_K7_bilan_seance.md` (livraison).
2. `docs/SRS_v1.1.md` §9 (dossiers : `~/OpenRide/Activities/` et son sous-dossier `.journal/`, noms `AAAA-MM-JJ_HH-MM_parcours.fit`) et §11 (arborescence).
3. Code : `core/src/openride_core/tools/session_summary.py`, `core/src/openride_core/journal.py` (`JOURNAL_DIR`, `read_journal`), `core/src/openride_core/__main__.py`, `core/src/openride_core/config.py` (FTP).

## 3. Prérequis

Aucun (K7 est livré). J1 modifie aussi `__main__.py` : fusionner l'un après l'autre.

## 4. Travail demandé

- `openride-core history [--dir DOSSIER] [--weeks N] [--ftp W] [--json]` :
  - liste les séances du dossier (défaut `~/OpenRide/Activities/`), de la plus récente à la plus ancienne : date, parcours, durée, distance, dénivelé, puissance moyenne et normalisée, TSS ;
  - une séance qui a à la fois un FIT et un journal n'apparaît qu'une fois (le FIT fait foi ; association par heure de début à ± 60 s) ; un journal sans FIT (plantage non récupéré) est listé avec la mention « à récupérer : openride-core recover » ;
  - cumul par semaine ISO (lundi à dimanche) des `N` dernières semaines (défaut 8) : nombre de séances, durée, distance, TSS ;
  - un fichier illisible est listé avec son erreur, sans arrêter la commande.
- **Cache :** les bilans sont mémorisés dans `~/.cache/openride/history.json` (clé : chemin, taille, date de modification) pour que la relance sur 200 séances soit rapide ; cache corrompu = recalcul, jamais d'erreur.
- Sortie texte alignée, ou `--json` aux clés stables documentées en tête du module.

## 5. Fichiers concernés

- **Nouveaux :** `core/src/openride_core/tools/history.py`, `core/tests/test_history.py`.
- **Modifiés :** `core/src/openride_core/__main__.py` (sous-commande `history`), `core/tests/test_docs_coherence.py` (si la liste des commandes y est contrôlée), `README.md`, `CLAUDE.md`, `docs/SUIVI_AVANCEMENT.md` (une ligne).

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `pytest -q` passe en entier dans `core/`.
2. Dossier de test avec 3 séances (FIT produits par le simulateur), dont une avec aussi son journal, et un journal orphelin : 4 lignes, l'orphelin marqué « à récupérer ».
3. Cumul : 2 séances la même semaine ISO et 1 la semaine d'avant donnent deux semaines aux bons totaux (TSS identique à la somme des `summary`).
4. Un fichier `.fit` tronqué apparaît avec son erreur ; le code de sortie reste 0.
5. Deuxième lancement sur 50 séances : moins de 10 % du temps du premier (cache), et cache effacé ou corrompu sans erreur.
6. `--json` : clés documentées présentes, valeurs numériques arrondies comme `summary`.

## 8. Hors périmètre

- Graphiques, export CSV, synchronisation avec un service en ligne (exclue par le SRS §9).
- Affichage dans l'engine (G).
