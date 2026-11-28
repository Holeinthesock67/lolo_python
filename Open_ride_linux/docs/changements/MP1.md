# MP1 : maisons des villages en pente, exclure ou simplifier

- PR : (à venir) ; cadrage : /mnt/project-files/statut/BRAINSTORMING_OW_2026-11-28.md §10 et ANALYSE_IMPACT_OW_2026-11-28.md §1.2 ; version : 6.0
- CHANGELOG (section « Modifié ») :
  - Parcours réels : les maisons qui paraîtraient étranges sur une pente sont retirées ou simplifiées à la
    compilation : socle visible de plus de 1,5 m, maison au bord de l'eau, maison en L ramenée à un rectangle à
    toit à pans, longue rangée sur une pente coupée en paliers. Un rapport par village signale un village vidé à
    plus de 30 %. Les Cols et les parcours compilés sont à recompiler.
- SUIVI :
  - [ ] MP1 : `building_simplify.py` (règles à la compilation de la couche `buildings`, maisons et dépendances
    seulement), rapport `buildings/rapport_maisons.json` avec les bâtiments que la chaussée dessinée (CD1) retire,
    garde-fou des villages à 30 % ; tests `compiler/tests/test_building_simplify.py` ; seuils à régler sur le
    rapport et les captures de la recompilation des Cols.
