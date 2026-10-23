# Lot A2 – Tracé de démonstration sans recouvrement

## 1. Objectif

Le parcours de démonstration (`demo_world.build_route`) repassait sur lui-même : ses deux épingles tournaient dans le même sens, la route faisait demi-tour complet et sa dernière partie recouvrait la première. Pour la démo de 5 000 m, les tronçons s ≈ 860–1 410 m et s ≈ 3 490–4 010 m sont à moins de 3 m l'un de l'autre en plan, avec environ 68 m d'écart d'altitude. Aucun terrain ne peut suivre les deux passages (constat du lot E1).

## 2. Travail demandé

- Garder la longueur, le pas, le profil de pente et le cap de départ.
- Remplacer les deux épingles par un vrai lacet : deux épingles de sens opposés, proches l'une de l'autre, après lesquelles la route repart dans sa direction d'origine.
- Garantir, pour toute longueur utilisée (tests, démo de 5 km, `fit_demo` de 30 km), que deux points distants de plus de 300 m le long de la route restent à plus de 90 m l'un de l'autre en plan.
- Régénérer `engine/demo/demo.world/` à l'identique du core.

## 3. Fichiers concernés

- `core/src/openride_core/demo_world.py`
- `core/tests/test_route.py`
- `engine/demo/demo.world/route.json`

## 4. Critères d'acceptation

1. Un test vérifie l'absence de recouvrement pour 1 234 m, 1 500 m, 5 000 m, 8 000 m et 30 000 m.
2. `test_engine_demo_is_the_core_demo` passe : la démo de l'engine est identique à celle du core.
3. `pytest` passe dans `core/` et `compiler/` ; les tests de l'engine passent.

## 5. Livraison

23 octobre 2026.
- Épingles en `0,45 × L` (sens horaire) puis `0,45 × L + min(500 m, max(250 m, 0,15 × L))` (sens antihoraire).
- Dérive lente du cap neutralisée de 500 m avant la première épingle à 500 m après la seconde : les branches du lacet restent droites et parallèles, à environ 95 m (deux rayons d'épingle).
- Écart minimal mesuré : 95,7 m pour les cinq longueurs testées. Altitudes et pentes inchangées.
- **À faire par le propriétaire :** supprimer `~/.local/share/openride/routes/demo.world` s'il existe. Le core ne recrée la démo que si elle manque, et l'engine lit ce dossier en priorité : sans suppression, l'ancien tracé resterait affiché.
