@echo off
title Installation des outils de build Microsoft Visual C++ (VS 2022)
echo =====================================================================
echo   Installation de Microsoft Visual C++ Build Tools (VS 2022)
echo   pour la compilation Tauri, Rust et logiciels natifs Windows
echo =====================================================================
echo.

net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [ATTENTION] Ce script necessite les privileges Administrateur Windows.
    echo.
    echo Veuillez faire un CLIC DROIT sur ce fichier :
    echo   "install_visual_cpp_build_tools.bat"
    echo et choisir :
    echo   "Executer en tant qu'administrateur"
    echo.
    pause
    exit /b 1
)

echo [OK] Privileges Administrateur confirmes.
echo.
echo Lancement du telechargement et de l'installation de la charge de travail C++...
echo (Composants : Compilateur MSVC C++, Windows SDK, CRT, CMake)
echo.

winget install --id Microsoft.VisualStudio.2022.BuildTools --accept-source-agreements --accept-package-agreements --override "--passive --wait --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended"

if %errorLevel% equ 0 (
    echo.
    echo =====================================================================
    echo   [SUCCES] Visual C++ Build Tools est installe avec succes !
    echo =====================================================================
) else (
    echo.
    echo Execution directe du programme d'installation telecharge...
    if exist "%LOCALAPPDATA%\Temp\WinGet\Microsoft.VisualStudio.2022.BuildTools.17.14.44\vs_BuildTools.exe" (
        "%LOCALAPPDATA%\Temp\WinGet\Microsoft.VisualStudio.2022.BuildTools.17.14.44\vs_BuildTools.exe" --passive --wait --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended
    )
)

echo.
pause

