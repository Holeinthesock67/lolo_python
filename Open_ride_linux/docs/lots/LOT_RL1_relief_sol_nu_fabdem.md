# Lot RL1 : relief au sol nu FABDEM pour le monde ouvert

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Monde ouvert au relief au sol nu FABDEM (Copernicus sans bâtiments ni arbres), tuiles d'un degré lues dans les archives de 10° par requêtes partielles, Copernicus en repli par tuile | Python | W8, #961 | Moyenne | En revue, **version 6.0** (décision du propriétaire du 25 novembre) |

## Constat (25 novembre)
- Balade de Biarritz du 22/11 (copie, sans le cache) : pentes de 18 à 21 % sur 20 à 30 m au HUD, avant le
  garde-fou de pente #961. Copernicus GLO-30 est un modèle de **surface** (toits, arbres) à 30 m : dans une ville
  serrée, la route « monte » quand une case déborde sur les maisons, puis les maisons d'OSM se posent par-dessus.
- Altitudes générales justes (0 à 86 m autour de Biarritz) : seul le détail urbain et forestier est faux.

## Règle (une seule, tous les lieux)
- `elevation.FabdemProvider` : FABDEM V1-2 (Hawker et al. 2022, université de Bristol, CC BY-NC-SA 4.0,
  usage non commercial : OpenRide est personnel). Tuile `<coin SO>_FABDEM_V1-2.tif` de l'archive de 10°
  `<bloc>_FABDEM_V1-2.zip` (`fabdem_zip_names` : deux graphies essayées pour un bloc qui touche l'équateur ou le
  méridien d'origine), cache `~/.cache/openride/dem/fabdem_v1_2/`.
- `remote_zip.py` : sommaire de l'archive (fin de fichier, ZIP64 compris) puis seulement le fichier voulu, par
  requêtes `Range` ; taille et CRC32 vérifiés. Archive absente (404), tuile absente ou serveur sans `Range` :
  marque `<tuile>.absent`, la tuile Copernicus sert à sa place. Pixels sans valeur : Copernicus. Hors ligne :
  Copernicus, sans marque (réessayé avec le réseau).
- `openride-worldgen --relief fabdem` (défaut depuis RL2 : `--relief ign`, FABDEM en repli ; `--relief copernicus` : l'ancien relief ; `--fabdem-url` pour les
  tests). Préchargement de la balade, `world-prefetch` et `world-measure` prennent la même source.
- Carrés et tuiles lointaines refaits d'eux-mêmes : le nom du relief (`fabdem_v1_2`) est dans leurs versions
  (`squares.square_versions`, `far_versions`) ; **pas de nouveau WORLDGEN_VERSION** (pas de renumérotation avec #940).
- Parcours compilés inchangés (altitude du GPX, terrain Copernicus) : à reprendre plus tard si utile.

## Limites connues
- Serveur réel (data.bris.ac.uk) hors de la liste du réseau du cloud : graphie exacte des archives et prise en
  charge de `Range` à vérifier sur le PC (essai ci-dessous). Si le serveur refuse `Range`, tout se rabat sur
  Copernicus, sans erreur, et le journal dit « FABDEM : … relief Copernicus pour cette tuile ».
- Une tuile passée en repli pendant une coupure réseau garde des carrés calculés sur Copernicus jusqu'à leur
  prochaine version (comme aujourd'hui).

## Tests
- `compiler/tests/test_fabdem.py` (faux serveur local) : noms, lecture d'un seul fichier (deflate, stocké, ZIP64),
  serveur sans `Range`, 404, cache réutilisé sans requête, marques d'absence, hors ligne, pixels sans valeur,
  monde ouvert sur FABDEM par défaut et nom du relief dans les versions.

## Essai sur le PC (avant le go)
```bash
cd /home/utilisateur/Games/lolo_python/Open_ride_linux/compiler && source ../core/.venv/bin/activate
python -c "from openride_compiler.elevation import FabdemProvider; p = FabdemProvider(); print(p.elevations([43.48], [-1.56]))"
```
Puis banc multi-zones (#1057) en cache séparé, `controle_profil_altitude` : pentes de Biarritz, Lyon et Sevrier
comparées à main.

## Suite
- Lot RL2 : IGN RGE ALTI en France (même PR #1073, FABDEM devient le repli de l'IGN) ; RL3 essais ; RL4
  parcours déjà générés.
