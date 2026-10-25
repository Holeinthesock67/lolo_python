# OpenRide 2.0 – Progression : niveaux, équipement et avatar (série V)

25 octobre 2026. Demande du propriétaire, acceptée pour la 2.0 : une progression façon Zwift, avec niveaux et points d'expérience, vélos, roues et tenues à débloquer, et un avatar personnalisable. **La série V commence après la 1.0.** Les cahiers des lots seront rédigés au démarrage de la série et ajoutés à `docs/lots/00_INDEX.md`.

## 1. En résumé

- **Une seule progression pour tous les modes :** une séance classique, un entraînement ERG et une run Cyber-Rogue rapportent de l'expérience au même profil.
- **Calculée depuis le journal :** l'expérience se recalcule à partir des séances enregistrées. Tes séances passées comptent donc dès l'arrivée de la série, et rien ne se perd si le fichier de progression est effacé.
- **Équipement à effets bornés :** vélos et roues changent un peu la masse et le CdA, donc la vitesse virtuelle seulement, par la même voie que les bonus de la série T. Tenues et avatar sont de l'apparence.
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
- Pas d'expérience pour une séance de moins de 5 minutes ou une séance rejouée (`replay`), pour éviter les doublons.

### 2.2 Équipement

| Catégorie | Exemples | Effet |
| --- | --- | --- |
| Cadre | Polyvalent, grimpeur, aéro, contre-la-montre | Masse de −1,5 à +0,5 kg, CdA de −4 % à 0 % |
| Roues | Standard, légères, profilées, lenticulaire | Masse de −0,5 à +0,5 kg, CdA de −3 % à 0 % |
| Casque, tenue, chaussettes, lunettes | Couleurs, motifs, maillots de club | Apparence seulement |

- **Déblocage :** par niveau atteint, et quelques pièces par défi (premier col HC, 1 000 km cumulés, maillot à pois gagné, boss Cyber-Rogue vaincu). Pas de monnaie à dépenser dans la première version (question V-Q2).
- **Effets bornés** à −3 % de masse totale et −6 % de CdA au plus, cadre et roues ensemble, pour garder les temps comparables.
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
- Contrat IPC v1.3, ajouts compatibles : `hello_ack.config` gagne l'équipement et l'avatar choisis ; message `xp` en fin de séance (gains détaillés, niveau, déblocages) ; commandes `equip` et `set_avatar` depuis le menu.

## 3. Risques

| # | Risque | Parade |
| --- | --- | --- |
| 1 | Équipement trop efficace : records et bots faussés | Effets bornés (§2.2), équipement noté avec chaque passage, calibrage des bots qui en tient compte |
| 2 | Progression trop lente ou trop rapide | Valeurs en fichier de données, simulation sur l'historique réel avant de figer la courbe |
| 3 | Avatar trop coûteux à afficher | Silhouette générée par le code, niveaux de détail, mesure sur la GTX 1060 |
| 4 | Fichier de progression perdu ou corrompu | Recalcul complet depuis le journal des séances |

## 4. Lots de la série V

| Lot | Contenu | Dépend de | Type |
| --- | --- | --- | --- |
| V1 | Contrat : équipement et avatar dans `hello_ack`, message `xp`, commandes `equip` et `set_avatar` (IPC v1.3) | P1 | Interne (décision) |
| V2 | Moteur d'expérience : gains, niveaux, défis, recalcul depuis le journal | — | Délégable |
| V3 | Catalogue d'équipement en données, effets bornés appliqués à `PhysicsParams` | V2 | Délégable |
| V4 | Profil local (niveau, déblocages, choix), lecture et écriture sûres, migration | V2 | Délégable |
| V5 | Liens avec les séries T et R : équipement noté dans les passages, calibrage des bots, expérience des segments, maillots et runs | V3, T5, T13, R9 | Délégable |
| V6 | Engine : avatar généré par le code, réglages, pédalage synchronisé, position en danseuse | V1 | Interne (rendu) |
| V7 | Engine : rendu des cadres, roues et tenues sur l'avatar | V6 | Interne (rendu) |
| V8 | Menu « Garage » : choix de l'équipement et de l'avatar, aperçu en 3D | V1, V6, N6 | Interne |
| V9 | Fin de séance : expérience gagnée, passage de niveau, déblocages | V1, N4 | Interne |
| V10 | Recette sur ton PC et ton vélo : progression sur ton historique réel, effet de l'équipement, rendu de l'avatar | V2 à V9 | Propriétaire |

Ordre conseillé : V1 avec les autres ajouts de la v1.3 ; V2, V3 et V4 en parallèle ; V5 quand les séries T et R sont avancées ; puis l'engine (V6 à V9) et la recette V10.

## 5. Questions pour le propriétaire

- [ ] **V-Q1 Équipement :** de petits effets sur la vitesse virtuelle (bornés comme au §2.2), ou seulement de l'apparence ? (Recommandé : petits effets, comme Zwift.)
- [ ] **V-Q2 Monnaie :** déblocage par niveau et par défi seulement, ou aussi une monnaie gagnée en roulant pour acheter des pièces ? (Recommandé : niveau et défis d'abord, monnaie plus tard si besoin.)
- [ ] **V-Q3 Séances passées :** compter dès le départ l'expérience de tes séances déjà enregistrées ? (Recommandé : oui.)
