# Lot O6 – Guide d'utilisation et README de la 1.0

## 1. Objectif

Le `README.md` décrit encore l'état du 23 octobre et un lancement par terminal. Après la série N, OpenRide s'installe en une commande et s'utilise depuis l'icône. Ce lot écrit un **guide d'utilisation court, sans terminal**, et remet le `README.md` à jour pour la 1.0 : ce qu'est OpenRide, comment l'installer, où trouver le guide, et une partie « développeur » séparée.

## 2. À lire

1. `README.md`, `CLAUDE.md`, `docs/SUIVI_AVANCEMENT.md`, `docs/lots/00_INDEX.md`.
2. Cahiers et « Livraison » de N6, N10, N11, N12, N13, N14 (et O3, O4, O5 s'ils sont livrés).
3. `core/tests/test_docs_coherence.py` (règles vérifiées sur la documentation : liens, lots cités, nombres de tests, caractères).

## 3. Prérequis

N6, N13 et N14 fusionnés (les écrans et l'installation décrits doivent exister). Peut être repris après O4 et O5 pour une ligne chacun.

## 4. Travail demandé

- **Nouveau `docs/GUIDE_UTILISATION.md`**, en français simple, une page par sujet au plus, sans commande sauf l'installation et le dépannage :
  1. Ce qu'il faut (Ubuntu, home trainer FTMS, Zwift Click facultatif, ceinture cardio facultative, carte graphique).
  2. Installer et mettre à jour (commande unique de N14, bouton « Mettre à jour »).
  3. Premier démarrage et appairage (section « Appareils », identification du bouton +).
  4. Rouler un parcours : déposer un GPX (ou FIT/TCX si O5 est livré) dans `~/OpenRide/GPX/`, choix au menu, pause, fin, bilan.
  5. Faire un entraînement ERG : ajouter un `.zwo`, biais au Click, saut de bloc.
  6. Commandes du Click et du clavier (tableau, en reprenant le code : `menu_model.gd`, `zwift_click.py`, et non de mémoire).
  7. Réglages (FTP, thème, qualité) et thèmes supplémentaires.
  8. Retrouver ses séances (`~/OpenRide/Activities/`, import dans Garmin Connect ou GoldenCheetah).
  9. Dépannage : trainer réservé par une autre application (« Libérer le trainer »), Click qui ne répond plus (dont le boîtier gauche), écran noir ou lent (qualité basse), où est le journal et quoi envoyer.
- **`README.md`** : réécrire la section « État » en une description de la version, garder l'installation courte avec un lien vers le guide, déplacer les commandes de développement (tests, `openride-dev.sh`, simulateur) dans une section « Développement ».
- Ajouter un test de cohérence : chaque raccourci cité dans le tableau du guide existe dans le code (mêmes touches que `menu_model.gd` et le lanceur).
- Aucune donnée personnelle (nom, adresse Bluetooth réelle, nom ou modèle du trainer, coordonnées précises) : exemples avec « HomeTrainer » et les adresses simulées.

## 5. Fichiers concernés

- **Nouveaux :** `docs/GUIDE_UTILISATION.md`.
- **Modifiés :** `README.md`, `CLAUDE.md` (lien vers le guide), `core/tests/test_docs_coherence.py`, `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Interdits :** le code applicatif.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `pytest -q` passe dans `core/` (tests de cohérence de la documentation compris).
2. Chaque option, commande ou fichier cité dans le guide existe dans le code de `main` (vérifié par le test ou listé dans la PR).
3. Le guide se lit sans connaître le projet : relu par une IA sans contexte, qui doit pouvoir répondre à « comment j'ajoute un parcours ? » et « que faire si le trainer ne répond pas ? » à partir du guide seul (questions et réponses jointes à la PR).
4. Aucune donnée personnelle (recherche dans la PR).

**Le propriétaire :** suivre le guide du début à la fin lors de la recette O8.

## 8. Hors périmètre

- Traduction en anglais, captures d'écran (à ajouter après la recette si souhaité).
