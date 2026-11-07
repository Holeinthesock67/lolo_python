# Série BC (5.0) – Badges et cartes à collectionner

7 novembre 2026. Étude du lot BC0, demande du propriétaire du 7 novembre : « ajouter un esprit collectif : on gagne des badges ou des cartes suivant des accomplissements tels que 100 km, lève-tôt… ou des périodes de l'année telles que Halloween, premier an, Noël… ». Ajout du même jour : les visuels des cartes et des badges seront dessinés par une IA d'images (Gemini, « Nano Banana ») ; la série le prévoit dans un lot délégué (BC4).

Les cahiers des lots sont dans `docs/lots/LOT_BC*.md` ; leur tableau se calcule avec `python3 scripts/index_lots.py` (lot X54).

## 1. Lecture de la demande

- **« Esprit collectif » est lu comme « esprit de collection »** : un album de cartes à compléter, chaque carte étant un badge illustré. C'est la lecture la plus probable, et c'est celle que la série code.
- **Pas de dimension sociale (décision du propriétaire du 7 novembre, BC-Q1) :** « c'est juste l'aspect collection qui pourrait stimuler l'utilisation du jeu ». Tout reste local, sans compte en ligne ni comparaison entre joueurs : rien ne quitte le PC.
- **Badge et carte sont une seule chose** : une carte porte un badge (le visuel), un titre, une ligne d'ambiance et sa rareté. Un seul système, une seule liste, pas de « badges » à part des « cartes » (principe de conception du 27 octobre : pas d'exception).

## 2. Ce qui existe déjà et que la série reprend

| Existant | Repris pour |
| --- | --- |
| Progression de la série V (`progression.py`, lot V2) : séances recalculées depuis le journal, sources comptées, séances trop courtes refusées, journaux repris après panne comptés une fois, statistiques cumulées (`STATS`) | Les cartes partent des mêmes séances comptées (`Progress.counted`) et des mêmes statistiques. Aucune seconde lecture du journal, aucune seconde règle d'éligibilité. |
| Défis de la série V (`data/progression.toml`, `[[challenges]]` : 1 000 km, 10 000 m, 50 km d'une traite, 10 ERG, premier HC, maillot à pois, premier boss) | Chaque défi devient une carte (règle `defi`) avec le seuil lu dans la table de la progression : une seule définition. Le défi garde sa pièce d'équipement offerte ; la carte s'y ajoute. |
| Profils de joueurs (série MJ) : `seances_comptees` du `profil.toml`, profil d'essai `_essai`, journaux marqués `profile_id` | Chaque profil a sa collection ; les séances simulées ne comptent que dans le profil d'essai. |
| Historique au menu (lot O28) : séances, semaines, tests de FTP | L'écran « Collection » est une ligne voisine de l'accueil ; une carte gagnée renvoie à la séance de l'historique. |
| Lignes de jeu du journal : `segment`, `jersey`, `rogue_run`, `ftp_test`, `wtf_summary`, `survivor_summary` | Cartes des modes de jeu et des tests de FTP. BC1 ajoute les trois dernières sortes aux faits de séance (`progression.FACT_EVENT_KINDS`) ; l'expérience et les pièces les ignorent. |

## 3. Principes

1. **Tout se recalcule depuis le journal**, comme l'expérience : effacer un fichier de cache ne perd aucune carte ; changer le catalogue change aussi les cartes des séances passées. Les séances d'avant la série comptent (première ouverture : §7, annonce groupée).
2. **Une seule information nouvelle à la fois** : à la fin d'une séance, le bilan montre au plus une carte nouvelle, la plus rare (puis la plus récente), avec « + N autres dans la Collection ». Jamais de pluie de cartes.
3. **Pas de pression** : une carte de saison manquée ne coûte rien ; elle reste grisée « à revenir l'an prochain ». Pas de série perdue affichée en rouge, pas de compte à rebours, pas de rappel.
4. **Rien dans la boucle à 50 Hz** : le calcul se fait à l'ouverture de l'écran et au bilan de fin de séance, avec le cache des faits de la progression (lot V11).
5. **Lisible au Click** : textes courts (titre de 24 caractères au plus, ligne de 70), le texte est écrit par l'engine et jamais dans l'image (accents, tailles, traductions futures).

## 4. Catalogue des accomplissements

Fichier `core/src/openride_core/data/collection.toml` (lot BC1), 42 cartes au départ. Le catalogue se règle sans toucher au code ; chaque règle est l'un des neuf genres ci-dessous.

| Genre (`kind`) | Condition | Exemples du catalogue |
| --- | --- | --- |
| `cumul` | statistique de la progression atteinte (`total_km`, `total_climb_m`, `sessions`, `segment_prs`, `jerseys_sprint`…) | 100, 500, 5 000 et 40 000 km ; Everest (8 849 m cumulés) ; 50 séances ; maillot vert ; 10 records de segment |
| `defi` | défi de la série V réussi | 1 000 km, 10 000 m, 50 km d'une traite, 10 ERG terminés, premier HC, maillot à pois, premier boss |
| `seance` | N séances d'au moins X km, Y m de dénivelé, Z minutes | première séance, Centurion (100 km), 3 h, 1 000 m de dénivelé |
| `heure` | N séances commencées entre deux heures locales, d'au moins Z minutes | Lève-tôt (avant 7 h, dès 4 h, 20 min), Chant du coq (10 fois), Pause de midi, Noctambule (après 22 h) |
| `semaines` | N semaines ISO d'affilée avec au moins K séances | 3 séances dans la semaine, 4 semaines d'affilée, 12 semaines à 2 séances |
| `jours` | N jours d'affilée avec une séance | Sept jours sur sept |
| `mode` | N lignes de jeu d'une sorte ; Dernier survivant gagné | premier test de FTP, 4 tests, première run Cyber-Rogue, première séance WTF, Dernier debout |
| `saison` | séance d'au moins Z minutes dans une fenêtre de dates, ou autour de Pâques | Nouvel an, Saint-Valentin, Pâques, solstice, Grande Boucle (10 séances en juillet), Halloween (25 au 31 octobre), Noël (24 au 26 décembre), Saint-Sylvestre |
| `anniversaire` | séance au moins N ans après la première séance comptée | Première année, Deux ans de route |

Familles affichées (ordre de l'écran) : distance, séances, dénivelé, régularité, heure, entraînement, modes de jeu, saisons, anniversaires.

**Règles de date :**
- heure et date locales du départ de la séance (événement `start` du journal), jamais l'heure de l'ouverture de l'écran ;
- une fenêtre de saison peut passer le 31 décembre ; l'édition est l'année du début de la fenêtre ;
- Pâques est calculé (calendrier grégorien), la fenêtre est donnée en jours autour du dimanche ;
- l'anniversaire du 29 février tombe le 1er mars ;
- une carte de saison est **exclusive à sa période** (jamais rattrapable après la fenêtre, décision du 7 novembre) et se gagne **une fois par année** : « Halloween 2026 », « Halloween 2027 »… sont des éditions de la même carte, empilées sur la même case de l'album.

**Hors du premier catalogue** (à ajouter plus tard, sans code nouveau sauf mention) : séances d'un plan d'entraînement terminé (il faut le champ `plan` dans les faits de séance), parcours du pack « Cols célèbres » (il faut l'identifiant du parcours, déjà dans les faits), vélodrome (série VD), Course tactique (série CT), Grand Prix des objets (série GP) : leurs lignes de jeu s'ajouteront à `FACT_EVENT_KINDS` à leur livraison.

## 5. Format d'une carte

| Élément | Contenu | Règle |
| --- | --- | --- |
| Visuel | badge illustré, nom `visual` du catalogue (un visuel par carte) | image du lot BC4, sans texte, fond transparent |
| Cadre | couleur de la rareté | commune (bronze), rare (argent), épique (or), légendaire (irisé) ; dessiné par l'engine, pas dans l'image |
| Titre | `title`, 24 caractères au plus | écrit par l'engine |
| Ligne d'ambiance | `text`, 70 caractères au plus | écrite par l'engine |
| Pied | date d'obtention, édition (saisons), « n° 12 / 42 » | calculé |
| Carte pas encore gagnée | silhouette grise du visuel, titre visible, condition et avancement (« 120 / 500 km ») | les cartes de saison montrent leur période à la place de l'avancement |

Rareté : choisie dans le catalogue (pas calculée), d'après l'effort demandé. Premier catalogue : 11 communes, 21 rares (dont 7 des 8 cartes de saison), 7 épiques, 3 légendaires.

## 6. Stockage, historique et profils

- **Cartes gagnées :** jamais stockées, recalculées (`collection.evaluate`). La date et la séance qui ont fait gagner la carte en sortent aussi ; l'écran renvoie à cette séance dans l'historique (O28).
- **Cartes déjà montrées :** seul fichier écrit, `collection_vue.json` dans le dossier du profil en cours (`Profils/<id>/`), liste triée de clés (`km_100`, `halloween:2026`). Écriture sûre (fichier temporaire puis remplacement). Un fichier absent veut dire « collection jamais ouverte » ; un fichier abîmé vaut « tout est déjà vu » (aucune avalanche d'annonces, et rien n'est perdu).
- **Profils :** chaque profil a sa collection et son fichier ; le profil d'essai compte aussi les séances simulées, mais dans sa collection seulement. Une carte ne passe jamais d'un profil à l'autre.
- **Historique (O28) :** lot BC6, la ligne d'une séance peut porter le petit badge de la carte gagnée ce jour-là (ajout compatible du message `history`).

## 7. Écran au menu et annonce (maquettes à valider avant tout code d'affichage)

Le lot BC3 dessine les maquettes en low, medium et high ; **aucune ligne d'affichage (BC5, BC6) ne s'écrit avant leur validation par le propriétaire** (règle des captures du 28 octobre).

Proposition à dessiner :

- **Accueil :** ligne « Collection » après « Historique », avec en détail « 12 / 42 cartes ».
- **Écran « Collection » :** une famille par rangée (distance, séances…), cartes en vignettes ; au Click, flèches pour se déplacer, A pour agrandir une carte (visuel, titre, ligne d'ambiance, date, « Voir la séance »), Y pour revenir. Les cartes nouvelles portent un point, retiré quand on les a agrandies (c'est là que `collection_vue.json` est écrit).
- **Annonce au bilan de fin de séance :** un seul encart, la carte la plus rare des nouvelles, et « + 2 autres dans la Collection » s'il y en a d'autres. Pendant la séance : rien (pas d'encart qui masque la route ou le HUD).
- **Première ouverture** (séances d'avant la série) : un seul message, « 18 cartes déjà gagnées par vos séances passées », puis l'album.

## 8. Anti-triche simple

- Séances simulées et rejouées : jamais comptées dans un profil de joueur (sources du `profil.toml`, série MJ) ; comptées seulement dans le profil d'essai, qui sert aux recettes.
- Séance de moins de 5 minutes chronométrées : refusée (règle `min_session_s` de la progression) ; les cartes d'heure et de saison demandent en plus 20 minutes.
- Journal d'un autre profil : ignoré ; journal repris après une panne : compté une fois.
- Horloge déréglée : une séance datée de plus d'un jour après l'heure de l'appel ne compte pas (`ignored_future`), ce qui bloque les cartes de saison gagnées en avançant la date du PC. Reculer l'horloge n'est pas bloqué : la collection est personnelle, sans enjeu à partager.

## 9. Vie privée

- Tout reste sur le PC, sans compte ni réseau ; aucune carte n'est envoyée nulle part.
- Le dépôt ne contient que le catalogue et des historiques synthétiques (dates fictives, aucune séance réelle, aucun nom, aucun lieu). `collection_vue.json` et les journaux restent dans `~/OpenRide/`.
- Les cartes ne contiennent ni lieu ni coordonnées : pas de carte « Votre ville », pas de nom de route réel sauf ceux du pack public des cols.
- Les consignes d'images envoyées à Gemini (BC4) ne contiennent que le nom et le thème de la carte, jamais une donnée du cycliste.

## 10. Lots

| Lot | Contenu | Langage | Dépend de | Recette |
| --- | --- | --- | --- | --- |
| BC0 | ce plan | Doc | – | relecture du propriétaire |
| BC1 | catalogue, calcul, cartes vues, annonce, commande `openride-core collection` | Python | V2, MJ2 | CI (historiques synthétiques) |
| BC2 | contrat IPC : `list_collection`, message `collection`, `collection_seen`, annonce dans `summary` | Python | BC1 | CI |
| BC3 | maquettes de l'écran, de la carte agrandie et de l'annonce (low, medium, high) | GDScript | BC1 | **validation du propriétaire** |
| BC4 | visuels des 42 cartes par Gemini : fiche de commande, contrôle à l'import | Doc + Python | BC0 | contrôle automatique + planche validée |
| BC5 | écran « Collection » au menu | GDScript | BC2, BC3 validé, BC4 | captures validées |
| BC6 | annonce au bilan, badge dans l'historique | Python + GDScript | BC2, BC3 validé | captures validées |
| BC7 | recette sur le PC (profil d'essai, séances simulées, low, medium, high) | – | BC5, BC6 | propriétaire |

## 11. Questions ouvertes (réponses par défaut appliquées, BC-Q1 et BC-Q2 tranchées le 7 novembre)

| # | Question | Réponse par défaut |
| --- | --- | --- |
| BC-Q1 | « Esprit collectif » : une collection personnelle, ou une vraie dimension sociale (comparer, gagner à plusieurs) ? | **tranché le 7 novembre** : collection personnelle seulement, pas de social |
| BC-Q2 | Cartes de saison : une par année (éditions empilées) ou une seule fois pour toujours ? | **tranché le 7 novembre** : éditions saisonnières exclusives, une par année, à gagner pendant leur période seulement |
| BC-Q3 | Les séances d'avant la série comptent-elles ? | oui, annonce groupée à la première ouverture |
| BC-Q4 | Lève-tôt : avant 7 h ? Noctambule : après 22 h ? | 4 h à 7 h et 22 h à 4 h, 20 minutes au moins |
| BC-Q5 | Les cartes rapportent-elles de l'expérience ou des pièces ? | non : les défis gardent leur pièce offerte, les autres cartes ne donnent rien (pas de double récompense, l'équilibrage de la série V ne bouge pas) |
| BC-Q6 | Fêtes à ajouter (fête des pères et des mères, 14 juillet, jour du Tour…) ? | catalogue de départ du §4, extensible sans code |
| BC-Q7 | Style des visuels pour Gemini (§12) ? | badges ronds en aplat, style de la charte cartoon (CT9), une planche d'essai de 6 cartes validée avant les 42 |

## 12. Visuels délégués à Gemini (lot BC4)

- **Une fiche de commande par carte** ([VISUELS_BC4.md](VISUELS_BC4.md), écrite le 7 novembre : bloc de style commun, couleur par rareté, une consigne par carte) : nom du visuel, sujet (« un coq sur un guidon au lever du soleil »), rareté, palette, à éviter (texte, chiffres, logos, marques, personnes réelles).
- **Format attendu :** PNG 512 × 512 (l'IA peut livrer en 1024 × 1024, réduit au contrôle), fond transparent, sujet centré dans un cercle de 440 px, aucune lettre ni chiffre dans l'image (le texte est écrit par l'engine), poids sous 200 Ko.
- **Contrôle à l'import** (script de BC4, en CI) : un fichier par `visual` du catalogue, taille, transparence, poids ; un visuel manquant s'affiche avec un pictogramme neutre, jamais une erreur.
- **Planche d'essai d'abord** : 6 cartes (une par rareté, une de saison, une d'heure), validée par le propriétaire avant de commander les 36 autres.
- Les images sont générées hors du dépôt par le propriétaire (ou une session qui a accès à Gemini) et déposées dans un dossier `collection` des ressources de l'engine (choisi par BC4) ; la licence d'usage des images générées est notée dans la PR.
