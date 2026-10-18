@echo off
echo ========================================
echo   Arena of Life - Lanceur combine
echo ========================================
echo.
echo Demarrage du jeu et de l'analyseur...
echo.

REM Lancer le jeu dans une nouvelle fenetre
start "Arena of Life - Jeu" cmd /k python main.py

REM Attendre 2 secondes
timeout /t 2 /nobreak > nul

REM Lancer l'analyseur dans une nouvelle fenetre
start "Arena of Life - Analyseur" cmd /k python analyze_training.py

echo.
echo Les deux programmes sont lances !
echo - Fenetre 1: Jeu (main.py)
echo - Fenetre 2: Analyseur (analyze_training.py)
echo.
pause
