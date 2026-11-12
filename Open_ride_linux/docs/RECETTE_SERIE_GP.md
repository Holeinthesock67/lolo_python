# Recette de la série GP – Grand Prix des objets (lot GP11)

Date de préparation : 12 novembre 2026  
Code : `main` après GP1, GP2, GP3, GP5, GP6, GP7 et GP8 ; les étapes sur le vélo attendent **GP9** (entrée du mode et réglages au menu) ; l'étape 5 attend aussi **GP4** (voiture d'équipe et Furtif).  
Machine cible : PC du propriétaire (GTX 1060, écran 1 920 × 1 080), home trainer et Click  
Cahier : [LOT_GP11_recette.md](lots/LOT_GP11_recette.md) ; plan : [PLAN_SERIE_GP.md](4.0/PLAN_SERIE_GP.md)

**Règle de la recette : aucune étape ne dépasse 10 minutes sur le vélo.** Chaque étape dit quand s'arrêter, même si l'arrivée n'est pas passée. Entre deux étapes, pause libre : on peut en faire une seule par jour. À cocher par le propriétaire : « fait », ou « à corriger » avec une remarque. Les valeurs réelles (FTP, poids, appareils) restent dans `~/OpenRide/config.toml`, jamais dans le dépôt ; tes traces GPS et tes journaux restent sur ton PC.

Tout se règle au menu (lot GP9) : Accueil › « Grand Prix des objets », puis parcours, réglages (adversaires, tours ou distance, chaos, écart des boîtes, niveau des bots) et « Objets » (une case par objet). Rien ne se lance en ligne de commande. Le mode se joue en SIM seulement.

Commandes de la recette, à lancer **dans un terminal à côté** après chaque étape :

```bash
cd ~/Games/lolo_python/Open_ride_linux/core && source .venv/bin/activate
python -m openride_core.tools.gp_recette            # bilan des courses du jour
python -m openride_core.tools.gp_recette --dernieres 6   # bilan cumulé des six dernières courses
```

Le bilan (`tools/gp_recette.py`) lit les journaux de séance du profil en cours et dit, pour chaque course, le format, la place et les esquives ; pour chaque objet, combien de fois tu l'as utilisé, subi et paré ; ce qu'il reste à faire (format, objet à utiliser, objet à subir) ; et il contrôle que la **pente envoyée reste lisse autour de chaque coup subi** (critère 1 du cahier : variation d'une seconde à l'autre pas plus forte qu'ailleurs dans la course, supplément de vent et d'abri sous 0,5 point par seconde). Une ligne « À-COUP ? » donne l'heure du coup à regarder. Le ressenti sous les pieds, la lisibilité et l'esquive restent à cocher ici : le journal ne note pas les changements de voie.

---

## 0. Préparation (sans le vélo)

```bash
cd ~/Games/lolo_python
git switch main && git pull --ff-only
cd Open_ride_linux
(cd core && source .venv/bin/activate && pytest -q)
engine/tests/run_engine_tests.sh
```

- [ ] Tests du core verts, dont `test_grandprix_session` et `test_gp_recette`.
- [ ] Tests Godot verts, dont `test_gp_scene`.
- [ ] Au menu : Accueil › « Grand Prix des objets » visible (GP9) ; l'écran « Objets » montre les treize cases.
- [ ] Pas de `~/OpenRide/grandprix.toml` hérité d'un essai (sinon le renommer) : les valeurs par défaut sont celles du plan §3.

Remarque : …

## 1. Banc sans vélo en `low`, `medium` et `high` (PC, séquencé par le fil de fusion)

Départ du mode au pire cas : 4 bots, chaos fou, boîtes tous les 1 000 m, Z toutes les 20 s, 8 minutes par préréglage (scénario `grand_prix`, lot GP7). Une seule mesure à la fois sur la machine.

```bash
cd ~/Games/lolo_python/Open_ride_linux
for q in low medium high; do
  python3 engine/tests/sim_bench.py --scenario grand_prix --quality $q --native --probe \
    --out ~/OpenRide/sim_bench/gp11_$q
done
```

- [ ] Les trois bancs passent (journaux du core et de l'engine : séance lancée, roulette, objet utilisé).
- [ ] Budgets GPU de `engine/tests/perf_targets.json` tenus : **low 8 ms, medium 13 ms, high 16 ms** (GPU de la vue médian) ; à-coups (bloc `hitches`) sans échec. Repère du 9 novembre (banc r831, GP7 seul) : 5,25 / 6,34 / 8,04 ms.
- [ ] Qualité appliquée = qualité demandée (contrôle X32 du rapport).
- [ ] Captures validées par le propriétaire : 35 m avant chaque rangée de boîtes, 1,5 s après chaque Z (objet lancé, effet sur le cycliste), dans les trois préréglages. Les effets diffèrent par préréglage (`low` sans particules, `medium` averse réduite, `high` averse et étincelles).

Remarque : …

## 2. Course en ligne à 4 bots (10 minutes au plus)

Parcours « Col du lacet » (`demo`), course en ligne de 5 km, 4 adversaires, chaos normal, boîtes tous les 1 500 m, niveau des bots inchangé, tous les objets. Arrête-toi à l'arrivée ou au bout de 10 minutes.

- [ ] Départ groupé : les 4 bots et toi sur la ligne ; place et écart en haut à droite (« 3e / 5 · à 6,4 s du premier »).
- [ ] Rangées de boîtes visibles de loin, une par voie ; roulette de 2 s puis objet dans la case en haut au centre, avec l'invite « Z : Trois musettes » (nom de l'objet).
- [ ] Z court utilise l'objet ; un Z sans objet ou trop tôt après une charge a une réponse visible (règle du 11 novembre : à noter en remarque sinon).
- [ ] Bande de course à gauche : coureurs dans l'ordre, objet que chacun tient.
- [ ] Avertissement « Musette guidée derrière ! » ou « Orage vers le premier » lisible, contour coloré, aucun flash plein écran.
- [ ] **Aucun à-coup de résistance** à la réception d'un objet : tu relances avec tes watts, la pente ne bouge pas.
- [ ] Bilan de fin : place, objets lancés, reçus, esquivés, temps gagné et perdu.
- [ ] `gp_recette` : course « en ligne, 5,0 km » listée, aucune ligne « À-COUP ? ».

Remarque : …

## 3. Course sur circuit à 2 bots (10 minutes au plus)

Un de tes parcours en boucle (trace qui revient à son départ : « circuit » au menu), 2 adversaires, autant de tours qu'il en tient en 10 minutes (un tour de 2 à 4 km, 1 à 3 tours), chaos normal. Le jeu de base ne livre aucun circuit à ce jour : sans parcours en boucle dans ta bibliothèque, note-le en remarque et passe à l'étape suivante.

- [ ] « tour 1 / N » puis « tour 2 / N » en haut à droite ; les rangées de boîtes restent aux mêmes endroits d'un tour à l'autre.
- [ ] Arrivée au bon tour, bilan avec le nombre de tours.
- [ ] `gp_recette` : course « circuit, N tour(s) » listée.

Remarque : …

## 4. Pièges, attaques et esquive au Click puis au clavier (10 minutes au plus)

Course en ligne de 5 km, 4 adversaires, **chaos fou**, boîtes tous les 1 000 m. Écran « Objets » : ne garder que **Bidon glissant, Trois bidons, Musette lancée, Trois musettes, Musette guidée** (les cinq autres cases décochées). Première moitié au Click, seconde moitié au clavier.

- [ ] Bidon lâché derrière toi sur ta voie ; musette lancée tout droit devant ; musette guidée qui suit le coureur devant et change de voie avec lui.
- [ ] Choix de voie : trois traits en bas du HUD (voie choisie en blanc, gris en placement automatique) et l'aide « Bidon glissant en vue : A ou ← → » dès qu'un objet est en vue sur ta voie.
- [ ] **Click** : A court change de voie quand un objet est en vue, sinon change de vue ; flèches gauche et droite : voie à gauche, à droite ; A long : retour au placement automatique.
- [ ] **Clavier** : mêmes touches (A, flèches, Z) avec le même effet.
- [ ] Au moins une esquive réussie au Click et une au clavier (le bidon ou la musette passe sur la voie d'à côté, pas de glissade) ; bidon ou musette tenus en réserve qui parent une musette guidée.
- [ ] Glissade reçue : étoiles, son de glissade, vitesse virtuelle qui chute puis remonte avec tes watts ; **aucun à-coup sous les pieds**.
- [ ] `gp_recette` : les cinq objets utilisés et subis ; esquives au bilan de course.

Remarque : …

## 5. Pour soi, défense et objets contre la tête (deux fois 10 minutes au plus)

Course en ligne de 5 km, 4 adversaires, chaos fou, boîtes tous les 1 000 m. Écran « Objets » : cocher **Coup de fouet, Trois coups de fouet, Super-forme, Sonnette, Nuage d'orage, Vent contraire**, plus **Voiture d'équipe** et **Furtif** si le lot GP4 est fusionné ; décocher les autres.

- **5a, devant** (niveau des bots 70 %) : tu mènes ; tu reçois surtout la sonnette et les coups de fouet, et tu subis l'orage et le vent contraire des bots.
- **5b, derrière** (niveau des bots 130 %) : tu es loin derrière ; tu reçois l'orage, le vent contraire, la super-forme et, à plus de 15 s du premier, la voiture d'équipe et le Furtif.

- [ ] Coup de fouet : impulsion de vitesse visible (traits), sans à-coup ; trois charges, une par Z.
- [ ] Super-forme : halo 8 s, les coureurs frôlés glissent, les objets au sol sans effet.
- [ ] Sonnette : dring, bidons et musettes proches détruits, coureurs à moins de 5 m qui glissent ; sonnée dans la seconde avant l'averse, elle chasse le nuage.
- [ ] Nuage d'orage : vole vers le premier, averse de 1,5 s ; jamais tiré par les deux premiers.
- [ ] Vent contraire : rafales vers les coureurs devant ; **aucun ressenti** sur le trainer.
- [ ] (GP4) Voiture d'équipe : remorquage 6 s dans son abri, abri ressenti en douceur (rampes) ; Furtif : avatar semi-transparent, vol de l'objet du coureur devant à moins de 50 m.
- [ ] `gp_recette --dernieres 6` : plus aucun objet « à voir » (tous utilisés, tous ceux qui touchent subis au moins une fois), aucune ligne « À-COUP ? », un circuit et une course en ligne, « Bilan : tous les contrôles passent ».

Remarque : …

## 6. Bilan de la recette

- [ ] Critère 1 du cahier : aucun à-coup de résistance ressenti à la réception d'un objet ; pente envoyée du journal lisse (`gp_recette`).
- [ ] Critère 2 du cahier : budgets GPU tenus dans les trois préréglages ; captures validées par le propriétaire.
- [ ] Gameplay lisible (règle du 11 novembre) : à tout moment, on sait sa place, son objet, quoi faire et avec quel bouton ; tout appui a une réponse visible.

Après la recette : écran « Objets », tout recocher (les cases sont gardées dans `~/OpenRide/grandprix.toml`).

Remarque générale : …
