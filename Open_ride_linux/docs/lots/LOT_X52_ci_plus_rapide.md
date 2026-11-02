# Lot X52 – CI plus rapide sur les demandes de fusion

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série X (outils de test) : CI plus rapide sur les PR : plus de nombre de tests écrit dans la doc (compte par `recompte_tests.py`, affiché dans le résumé du run), une seule colonne Python (3.14) sur les PR et les deux sur `main`, filet de compilation 3.11 | YAML + Python | X34 | Petite | Livré le 30 octobre (PR #630) |

## 1. Objectif

Le 30 octobre, la file de la CI était saturée et chaque fusion forçait à remettre à jour toutes les PR ouvertes. Le propriétaire a validé deux changements, avec un filet sur `main`.

1. Les nombres de tests écrits dans `README.md` et `docs/SUIVI_AVANCEMENT.md` changeaient à chaque fusion. Les autres PR entraient alors en conflit ou échouaient à `test_docs_coherence`, puis repassaient toute la CI.
2. Chaque PR lançait deux colonnes Python complètes (3.11 et 3.14, environ 28 min chacune) en plus de Godot.

Écarté : sauter Godot ou Python selon les dossiers modifiés, à cause des liens cachés (docs ou scripts qui cassent des tests du core).

## 2. Spécification

| # | Règle |
| --- | --- |
| X52-1 | La doc n'écrit plus de nombre de tests. `scripts/recompte_tests.py` les compte (core et compilateur collectés par pytest, fichiers de tests unitaires et de rendu de l'engine). `--resume F` ajoute le tableau à `F`. `--verifier` sort en code 1 si `README.md` ou le suivi écrit encore un nombre. `test_docs_coherence` et `test_recompte_tests` le vérifient. |
| X52-2 | Chaque run de la colonne 3.14 écrit le tableau des nombres de tests dans son résumé (`$GITHUB_STEP_SUMMARY`). |
| X52-3 | Sur une demande de fusion : une seule colonne Python, 3.14 avec `constraints.txt` (pas de dérive des dépendances qui ferait échouer une PR sans rapport). Filet : tout le code Python est compilé par Python 3.11 (`compileall`), ce qui attrape une syntaxe trop récente en quelques secondes. |
| X52-4 | Sur `main`, sur demande et chaque lundi : les deux colonnes 3.11 et 3.14, comme avant. Godot et le scan de confidentialité tournent toujours, sur les PR comme sur `main`. |

## 3. Fichiers

- `.github/workflows/openride.yml` ;
- `scripts/recompte_tests.py`, `core/tests/test_recompte_tests.py`, `core/tests/test_docs_coherence.py` ;
- `README.md`, `docs/SUIVI_AVANCEMENT.md`, `docs/OUTILS_DE_TEST.md`, `docs/PLAN_DE_TESTS.md`, `CLAUDE.md`.

## 4. Critères d'acceptation

1. Une PR qui ajoute un test ne touche plus ni le README ni le suivi, et ne met plus les autres PR en conflit.
2. Sur une PR, la CI lance `python (3.14)`, `engine (Godot 4.7)` et `scan` ; sur `main`, `python (3.11)` en plus.
3. Le résumé du run de la colonne 3.14 montre le tableau des nombres de tests.

## 5. Gain attendu

Temps machine d'une PR : environ 78 min (28 + 28 + 22) ramené à environ 50 min, soit un tiers de moins dans la file. La durée d'une PR seule reste fixée par la colonne Python la plus longue (environ 28 min). Le vrai gain est la fin des remises à jour en chaîne : jusqu'ici, chaque fusion relançait la CI de toutes les PR ouvertes, uniquement pour recompter les tests.

## Livraison

PR #630, fusionnée le 30 octobre 2026. Statut remis à jour par la passe documentaire du 1er novembre, d'après les PR fusionnées ; statut précédent : « En PR (30 octobre) ».
