================================================================================
                    ARENA OF LIFE - SCRIPTS DE LANCEMENT
================================================================================

Ce dossier contient deux scripts .bat pour lancer facilement le jeu
et l'analyseur de statistiques en même temps.

================================================================================
📁 FICHIERS DISPONIBLES
================================================================================

1. launch_both.bat
   - Lance le jeu ET l'analyseur
   - L'analyseur génère le rapport UNE SEULE FOIS
   - Utilisez-le pour une analyse ponctuelle

2. launch_auto.bat ⭐ RECOMMANDÉ
   - Lance le jeu ET l'analyseur en mode surveillance
   - Le rapport se régénère AUTOMATIQUEMENT toutes les 30 secondes
   - Parfait pour un entraînement long avec monitoring en temps réel

================================================================================
🚀 UTILISATION RAPIDE
================================================================================

MÉTHODE SIMPLE (analyse unique)
-------------------------------
1. Double-cliquer sur "launch_both.bat"
2. Deux fenêtres s'ouvrent (jeu + analyseur)
3. Le rapport "training_report.html" est généré
4. Ouvrir le rapport dans votre navigateur

MÉTHODE AUTOMATIQUE (mise à jour continue) ⭐
--------------------------------------------
1. Double-cliquer sur "launch_auto.bat"
2. Deux fenêtres s'ouvrent (jeu + analyseur auto)
3. Ouvrir "training_report.html" dans votre navigateur
4. Le rapport se met à jour automatiquement !
5. Rafraîchir (F5) pour voir les nouvelles statistiques

================================================================================
📊 CE QUI SE PASSE
================================================================================

Fenêtre 1: Arena of Life (main.py)
   → Le jeu tourne normalement
   → Écrit les stats dans training_stats.csv

Fenêtre 2: Analyseur de statistiques
   → Lit training_stats.csv
   → Génère 9 graphiques PNG
   → Crée/met à jour training_report.html

MODE AUTO uniquement:
   → Surveille les changements toutes les 30 secondes
   → Régénère automatiquement si nouvelles données
   → Affiche les stats actuelles dans la console

================================================================================
⚙️ CONFIGURATION
================================================================================

Modifier l'intervalle de surveillance (mode auto):
   → Ouvrir "analyze_training_watch.py"
   → Ligne 18: WATCH_INTERVAL = 30  (changer la valeur)
   → 30 = 30 secondes entre chaque vérification

================================================================================
🛑 ARRÊT DES PROGRAMMES
================================================================================

Pour arrêter:
   - Fermer les fenêtres CMD (cliquer sur X)
   OU
   - Appuyer sur Ctrl+C dans chaque fenêtre

================================================================================
📋 FICHIERS GÉNÉRÉS
================================================================================

training_report.html     → Rapport HTML avec toutes les stats
analysis_plots/          → Dossier contenant les 9 graphiques PNG
   ├── general_behavior.png
   ├── class_survival.png
   ├── weapon_efficiency.png
   ├── loss_evolution.png
   ├── rewards_by_season.png
   ├── epsilon_decay.png
   ├── kills_by_season.png
   ├── cv_evolution.png
   └── genhr_evolution.png

================================================================================
❓ DÉPANNAGE
================================================================================

PROBLÈME: "Python n'est pas reconnu"
   → Installer Python depuis python.org
   → Ou utiliser le chemin complet: C:\Python3X\python.exe

PROBLÈME: "Module pandas not found"
   → Ouvrir CMD et taper: pip install pandas matplotlib

PROBLÈME: Le rapport ne se met pas à jour
   → Vérifier que training_stats.csv change bien
   → Attendre 30 secondes (mode auto)
   → Regarder les messages dans la fenêtre de l'analyseur

PROBLÈME: Erreur lors de la génération
   → L'analyseur continue même en cas d'erreur
   → Vérifier les messages d'erreur dans la console
   → Le prochain cycle réessayera automatiquement

================================================================================
💡 CONSEILS
================================================================================

✓ Ouvrez training_report.html dans votre navigateur favori
✓ Rafraîchissez (F5) pour voir les nouvelles stats
✓ Gardez la fenêtre de l'analyseur visible pour suivre en temps réel
✓ Utilisez launch_auto.bat pour les longues sessions d'entraînement

================================================================================
📧 FICHIERS PYTHON
================================================================================

main.py                      → Le jeu principal
analyze_training.py          → Analyseur (génération unique)
analyze_training_watch.py    → Analyseur en mode surveillance
training_stats.csv           → Données d'entraînement (généré par le jeu)

================================================================================
