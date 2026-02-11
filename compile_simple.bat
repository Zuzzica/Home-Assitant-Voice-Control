@echo off
echo ============================================
echo  Compilare SIMPLIFICATA (pentru debugging)
echo ============================================
echo.

REM Verificare fisier
if not exist "home_assistant_voice_v3_modified.py" (
    echo [EROARE] Nu gasesc fisierul home_assistant_voice_v3_modified.py
    echo Asigura-te ca acest script .bat este in acelasi folder cu fisierul .py
    echo.
    echo Fisiere gasite in folderul curent:
    dir *.py
    pause
    exit /b 1
)

echo [OK] Fisier gasit: home_assistant_voice_v3_modified.py
echo.

REM Curatare compilari anterioare
echo Curatare fisiere vechi...
if exist "build" rmdir /s /q build
if exist "dist" rmdir /s /q dist
if exist "*.spec" del /q *.spec
echo.

REM Dezinstalare pathlib
echo Dezinstalare pathlib...
python -m pip uninstall pathlib -y >nul 2>&1
echo.

REM Instalare dependente
echo Instalare dependente...
pip install --upgrade pip setuptools wheel >nul 2>&1
pip install numpy sounddevice SpeechRecognition requests PyQt5 pyinstaller
echo.

REM Compilare cu setari minime
echo.
echo Compilare in curs...
echo.

pyinstaller ^
    --onefile ^
    --windowed ^
    --name HAVoiceControl ^
    --noconfirm ^
    --clean ^
    home_assistant_voice_v3_modified.py

if %errorlevel% equ 0 (
    echo.
    echo ============================================
    echo  SUCCES!
    echo ============================================
    echo.
    echo Executabil creat: dist\HAVoiceControl.exe
    echo.
) else (
    echo.
    echo ============================================
    echo  EROARE!
    echo ============================================
    echo.
    echo Verifica mesajele de eroare de mai sus.
    echo.
)

pause
