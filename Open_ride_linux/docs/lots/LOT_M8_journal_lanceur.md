# Lot M8 – Journal du lanceur sans terminal

## 1. Objectif

Lancé par le raccourci de bureau (lot L8, `Terminal=false`), le lanceur `openride` n'a pas de terminal : ses propres messages (relance de Godot, arrêt forcé, rappel de `recover`) et la sortie de Godot (non redirigée) sont perdus, et `~/run_trainer.log` est écrasé à chaque lancement : le journal de la séance précédente disparaît, alors que c'est souvent lui qu'on veut relire après une panne. Ce lot donne au lanceur un journal complet et tournant, signalé à faire lors du lot L8.

## 2. À lire

1. `docs/lots/00_INDEX.md`, `docs/lots/LOT_K6_lanceur_unique.md`, `docs/lots/LOT_L8_raccourci_bureau.md` (livraisons), `docs/SUIVI_AVANCEMENT.md` (« Améliorer la journalisation du lanceur sans terminal »).
2. Code : `core/src/openride_core/launcher.py` (`Supervisor`, `DEFAULT_LOG`, `_spawn`, `_start_core`, `_start_engine`, `say`), `core/src/openride_core/tools/log_report.py` (lit `~/run_trainer.log` par défaut, découpe par séance), `scripts/desktop/openride.desktop.in`.
3. Tests : `core/tests/test_launcher.py`, `core/tests/test_desktop_entry.py`.

## 3. Prérequis

Aucun.

## 4. Travail demandé

- **Un journal par lancement** dans `~/OpenRide/Logs/openride_AAAA-MM-JJ_HH-MM-SS.log` (dossier créé au besoin), qui reçoit :
  - la sortie du core (comme aujourd'hui) ;
  - la sortie de Godot, chaque ligne préfixée `[engine] ` (lue par un fil dédié ou un tube, sans bloquer la supervision) ;
  - les messages du lanceur (`say`), préfixés `[openride] ` et horodatés au même format que le core.
- **Compatibilité :** `~/run_trainer.log` devient un lien symbolique vers le dernier journal (remplacé à chaque lancement ; si un fichier ordinaire existe déjà, il est renommé `run_trainer.log.ancien` une seule fois). `log_report` sans argument continue donc de lire la dernière séance, sans modification.
- **Rotation :** on garde les 20 derniers journaux et au plus 200 Mo en tout ; les plus anciens sont supprimés au lancement.
- **Sans terminal :** quand la sortie standard n'est pas un terminal, `say` n'écrit que dans le journal ; avec un terminal, dans les deux.
- La variable d'environnement `OPENRIDE_LOG`, si elle est définie, garde son effet actuel : elle remplace le journal tournant, sans lien ni rotation.

## 5. Fichiers concernés

- **Modifiés :** `core/src/openride_core/launcher.py`, `core/tests/test_launcher.py`, `README.md` et `CLAUDE.md` (emplacement des journaux), `docs/SUIVI_AVANCEMENT.md` (case cochée, une ligne).
- **Interdits :** `log_report.py`, `scripts/desktop/` (lecture seule), l'engine.

## 6. Modifications de contrat autorisées

Aucune. Si `docs/SRS_v1.1.md` §11 (arborescence de `~/OpenRide/`) ne cite pas `Logs/`, l'ajouter.

## 7. Critères d'acceptation

1. `pytest -q` passe en entier dans `core/`.
2. Lanceur testé avec de faux core et engine (scripts Python courts, comme les tests existants) : le journal contient les lignes des deux, celles de l'engine préfixées, et les messages du lanceur.
3. `run_trainer.log` pointe vers le dernier journal après deux lancements ; un ancien fichier ordinaire est renommé, pas effacé.
4. 25 journaux factices présents : il en reste 20 après un lancement ; idem avec la limite de 200 Mo (fichiers creux).
5. Un engine qui écrit 10 000 lignes d'un coup ne retarde pas l'arrêt propre au-delà des délais actuels.
6. Sortie standard redirigée vers un fichier (pas un terminal) : aucun message en double.

**Sur le PC cible (le propriétaire) :** lancer par l'icône du bureau, quitter, puis `log_report` sans argument.

## 8. Hors périmètre

- Relance du core sans perdre la séance (supervision, lot G ou suivant).
- Journal structuré (JSON) du lanceur.

## 9. Livraison (24 octobre 2026)

- `launcher.py` : nouvelle classe `LogRotation` (dossier `~/OpenRide/Logs/`, lien `~/run_trainer.log`, 20 journaux, 200 Mo). `prepare()` supprime d'abord les plus anciens, de sorte qu'avec le nouveau journal il en reste 20 au plus et que les anciens pèsent 200 Mo au plus. Elle crée ensuite `openride_AAAA-MM-JJ_HH-MM-SS.log` (suffixe `_2` si deux lancements tombent dans la même seconde), puis remplace le lien de façon atomique (lien temporaire puis `os.replace`). Un `run_trainer.log` qui est un fichier ordinaire est renommé `run_trainer.log.ancien`. Si ce nom est déjà pris, le lien n'est pas posé et le journal le dit : rien n'est jamais effacé.
- `Supervisor` : le journal est ouvert sans tampon, en ajout. Le core y écrit directement, comme avant. La sortie de Godot passe par un tube lu par un fil dédié (`[engine] ` devant chaque ligne), vidé au plus 2 s après l'arrêt de l'engine. Les messages du lanceur (`_say`) prennent la forme `AAAA-MM-JJ HH:MM:SS,mmm INFO    [openride] …` : c'est le format du core, donc `log_report` les reconnaît. Ils ne s'affichent au terminal que si la sortie standard en est un, et les dernières alertes ne s'affichent qu'avec un terminal.
- `OPENRIDE_LOG` : fichier écrasé à chaque lancement comme avant, sans lien ni rotation (`rotation=None`).
- `log_report.py` et `scripts/desktop/` inchangés. SRS §11 : `Logs/` et le lien ajoutés à l'arborescence.
- Tests (`test_launcher.py`, +10) : critère 2 (lignes du core, de l'engine préfixées, du lanceur au format du core), critère 3 (lien après deux lancements, ancien fichier renommé), critère 4 (25 journaux → 20 ; 6 × 60 Mo creux → 3 gardés), critère 5 (10 000 lignes d'un coup, arrêt dans les délais, toutes au journal), critère 6 (sans terminal : rien sur la sortie standard, message présent une seule fois), `isatty` par pseudo-terminal, `OPENRIDE_LOG`.
