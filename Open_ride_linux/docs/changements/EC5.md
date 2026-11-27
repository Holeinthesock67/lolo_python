# EC5 : liaison engine et core (revue de code vague 3, constats E1-02, E1-03, E1-07)

- PR : à venir ; bilan : revue de code vague 3 engine (E1) ; version : 6.0
- CHANGELOG (section « Corrigé ») :
  - Une touche pressée pendant un gel du core (« Core non joignable ») n'est plus exécutée deux à quatre fois à la reprise : l'engine ne renvoie plus une commande après un `hello` (le core y remet son compteur à zéro), et il n'affiche plus « Commande … sans réponse » en plus du bandeau du core.
  - Fermer la fenêtre (Alt+F4, bouton du bureau) passe par la même fermeture que « Quitter » du menu : tâches de fond attendues, ligne de fin lue par le lanceur, plus d'arrêt de Godot bloqué. Un second engine dont le port est pris s'arrête par le même chemin.
  - Confidentialité : le journal de l'engine n'écrit plus la configuration entière du `hello_ack` (dernier départ du monde ouvert, FTP, profil, dossiers) ; seules des clés sûres gardent leur valeur. Le fichier de diagnostic masque aussi les positions écrites `"lat": 48.1`.
- SUIVI :
  - [ ] EC5 : E1-02 (pas de renvoi d'une commande après un hello, scénario IPC 9 « commande pendant un gel du core »), E1-03 (fermeture de la fenêtre par `_quit`), E1-07 (hello_ack sans donnée privée au journal, masque `"lat":`).
