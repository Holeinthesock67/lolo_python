# Lot J6 – Une seule logique de catalogue des parcours

## 1. Objectif

Le statut d'un parcours (`ready`, `to_compile`, `outdated`, `invalid`) est calculé à deux endroits (audit J, constat J-F3) :
- `core/src/openride_core/catalog.py` (`list_routes`), utilisé par `openride-compiler list` et `build-all` quand le core est installé ;
- un repli dans `compiler/src/openride_compiler/cli.py` (`_catalog_entries`), utilisé sinon, qui n'est **jamais exécuté par les tests** (le core est toujours installé) et qui diverge déjà : il ne retrouve pas un GPX renommé par sa somme SHA-256, contrairement au core.

De même, la normalisation des noms existe en double (`catalog._normalize_name` et `writer.normalize_name`).

Le lot garantit que les deux chemins donnent le même résultat, ou supprime le repli si c'est plus simple.

## 2. À lire

1. `docs/lots/00_INDEX.md` et `docs/lots/LOT_I2_catalogue_parcours.md` (règles des statuts, §4.1).
2. `docs/contracts/world_format_v1.md` §2 (source du manifeste).
3. Code : `core/src/openride_core/catalog.py`, `compiler/src/openride_compiler/cli.py` (`_catalog_entries`, `cmd_list`, `cmd_build_all`), `compiler/src/openride_compiler/writer.py` (`normalize_name`) ; tests `core/tests/test_catalog.py`, `compiler/tests/test_build_all.py`.

## 3. Prérequis

Aucun. Partir de `main` à jour (après la PR de l'audit J, qui corrige `build-all`).

## 4. Travail demandé

Choisir l'une des deux voies et la justifier dans le rapport :

- **Voie A (préférée) :** garder le repli, mais le rendre équivalent au core. Un test paramétré construit les mêmes dossiers (GPX compilé, GPX modifié, GPX jamais compilé, GPX renommé après compilation, `.world` corrompu, `.world` dont le GPX a disparu, parcours `demo`) et compare champ par champ `list_routes` et le repli (forcé en masquant `openride_core` du `sys.modules`, par `monkeypatch`).
- **Voie B :** supprimer le repli et déclarer `openride-core` comme dépendance du compilateur ; mettre à jour `compiler/pyproject.toml`, `README.md`, `CLAUDE.md` et la section « Livraison » d'I2.

Dans les deux cas :
- un test vérifie que `catalog._normalize_name` et `writer.normalize_name` donnent le même résultat sur une liste de noms difficiles (accents, espaces, majuscules, tirets multiples, chiffres en tête, noms vides ou réduits à des signes) ;
- l'ordre de sortie de `list` est identique dans les deux chemins (démo d'abord, puis tri par identifiant).

## 5. Fichiers concernés

- **Nouveau :** `compiler/tests/test_catalog_parity.py`.
- **Modifiés :** `compiler/src/openride_compiler/cli.py` (repli seulement), éventuellement `core/src/openride_core/catalog.py` (normalisation) ; voie B : `compiler/pyproject.toml`, `README.md`, `CLAUDE.md`, `docs/lots/LOT_I2_catalogue_parcours.md`. `docs/SUIVI_AVANCEMENT.md` (une ligne).

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `pytest -q` passe en entier dans `core/` et `compiler/`.
2. Voie A : le test de parité couvre les 7 situations du §4 et passe ; une modification volontaire du repli (par exemple retirer la recherche par SHA-256) le fait échouer (démonstration dans le rapport).
3. Test de normalisation commun : au moins 15 noms.
4. Aucune régression des critères d'I2 (`test_build_all.py`, `test_catalog.py`).

## 8. Hors périmètre

- Messages IPC de liste des parcours (lot G).
