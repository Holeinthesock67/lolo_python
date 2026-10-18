@echo off
echo ========================================
echo   Arena of Life - Lanceur Automatique
echo ========================================
echo.
echo Ce script lance:
echo 1. Le jeu (main.py)
echo 2. L'analyseur en mode surveillance auto (analyze_training_watch.py)
echo.
echo Le rapport HTML sera mis a jour automatiquement!
echo.


REM Lancer le jeu dans une nouvelle fenetre
start "Arena of Life - Jeu" cmd /k python main.py

REM Attendre 2 secondes
timeout /t 2 /nobreak > nul

REM Lancer l'analyseur en mode watch dans une nouvelle fenetre
start "Arena of Life - Analyseur Auto" cmd /k python analyze_training_watch.py

echo.
echo ========================================
echo Les deux programmes sont lances !
echo ========================================
echo.
echo Fenetre 1: Jeu (main.py)
echo Fenetre 2: Analyseur automatique
echo.
echo Le rapport sera regenere automatiquement
echo toutes les 30 secondes si de nouvelles
echo donnees sont detectees.
echo.
echo Vous pouvez ouvrir training_report.html
echo dans votre navigateur et le rafraichir
echo pour voir les mises a jour.
echo.
echo ========================================
