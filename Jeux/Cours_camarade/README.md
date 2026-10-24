# Cours, camarade

*Le vieux monde est derrière toi. Le CRS aussi.*

Jeu de course sans fin pour navigateur, façon Subway Surfers. Un manifestant remonte
un boulevard parisien sur trois files, esquive les obstacles et doit semer le CRS
qui le poursuit.

## Lancer le jeu

Tout le jeu tient dans **un seul fichier** : `index.html`.

- Double-cliquer sur `index.html` : il s'ouvre dans le navigateur (Chrome, Firefox,
  Edge, Safari, ordinateur ou téléphone).
- Rien à installer, aucun serveur, aucune image ni aucun son à côté : les dessins sont
  faits par le code (canvas) et les sons sont générés par le navigateur (Web Audio).
- Seule dépendance réseau : les polices **Anton** et **Barlow Semi Condensed**
  (Google Fonts). Hors ligne, le jeu marche pareil avec une police de remplacement (Impact).

## Commandes

| Action | Clavier | Tactile |
|---|---|---|
| Changer de file | `←` `→` (ou `Q`/`A` et `D`) | Balayer à gauche / à droite |
| Sauter | `↑`, `Espace` (ou `Z`/`W`) | Balayer vers le haut ou toucher |
| Glisser | `↓` (ou `S`) ; en l'air : descente rapide | Balayer vers le bas |
| Pause | `P` ou `Échap` | Bouton `II` |
| Démarrer / rejouer | `Entrée` | Bouton du menu |

Le bouton `♪` coupe ou rétablit le son. Le jeu se met en pause tout seul quand
l'onglet passe en arrière-plan.

## Règles

### Obstacles

| Obstacle | Comment le passer | Si on le heurte |
|---|---|---|
| Barrière de police | Sauter | Faux pas |
| Poubelle en feu | Sauter | Faux pas |
| Banderole (une file ou toute la rue) | Glisser dessous | Faux pas |
| Fourgon de police | Changer de file | De face : interpellation immédiate. Par le côté : faux pas et retour dans sa file |
| Nuage de lacrymo | Changer de file | Faux pas atténué, écran voilé quelques secondes |

### Le CRS

- La jauge en haut de l'écran donne la distance du CRS (« CRS à 12 m »).
- Au départ il est juste derrière. En courant sans heurt, il recule petit à petit.
  À 100 % il est **semé** : +100 points.
- Chaque faux pas le rapproche beaucoup (bords de l'écran rouges quand il est tout près).
  S'il arrive au contact, c'est **« Interpellé ! »** et la partie s'arrête.
- Un CRS semé revient au faux pas suivant.

### Bonus et score

- **Merguez** : 10 points chacune.
- **Mégaphone** : 8 secondes inarrêtable. On renverse les obstacles (+20 points chacun)
  et le CRS recule plus vite.
- **Score** = distance parcourue (m) + merguez × 10 + bonus (CRS semés, obstacles renversés).
- La vitesse augmente avec le temps, et les obstacles deviennent plus fréquents.
- Le **record** est gardé dans le navigateur (`localStorage`). Il reste propre à chaque
  navigateur et à chaque appareil.

## Organisation du code (`index.html`)

Un seul fichier : HTML (menus, HUD), CSS, puis un script JavaScript sans bibliothèque.

| Partie du script | Rôle |
|---|---|
| Monde & projection | Perspective 3D simplifiée : `proj(x, y, z)` convertit une position du monde (x : files, y : hauteur, z : distance devant le joueur) en pixels |
| Son | Bruitages synthétisés : saut, merguez, choc, toux, sifflet du CRS |
| Contenu | Slogans des banderoles et dimensions de chaque obstacle (`DEF`) |
| État / génération | `spawnRow` crée une rangée d'obstacles en laissant toujours au moins une file passable ; `addBuilding` ajoute les immeubles haussmanniens |
| Mise à jour | Défilement, physique du saut et de la glissade, distance du CRS, collisions (de face ou de côté) |
| Rendu | Ciel et fumées, immeubles, chaussée, obstacles triés du plus loin au plus près, manifestant et CRS |
| HUD / boucle | Score, jauge du CRS, boucle `requestAnimationFrame` |

### Réglages faciles

Constantes en tête du script ou dans `update` :

- `GRAV`, `JUMP_V` : gravité et hauteur du saut.
- `speed = Math.min(30, 13 + t * .2)` : vitesse de départ, accélération et vitesse maximale.
- `crs += dt * 4.2` : vitesse à laquelle on sème le CRS ; `stumble(msg, 50)` : ce que coûte un faux pas.
- `SLOGANS`, `SLOGANS_WIDE` : textes des banderoles.
