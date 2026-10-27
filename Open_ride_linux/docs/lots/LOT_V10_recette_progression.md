# Lot V10 – Recette de la série V sur le PC et le vélo du propriétaire

## 1. Objectif

Vérifier sur le matériel réel que la progression est juste, que l'équipement se sent sans fausser les temps et que l'avatar s'affiche dans le budget de rendu.

**Lot du propriétaire :** essais sur le PC cible (GTX 1060) et le home trainer ; l'assistant prépare les commandes et lit les journaux.

## 2. À lire

`docs/2.0/PLAN_SERIE_V.md`, les sections « Livraison » des lots T1 (contrat 1.4), V2 à V9 et V11, `docs/OUTILS_DE_TEST.md`.

## 3. Prérequis

T1 (contrat 1.4), V2 à V9 et V11 livrés (V5 pour la partie segments, maillots et Cyber-Rogue, sinon cette partie est recettée avec les séries T et R).

## 4. Déroulé

1. **Historique réel :** `openride-core xp` sur `~/OpenRide/Activities/.journal` ; relire niveau, séances comptées et refusées (rejeu, simulation, moins de 5 min). Si la courbe paraît trop lente ou trop rapide, ajuster `~/OpenRide/progression.toml` (copie locale) avant de figer les valeurs du dépôt (risque 2 du plan). Aucune donnée de l'historique n'entre dans le dépôt.
2. **Séance courte (20 min) en SIM** avec l'équipement de départ : bilan V9 cohérent avec `openride-core xp`, pièces gagnées.
3. **Garage :** acheter et choisir un cadre et des roues au Click ; même parcours plat de 10 min à puissance comparable : vitesse virtuelle plus haute avec Aéro + Lenticulaire, résistance du trainer identique au ressenti et dans le journal (pente envoyée), « temps gagné » affiché.
4. **Avatar :** caméra de suivi, pédalage à 60 et 100 rpm, danseuse dans une rampe, réglages de l'avatar ; ligne `[perf-rendu]` : au moins 55 images/s en qualité basse avec la série P activée.
5. **Robustesse :** effacer `~/OpenRide/profile.json` (après copie) : niveau et pièces gagnées recalculés, choix revenus aux défauts.

## 5. Critères d'acceptation

Les cinq étapes passent ; les écarts sont notés dans `docs/SUIVI_AVANCEMENT.md` et deviennent des issues.

## 6. Hors périmètre

Séries T et R elles-mêmes (leurs recettes T11 et R14).
