# Lots de travail sous-traitables – index et règles communes

23 octobre 2026. Ces cahiers des charges permettent de confier une partie d'OpenRide à une autre IA (ou à un développeur) sans le contexte des conversations précédentes. Chaque lot est **autonome** : il dit quoi lire, quoi produire, quels fichiers toucher et comment la livraison sera recettée.

## 1. Liste des lots

| Lot | Titre | Langage | Dépend de | Taille | Prêt à confier |
| --- | --- | --- | --- | --- | --- |
| [A](LOT_A_route.md) | Lecteur `.world` et interpolation de route partagés core/engine | Python + GDScript | — | Moyenne | Oui |
| [B1](LOT_B1_compilateur_route.md) | Compilateur : GPX vers `.world` (couche route) | Python | Aucune (A utile pour la vérification croisée) | Moyenne | Oui |
| [B2](LOT_B2_compilateur_terrain.md) | Compilateur : couche terrain (MNT Copernicus, tuiles) | Python | B1 | Grande | Après B1 |
| [C](LOT_C_core_conformite.md) | Mise en conformité du core avec le contrat IPC (défauts de l'audit) | Python | — | Petite | Oui |
| [D](LOT_D_engine_ipc.md) | Mise en conformité de l'engine avec le contrat IPC | GDScript | A (lecture du parcours par `route_id`) | Moyenne | Oui, partie route après A |
| [E1](LOT_E1_rendu_route_terrain.md) | Rendu 3D : ruban de route et terrain par tronçons | GDScript | A, D ; tuiles du format (B2 ou générateur fourni) | Grande | Après A et D |
| [F](LOT_F_erg_zwo.md) | Entraînements ERG : lecteur `.zwo` et pilotage ERG dans le core | Python | C | Moyenne | Après C |

**Restent en interne** (matériel nécessaire) :
- stabilité du Zwift Click (déconnexions spontanées) ;
- essais sur le vélo ;
- validation des fichiers FIT dans GoldenCheetah et Garmin Connect.

**À rédiger plus tard :**
- E2 : shader triplanaire et chargeur de thèmes ;
- E3 : végétation par bruit ;
- G : lanceur unique et menus pilotés au Click.

Leur forme dépendra des choix faits dans E1 et D.

**Ordre conseillé :** C et A en parallèle, puis B1 et D, puis B2, E1 et F.

```text
A ──► B1 ──► B2 ──┐
│                 ├──► E1
└──► D ───────────┘
C ──► F
```

## 2. Prérequis côté propriétaire du projet (avant de confier un lot)

1. Fusionner la branche `claude/openride-sprint1-drivers` dans `main` (audit, E4).
2. Donner à l'IA un accès en écriture au dépôt `Holeinthesock67/lolo_python`, ou lui remettre une copie et récupérer un correctif.
3. Lui transmettre le texte du lot et les documents listés dans sa section « À lire ».

## 3. Règles communes à tous les lots

**Documents qui font loi.** `docs/SRS_v1.1.md`, `docs/contracts/ipc_v1.md`, `docs/contracts/world_format_v1.md` et les schémas JSON de `docs/contracts/`.
- Un lot ne modifie un contrat que si sa section « Modifications de contrat autorisées » le prévoit.
- Si le travail révèle qu'un contrat est faux ou incomplet, l'IA **s'arrête et le signale** dans son rapport, au lieu de l'interpréter.

**Dépôt.**
- Le projet est dans le dossier `Open_ride_linux/` du dépôt `lolo_python`, qui contient d'autres projets sans rapport : ne rien toucher en dehors de `Open_ride_linux/`.
- Chaque lot se fait sur une branche `lot-<id>-<sujet>` partant de `main` à jour. Une demande de fusion (pull request) par lot.
- Ne modifier que les fichiers listés dans « Fichiers concernés ». Un fichier supplémentaire indispensable est signalé et justifié dans le rapport.

**Code.**
- **Python :**
  - version 3.11 minimum, et le code doit aussi tourner en 3.14 (version du PC cible) ;
  - typage avec annotations et dataclasses comme dans le code existant ;
  - aucune entrée-sortie bloquante dans la boucle du core.
- **GDScript :**
  - Godot 4.3 ;
  - pas de `class_name` pour les scripts dont dépend la scène principale : l'engine est lancé sans passer par l'éditeur, et Godot ne connaît alors pas les `class_name`. Utiliser `preload`.
- **Langue :** commentaires, docstrings et messages de journal en français ; identifiants en anglais.
- **Dépendances :** toute nouvelle dépendance est déclarée dans le `pyproject.toml` concerné et justifiée dans le rapport. Pas de bibliothèque pour ce que la bibliothèque standard ou une dépendance existante fait déjà.
- **Hors ligne :** aucun accès réseau à l'exécution, sauf dans le lot B2, qui télécharge des tuiles d'altitude dans un cache.

**Tests.**
- Chaque critère d'acceptation vérifiable par machine a son test automatique.
- `pytest` passe en entier (tests existants compris) dans `Open_ride_linux/core/` et, s'il existe, dans `Open_ride_linux/compiler/`.
- Côté Godot, les tests se lancent sans écran : `godot --headless --path engine ...` (Godot 4.3 officiel, téléchargeable sur GitHub).
- Le matériel (HomeTrainer, Click) n'est pas disponible pour l'IA. Tout ce qui dépend du matériel se teste avec les doublures existantes (`MockDriver`, faux clients BLE dans `core/tests/test_drivers_session.py`). Les essais réels sont listés dans le rapport pour le propriétaire.

**Livraison.** La demande de fusion contient :
1. le résumé de ce qui a été fait ;
2. la liste des critères d'acceptation, cochés, avec la commande qui les prouve ;
3. la sortie des tests ;
4. les écarts ou questions ouvertes ;
5. les essais à faire sur le matériel, s'il y en a.

**Recette.** Le propriétaire (ou Claude) relit la demande, relance les tests, vérifie les critères et fait les essais réels. Un critère non tenu renvoie le lot.

## 4. Modèle de message pour confier un lot

```text
Tu travailles sur OpenRide Linux, dépôt GitHub Holeinthesock67/lolo_python, dossier Open_ride_linux/.
Lis d'abord docs/lots/00_INDEX.md (règles communes), puis docs/lots/LOT_<X>_....md (ton lot), puis
les documents listés dans sa section « À lire ». Respecte strictement les fichiers autorisés et les
contrats. Crée la branche lot-<x>-<sujet> depuis main, fais le travail, fais passer tous les tests,
puis ouvre une pull request avec la liste des critères d'acceptation cochés et la sortie des tests.
Si un contrat te semble faux ou incomplet, arrête-toi et pose la question au lieu d'improviser.
```
