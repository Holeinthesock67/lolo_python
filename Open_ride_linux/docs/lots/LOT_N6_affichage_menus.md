# Lot N6 – Affichage des menus, de l'état des appareils et du bilan ; fin de `--autostart` obligatoire

## 1. Objectif

Lancer OpenRide depuis l'icône du bureau, choisir un parcours et un entraînement au Click, rouler, mettre en pause, terminer et lire son bilan, **sans terminal ni `--autostart`**. Ce lot affiche les modèles déjà écrits (K5, N3, N4, N5) dans la scène principale et les raccorde au core v1.1 (N2).

**Lot interne :** il modifie `main.gd` et la scène après E3/E4, et sa recette est visuelle (lisibilité à 2 m de l'écran, navigation au Click réel).

## 2. À lire

1. `docs/lots/00_INDEX.md`, `docs/contracts/ipc_v1.md` en v1.1.
2. Cahiers K5, N3, N4, N5 et leurs sections « Livraison ».
3. Code : `engine/scripts/main.gd`, `engine/scenes/main.tscn`, le HUD final d'E3, `engine/scripts/banner.gd`, `core/src/openride_core/launcher.py`, `scripts/openride-dev.sh`.

## 3. Prérequis

PR #91 (E3/E4), N2, N3, N4 et N5 fusionnés.

## 4. Travail demandé

- Couche d'interface au-dessus de la vue 3D : écran d'accueil, listes, écran « Prêt » (aperçu du profil d'altitude ou de l'entraînement), pause, confirmation, état des appareils, bilan de fin ; police lisible à 2 m (taille du HUD final d'E3), focus très visible, retour sonore à chaque appui (bips existants).
- Pendant `RUNNING`, le menu est caché et les événements `input` ne servent qu'aux bips (contrat §4) ; la pause au clavier (et au Click, geste à choisir avec Laurent : l'appui long − sert déjà au braquet en SIM) ouvre l'écran de pause.
- Le décor tourne en fond pendant les menus (caméra lente sur le parcours choisi, ou parcours de démonstration).
- `openride` (lanceur) démarre par défaut **sans** `--autostart` ; `--autostart` reste disponible pour les essais.
- Tests graphiques (`engine/tests/run_visual_tests.sh`) : ajouter les écrans de menu aux captures de référence.

## 5. Fichiers concernés

`main.gd`, `main.tscn`, nouveaux `menu_view.gd`, `devices_view.gd`, `summary_view.gd`, `launcher.py` (défaut sans `--autostart`), tests graphiques, `README.md`, `docs/SUIVI_AVANCEMENT.md`.

## 6. Modifications de contrat autorisées

Aucune (contrat v1.1 du lot N1).

## 7. Critères d'acceptation

1. Toutes les suites passent (core, compilateur, engine, bout en bout, tests graphiques avec les nouveaux écrans).
2. Sur le PC cible : depuis l'icône, choisir le 2ᵉ parcours et un entraînement au Click, rouler 5 min, pause, reprise, terminer et enregistrer, lire le bilan, nouvelle séance, quitter ; aucun terminal ouvert.
3. Un parcours « à compiler » ne peut pas être choisi et affiche pourquoi.
4. Débrancher un boîtier du Click pendant le menu : la ligne d'état change, le clavier reste utilisable.
5. Images par seconde inchangées pendant la séance (menu caché) par rapport à E3.

## 8. Hors périmètre

- Réglages modifiables depuis le menu (FTP, thème, qualité) : lot ultérieur.
- Compilation depuis le menu (N11 compile au lancement).
