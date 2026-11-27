# GF2 : témoin sur main dans la file des bancs

- PR : à venir ; garde-fou 2 du fil « Fiabiliser les outils de banc » (27 novembre 2026) ; version : 6.0
- CHANGELOG (section « Ajouté ») :
  - File des bancs : une étape de branche en ÉCHEC est rejouée sur main (précédée de la fumée de la PR). Main en
    échec aussi = « ÉCHEC AUSSI SUR MAIN », défaut de l'outil ou de main, non bloquant pour la PR ; main qui passe
    confirme l'échec. Une fois par commit de main et par commande ; `[file] temoin_main = false` le coupe.
- SUIVI :
  - [ ] GF2 : file_bancs, témoin sur main d'office, échec bloquant seulement si main passe.
