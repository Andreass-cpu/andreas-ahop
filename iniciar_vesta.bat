@echo off
setlocal
cd /d "%~dp0"
echo ==========================================
echo       VESTA - Tienda de moda (Python)
echo ==========================================
echo.
py -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo No se pudieron instalar las dependencias. Revisa tu conexion e intenta otra vez.
  pause
  exit /b 1
)
echo.
echo Iniciando VESTA...
echo Abre http://127.0.0.1:5000 en tu navegador.
echo Para comprar realmente debes configurar Atlas en el archivo .env.
echo.
py app.py
pause
