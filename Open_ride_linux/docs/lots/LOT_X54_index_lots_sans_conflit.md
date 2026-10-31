# Lot X54 – Index des lots sans conflit de fusion

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série X (outils de test) : index des lots calculé à partir des cahiers (`scripts/index_lots.py`), plus de tableau dans `00_INDEX.md` | Python | X52 | Petite | **Livré le 31 octobre** (branche `claude/project-thread-47k1h1`) |

## 1. Objectif

Depuis que le lot X52 a retiré les nombres de tests de la doc, le dernier fichier que toutes les PR modifiaient était `docs/lots/00_INDEX.md` : chaque lot y ajoutait sa ligne en fin de série, ou y changeait son statut. Deux PR ouvertes en même temps touchaient des lignes voisines, et git les mettait en conflit à chaque fusion (#629, #635, #643, #644 le 31 octobre ; quinze PR ouvertes modifiaient ce tableau).

Écarté :
- un index généré mais gardé dans le dépôt : chaque PR le régénère, les conflits restent ;
- une régénération par la CI sur `main` : commit automatique sur la branche principale, et l'index est faux entre deux runs ;
- `merge=union` dans `.gitattributes` : ignoré par le bouton de fusion de GitHub, et doublerait les lignes dont le statut change.

## 2. Spécification

| # | Règle |
| --- | --- |
| X54-1 | La ligne d'un lot (titre, langage, dépendances, taille, statut) est écrite dans son cahier, juste sous le titre, derrière un commentaire repère. L'identifiant est celui du nom de fichier. |
| X54-2 | `scripts/index_lots.py` calcule le tableau complet (trié par série puis numéro), le nombre de lots et de lots livrés par série (`--stats`, `--resume F`), et vérifie les cahiers (`--verifier`). |
| X54-3 | `00_INDEX.md` garde les règles communes, les paragraphes des séries et le graphe des dépendances, mais plus aucune ligne de lot. |
| X54-4 | `--migrer` déplace dans leur cahier les lignes de lot restées dans `00_INDEX.md` : c'est la résolution d'un rebase pour une PR ouverte avant ce lot. |
| X54-5 | `core/tests/test_docs_coherence.py` refuse un cahier sans ligne, une ligne revenue dans `00_INDEX.md`, et un lot « Livré » sans section « Livraison ». |
| X54-6 | La colonne 3.14 de la CI ajoute le tableau des lots par série au résumé du run. |

Migration faite par le lot : les 325 lignes du tableau du 31 octobre sont passées dans leur cahier, mot pour mot (vérifié en comparant le tableau calculé à l'ancien). Deux lignes en double (X10 et X11, chacune avec un ancien statut) ont gardé le statut « Livré ». La ligne MJ0, qui pointait vers le plan de la série, a reçu un cahier rétrospectif `LOT_MJ0_plan_serie.md`.

## 3. Fichiers

- `scripts/index_lots.py`, `core/tests/test_index_lots.py`, `core/tests/test_docs_coherence.py` ;
- `docs/lots/00_INDEX.md`, tous les `docs/lots/LOT_*.md` (ligne d'index sous le titre), `docs/lots/LOT_MJ0_plan_serie.md` (nouveau) ;
- `.github/workflows/openride.yml`, `CLAUDE.md`, `docs/OUTILS_DE_TEST.md`.

## 4. Critères d'acceptation

1. Deux PR qui ajoutent chacune un lot de la même série ne touchent que leurs propres cahiers : aucun conflit entre elles.
2. `python3 scripts/index_lots.py` redonne les 325 lignes de l'ancien tableau, et `--verifier` rend 0.
3. Une ligne de lot remise dans `00_INDEX.md` fait échouer `test_docs_coherence` avec la commande `--migrer` dans le message.

## Livraison

Livré le 31 octobre 2026 (branche `claude/project-thread-47k1h1`).

- `scripts/index_lots.py` et `core/tests/test_index_lots.py` (lecture, tri, nombres, cahier sans ligne, identifiant en double, migration).
- `core/tests/test_docs_coherence.py` : contrôles 4 et 10 lus dans les cahiers.
- Rebase des PR ouvertes avant ce lot : garder leurs lignes de tableau dans `00_INDEX.md` en résolvant le conflit, puis `python3 scripts/index_lots.py --migrer` et commit.
