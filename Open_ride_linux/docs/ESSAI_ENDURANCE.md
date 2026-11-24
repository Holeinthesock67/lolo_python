# Essai d'endurance avant livraison (lot EN1)

But : vérifier, avant l'installateur J9, que le jeu tient la durée d'un vrai hiver d'utilisation sans que la
mémoire grimpe, sans à-coups qui s'installent et sans fichiers qui enflent. Une seule commande enchaîne, dans le
même core et le même engine (sans relancer les processus) :

1. **une séance de 2 h** en balade libre ;
2. **une saison complète de la ligue d'hiver** : 8 semaines simulées, une manche par semaine.

Outil : `engine/tests/essai_endurance.py` (avec `engine/tests/horloge_decalee.py`). Il reprend les pièces du banc
simulé (`sim_bench.py`) et de la sonde de performance (`perf_probe.py`, lots X13 et X16). Aucun code du jeu n'est
modifié : le banc ne fait qu'envoyer les commandes du menu (`select_route`, `start`, `league_new`,
`league_status`, `end_session`) et piloter le cycliste virtuel du Bluetooth simulé.

## 1. Ce que fait l'essai

| Étape | Détail | Durée réelle |
| --- | --- | --- |
| Préparation | HOME temporaire, anneau synthétique de 3 km (bosse de 8 m) écrit dans ses parcours, `config.toml` du banc (qualité, ports UDP libres, départ immédiat), trainer, Click et ceinture simulés | 10 s |
| Séance | Balade libre sur l'anneau. Toutes les 5 min : effort du cycliste virtuel changé (220, 200, 260, 180, 300, 240 W, pour une FTP fictive de 250 W) et un appui du Click (+ ou −) ; parcours relancé s'il se termine ; fin par `end_session` (FIT et bilan écrits) | 2 h |
| Saison | L'horloge du core avance au mercredi 18 h de chaque semaine (`horloge_decalee.py`). Semaine 1 : `league_new`. Chaque semaine : `league_status`, puis la manche dans son mode (`start` avec `league` = vrai, 11 rivaux, environ 27 min) ; une manche d'un mode pas encore branché dans la ligue est laissée aux rivaux (semaine non courue, simulée). Le lundi après la semaine 8 : `league_status`, la saison doit être close | 8 × ~28 min avec la ligue complète ; ~1 h 15 avec CH3a seul (3 manches de Course) |
| Verdict | `verdict.md`, `verdict.json`, `fichiers.csv`, `core.log`, `engine.log`, `sonde/rapport.html` dans le dossier de sortie | 1 min |

Total sur le PC : environ **6 h** quand toutes les manches seront jouables (CH3b), **3 h 30** avec CH3a. C'est un essai
de nuit, sans personne devant le PC.

**L'horloge décalée.** Seule `time.time()` du core est décalée (jour de la ligue, horodatage du journal et des
fichiers) ; `time.monotonic()`, qui cadence la boucle à 50 Hz, ne bouge pas. Le décalage ne vit que dans le
processus du core lancé par le banc : l'horloge du PC n'est pas touchée.

## 2. Procédure

Sur le PC cible, **jamais pendant un essai vélo ni pendant un banc d'un autre fil** : la file du PC passe par le fil
de fusion. Le PC doit rester allumé, sans veille. Rien n'est lu ni écrit dans le vrai `~/OpenRide` (profil,
`Cache/monde` compris) : tout se passe dans un HOME temporaire effacé à la fin.

```bash
cd ~/Games/lolo_python/Open_ride_linux
git checkout main && git pull
# 1. Essai à blanc (~25 min) : vérifie la chaîne avant la nuit
python3 engine/tests/essai_endurance.py --native --court --quality medium
# 2. Essai complet (~3 h 30 à 6 h), la nuit
python3 engine/tests/essai_endurance.py --native --quality medium
```

Résultat dans `~/OpenRide/rapports/endurance-AAAAMMJJ-HHMM/verdict.md` (code de sortie 0 si tout passe, 1 sinon).
Options utiles :

- `--quality low|medium|high` : préréglage mesuré (budget GPU de 8, 13 ou 16 ms) ; une nuit par qualité si besoin,
  medium d'abord (qualité habituelle) ;
- `--phase seance|saison` : une seule des deux parties ;
- `--seance-min 60` : séance plus courte ;
- `--debut AAAA-MM-JJ` : lundi de la semaine 1 de la saison simulée (défaut : lundi prochain) ;
- `--sans-engine` : core seul (cloud, sans Godot ni mesures de rendu) ;
- `--garder` : garde le HOME temporaire, pour lire le profil produit (`ligue.json`, journaux, FIT).

## 3. Critères de réussite

Les mesures GPU et d'images ne sont jugées qu'en fenêtre réelle (`--native`) ; sous Xvfb elles sont données à
titre indicatif. Les 5 premières minutes (chargement, premières tuiles) sont hors calcul.

| Domaine | Vérification | Seuil | D'où vient le seuil |
| --- | --- | --- | --- |
| Mémoire | Croissance du core (pente des médianes par minute) | ≤ 20 Mo/h | `perf_probe.ENDURANCE_LIMITS` (lot X16) |
| Mémoire | Maximum du core | ≤ 400 Mo | ~3 fois le core mesuré à l'essai à blanc |
| Mémoire | Croissance de Godot | ≤ 100 Mo/h | lot X16 |
| Mémoire | Godot, dernière demi-heure contre la première | ≤ + 300 Mo | sur 6 h, une fuite de 50 Mo/h passe la pente mais pas ce seuil |
| Mémoire | Croissance de la mémoire vidéo | ≤ 50 Mo/h | lot X16 |
| GPU | Temps GPU de la vue, médiane de chaque partie (séance, saison) | low ≤ 8 ms, medium ≤ 13 ms, high ≤ 16 ms | budgets du propriétaire (`perf_targets.json`) |
| GPU | Temps GPU de la vue, dernière demi-heure contre la première | ≤ + 10 % | chauffe de la carte (enquête 7bi) |
| À-coups | Secondes avec une image de plus de 100 ms | ≤ 6 par heure | lot X16 (recette 1.0, ligne 18) |
| Images | Images/s médianes | ≥ 30 | lot X16 (recette 1.0, ligne 17) |
| Fichiers | Journaux de séance (`.jsonl`) | ≤ 15 Mo par heure roulée | voir §4 |
| Fichiers | FIT | ≤ 1 500 Ko par heure | voir §4 |
| Fichiers | Journal du core sur tout l'essai | ≤ 50 Mo | voir §4 |
| Fichiers | Journal de l'engine sur tout l'essai | ≤ 50 Mo | voir §4 |
| Fichiers | `ligue.json` | ≤ 100 Ko | une saison de 8 manches |
| Fichiers | `elo.json` | ≤ 200 Ko | historique des cotes |
| Fichiers | Croissance du profil `~/OpenRide` entier | ≤ 200 Mo | place disque d'un hiver |
| Séances | FIT écrits | 1 (séance) + 1 par manche courue | |
| Ligue | Saison créée | 11 rivaux | plan CH §2 |
| Ligue | Chaque manche jouable | départ, arrivée, résultat « joueur » dans `ligue.json` | CH3 |
| Ligue | Fin de saison | 8 résultats au calendrier, saison close (`closed` = `fin`) le lundi qui suit la semaine 8 | CH1 |
| Robustesse | Core et engine vivants jusqu'au bout, arrêt du core propre (code 0), aucune trace d'exception au journal du core | | |

Un échec n'est pas corrigé dans le banc : il ouvre un lot (fuite, à-coup, journal trop bavard). Les seuils de
fichiers seront revus après la première nuit sur le PC, avec la mesure réelle, sans jamais les relâcher pour
faire passer un essai (règle de cohérence du projet : la valeur et sa raison s'écrivent ici).

## 4. Essai à blanc au cloud (22 novembre)

Voir la section « Livraison » du lot `docs/lots/LOT_EN1_essai_endurance.md` : chaîne vérifiée en core seul sur la
branche de CH3 (#989), mesures de fichiers et de mémoire du core qui fondent les seuils ci-dessus.

## 5. Limites

- Avec CH3a seul, 3 manches sur 8 sont jouables (Course en tours : semaines 1, 5 et 8) ; les 5 autres sont simulées
  pour les rivaux. L'essai prend les autres modes d'eux-mêmes dès que CH3b les branche (`league.PLAYABLE_MODES`).
  Les manches « Grand Prix », « Vélodrome » et « Arrivée en côte » demanderont alors leur parcours ; le banc court
  pour l'instant toutes les manches sur l'anneau.
- L'anneau synthétique n'a ni bâtiments ni forêt OSM : la mémoire et le GPU y sont ceux d'un décor léger. Pour un
  décor lourd, le scénario `endurance` de `sim_bench.py` (village simulé, 1 h) reste l'outil.
- Le monde ouvert n'est pas dans l'essai (son cache ne doit jamais être touché par un banc).
