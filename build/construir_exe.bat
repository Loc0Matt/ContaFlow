@echo off
REM ============================================================
REM  Genera ContaFlow.exe en Windows.
REM  Requisitos: Python 3.11 o superior instalado y en el PATH.
REM  Uso: doble clic sobre este archivo, o ejecutarlo desde cmd.
REM ============================================================
setlocal
cd /d "%~dp0\.."

echo.
echo === ContaFlow: construccion del ejecutable ===
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] No se encontro Python. Instalalo desde https://www.python.org/downloads/
    echo          Marca la opcion "Add Python to PATH" durante la instalacion.
    pause
    exit /b 1
)

echo [1/4] Creando entorno virtual...
if not exist .venv (
    python -m venv .venv || goto :error
)

echo [2/4] Instalando dependencias...
call .venv\Scripts\python.exe -m pip install --upgrade pip --quiet || goto :error
call .venv\Scripts\python.exe -m pip install -r requirements.txt --quiet || goto :error
call .venv\Scripts\python.exe -m pip install pyinstaller --quiet || goto :error

echo [3/4] Ejecutando las pruebas...
call .venv\Scripts\python.exe -m unittest discover -s tests -v || goto :error

echo [4/4] Empaquetando con PyInstaller (puede tardar unos minutos)...
call .venv\Scripts\pyinstaller.exe build\contaflow.spec --clean --noconfirm || goto :error

echo.
echo ============================================================
echo  LISTO. El ejecutable quedo en:  dist\ContaFlow.exe
echo  Copialo donde quieras y abrelo con doble clic.
echo ============================================================
echo.
pause
exit /b 0

:error
echo.
echo [ERROR] La construccion fallo. Revisa los mensajes de arriba.
pause
exit /b 1
