# OpenRide 2.0 – Progression : niveaux, équipement et avatar (série V)

25 octobre 2026. Demande du propriétaire, acceptée pour la 2.0 : une progression façon Zwift, avec niveaux et points d'expérience, vélos, roues et tenues à débloquer, et un avatar personnalisable. **La série V commence après la 1.0.** Cahiers des lots rédigés le 26 octobre 2026 (`docs/lots/LOT_V*.md`, index `docs/lots/00_INDEX.md`) ; les choix encore ouverts sont les questions V-Q5 à V-Q13 du §5 (V-Q4 réglée le 26 octobre).

## 1. En résumé

- **Une seule progression pour tous les modes :** une séance classique, un entraînement ERG et une run Cyber-Rogue rapportent de l'expérience au même profil.
- **Calculée depuis le journal :** l'expérience se recalcule à partir des séances enregistrées par OpenRide (son propre journal). Tes séances passées dans le jeu comptent donc dès l'arrivée de la série, et rien ne se perd si le fichier de progression est effacé. Les traces importées (FIT ou GPX de Garmin, lot M7) ne rapportent rien.
- **Équipement à effets bornés mais sensibles :** vélos et roues changent un peu la masse et le CdA, donc la vitesse virtuelle seulement, par la même voie que les bonus de la série T. L'écart reste petit en chiffres, mais il se voit, s'entend et se compte (§2.2). Tenues et avatar sont de l'apparence.
- **Pièces :** une monnaie gagnée en roulant achète de l'équipement, et des vies dans le mode Cyber-Rogue.
- **Les châssis du Cyber-Rogue** (série R, lot R9) sont le pendant de l'équipement dans ce mode : même système de déblocage, effets propres au jeu.

## 2. Choix de conception proposés

### 2.1 Expérience et niveaux

| Source | Gain proposé |
| --- | --- |
| Distance roulée | 20 points par km |
| Dénivelé positif | 2 points par mètre |
| Entraînement ERG | 10 points par minute, + 20 % si l'entraînement est terminé |
| Segments (série T) | 50 points par segment, 100 par record personnel |
| Maillots (série T) | 200 points par maillot gagné dans la séance |
| Run Cyber-Rogue (série R) | 10 points par minute, + bonus selon le boss vaincu |

- 50 niveaux ; points nécessaires croissants (environ 1 000 au niveau 2, 100 000 au total pour le niveau 50, soit quelques mois de pratique régulière).
- Valeurs dans un fichier de données modifiable, comme les tables d'équilibrage des séries R et T.
- Seules les séances enregistrées par le jeu comptent (décision du 25 octobre) : pas de traces importées, pas de séance de moins de 5 minutes, pas de séance rejouée (`replay`).

### 2.1 bis Pièces

- Gagnées en roulant, en même temps que l'expérience, selon l'effort fourni (V-Q10, 27 octobre) : chaque minute rapporte de 0,25 à 2 pièces selon la puissance en % de la FTP, en SIM comme en ERG ; en plus, 5 par segment, 20 par maillot, 10 à 50 par run Cyber-Rogue selon le boss.
- Dépensées dans le Garage pour l'équipement, et dans le mode Cyber-Rogue pour des vies (série R).
- Prix et gains dans le même fichier de données que l'expérience.

### 2.2 Équipement

| Catégorie | Exemples | Effet |
| --- | --- | --- |
| Cadre | Polyvalent, grimpeur, aéro, contre-la-montre | Masse de −1,5 à +0,5 kg, CdA de −4 % à 0 % |
| Roues | Standard, légères, profilées, lenticulaire | Masse de −0,5 à +0,5 kg, CdA de −3 % à 0 % |
| Casque, tenue, chaussettes, lunettes | Couleurs, motifs, maillots de club | Apparence seulement |

- **Déblocage :** une pièce d'équipement devient achetable à un niveau donné, puis s'achète avec des pièces ; quelques pièces sont offertes par défi (premier col HC, 1 000 km cumulés, maillot à pois gagné, boss Cyber-Rogue vaincu).
- **Effets bornés** à −3 % de masse totale et −6 % de CdA au plus, cadre et roues ensemble, pour garder les temps comparables.
- **Rendre ces effets sensibles (décision du 25 octobre : petits effets sur la physique, impact notable sur le plaisir de jeu) :**
    - **des compromis qui obligent à choisir :** le cadre aéro est plus lourd, le cadre grimpeur moins aéro, la roue lenticulaire perd de son avantage par vent de travers (série P) ; le bon choix dépend du parcours, que le menu décrit (plat, vallonné, col) ;
    - **un gain compté :** à chaque segment et en fin de séance, le temps gagné ou perdu par l'équipement (« cadre grimpeur : −14 s dans la montée ») ;
    - **des sensations :** son propre à chaque roue (bourdonnement de la lenticulaire, sifflement des jantes hautes), position plus basse de l'avatar sur un vélo aéro, traînées d'air au-delà de 45 km/h ;
    - **des objectifs :** chaque pièce a un défi associé et une fiche (masse, CdA, terrain conseillé).
- **Résistance au trainer :** inchangée, comme pour les bonus. Le supplément de vent et d'aspiration (série P) suit le CdA courant, donc il s'allège un peu avec un équipement aéro.
- **Records :** chaque passage de segment garde l'équipement utilisé ; un record reste un record, l'équipement est affiché à côté.
- **Bots à profil (série T, lot T13) :** le calibrage avant le départ utilise ton équipement, pour que le niveau choisi reste juste.
- **Bilan, FIT et historique :** inchangés, sur la puissance mesurée.

### 2.3 Avatar

- Silhouette 3D générée par le code, comme les arbres d'E3 et les bots d'O7 : aucun fichier 3D sous licence.
- Réglages : morphologie (taille, carrure), couleur de peau, cheveux, couleurs de tenue, numéro.
- Animation de pédalage synchronisée sur la cadence réelle ; position assise ou en danseuse au-dessus d'une pente ou d'une puissance réglables.
- Budget de rendu : un avatar détaillé pour toi, les bots gardent une version allégée ; cible de la série P (au moins 55 images par seconde en qualité basse sur la GTX 1060).

### 2.4 Où vivent les données

- Profil local dans `~/OpenRide/` : niveau, équipement débloqué et choisi, réglages de l'avatar. Aucune donnée personnelle dans le dépôt.
- Expérience et déblocages calculés par le core, module pur testé en pytest (comme les règles des séries R et T).
- Contrat IPC v1.4 avec R1 et T1, ajouts compatibles (V-Q4 réglée le 26 octobre) : `hello_ack.config` gagne l'équipement et l'avatar choisis et le solde de pièces ; message `xp_result` en fin de séance (gains détaillés, niveau, déblocages) ; commandes `equip` et `set_avatar` depuis le menu ; le cahier V1 ajoute `buy`, `list_garage`, le message `garage` et le message `progression` envoyé après un choix (décision D7 de l'audit IPC).

## 3. Risques

| # | Risque | Parade |
| --- | --- | --- |
| 1 | Équipement trop efficace (records et bots faussés) ou trop discret (sans intérêt) | Effets bornés, mais rendus visibles et comptés (§2.2) ; équipement noté avec chaque passage, calibrage des bots qui en tient compte |
| 2 | Progression trop lente ou trop rapide | Valeurs en fichier de données, simulation sur l'historique réel avant de figer la courbe |
| 3 | Avatar trop coûteux à afficher | Silhouette générée par le code, niveaux de détail, mesure sur la GTX 1060 |
| 4 | Fichier de progression perdu ou corrompu | Recalcul complet depuis le journal des séances |

## 4. Lots de la série V

| Lot | Contenu | Dépend de | Type |
| --- | --- | --- | --- |
| V1 | Contrat : progression dans `hello_ack`, messages `progression` et `xp_result`, catalogue `garage`, commandes `list_garage`, `buy`, `equip` et `set_avatar` (révision 1.4, avec R1 et T1) | P1 | Interne (décision) |
| V2 | Moteur d'expérience : gains, niveaux, défis, recalcul depuis le journal | — | Délégable |
| V3 | Catalogue d'équipement en données, effets bornés appliqués à `PhysicsParams`, compromis par terrain, calcul du temps gagné par l'équipement | V2 | Délégable |
| V3b | Pièces : gains, prix, achats, solde dans le profil, vies du mode Cyber-Rogue | V2, V3, V4 | Délégable |
| V4 | Profil local (niveau, déblocages, choix), lecture et écriture sûres, migration | V2 | Délégable |
| V5 | Liens avec les séries T et R : équipement noté dans les passages, calibrage des bots, expérience des segments, maillots et runs | V3, V3b, V11, T4, T5, T13, T14, R9 | Délégable |
| V6 | Engine : avatar généré par le code, réglages, pédalage synchronisé, position en danseuse | V1 | Interne (rendu) |
| V7 | Engine : rendu des cadres, roues et tenues sur l'avatar | V6 | Interne (rendu) |
| V8 | Menu « Garage » : choix de l'équipement et de l'avatar, aperçu en 3D | V1, V6, V11, N6 | Interne |
| V9 | Fin de séance : expérience et pièces gagnées, temps gagné par l'équipement, passage de niveau, déblocages | V1, V11, N4 | Interne |
| V10 | Recette sur ton PC et ton vélo : progression sur ton historique réel, effet de l'équipement, rendu de l'avatar | V2 à V9, V11 | Propriétaire |
| V11 | Core : progression branchée dans la séance (équipement appliqué, `loadout` au journal, `hello_ack`, `progression`, `xp_result`, commandes du Garage) ; lot ajouté le 26 octobre, absent du premier découpage | V1, V2, V3, V3b, V4 | Délégable |

Ordre conseillé : V2 tout de suite, puis V3 et V4, puis V3b (modules purs, sans effet sur la séance, développables avant la 1.0) ; V1 avec les autres ajouts de sa révision, puis V11 ; V5 quand les séries T et R sont avancées ; puis l'engine (V6 à V9) et la recette V10.

## 5. Questions pour le propriétaire

- [x] **V-Q1 Équipement (25 octobre) :** petits effets sur la physique, mais un impact notable sur le plaisir de jeu (§2.2).
- [x] **V-Q2 Monnaie (25 octobre) :** oui, des pièces, qui achètent aussi des vies dans le mode Cyber-Rogue (§2.1 bis).
- [x] **V-Q3 Séances passées (25 octobre) :** oui, mais seulement celles enregistrées par le jeu.

### Questions du 26 octobre (rédaction des cahiers)

Réponses du propriétaire le 27 octobre : propositions de V-Q5 à V-Q13 validées, sauf V-Q10 (pièces à l'effort).

Chaque cahier applique la proposition recommandée en attendant la réponse ; une autre réponse ne change que le fichier de données ou le cahier concerné.

- [x] **V-Q4 Révision du contrat (26 octobre, décision D2 de l'audit IPC) :** P1 en 1.3 ; V1 dans la révision 1.4 avec R1 et T1, en un seul lot de contrat. Décision D7 : message `progression` dédié après un choix au Garage, bilan nommé `xp_result`.
- [x] **V-Q5 Calendrier :** proposition : modules purs du core (V2, V3, V3b, V4) développés dès maintenant, sans branchement ; V1, V11 et l'engine (V6 à V9) après la 1.0, comme prévu.
- [x] **V-Q6 Journaux anciens :** avant V2, le journal ne dit pas si la séance était réelle, simulée (banc simulé, `--trainer mock`) ou rejouée. Proposition : tout journal ancien compte ; `openride-core xp` les liste pour que tu repères les séances simulées.
- [x] **V-Q7 ERG et distance :** proposition : une séance ERG rapporte 10 points par minute (+ 20 % si terminée) **à la place** de la distance et du dénivelé, pour ne pas compter deux fois (10 points par minute valent 20 points par km à 30 km/h).
- [x] **V-Q8 Courbe des niveaux :** proposition : écart croissant de façon régulière d'un niveau au suivant (1 000 points pour le niveau 2, environ 3 100 pour le dernier, 100 000 au total) ; une séance d'une heure (30 km, 300 m) rapporte environ 1 200 points, soit environ 80 h de selle pour le niveau 50.
- [x] **V-Q9 Catalogue :** cinq cadres, quatre paires de roues et les prix ou niveaux du cahier V3 §4.1 (à valider ou corriger).
- [ ] **V-Q10 Pièces (27 octobre) :** le propriétaire veut des pièces qui récompensent l'effort (temps et % de la FTP). Proposition appliquée, à confirmer : par minute, 0,25 pièce sous 55 % de la FTP, 0,5 de 55 à 75 %, 1 de 75 à 90 %, 1,5 de 90 à 105 %, 2 au-delà, en SIM comme en ERG (une heure d'endurance : 30 pièces ; une heure avec 2 × 20 min au seuil : 70) ; la distance ne compte plus ; vie Cyber-Rogue à 30 pièces, équipement de 100 à 500 pièces inchangés.
- [x] **V-Q11 Caméra :** la caméra actuelle est subjective (yeux du cycliste) : l'avatar ne se voit pas. Proposition : caméra de suivi derrière le cycliste par défaut, subjective au choix dans le Garage ou au clavier.
- [x] **V-Q12 Équipement en mode Cyber-Rogue :** proposition : sans effet dans ce mode, les châssis de R9 en tiennent lieu.
- [x] **V-Q13 Lenticulaire et vent de travers :** la série P ne modélise pas encore le vent de travers (P2). Proposition : la lenticulaire est pénalisée par sa masse en montée seulement ; la pénalité au vent de travers attend un lot de la série P.
