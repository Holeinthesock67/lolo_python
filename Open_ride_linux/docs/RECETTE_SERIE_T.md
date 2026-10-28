# Recette de la série T – Sprints, montées chronométrées, bonus et bots à profil (lot T11)

Date de préparation : 27 octobre 2026  
Code : `main` après T8, T9 et T10 (PR #408, #409, #414) ; l'étape 8 attend T12, T13 et T15.  
Machine cible : PC du propriétaire (GTX 1060, écran 1 920 × 1 080), home trainer et Click  
Cahier : [LOT_T11_recette.md](lots/LOT_T11_recette.md)

**Règle de la recette : aucune étape ne dépasse 10 minutes sur le vélo.** Chaque étape dit quand s'arrêter. Entre deux étapes, pause libre : on peut en faire une seule par jour. À cocher par le propriétaire : « fait », ou « à corriger » avec une remarque. Les valeurs réelles (FTP, poids, appareils) restent dans `~/OpenRide/config.toml`, jamais dans le dépôt ; tes traces GPS restent sur ton PC.

Parcours de démonstration (`demo`, 5 km, ouvert) : montée « Montée 1 » de 0 à 1 500 m (4e catégorie, 3,6 %), puis sprint « Sprint 1 » de 2 860 à 3 290 m. Vers 25 km/h, le sprint est atteint en 7 minutes environ.

---

## 0. Préparation (sans le vélo, environ 15 minutes de calcul)

```bash
cd ~/Games/lolo_python
git switch main && git pull --ff-only
cd Open_ride_linux
(cd core && source .venv/bin/activate && pytest -q)
engine/tests/run_engine_tests.sh
python3 engine/tests/visual_check.py --native
```

- [ ] Tests du core verts.
- [ ] Tests Godot verts, dont `test_segment_markers_model`, `test_segment_hud_model` et `test_records_view_model`.
- [ ] Tests graphiques verts (scène « col » comprise).

Pour voir plusieurs arches pendant une étape courte, crée `~/OpenRide/powerups.toml` :

```toml
[obtain]
arch_every_m = 1000   # une arche par kilomètre pendant la recette ; 5000 par défaut
per_segment = true
```

Remarque : …

## 1. Montée et sprint du parcours de démonstration (9 minutes au plus)

Mode classique (SIM), parcours `demo`, option « Bonus » à « oui ». Arrête-toi juste après la ligne d'arrivée du sprint (km 3,3), ou au bout de 9 minutes.

- [ ] Au départ : portique à pois « Montée 1 · Départ » et panneau « Montée de 4e catégorie · 1,5 km à 3,6 % » à gauche de la route.
- [ ] Panneaux « Sommet dans 1 km » et « Sommet dans 500 m », puis portique d'arrivée avec la ligne en damier.
- [ ] HUD sous le panneau de droite : chrono de la montée pendant l'effort, puis résultat pendant 8 s (temps au dixième, « Record ! » au premier passage).
- [ ] Après la montée : approche « Sprint 1 dans 1,2 km », panneaux « Sprint dans 1 km, 500 m, 200 m » et portique vert.
- [ ] Résultat du sprint, puis bonus en réserve « Z : … » dans le bloc du bonus.
- [ ] Jingles (lot T17) : trois notes montantes et une cloche au sommet de la montée, deux notes vives à la fin du sprint, avec une note de plus quand c'est un record ; chacun une seule fois, audible par-dessus le vent sans gêner.
- [ ] Lisibilité du HUD et des panneaux à ta distance de pédalage.

Remarque : …

## 2. Records et écart en direct (8 minutes au plus)

Relance une séance sur `demo` et refais la montée seulement : arrête-toi au sommet (km 1,5).

- [ ] Pendant la montée : écart au record en direct, vert quand tu es en avance, rouge en retard.
- [ ] À l'arrivée : temps, ancien record si tu le bats, place.
- [ ] En terminant la séance : courte fanfare de fin, une seule fois, avant le bilan (lot T17).
- [ ] Menu, écran « Prêt », « Records du parcours » : la montée et le sprint ont leurs temps, avec date, W et W/kg ; A court bascule entre « sans bonus » et « avec bonus ».

Remarque : …

## 3. Les trois bonus (10 minutes au plus)

Séance sur `demo`, avec l'arche tous les 1 000 m de la préparation. À chaque bonus reçu (arche ou fin de segment), appuie sur Z. Arrête-toi quand tu as vu les trois bonus, ou au bout de 10 minutes. Le type du bonus est tiré au hasard : s'il en manque un, refais l'étape un autre jour.

- [ ] Arches violettes visibles sur la route, avec un arpège de cloches à chaque passage dessous (lot T17).
- [ ] Légèreté : la vitesse monte un peu, la résistance du trainer ne change pas.
- [ ] Aérodynamique : la vitesse monte sur le plat ; seul le supplément dû au vent peut s'alléger.
- [ ] Puissance : la vitesse monte, la résistance ne change pas.
- [ ] Barre de temps du bonus actif, 15 s.
- [ ] Un passage de segment fait avec un bonus actif va dans la table « avec bonus » de l'écran « Records ».

Remarque : …

## 4. ERG (8 minutes au plus)

Session ERG avec un entraînement court, sur `demo`. Arrête-toi après la montée (km 1,5), ou au bout de 8 minutes.

- [ ] Segments chronométrés (bloc segment du HUD), aucun bonus, aucune arche, aucun bloc bonus.

Remarque : …

## 5. Option « Bonus » à « non » (5 minutes au plus)

Réglages, « Bonus : non ». Séance sur `demo` jusqu'au km 1,5.

- [ ] Ni arche, ni bonus, ni bloc bonus ; les segments restent chronométrés.
- [ ] Remets « Bonus : oui » à la fin.

Remarque : …

## 6. Reprise après une coupure du core (5 minutes au plus)

Pendant la montée de `demo`, coupe le core depuis un autre terminal, puis relance-le comme d'habitude.

```bash
pkill -f "openride-core"
```

- [ ] Bandeau « Core non joignable », puis reprise de la séance.
- [ ] Après la reprise, le journal de la séance a toujours ses lignes `powerup`, `segment` et `jersey`.

Remarque : …

## 7. Montée réelle (10 minutes au plus)

Une de tes traces compilées dont la montée commence dans les 2 premiers kilomètres (sinon un fichier `<trace>.segments.toml` qui déclare une montée courte au début). Arrête-toi au sommet, ou au bout de 10 minutes.

- [ ] Catégorie juste sur le panneau du pied de montée.
- [ ] Écart au record en direct au deuxième passage (un autre jour).
- [ ] Maillot à pois attribué au sommet.

Remarque : …

## 8. Course contre 4 bots à profil (10 minutes au plus, après T12, T13 et T15)

Grimpeur, Rouleur, Sprinteur et Diesel au niveau 100 %, sur `demo`. Arrête-toi après le sprint (km 3,3).

- [ ] Encart des voisins (« ▲ … +x,x s », « ▼ … −x,x s ») juste et stable dans la montée.
- [ ] Grimpeur devant dans la montée, Sprinteur qui lance le sprint dans les 200 derniers mètres.
- [ ] Ressenti de l'équilibrage : les bots ne sont ni intouchables ni trop faciles à 100 %.

Remarque : …

## 9. Rendu sur la GTX 1060

À relever pendant n'importe laquelle des étapes 1 à 3, dans le journal du lanceur (`~/run_trainer.log`), lignes `[perf-rendu]`.

- [ ] Pas de baisse d'images à l'approche des portiques et des arches.

Remarque : …

---

**Bilan :** validé / à corriger (une issue par point à corriger).
