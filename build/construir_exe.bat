@echo off
REM ============================================================
REM  ContAll - Generador del ejecutable para Windows
REM  Autor: Loc0Matt
REM
REM  Requisitos: Python 3.11 o superior instalado y en el PATH.
REM  Uso: doble clic sobre este archivo, o ejecutarlo desde cmd.
REM ============================================================
setlocal enabledelayedexpansion
cd /d "%~dp0\.."

echo.
echo ============================================================
echo   ContAll - construccion del ejecutable
echo ============================================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] No se encontro Python en el PATH.
    echo         Instalalo desde https://www.python.org/downloads/
    echo         y marca la opcion "Add Python to PATH" durante la instalacion.
    echo.
    pause
    exit /b 1
)

echo [1/5] Creando el entorno virtual...
if not exist .venv (
    python -m venv .venv || goto :error
)

echo [2/5] Instalando dependencias de la aplicacion...
call .venv\Scripts\python.exe -m pip install --upgrade pip --quiet || goto :error
call .venv\Scripts\python.exe -m pip install -r requirements.txt --quiet || goto :error

echo [3/5] Instalando herramientas de construccion...
REM requirements-dev.txt trae pyinstaller y las librerias que usan las pruebas
REM (httpx para el cliente de FastAPI, pypdf para verificar el manual).
REM Sin ellas las pruebas fallan y la construccion se detiene.
call .venv\Scripts\python.exe -m pip install -r requirements-dev.txt --quiet || goto :error

echo [4/5] Ejecutando las pruebas...
call .venv\Scripts\python.exe -m unittest discover -s tests
if errorlevel 1 (
    echo.
    echo ------------------------------------------------------------
    echo  [AVISO] Algunas pruebas no pasaron.
    echo  Puedes generar el ejecutable igual, pero revisa los mensajes
    echo  de arriba: puede haber algo que no funcione bien.
    echo ------------------------------------------------------------
    echo.
    choice /c SN /m "Continuar de todas formas"
    if errorlevel 2 goto :cancelado
)

echo.
echo [5/5] Preparando el icono y empaquetando (puede tardar varios minutos)...
call .venv\Scripts\python.exe herramientas\generar_icono.py
call .venv\Scripts\pyinstaller.exe build\contaflow.spec --clean --noconfirm || goto :error

if not exist dist\ContAll.exe goto :error

echo.
echo ============================================================
echo  LISTO. El ejecutable quedo en:
echo.
echo     dist\ContAll.exe
echo.
echo  Copialo donde quieras y abrelo con doble clic.
echo ============================================================
echo.
pause
exit /b 0

:cancelado
echo.
echo Construccion cancelada por el usuario.
pause
exit /b 1

:error
echo.
echo ============================================================
echo  [ERROR] La construccion fallo. Revisa los mensajes de arriba.
echo ============================================================
echo.
pause
exit /b 1
