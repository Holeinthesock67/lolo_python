# Notes de changement par lot

Règle du 22 novembre 2026 (audit de cohérence et de qualité, constat P3, validée par le propriétaire) : une PR
**n'écrit plus dans `CHANGELOG.md` ni dans `docs/SUIVI_AVANCEMENT.md`**. Ces deux fichiers étaient touchés par
presque toutes les PR : chaque fusion créait un conflit dans toutes les autres.

À la place, chaque PR ajoute **un seul fichier à elle** dans ce dossier, nommé d'après son lot :
`docs/changements/<LOT>.md` (par exemple `R27.md`, `CH3a.md`). Deux PR n'écrivent jamais le même fichier, donc
plus de conflit.

## Forme du fichier

```markdown
# R27 : Cyber-Rogue sans voile en high

- PR : #965 ; cahier : docs/lots/LOT_R27_....md ; version : 2.0
- CHANGELOG (section « Modifié », « Ajouté » ou « Corrigé ») :
  - Une ou deux lignes pour le joueur : ce qui change à l'écran ou sur le vélo.
- SUIVI :
  - [ ] La ligne du suivi, telle qu'elle y sera recopiée (case cochée une fois fusionnée et recettée).
```

Le cahier du lot (`docs/lots/`) garde son statut et sa section « Livraison », comme avant : c'est son fichier.

## Rassemblement

La passe de doc (une PR de docs seule, CI seulement, au rythme des fusions, au moins une fois avant chaque Release)
recopie les fichiers des lots fusionnés dans `CHANGELOG.md` (section « Non publié ») et `SUIVI_AVANCEMENT.md`,
puis les retire de ce dossier. Un fichier encore présent veut donc dire : lot fusionné, pas encore rassemblé.
