# Lot R10 – Engine : scène néon, ruban 3D, shader de pente, arches et zones

## 1. Objectif

La scène Godot du mode Cyber-Rogue : une piste suspendue dans le vide (le « ruban tactique »), construite depuis le message `room`, colorée selon la pente, avec ses arches, zones et balises, dans un décor néon (grille, glow, particules) et le Firewall derrière le joueur. Elle est séparée de la scène du mode classique et partage le client IPC, le menu et le HUD de base. Lot interne : contrôle visuel.

## 2. À lire

1. `docs/lots/00_INDEX.md`, `docs/2.0/GDD_CYBER_ROGUE.md` §1.3, §2.4 et §3 (avec leurs corrections), `docs/lots/LOT_R1_contrat_ipc_rogue.md` §4.4 et §4.5.
2. Code : `engine/scenes/main.tscn`, `engine/scripts/main.gd`, `engine/scripts/ipc_client.gd`, `engine/scripts/road_builder.gd` (construction d'un ruban), `engine/scripts/quality_presets.gd` et `render_quality.gd` (lot L4).

## 3. Prérequis

R1 livré. Un faux core (`engine/tests/fake_core.py`) qui joue une salle d'exemple, ajouté par ce lot.

## 4. Travail demandé

### 4.1 Chargement de la scène

- `engine/scenes/rogue.tscn`, chargée par `preload` (pas de `class_name`, règle commune) et **instanciée par `main.gd`** comme enfant de la scène principale quand `state.mode` devient `"ROGUE"` ; le monde du mode classique (terrain, route, décor, ciel) est alors masqué et ses mises à jour arrêtées. Retour à `FINISHED` puis au menu : la scène est libérée et le monde classique revient. Pas de `change_scene` : le client IPC, le menu et la pause restent ceux de `main.gd`.

### 4.2 Ruban

- Construit depuis `room.profile` (tous les 10 m), largeur 6 m, épaisseur 0,3 m, sans terrain ; la salle suivante (`next`) est accrochée au bout pendant le couloir.
- Inclinaison visible exagérée pour la lisibilité (comme Q2), même facteur réglable.
- **Couleur selon la pente** (corrigée le 26 octobre, le GDD laissait des trous) :

| Pente de l'ennemi | Couleur |
| --- | --- |
| < −3 % | Bleu (descente, utile au Tremplin cinétique) |
| −3 à +1,5 % | Cyan |
| +1,5 à +4 % | Jaune |
| +4 à +6,5 % | Orange |
| ≥ +6,5 % | Magenta (mur) |

- Les 200 m devant le joueur sont toujours affichés en couleurs franches (10 à 15 s à l'avance).
- Marqueurs : arches dorées (`arch`), cibles d'attaque [Z] orange, zones de parade [Z] bleues, pavés, balises de purge, tunnels de cadence (anneaux), rochers ; la fenêtre active (`state.rogue.windows`) s'allume.

### 4.3 Décor et Firewall

- Fond noir ou bleu nuit, grille au sol infinie (shader), glow de l'environnement Godot, particules GPU légères ; aucune texture photo.
- Firewall : mur translucide rouge à `firewall_gap_m` derrière le joueur, qui pulse au contact.
- Qualité : les préréglages existants (`low` à `high`) règlent glow, particules et distance de vue ; sur la GTX 1060 en `low`, 60 images/s ou plus.

### 4.4 Noms

Aucune référence à des marques ni à des œuvres existantes dans les noms de fichiers, de nœuds ou de ressources (risque 7 du plan).

## 5. Fichiers concernés

- **Créés :** `engine/scenes/rogue.tscn`, `engine/scripts/rogue/ribbon_builder.gd`, `engine/scripts/rogue/ribbon_colors.gd`, `engine/scripts/rogue/neon_grid.gdshader`, `engine/scripts/rogue/firewall_view.gd`, `engine/tests/unit/test_ribbon_builder.gd`, `engine/tests/unit/test_ribbon_colors.gd`.
- **Modifiés :** `engine/scripts/main.gd` (chargement de la scène), `engine/scripts/ipc_client.gd` (messages `room` et `loot`, `rogue_resync`), `engine/tests/fake_core.py` (salle d'exemple), `docs/SUIVI_AVANCEMENT.md`.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. Tests sans écran (`engine/tests/run_engine_tests.sh`) : couleurs aux bornes du tableau, ruban de la bonne longueur et des bonnes pentes, marqueurs aux bonnes distances.
2. `rogue_resync` envoyé quand un `room_id` est inconnu, au plus une fois par seconde (test avec le faux core).
3. Passage `ROGUE` puis retour au menu : le monde classique revient intact (test sans écran : nœuds visibles et mis à jour).
4. Contrôle visuel du propriétaire sur la GTX 1060 : lisibilité à l'effort, 60 images/s en `low`.

## 8. Hors périmètre

- HUD diégétique (R11), ennemis (R12), menus (R13).
