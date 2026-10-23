# Lot J7 – Cohérence de la documentation, deuxième passe

## 1. Objectif

Le lot I1 a ajouté des tests qui comparent la documentation au code. L'audit J du 23 octobre a trouvé trois dérives qu'ils ne voient pas (constats J-D1 à J-D3) :
- `docs/SUIVI_AVANCEMENT.md` contenait des **caractères de contrôle** (tabulation et retour arrière à la place de `` `t `` et `` `b ``, accents gras perdus) : une séquence d'échappement mal tapée lors d'une fusion ;
- les **nombres de tests** annoncés divergeaient : README 156 (core) et 126 (compilateur), SUIVI 153 et 115, réalité 153 et 122 ; README annonçait 34 vérifications ERG côté Godot pour 54 réelles ;
- le README disait encore « Pas encore commencés : rendu 3D (E1) et entraînements ERG (F) » alors que F est livré et E1 en attente de fusion.

## 2. À lire

1. `docs/lots/00_INDEX.md` et `docs/lots/LOT_I1_coherence_doc_code.md` (livraison).
2. `core/tests/test_docs_coherence.py`.
3. `README.md`, `CLAUDE.md`, `docs/SUIVI_AVANCEMENT.md`, `docs/lots/*.md`, `engine/tests/README.md`.

## 3. Prérequis

Aucun. Partir de `main` à jour.

## 4. Travail demandé

Ajouter à `core/tests/test_docs_coherence.py` (mêmes conventions : fonction de contrôle pure qui prend le texte, test réel et test négatif) :

| Contrôle | Méthode |
| --- | --- |
| Caractères interdits | Aucun caractère de contrôle (U+0000 à U+001F sauf `\n`, `\r`, `\t` en début de ligne de bloc de code), aucun U+FFFD, aucune séquence typique d'un double encodage (`Ã©`, `Ã¨`, `â€™`) dans les `*.md` et `*.json` de `Open_ride_linux/` |
| Liens internes | Chaque lien Markdown relatif `[..](chemin)` et `[..](chemin#ancre)` des `*.md` vise un fichier existant ; l'ancre, si présente, correspond à un titre du fichier cible (règle de génération des ancres GitHub) |
| Nombres de tests | Les phrases « N tests ... core » et « N ... compilateur » du `README.md` et de `SUIVI_AVANCEMENT.md` sont comparées au nombre réel de tests collectés (`pytest --collect-only -q`, en sous-processus, sans les tests `network`) ; un écart échoue avec la valeur à écrire. Alternative acceptée : retirer ces nombres de la documentation au profit d'une phrase sans chiffre, et ajouter un test qui interdit leur retour |
| Fichiers cités | Tout chemin entre accents graves qui ressemble à un fichier du projet (`core/…`, `compiler/…`, `engine/…`, `docs/…`, `scripts/…`) existe, sauf liste d'exceptions motivées (fichiers à créer dans un lot non livré) |

**Si un contrôle échoue sur `main` au moment du lot :** corriger la documentation (pas le code) et lister chaque correction.

## 5. Fichiers concernés

- **Modifiés :** `core/tests/test_docs_coherence.py`, et seulement pour corriger un écart trouvé : `README.md`, `CLAUDE.md`, `docs/**/*.md`, `engine/tests/README.md`.

## 6. Modifications de contrat autorisées

Aucune. Les documents de contrat peuvent recevoir une correction de lien ou de caractère, sans changement de sens, avec une ligne au journal des changements.

## 7. Critères d'acceptation

1. `cd core && pytest -q` passe en entier.
2. Chaque contrôle a un test négatif (texte fabriqué : caractère `\b`, lien vers un fichier absent, ancre absente, nombre faux, chemin inexistant).
3. Le contrôle des nombres tient en moins de 10 s ; il est marqué `slow` s'il dépasse 5 s.
4. Les autres nouveaux contrôles tiennent en moins de 2 s au total.

## 8. Hors périmètre

- Orthographe et style.
- Liens externes (`https://`).

## 9. Livraison (23 octobre 2026, fait directement à la demande du propriétaire, sans sous-traitance)

- Quatre contrôles ajoutés à `core/tests/test_docs_coherence.py`, chacun avec un test réel et un test négatif sur texte fabriqué :
  - caractères interdits (contrôle hors `\n`, `\r`, `\t`, U+FFFD, double encodage) dans les `*.md` et `*.json` du projet ; le double encodage est cherché hors du code entre accents graves, où ce cahier cite les séquences ;
  - liens Markdown relatifs et ancres, avec la règle des ancres GitHub (titres en double suffixés `-1`, `-2`) ;
  - nombres de tests du `README.md` et du suivi comparés à `pytest --collect-only -q` lancé en sous-processus dans `core/` et `compiler/` (options du paquet, donc sans les tests `network`) ; le message donne la valeur à écrire ; test sauté si le compilateur n'est pas installé ;
  - chemins `core/…`, `compiler/…`, `engine/…`, `docs/…`, `scripts/…` cités entre accents graves. Exceptions motivées : les cahiers des lots non livrés (ils citent les fichiers qu'ils créeront), `core/.venv` (environnement local) et les trois scripts du lot E1, pas encore fusionné.
- Durées mesurées : 2,2 s pour les nombres de tests (pas de marque `slow`), moins de 0,1 s pour les trois autres.
- Écart trouvé sur `main` et corrigé : le nombre de tests du core était faux dans le `README.md` et le suivi (222 annoncés, 236 avec ce lot). Aucun lien cassé ni caractère interdit trouvé.
- `CLAUDE.md` : la règle de livraison rappelle que ces nombres sont vérifiés.
